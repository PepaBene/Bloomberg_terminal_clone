"""Tests for Pillar 3 Phase 4A -- Anomaly Detection Engine."""

import pytest

from src.engines.anomaly_detection_engine import (
    ALERT_ROUTING,
    ANOMALY_TYPES,
    SEVERITY_THRESHOLDS,
    AnomalyResult,
    ContextualAnalysis,
    RecommendedAction,
    RelatedData,
    StatisticalEvidence,
    classify_severity,
    compute_percentile,
    compute_z_score,
    detect_earnings_surprise_anomaly,
    detect_fundamental_shift,
    detect_peer_divergence,
    detect_price_momentum_anomaly,
    detect_sentiment_anomaly,
    detect_supply_chain_anomaly,
    detect_volume_spike,
    generate_anomaly_narrative_template,
    run_full_anomaly_scan,
)


# -- TestZScore ---------------------------------------------------------------


class TestZScore:
    """Tests for compute_z_score()."""

    def test_empty_list_returns_zero(self):
        assert compute_z_score([], 5.0) == 0.0

    def test_single_value_returns_zero(self):
        assert compute_z_score([10.0], 10.0) == 0.0

    def test_normal_distribution(self):
        """Mean=0, stdev=1 data; current=0 should give z~0."""
        values = [-1.0, 0.0, 1.0, -1.0, 0.0, 1.0]
        z = compute_z_score(values, 0.0)
        assert abs(z) < 0.01

    def test_outlier_detection(self):
        """Current far from mean should produce large |z|."""
        values = [10.0, 10.1, 9.9, 10.0, 10.2, 9.8]
        z = compute_z_score(values, 15.0)
        assert z > 3.0


# -- TestPercentile -----------------------------------------------------------


class TestPercentile:
    """Tests for compute_percentile()."""

    def test_at_bottom(self):
        """Value below all should be 0th percentile."""
        values = [10.0, 20.0, 30.0, 40.0]
        assert compute_percentile(values, 5.0) == 0.0

    def test_at_top(self):
        """Value above all should be 100th percentile."""
        values = [10.0, 20.0, 30.0, 40.0]
        assert compute_percentile(values, 50.0) == 100.0

    def test_middle(self):
        """Value in the middle gets ~50%."""
        values = [10.0, 20.0, 30.0, 40.0]
        # 25 is above 10 and 20 -> 2/4 = 50%
        assert compute_percentile(values, 25.0) == 50.0

    def test_empty_list(self):
        assert compute_percentile([], 10.0) == 0.0


# -- TestPriceMomentum -------------------------------------------------------


class TestPriceMomentum:
    """Tests for detect_price_momentum_anomaly()."""

    def _historical_returns(self) -> list[float]:
        """Typical daily returns (mean ~0, stdev ~0.01)."""
        return [
            0.005, -0.003, 0.002, -0.001, 0.004,
            -0.002, 0.001, -0.004, 0.003, -0.001,
            0.002, -0.003, 0.001, -0.002, 0.003,
            0.001, -0.001, 0.002, -0.003, 0.004,
        ]

    def test_three_sigma_move_detected(self):
        """A 3-sigma move should be detected."""
        returns = self._historical_returns()
        # A 10% move is far outside normal range
        result = detect_price_momentum_anomaly(returns, 0.10)
        assert result is not None
        assert result.anomaly_type == "price_momentum"
        assert result.severity_score > 0
        assert abs(result.evidence.z_score) >= 2

    def test_normal_move_returns_none(self):
        """A move within normal range should not trigger."""
        returns = self._historical_returns()
        result = detect_price_momentum_anomaly(returns, 0.001)
        assert result is None

    def test_beta_adjusted(self):
        """Beta-adjusted detection should account for market return."""
        returns = self._historical_returns()
        # With beta=1.0 and market_return=0.001, expected = 0.001
        # A return of 0.002 yields excess = 0.001, which is well within
        # the distribution of (returns - 0.001), so no anomaly.
        result = detect_price_momentum_anomaly(
            returns, 0.002, beta=1.0, market_return=0.001,
        )
        # Should not trigger since the excess return is small
        assert result is None

    def test_negative_anomaly(self):
        """A large negative move should also be detected."""
        returns = self._historical_returns()
        result = detect_price_momentum_anomaly(returns, -0.10)
        assert result is not None
        assert result.evidence.z_score < 0


