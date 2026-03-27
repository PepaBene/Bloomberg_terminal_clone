"""Tests for Pillar 3 Phase 3A — Competitive Landscape Engine."""

from src.engines.competitive_landscape import (
    LandscapeResult,
    PeerComparison,
    analyze_competitive_landscape,
    build_peer_group,
    classify_value_chain_position,
    compute_peer_relative_metrics,
    detect_share_gainer,
    estimate_market_share,
    identify_competitive_advantages,
    identify_competitive_threats,
)


# ── Helpers ──────────────────────────────────────────────────────────────


def _make_company(
    entity_id: str,
    name: str,
    market_cap: float,
    gics_sector: str = "Technology",
    gics_industry: str = "Software",
    **kwargs,
) -> dict:
    """Create a company dict for testing."""
    return {
        "entity_id": entity_id,
        "name": name,
        "market_cap": market_cap,
        "gics_sector": gics_sector,
        "gics_industry": gics_industry,
        **kwargs,
    }


# ── Market Share Tests ───────────────────────────────────────────────────


class TestMarketShare:
    """Tests for estimate_market_share()."""

    def test_twenty_percent_share(self):
        """$200B revenue in $1T industry -> 20% share."""
        share = estimate_market_share(200.0, 1000.0)
        assert abs(share - 0.20) < 0.001

    def test_tiny_company(self):
        """$1B in $500B industry -> tiny share."""
        share = estimate_market_share(1.0, 500.0)
        assert share < 0.01

    def test_zero_industry_revenue(self):
        """Zero industry revenue -> 0 share."""
        share = estimate_market_share(100.0, 0.0)
        assert share == 0.0


# ── Share Gainer Tests ───────────────────────────────────────────────────


class TestShareGainer:
    """Tests for detect_share_gainer()."""

    def test_outperformer(self):
        """Entity growth 15% vs industry 5% -> gaining share."""
        assert detect_share_gainer(15.0, 5.0) is True

    def test_underperformer(self):
        """Entity growth 3% vs industry 8% -> not gaining."""
        assert detect_share_gainer(3.0, 8.0) is False

    def test_at_pace(self):
        """Entity growth 6% vs industry 5% -> within threshold."""
        assert detect_share_gainer(6.0, 5.0) is False


# ── Value Chain Tests ────────────────────────────────────────────────────


class TestValueChain:
    """Tests for classify_value_chain_position()."""

    def test_upstream_mining(self):
        """Mining company -> UPSTREAM."""
        result = classify_value_chain_position(
            {"description": "We are a mining and extraction company focused on raw material exploration."},
            None,
        )
        assert result == "UPSTREAM"

    def test_downstream_retail(self):
        """Retail company -> DOWNSTREAM."""
        result = classify_value_chain_position(
            {"description": "We operate retail stores for consumer sales and distribution."},
            None,
        )
        assert result == "DOWNSTREAM"

    def test_integrated(self):
        """Company spanning multiple segments -> INTEGRATED."""
        result = classify_value_chain_position(
            {"description": "We handle mining extraction, manufacturing processing, and retail distribution."},
            None,
        )
        assert result == "INTEGRATED"


# ── Peer Group Tests ─────────────────────────────────────────────────────


class TestBuildPeerGroup:
    """Tests for build_peer_group()."""

    def test_select_ten_from_fifty(self):
        """Select max 10 peers from 50 candidates in same industry."""
        target = _make_company("T1", "Target", 500.0)
        companies = [
            _make_company(f"C{i}", f"Company {i}", 100.0 + i * 20)
            for i in range(50)
        ]
        peers = build_peer_group(target, companies, max_peers=10)
        assert len(peers) == 10
        assert all(isinstance(p, PeerComparison) for p in peers)

    def test_few_available(self):
        """Only 3 candidates -> return all 3."""
        target = _make_company("T1", "Target", 500.0)
        companies = [
            _make_company(f"C{i}", f"Company {i}", 400.0 + i * 50)
            for i in range(3)
        ]
        peers = build_peer_group(target, companies, max_peers=10)
        assert len(peers) == 3

    def test_market_cap_proximity(self):
        """Peers should be sorted by market cap proximity."""
        target = _make_company("T1", "Target", 500.0)
        companies = [
            _make_company("C1", "Far Small", 100.0),
            _make_company("C2", "Close", 480.0),
            _make_company("C3", "Far Large", 2000.0),
        ]
        peers = build_peer_group(target, companies, max_peers=10)
        assert peers[0].name == "Close"  # Closest by market cap


# ── Peer Relative Metrics Tests ──────────────────────────────────────────