# -- TestVolumeSpike ----------------------------------------------------------


class TestVolumeSpike:
    """Tests for detect_volume_spike()."""

    def _historical_volumes(self) -> list[float]:
        return [
            1_000_000, 1_100_000, 950_000, 1_050_000, 1_000_000,
            980_000, 1_020_000, 1_010_000, 990_000, 1_030_000,
            1_000_000, 1_050_000, 970_000, 1_040_000, 1_000_000,
            1_010_000, 990_000, 1_020_000, 980_000, 1_030_000,
        ]

    def test_five_x_volume_detected(self):
        """5x average volume should trigger."""
        volumes = self._historical_volumes()
        result = detect_volume_spike(volumes, 5_000_000)
        assert result is not None
        assert result.anomaly_type == "volume_spike"
        assert result.severity_score > 40

    def test_normal_volume_returns_none(self):
        """Volume at average should not trigger."""
        volumes = self._historical_volumes()
        result = detect_volume_spike(volumes, 1_000_000)
        assert result is None

    def test_borderline_volume(self):
        """Volume slightly above 2-sigma threshold."""
        volumes = self._historical_volumes()
        # Find what 2-sigma above mean would be
        from statistics import mean as smean, stdev as sstdev

        m = smean(volumes)
        s = sstdev(volumes)
        # Just below 2-sigma -> no trigger
        result = detect_volume_spike(volumes, m + 1.9 * s)
        assert result is None


# -- TestEarningsSurprise -----------------------------------------------------


class TestEarningsSurprise:
    """Tests for detect_earnings_surprise_anomaly()."""

    def _historical_surprises(self) -> list[float]:
        """Typical surprise distribution: mean ~2%, stdev ~5%."""
        return [3.0, -1.0, 2.0, 5.0, -2.0, 1.0, 4.0, -3.0, 2.0, 0.0,
                3.0, 1.0, -1.0, 2.0, 4.0, 0.0, -2.0, 3.0, 1.0, 2.0]

    def test_huge_beat_detected(self):
        """30% earnings beat should trigger."""
        hist = self._historical_surprises()
        result = detect_earnings_surprise_anomaly(1.30, 1.00, hist)
        assert result is not None
        assert result.anomaly_type == "earnings_surprise"

    def test_inline_returns_none(self):
        """EPS matching consensus should not trigger."""
        hist = self._historical_surprises()
        result = detect_earnings_surprise_anomaly(1.02, 1.00, hist)
        assert result is None

    def test_earnings_miss(self):
        """A large miss should also be detected."""
        hist = self._historical_surprises()
        result = detect_earnings_surprise_anomaly(0.70, 1.00, hist)
        assert result is not None
        assert result.evidence.z_score < 0

    def test_zero_consensus_returns_none(self):
        """Zero consensus avoids division-by-zero."""
        hist = self._historical_surprises()
        result = detect_earnings_surprise_anomaly(1.00, 0.0, hist)
        assert result is None


# -- TestFundamentalShift -----------------------------------------------------


class TestFundamentalShift:
    """Tests for detect_fundamental_shift()."""

    def test_margin_collapse_detected(self):
        """Operating margin dropping from 20% to 5% (>30% change) triggers."""
        current = {"operating_margin": 0.05, "roe": 0.12, "debt_to_equity": 0.5, "revenue_growth": 0.08}
        prior = {"operating_margin": 0.20, "roe": 0.12, "debt_to_equity": 0.5, "revenue_growth": 0.08}
        result = detect_fundamental_shift(current, prior)
        assert result is not None
        assert result.anomaly_type == "fundamental_shift"
        assert "operating_margin" in result.narrative_template

    def test_stable_metrics_return_none(self):
        """Metrics that barely changed should not trigger."""
        current = {"operating_margin": 0.20, "roe": 0.12, "debt_to_equity": 0.5, "revenue_growth": 0.08}
        prior = {"operating_margin": 0.19, "roe": 0.12, "debt_to_equity": 0.5, "revenue_growth": 0.08}
        result = detect_fundamental_shift(current, prior)
        assert result is None

    def test_no_prior_data(self):
        """Missing prior metrics should return None."""
        current = {"operating_margin": 0.20}
        prior = {}
        result = detect_fundamental_shift(current, prior)
        assert result is None


# -- TestSentimentAnomaly -----------------------------------------------------


class TestSentimentAnomaly:
    """Tests for detect_sentiment_anomaly()."""

    def _historical_sentiments(self) -> list[float]:
        """Scores on -1 to +1 scale, mean ~0.2."""
        return [0.2, 0.3, 0.1, 0.25, 0.15, 0.2, 0.3, 0.1,
                0.25, 0.15, 0.2, 0.3, 0.1, 0.25, 0.15,
                0.2, 0.3, 0.1, 0.25, 0.15]

    def test_extreme_negative_detected(self):
        """A score of -0.8 should trigger when historical is ~+0.2."""
        hist = self._historical_sentiments()
        result = detect_sentiment_anomaly(-0.8, hist, 10, 10.0)
        assert result is not None
        assert result.anomaly_type == "sentiment"

    def test_normal_sentiment_returns_none(self):
        """A score near the mean should not trigger."""
        hist = self._historical_sentiments()
        result = detect_sentiment_anomaly(0.2, hist, 10, 10.0)
        assert result is None

    def test_high_volume_amplifier(self):
        """High news volume should amplify severity."""
        hist = self._historical_sentiments()
        # Use a moderately extreme score so base severity stays below 100
        # -0.2 with hist mean ~0.2 and stdev ~0.065 -> z ~ -6 -> severity=100
        # We need something milder: use a wider distribution
        wide_hist = [0.5, -0.3, 0.4, -0.2, 0.3, -0.1, 0.2, 0.0,
                     0.1, -0.4, 0.3, -0.2, 0.5, -0.3, 0.4, -0.1,
                     0.2, 0.0, 0.1, -0.3]
        # -0.9 vs wide_hist should produce a detectable but not 100 base
        result_normal = detect_sentiment_anomaly(-0.9, wide_hist, 5, 10.0)
        result_amplified = detect_sentiment_anomaly(-0.9, wide_hist, 25, 10.0)
        assert result_normal is not None
        assert result_amplified is not None
        assert result_amplified.severity_score > result_normal.severity_score


# -- TestSupplyChain ----------------------------------------------------------


class TestSupplyChain:
    """Tests for detect_supply_chain_anomaly()."""

    def test_many_supplier_negatives_detected(self):
        """4+ negative supplier news items should trigger."""
        supplier_news = [
            {"sentiment": "negative"}, {"sentiment": "negative"},
            {"sentiment": "negative"}, {"sentiment": "negative"},
        ]
        customer_news = []
        result = detect_supply_chain_anomaly(supplier_news, customer_news)
        assert result is not None
        assert result.anomaly_type == "supply_chain"

    def test_no_news_returns_none(self):
        """Empty news lists should not trigger."""
        result = detect_supply_chain_anomaly([], [])
        assert result is None

    def test_customer_disruption(self):
        """Negative customer news should also trigger."""
        supplier_news = [{"sentiment": "positive"}]
        customer_news = [
            {"sentiment": "negative"}, {"sentiment": "negative"},
            {"sentiment": "negative"}, {"sentiment": "negative"},
        ]
        result = detect_supply_chain_anomaly(supplier_news, customer_news)
        assert result is not None
        assert "customer" in result.narrative_template


# -- TestPeerDivergence -------------------------------------------------------


class TestPeerDivergence:
    """Tests for detect_peer_divergence()."""

    def _peer_returns(self) -> list[float]:
        """Peer returns clustered around 2%."""
        return [0.02, 0.015, 0.025, 0.018, 0.022,
                0.019, 0.021, 0.017, 0.023, 0.02]

    def test_massive_outperformance_detected(self):
        """15% return vs ~2% peers should trigger."""
        result = detect_peer_divergence(0.15, self._peer_returns())
        assert result is not None
        assert result.anomaly_type == "peer_divergence"
        assert "outperformance" in result.narrative_template

    def test_inline_returns_none(self):
        """Return near peer mean should not trigger."""
        result = detect_peer_divergence(0.02, self._peer_returns())
        assert result is None

    def test_underperformance(self):
        """Large negative divergence should also be detected."""
        result = detect_peer_divergence(-0.10, self._peer_returns())
        assert result is not None
        assert "underperformance" in result.narrative_template