class TestPeerRelativeMetrics:
    """Tests for compute_peer_relative_metrics()."""

    def test_leader_vs_peers(self):
        """Entity outperforms peers on all metrics."""
        entity = {"revenue_growth": 20.0, "operating_margin": 0.35, "roic": 0.25}
        peers = [
            PeerComparison("P1", "Peer1", 100, revenue_growth=8.0, operating_margin=0.18, roic=0.12),
            PeerComparison("P2", "Peer2", 200, revenue_growth=10.0, operating_margin=0.20, roic=0.14),
            PeerComparison("P3", "Peer3", 150, revenue_growth=12.0, operating_margin=0.22, roic=0.16),
        ]
        result = compute_peer_relative_metrics(entity, peers)
        assert result["revenue_growth_vs_peers"] > 0
        assert result["margin_vs_peers"] > 0
        assert result["roic_vs_peers"] > 0

    def test_laggard_vs_peers(self):
        """Entity underperforms peers on all metrics."""
        entity = {"revenue_growth": 2.0, "operating_margin": 0.08, "roic": 0.05}
        peers = [
            PeerComparison("P1", "Peer1", 100, revenue_growth=10.0, operating_margin=0.20, roic=0.15),
            PeerComparison("P2", "Peer2", 200, revenue_growth=12.0, operating_margin=0.22, roic=0.18),
        ]
        result = compute_peer_relative_metrics(entity, peers)
        assert result["revenue_growth_vs_peers"] < 0
        assert result["margin_vs_peers"] < 0
        assert result["roic_vs_peers"] < 0


# ── Competitive Advantages Tests ─────────────────────────────────────────


class TestCompetitiveAdvantages:
    """Tests for identify_competitive_advantages()."""

    def test_multiple_advantages_msft_like(self):
        """MSFT-like: superior margins, ROIC, growth, market share."""
        advantages = identify_competitive_advantages(
            {
                "operating_margin": 0.42,
                "roic": 0.28,
                "revenue_growth": 18.0,
                "market_share": 0.30,
                "pe_ratio": 28.0,
            },
            {
                "operating_margin": 0.18,
                "roic": 0.12,
                "revenue_growth": 8.0,
                "pe_ratio": 25.0,
            },
        )
        assert len(advantages) >= 3
        assert any("margin" in a.lower() for a in advantages)
        assert any("capital efficiency" in a.lower() or "roic" in a.lower() for a in advantages)

    def test_no_advantages(self):
        """Laggard company has no advantages."""
        advantages = identify_competitive_advantages(
            {"operating_margin": 0.08, "roic": 0.05, "revenue_growth": 2.0},
            {"operating_margin": 0.20, "roic": 0.15, "revenue_growth": 10.0},
        )
        assert len(advantages) == 0

    def test_valuation_discount(self):
        """Low P/E vs peers -> valuation discount advantage."""
        advantages = identify_competitive_advantages(
            {"operating_margin": 0.15, "pe_ratio": 10.0},
            {"operating_margin": 0.15, "pe_ratio": 25.0},
        )
        assert any("valuation" in a.lower() for a in advantages)


# ── Competitive Threats Tests ────────────────────────────────────────────


class TestCompetitiveThreats:
    """Tests for identify_competitive_threats()."""

    def test_multiple_threats(self):
        """Company with declining share and margin compression."""
        threats = identify_competitive_threats(
            {"share_trend": "LOSING", "margin_trend": -0.05, "revenue_growth": 2.0},
            {"revenue_growth": 10.0, "new_entrants": 8, "disruption_risk": 0.7},
        )
        assert len(threats) >= 3
        assert any("share" in t.lower() for t in threats)
        assert any("margin" in t.lower() for t in threats)

    def test_no_threats(self):
        """Stable company with no threats."""
        threats = identify_competitive_threats(
            {"share_trend": "STABLE", "margin_trend": 0.02, "revenue_growth": 12.0},
            {"revenue_growth": 8.0, "new_entrants": 1, "disruption_risk": 0.2},
        )
        assert len(threats) == 0


# ── Full Landscape Analysis Tests ────────────────────────────────────────


class TestAnalyzeLandscape:
    """Tests for analyze_competitive_landscape() orchestrator."""

    def test_full_analysis_tech_companies(self):
        """Full analysis with 15 tech companies."""
        target = _make_company(
            "MSFT", "Microsoft", 2800.0,
            revenue=211.0, revenue_growth=15.0,
            operating_margin=0.42, roic=0.28,
            pe_ratio=32.0, market_share=0.30,
        )
        companies = [
            _make_company("AAPL", "Apple", 2900.0, revenue_growth=8.0, operating_margin=0.30, roic=0.20, pe_ratio=28.0),
            _make_company("GOOG", "Alphabet", 1800.0, revenue_growth=12.0, operating_margin=0.28, roic=0.18, pe_ratio=25.0),
            _make_company("AMZN", "Amazon", 1600.0, revenue_growth=20.0, operating_margin=0.06, roic=0.08, pe_ratio=60.0),
            _make_company("META", "Meta", 900.0, revenue_growth=22.0, operating_margin=0.35, roic=0.22, pe_ratio=22.0),
            _make_company("CRM", "Salesforce", 250.0, revenue_growth=10.0, operating_margin=0.20, roic=0.12, pe_ratio=30.0),
            _make_company("ORCL", "Oracle", 300.0, revenue_growth=6.0, operating_margin=0.25, roic=0.15, pe_ratio=20.0),
            _make_company("SAP", "SAP", 200.0, revenue_growth=8.0, operating_margin=0.22, roic=0.14, pe_ratio=28.0),
            _make_company("ADBE", "Adobe", 250.0, revenue_growth=11.0, operating_margin=0.35, roic=0.25, pe_ratio=35.0),
            _make_company("INTU", "Intuit", 180.0, revenue_growth=13.0, operating_margin=0.28, roic=0.18, pe_ratio=40.0),
            _make_company("NOW", "ServiceNow", 150.0, revenue_growth=25.0, operating_margin=0.22, roic=0.16, pe_ratio=60.0),
            _make_company("SNOW", "Snowflake", 50.0, revenue_growth=35.0, operating_margin=-0.05, roic=-0.02, pe_ratio=None),
            _make_company("PLTR", "Palantir", 60.0, revenue_growth=18.0, operating_margin=0.10, roic=0.06, pe_ratio=80.0),
            _make_company("ZS", "Zscaler", 30.0, revenue_growth=28.0, operating_margin=0.05, roic=0.04, pe_ratio=100.0),
            _make_company("DDOG", "Datadog", 40.0, revenue_growth=22.0, operating_margin=0.15, roic=0.10, pe_ratio=70.0),
            _make_company("NET", "Cloudflare", 25.0, revenue_growth=30.0, operating_margin=-0.02, roic=-0.01, pe_ratio=None),
        ]
        result = analyze_competitive_landscape(
            target, companies,
            {"total_industry_revenue": 1000.0, "revenue_growth": 10.0},
        )
        assert isinstance(result, LandscapeResult)
        assert len(result.peer_group) == 10
        assert result.entity_rank >= 1
        assert result.share_gainer is True  # 15% vs 10% industry
        assert result.revenue_growth_vs_peers > 0
        assert len(result.competitive_advantages) > 0

    def test_minimal_data(self):
        """Minimal data should not crash."""
        result = analyze_competitive_landscape(
            {"entity_id": "X", "market_cap": 100.0},
            [],
            {"total_industry_revenue": 0},
        )
        assert isinstance(result, LandscapeResult)
        assert len(result.peer_group) == 0
        assert result.entity_rank == 1

    def test_entity_not_in_peers(self):
        """Entity should not appear in its own peer group."""
        target = _make_company("T1", "Target", 500.0)
        companies = [
            _make_company("T1", "Target", 500.0),  # Same entity
            _make_company("C1", "Peer1", 450.0),
            _make_company("C2", "Peer2", 550.0),
        ]
        result = analyze_competitive_landscape(
            target, companies, {"total_industry_revenue": 2000.0, "revenue_growth": 5.0},
        )
        peer_ids = [p.entity_id for p in result.peer_group]
        assert "T1" not in peer_ids


# ── Integration Tests ────────────────────────────────────────────────────


class TestIntegration:
    """Integration tests for the full pipeline."""

    def test_complete_pipeline(self):
        """Full end-to-end test with realistic data."""
        target = _make_company(
            "AAPL", "Apple", 2900.0,
            revenue=394.0, revenue_growth=8.0,
            operating_margin=0.30, roic=0.55,
            pe_ratio=28.0, market_share=0.20,
            segment_data={"description": "consumer electronics retail and distribution"},
        )
        companies = [
            _make_company("MSFT", "Microsoft", 2800.0, revenue_growth=15.0, operating_margin=0.42, roic=0.28, pe_ratio=32.0),
            _make_company("GOOG", "Alphabet", 1800.0, revenue_growth=12.0, operating_margin=0.28, roic=0.18, pe_ratio=25.0),
            _make_company("SMSN", "Samsung", 350.0, revenue_growth=5.0, operating_margin=0.12, roic=0.10, pe_ratio=12.0),
        ]
        result = analyze_competitive_landscape(
            target, companies,
            {"total_industry_revenue": 2000.0, "revenue_growth": 7.0},
        )
        assert result.market_share_est == 0.20  # Provided, not estimated
        assert result.value_chain_position == "DOWNSTREAM"
        assert result.entity_rank >= 1

    def test_edge_case_empty_industry(self):
        """Zero industry revenue should not crash."""
        target = _make_company("T1", "Target", 100.0, revenue=50.0)
        result = analyze_competitive_landscape(
            target, [], {"total_industry_revenue": 0, "revenue_growth": 0},
        )
        assert result.market_share_est == 0.0  # Falls back to estimation with zero

    def test_no_gics_match_fallback_to_sector(self):
        """When no industry match, fall back to sector peers."""
        target = _make_company("T1", "Target", 500.0, gics_industry="Niche Software")
        companies = [
            _make_company("C1", "Peer1", 450.0, gics_industry="Enterprise Software", gics_sector="Technology"),
            _make_company("C2", "Peer2", 550.0, gics_industry="Enterprise Software", gics_sector="Technology"),
            _make_company("C3", "Peer3", 600.0, gics_industry="Enterprise Software", gics_sector="Technology"),
        ]
        result = analyze_competitive_landscape(
            target, companies, {"total_industry_revenue": 5000.0, "revenue_growth": 8.0},
        )
        # Should fall back to sector-level matching
        assert len(result.peer_group) == 3