# -- TestSeverity -------------------------------------------------------------


class TestSeverity:
    """Tests for classify_severity()."""

    def test_high_z_score(self):
        """z=4 should produce severity=80."""
        score = classify_severity(4.0, "price_momentum")
        assert score == 80.0

    def test_type_multiplier(self):
        """Earnings surprise gets 1.2x multiplier."""
        base_score = classify_severity(3.0, "price_momentum")
        boosted = classify_severity(3.0, "earnings_surprise")
        assert boosted == base_score * 1.2

    def test_cap_at_100(self):
        """Severity should never exceed 100."""
        score = classify_severity(10.0, "earnings_surprise")
        assert score == 100.0


# -- TestNarrative ------------------------------------------------------------


class TestNarrative:
    """Tests for generate_anomaly_narrative_template()."""

    def _make_anomaly(self, severity: float = 75.0) -> AnomalyResult:
        return AnomalyResult(
            anomaly_type="price_momentum",
            severity_score=severity,
            evidence=StatisticalEvidence(
                observed_value=0.10,
                expected_value=0.001,
                z_score=3.5,
                percentile_rank=99.0,
            ),
            context=ContextualAnalysis(
                peer_comparison=None,
                historical_precedent="3.5-sigma move",
                potential_catalysts=[],
                estimated_impact="high",
            ),
            related_data=None,
            narrative_template="placeholder",
            actions=[RecommendedAction(
                action="Review price momentum anomaly",
                urgency="near_term",
                resource_required="trader",
            )],
            confidence=0.7,
        )

    def test_entity_name_in_narrative(self):
        """Narrative should include the entity name."""
        anomaly = self._make_anomaly()
        narrative = generate_anomaly_narrative_template(anomaly, "AAPL")
        assert "AAPL" in narrative
        assert "price momentum" in narrative

    def test_severity_and_metrics_in_narrative(self):
        """Narrative should include z-score and severity."""
        anomaly = self._make_anomaly(severity=85.0)
        narrative = generate_anomaly_narrative_template(anomaly, "TSLA")
        assert "85" in narrative
        assert "3.50" in narrative  # z-score
        assert "CRITICAL" in narrative


# -- TestFullScan -------------------------------------------------------------


class TestFullScan:
    """Tests for run_full_anomaly_scan()."""

    def _clean_entity(self) -> dict:
        """Entity with all normal metrics -- should produce no anomalies."""
        returns = [0.005, -0.003, 0.002, -0.001, 0.004,
                   -0.002, 0.001, -0.004, 0.003, -0.001,
                   0.002, -0.003, 0.001, -0.002, 0.003]
        volumes = [1_000_000] * 15
        return {
            "returns": returns,
            "volumes": volumes,
            "current_return": 0.001,
            "current_volume": 1_050_000,
            "eps_actual": 1.02,
            "eps_consensus": 1.00,
            "historical_surprises": [2.0, 1.0, -1.0, 3.0, 0.0,
                                     2.0, -1.0, 1.0, 3.0, -2.0],
            "sentiment_score": 0.2,
            "historical_sentiments": [0.2, 0.25, 0.15, 0.2, 0.3,
                                      0.1, 0.2, 0.25, 0.15, 0.2],
            "news_volume": 10,
            "avg_news_volume": 10.0,
            "fundamentals_current": {
                "operating_margin": 0.20,
                "roe": 0.12,
                "debt_to_equity": 0.5,
                "revenue_growth": 0.08,
            },
            "fundamentals_prior": {
                "operating_margin": 0.19,
                "roe": 0.12,
                "debt_to_equity": 0.5,
                "revenue_growth": 0.08,
            },
            "supplier_news": [],
            "customer_news": [],
        }

    def _anomalous_entity(self) -> dict:
        """Entity with multiple anomalies."""
        returns = [0.005, -0.003, 0.002, -0.001, 0.004,
                   -0.002, 0.001, -0.004, 0.003, -0.001,
                   0.002, -0.003, 0.001, -0.002, 0.003]
        volumes = [1_000_000, 1_050_000, 980_000, 1_020_000, 990_000,
                   1_010_000, 1_030_000, 970_000, 1_040_000, 1_000_000,
                   1_020_000, 980_000, 1_010_000, 990_000, 1_050_000]
        return {
            "returns": returns,
            "volumes": volumes,
            "current_return": 0.15,  # Huge move
            "current_volume": 8_000_000,  # 8x volume
            "eps_actual": 2.00,
            "eps_consensus": 1.00,
            "historical_surprises": [2.0, 1.0, -1.0, 3.0, 0.0,
                                     2.0, -1.0, 1.0, 3.0, -2.0],
            "sentiment_score": -0.9,
            "historical_sentiments": [0.2, 0.25, 0.15, 0.2, 0.3,
                                      0.1, 0.2, 0.25, 0.15, 0.2],
            "news_volume": 50,
            "avg_news_volume": 10.0,
            "fundamentals_current": {
                "operating_margin": 0.03,
                "roe": 0.02,
                "debt_to_equity": 2.0,
                "revenue_growth": -0.10,
            },
            "fundamentals_prior": {
                "operating_margin": 0.20,
                "roe": 0.12,
                "debt_to_equity": 0.5,
                "revenue_growth": 0.08,
            },
            "supplier_news": [
                {"sentiment": "negative"}, {"sentiment": "negative"},
                {"sentiment": "negative"}, {"sentiment": "negative"},
            ],
            "customer_news": [{"sentiment": "negative"}],
        }

    def test_clean_entity_no_anomalies(self):
        """A normal entity should produce zero anomalies."""
        entity = self._clean_entity()
        market = {"market_return": 0.001, "beta": 1.0}
        results = run_full_anomaly_scan(entity, market)
        assert len(results) == 0

    def test_anomalous_entity_finds_multiple(self):
        """An entity with extreme metrics should produce several anomalies."""
        entity = self._anomalous_entity()
        market = {"market_return": 0.001, "beta": 1.0}
        results = run_full_anomaly_scan(entity, market)
        assert len(results) >= 3
        types_found = {r.anomaly_type for r in results}
        assert "volume_spike" in types_found

    def test_results_sorted_by_severity(self):
        """Results should be sorted descending by severity_score."""
        entity = self._anomalous_entity()
        market = {"market_return": 0.001, "beta": 1.0}
        results = run_full_anomaly_scan(entity, market)
        severities = [r.severity_score for r in results]
        assert severities == sorted(severities, reverse=True)

    def test_peer_divergence_in_full_scan(self):
        """Peer data should trigger peer divergence when entity diverges."""
        entity = self._anomalous_entity()
        market = {"market_return": 0.001, "beta": 1.0}
        peer_data = [
            {"return_pct": 0.01}, {"return_pct": 0.015},
            {"return_pct": 0.02}, {"return_pct": 0.012},
            {"return_pct": 0.018}, {"return_pct": 0.011},
            {"return_pct": 0.022}, {"return_pct": 0.013},
        ]
        results = run_full_anomaly_scan(entity, market, peer_data)
        types_found = {r.anomaly_type for r in results}
        assert "peer_divergence" in types_found

    def test_full_scan_with_missing_optional_fields(self):
        """Scan should handle entity_data with missing optional fields."""
        entity = {
            "returns": [0.01, -0.01, 0.02, -0.005, 0.01] * 4,
            "current_return": 0.001,
        }
        market = {}
        results = run_full_anomaly_scan(entity, market)
        # Should not crash; returns empty or minimal list
        assert isinstance(results, list)


# -- Integration Tests --------------------------------------------------------


class TestIntegration:
    """Integration tests with realistic AAPL-like data."""

    def _aapl_data(self) -> tuple[dict, dict, list[dict]]:
        """Realistic AAPL data showing earnings surprise + volume spike."""
        # Normal daily returns (stdev ~ 0.015)
        returns = [
            0.012, -0.008, 0.005, -0.003, 0.010,
            -0.007, 0.004, -0.012, 0.008, -0.002,
            0.006, -0.009, 0.003, -0.005, 0.011,
            -0.004, 0.007, -0.010, 0.002, -0.006,
            0.009, -0.003, 0.005, -0.008, 0.004,
            -0.011, 0.006, -0.002, 0.008, -0.007,
        ]
        # Normal volumes ~50M
        volumes = [
            50e6, 52e6, 48e6, 51e6, 49e6,
            53e6, 47e6, 50e6, 52e6, 48e6,
            51e6, 49e6, 53e6, 47e6, 50e6,
            52e6, 48e6, 51e6, 49e6, 53e6,
            47e6, 50e6, 52e6, 48e6, 51e6,
            49e6, 53e6, 47e6, 50e6, 52e6,
        ]
        # Historical earnings surprises (mean ~3%, stdev ~4%)
        historical_surprises = [
            2.5, 4.0, -1.0, 5.0, 3.0, 1.5, 6.0, -2.0,
            3.5, 2.0, 4.5, 1.0, 3.0, -0.5, 5.5, 2.5,
        ]
        # Historical sentiment (~0.3 avg)
        historical_sentiments = [
            0.3, 0.35, 0.25, 0.28, 0.32, 0.30, 0.27, 0.33,
            0.29, 0.31, 0.34, 0.26, 0.30, 0.28, 0.32, 0.35,
        ]

        entity_data = {
            "returns": returns,
            "volumes": volumes,
            # Earnings day: big move + huge volume
            "current_return": 0.08,  # 8% move (massive for AAPL)
            "current_volume": 180e6,  # 3.6x average
            # Huge earnings beat
            "eps_actual": 2.10,
            "eps_consensus": 1.52,
            "historical_surprises": historical_surprises,
            # Sentiment shift
            "sentiment_score": 0.30,
            "historical_sentiments": historical_sentiments,
            "news_volume": 25,
            "avg_news_volume": 12.0,
            # Fundamentals stable
            "fundamentals_current": {
                "operating_margin": 0.30,
                "roe": 1.50,
                "debt_to_equity": 1.70,
                "revenue_growth": 0.08,
            },
            "fundamentals_prior": {
                "operating_margin": 0.29,
                "roe": 1.45,
                "debt_to_equity": 1.65,
                "revenue_growth": 0.07,
            },
            "supplier_news": [],
            "customer_news": [],
        }

        market_data = {"market_return": 0.003, "beta": 1.2}

        peer_data = [
            {"return_pct": 0.005, "operating_margin": 0.22},
            {"return_pct": 0.003, "operating_margin": 0.18},
            {"return_pct": -0.002, "operating_margin": 0.25},
            {"return_pct": 0.008, "operating_margin": 0.20},
            {"return_pct": 0.001, "operating_margin": 0.15},
            {"return_pct": 0.004, "operating_margin": 0.23},
        ]

        return entity_data, market_data, peer_data

    def test_aapl_earnings_day_detects_earnings_surprise(self):
        """AAPL earnings day should flag earnings surprise."""
        entity, market, peers = self._aapl_data()
        results = run_full_anomaly_scan(entity, market, peers)
        types = {r.anomaly_type for r in results}
        assert "earnings_surprise" in types

    def test_aapl_earnings_day_detects_volume_spike(self):
        """AAPL earnings day should flag volume spike."""
        entity, market, peers = self._aapl_data()
        results = run_full_anomaly_scan(entity, market, peers)
        types = {r.anomaly_type for r in results}
        assert "volume_spike" in types

    def test_aapl_earnings_day_detects_price_momentum(self):
        """An 8% move should flag price momentum."""
        entity, market, peers = self._aapl_data()
        results = run_full_anomaly_scan(entity, market, peers)
        types = {r.anomaly_type for r in results}
        assert "price_momentum" in types

    def test_aapl_narrative_generation(self):
        """Generated narrative should mention AAPL and key metrics."""
        entity, market, peers = self._aapl_data()
        results = run_full_anomaly_scan(entity, market, peers)
        assert len(results) > 0
        narrative = generate_anomaly_narrative_template(results[0], "AAPL")
        assert "AAPL" in narrative
        assert "anomaly" in narrative
        assert "z-score" in narrative
