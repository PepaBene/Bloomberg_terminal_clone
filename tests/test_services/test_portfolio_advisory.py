"""Tests for src/services/portfolio_advisory.py (Layer 3 §5.1: wiring the
previously-dormant whatif_engine/drift_engine/trade_list_engine to real
portfolio data)."""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from src.models.analytics import AnalyticsResult
from src.models.compliance import ComplianceRule, DriftSnapshot
from src.models.entity import Entity
from src.models.portfolio import Portfolio
from src.models.portfolio_risk import PortfolioVarSnapshot
from src.models.position import Position
from src.models.risk import VaRResult
from src.models.security import EODPrice, Security, SecurityIdentifier
from src.services import portfolio_advisory


async def _seed_portfolio(session, **kwargs) -> Portfolio:
    defaults = dict(
        id=uuid.uuid4(), user_id="default_user", portfolio_name="Advisory Test Portfolio",
        portfolio_type="REAL", inception_date=date(2025, 1, 1),
        initial_cash=Decimal("100000.00"), current_cash=Decimal("20000.00"),
    )
    defaults.update(kwargs)
    p = Portfolio(**defaults)
    session.add(p)
    await session.flush()
    return p


async def _seed_position(session, portfolio_id, **kwargs) -> Position:
    defaults = dict(
        id=uuid.uuid4(), portfolio_id=portfolio_id, ticker="AAPL", status="OPEN",
        shares=Decimal("100"), market_value=Decimal("40000.00"), weight=Decimal("0.5"),
        closing_price=Decimal("400.00"),
    )
    defaults.update(kwargs)
    p = Position(**defaults)
    session.add(p)
    await session.flush()
    return p


async def _seed_compliance_rule(session, portfolio_id, **kwargs) -> ComplianceRule:
    defaults = dict(
        rule_id=uuid.uuid4(), portfolio_id=portfolio_id, rule_name="Max Position",
        rule_type="POSITION_LIMIT", rule_definition={}, threshold=Decimal("0.100000"),
        comparison="LTE", severity="WARNING", is_active=True,
    )
    defaults.update(kwargs)
    rule = ComplianceRule(**defaults)
    session.add(rule)
    await session.flush()
    return rule


async def _seed_security(session, ticker: str, *, legal_name: str | None = None) -> Security:
    """Entity + Security + a TICKER SecurityIdentifier -- the minimal real
    join path from a Position's ticker to security-level analytics
    (AnalyticsResult/VaRResult/EODPrice), matching the pattern
    e2_wacc.py/news_enrichment.py use elsewhere for the same lookup."""
    entity = Entity(
        entity_id=uuid.uuid4(), entity_type="PUBLIC_COMPANY",
        legal_name=legal_name or f"{ticker} Corp", status="ACTIVE", source="TEST",
    )
    session.add(entity)
    await session.flush()
    security = Security(
        security_id=uuid.uuid4(), security_type="EQUITY", issuer_entity_id=entity.entity_id,
        name=entity.legal_name, status="ACTIVE", asset_class="EQUITY",
    )
    session.add(security)
    await session.flush()
    session.add(SecurityIdentifier(
        id=uuid.uuid4(), security_id=security.security_id,
        identifier_type="TICKER", identifier_value=ticker,
    ))
    await session.flush()
    return security


async def _seed_factor(session, security: Security, metric_name: str, value, *, as_of=date(2026, 1, 1)) -> None:
    session.add(AnalyticsResult(
        result_id=uuid.uuid4(), security_id=security.security_id, entity_id=security.issuer_entity_id,
        engine_id="E5", metric_name=metric_name, metric_category="FACTOR",
        value=Decimal(str(value)), period="SNAPSHOT", as_of_date=as_of,
    ))
    await session.flush()


async def _seed_beta(session, security: Security, value, *, as_of=date(2026, 1, 1)) -> None:
    session.add(AnalyticsResult(
        result_id=uuid.uuid4(), security_id=security.security_id, entity_id=security.issuer_entity_id,
        engine_id="E7", metric_name="beta_market", metric_category="RISK",
        value=Decimal(str(value)), period="SNAPSHOT", as_of_date=as_of,
    ))
    await session.flush()


async def _seed_var_result(session, security: Security, *, var_value, annualized_volatility, confidence_level=Decimal("0.95"), holding_period_days=1, calculation_date=date(2026, 1, 1)) -> None:
    session.add(VaRResult(
        var_id=uuid.uuid4(), security_id=security.security_id, calculation_date=calculation_date,
        method="HISTORICAL", confidence_level=confidence_level, holding_period_days=holding_period_days,
        var_value=Decimal(str(var_value)), annualized_volatility=Decimal(str(annualized_volatility)),
        lookback_days=252,
    ))
    await session.flush()


async def _seed_eod_prices(session, security: Security, closes: list[float], *, start=None) -> None:
    # Default start keeps every seeded row inside
    # portfolio_advisory.CORRELATION_LOOKBACK_DAYS's lookback window
    # regardless of what "today" is when the suite runs.
    start = start or (date.today() - timedelta(days=len(closes) + 5))
    for i, close in enumerate(closes):
        session.add(EODPrice(
            security_id=security.security_id, price_date=date.fromordinal(start.toordinal() + i),
            close=Decimal(str(close)), close_adjusted=Decimal(str(close)),
        ))
    await session.flush()


class TestPositionDicts:

    def test_converts_fraction_weight_to_percentage(self):
        pos = Position(
            id=uuid.uuid4(), portfolio_id=uuid.uuid4(), ticker="MSFT", status="OPEN",
            shares=Decimal("10"), market_value=Decimal("5000"), weight=Decimal("0.25"),
        )
        result = portfolio_advisory.position_dicts([pos])
        assert result == [{"ticker": "MSFT", "shares": 10.0, "market_value": 5000.0, "weight": 25.0}]

    def test_handles_null_fields(self):
        pos = Position(id=uuid.uuid4(), portfolio_id=uuid.uuid4(), ticker="ZZZ", status="OPEN")
        result = portfolio_advisory.position_dicts([pos])
        assert result == [{"ticker": "ZZZ", "shares": 0.0, "market_value": 0.0, "weight": 0.0}]

    def test_merges_beta_and_volatility_when_supplied(self):
        pos = Position(
            id=uuid.uuid4(), portfolio_id=uuid.uuid4(), ticker="AAPL", status="OPEN",
            shares=Decimal("10"), market_value=Decimal("4000"), weight=Decimal("0.5"),
        )
        result = portfolio_advisory.position_dicts(
            [pos], beta_by_ticker={"AAPL": 1.2}, volatility_by_ticker={"AAPL": 0.25},
        )
        assert result[0]["beta"] == 1.2
        assert result[0]["volatility"] == 0.25

    def test_omits_beta_and_volatility_for_unmatched_ticker(self):
        pos = Position(
            id=uuid.uuid4(), portfolio_id=uuid.uuid4(), ticker="MSFT", status="OPEN",
            shares=Decimal("10"), market_value=Decimal("4000"), weight=Decimal("0.5"),
        )
        result = portfolio_advisory.position_dicts([pos], beta_by_ticker={"AAPL": 1.2})
        assert "beta" not in result[0]
        assert "volatility" not in result[0]


@pytest.mark.asyncio
class TestComputeWhatif:

    async def test_returns_none_for_missing_portfolio(self, session):
        result = await portfolio_advisory.compute_whatif(session, uuid.uuid4(), [])
        assert result is None

    async def test_computes_position_impact_from_real_positions(self, session):
        p = await _seed_portfolio(session)
        await _seed_position(session, p.id, ticker="AAPL", shares=Decimal("100"), market_value=Decimal("40000"), weight=Decimal("0.5"))

        result = await portfolio_advisory.compute_whatif(
            session, p.id,
            [{"ticker": "AAPL", "action": "SELL", "shares": 50, "price_per_share": 400.0}],
        )
        assert result is not None
        assert any(pi.ticker == "AAPL" for pi in result.position_impacts)

    async def test_uses_real_var_snapshot_when_present(self, session):
        p = await _seed_portfolio(session)
        await _seed_position(session, p.id)
        session.add(PortfolioVarSnapshot(
            id=uuid.uuid4(), portfolio_id=p.id, snapshot_date=date(2026, 1, 1),
            var_1d_95=Decimal("-5000.0000"),
        ))
        await session.flush()

        result = await portfolio_advisory.compute_whatif(session, p.id, [])
        assert result.risk_impact.current_var_95 == -5000.0

    async def test_degrades_gracefully_with_no_var_snapshot(self, session):
        p = await _seed_portfolio(session)
        await _seed_position(session, p.id)
        result = await portfolio_advisory.compute_whatif(session, p.id, [])
        assert result is not None
        assert result.risk_impact.current_var_95 == 0.0

    async def test_maps_active_position_limit_rule(self, session):
        p = await _seed_portfolio(session)
        await _seed_position(session, p.id, weight=Decimal("0.5"))
        await _seed_compliance_rule(session, p.id, rule_type="POSITION_LIMIT", threshold=Decimal("0.100000"))

        result = await portfolio_advisory.compute_whatif(session, p.id, [])
        assert any(ci.rule_name == "Max Position" for ci in result.compliance_impacts)

    async def test_inactive_rule_excluded(self, session):
        p = await _seed_portfolio(session)
        await _seed_position(session, p.id)
        await _seed_compliance_rule(session, p.id, is_active=False)

        result = await portfolio_advisory.compute_whatif(session, p.id, [])
        assert result.compliance_impacts == []

    async def test_uses_real_factor_var_beta_data_when_present(self, session):
        """End-to-end: seeded FACTOR/VaR/beta rows for a held position
        actually flow through compute_whatif into whatif_engine's factor
        and risk dimensions -- not the {} placeholders this used to
        always pass."""
        p = await _seed_portfolio(session)
        security = await _seed_security(session, "AAPL")
        await _seed_position(
            session, p.id, ticker="AAPL", security_id=security.security_id,
            shares=Decimal("100"), market_value=Decimal("40000"), weight=Decimal("1.0"),
        )
        await _seed_factor(session, security, "factor_momentum", 0.15)
        await _seed_beta(session, security, 1.3)
        await _seed_var_result(session, security, var_value=0.02, annualized_volatility=0.30)

        result = await portfolio_advisory.compute_whatif(session, p.id, [])

        assert any(fi.factor == "factor_momentum" for fi in result.factor_impacts)
        # current_beta is portfolio-level (from risk_data, unset here);
        # proposed_beta is the weighted average of per-position beta,
        # which is what the seeded beta_market row actually feeds.
        assert result.risk_impact.proposed_beta == pytest.approx(1.3)

    async def test_resolves_new_trade_only_ticker_for_factor_data(self, session):
        """A ticker being bought that isn't currently held still gets its
        real analytics resolved via SecurityIdentifier, not silently
        skipped just because it has no Position row."""
        p = await _seed_portfolio(session)
        held = await _seed_security(session, "AAPL")
        await _seed_position(session, p.id, ticker="AAPL", security_id=held.security_id, weight=Decimal("1.0"))
        new_ticker = await _seed_security(session, "NVDA")
        await _seed_factor(session, new_ticker, "factor_momentum", 0.40)

        result = await portfolio_advisory.compute_whatif(
            session, p.id,
            [{"ticker": "NVDA", "action": "BUY", "shares": 10, "price_per_share": 100.0}],
        )
        assert any(fi.factor == "factor_momentum" for fi in result.factor_impacts)


@pytest.mark.asyncio
class TestResolveSecurityIds:

    async def test_resolves_held_position_directly(self, session):
        p = await _seed_portfolio(session)
        security = await _seed_security(session, "AAPL")
        position = await _seed_position(session, p.id, ticker="AAPL", security_id=security.security_id)

        result = await portfolio_advisory._resolve_security_ids(session, [position], [])
        assert result == {"AAPL": security.security_id}

    async def test_resolves_trade_only_ticker_via_security_identifier(self, session):
        security = await _seed_security(session, "NVDA")
        result = await portfolio_advisory._resolve_security_ids(
            session, [], [{"ticker": "NVDA", "action": "BUY", "shares": 1, "price_per_share": 1.0}],
        )
        assert result == {"NVDA": security.security_id}

    async def test_unresolvable_ticker_is_absent(self, session):
        result = await portfolio_advisory._resolve_security_ids(
            session, [], [{"ticker": "NOSUCHTICKER", "action": "BUY", "shares": 1, "price_per_share": 1.0}],
        )
        assert result == {}

    async def test_held_position_with_no_security_id_is_absent(self, session):
        p = await _seed_portfolio(session)
        position = await _seed_position(session, p.id, ticker="ZZZ", security_id=None)
        result = await portfolio_advisory._resolve_security_ids(session, [position], [])
        assert result == {}


@pytest.mark.asyncio
class TestFactorDataForTickers:

    async def test_builds_factor_dict_from_analytics_results(self, session):
        security = await _seed_security(session, "AAPL")
        await _seed_factor(session, security, "factor_momentum", 0.15)
        await _seed_factor(session, security, "factor_value", 0.05)

        result = await portfolio_advisory._factor_data_for_tickers(session, {"AAPL": security.security_id})
        assert result == {"AAPL": {"factor_momentum": 0.15, "factor_value": 0.05}}

    async def test_uses_latest_value_per_factor(self, session):
        security = await _seed_security(session, "AAPL")
        await _seed_factor(session, security, "factor_momentum", 0.10, as_of=date(2025, 12, 1))
        await _seed_factor(session, security, "factor_momentum", 0.20, as_of=date(2026, 1, 1))

        result = await portfolio_advisory._factor_data_for_tickers(session, {"AAPL": security.security_id})
        assert result["AAPL"]["factor_momentum"] == 0.20

    async def test_ticker_with_no_factor_rows_is_absent(self, session):
        security = await _seed_security(session, "AAPL")
        result = await portfolio_advisory._factor_data_for_tickers(session, {"AAPL": security.security_id})
        assert result == {}

    async def test_empty_ticker_map_returns_empty_dict(self, session):
        assert await portfolio_advisory._factor_data_for_tickers(session, {}) == {}


@pytest.mark.asyncio
class TestRiskMetricsForTickers:

    async def test_scales_var_to_dollar_terms_by_market_value(self, session):
        security = await _seed_security(session, "AAPL")
        await _seed_var_result(session, security, var_value=0.02, annualized_volatility=0.30)

        individual_vars, volatility, beta = await portfolio_advisory._risk_metrics_for_tickers(
            session, {"AAPL": security.security_id}, {"AAPL": 40000.0},
        )
        assert individual_vars["AAPL"] == pytest.approx(0.02 * 40000.0)
        assert volatility["AAPL"] == pytest.approx(0.30)

    async def test_picks_the_95_percent_1day_row_among_others(self, session):
        security = await _seed_security(session, "AAPL")
        await _seed_var_result(session, security, var_value=0.05, annualized_volatility=0.40, confidence_level=Decimal("0.99"), holding_period_days=1)
        await _seed_var_result(session, security, var_value=0.10, annualized_volatility=0.40, confidence_level=Decimal("0.95"), holding_period_days=10)
        await _seed_var_result(session, security, var_value=0.02, annualized_volatility=0.30, confidence_level=Decimal("0.95"), holding_period_days=1)

        individual_vars, volatility, _ = await portfolio_advisory._risk_metrics_for_tickers(
            session, {"AAPL": security.security_id}, {"AAPL": 1000.0},
        )
        assert individual_vars["AAPL"] == pytest.approx(0.02 * 1000.0)
        assert volatility["AAPL"] == pytest.approx(0.30)

    async def test_reads_beta_market_metric(self, session):
        security = await _seed_security(session, "AAPL")
        await _seed_beta(session, security, 1.45)

        _, _, beta = await portfolio_advisory._risk_metrics_for_tickers(
            session, {"AAPL": security.security_id}, {"AAPL": 1000.0},
        )
        assert beta["AAPL"] == pytest.approx(1.45)

    async def test_ticker_with_no_data_is_absent_everywhere(self, session):
        security = await _seed_security(session, "AAPL")
        individual_vars, volatility, beta = await portfolio_advisory._risk_metrics_for_tickers(
            session, {"AAPL": security.security_id}, {"AAPL": 1000.0},
        )
        assert individual_vars == {}
        assert volatility == {}
        assert beta == {}


class TestPearsonCorrelation:

    def test_perfectly_correlated_series(self):
        a = {date(2026, 1, i): float(i) for i in range(1, 25)}
        b = {date(2026, 1, i): float(i) * 2.0 for i in range(1, 25)}
        assert portfolio_advisory._pearson_correlation(a, b) == pytest.approx(1.0)

    def test_perfectly_anti_correlated_series(self):
        a = {date(2026, 1, i): float(i) for i in range(1, 25)}
        b = {date(2026, 1, i): -float(i) for i in range(1, 25)}
        assert portfolio_advisory._pearson_correlation(a, b) == pytest.approx(-1.0)

    def test_insufficient_overlap_returns_none(self):
        a = {date(2026, 1, i): float(i) for i in range(1, 5)}
        b = {date(2026, 1, i): float(i) for i in range(1, 5)}
        assert portfolio_advisory._pearson_correlation(a, b) is None

    def test_zero_variance_series_returns_none(self):
        a = {date(2026, 1, i): 1.0 for i in range(1, 25)}
        b = {date(2026, 1, i): float(i) for i in range(1, 25)}
        assert portfolio_advisory._pearson_correlation(a, b) is None


@pytest.mark.asyncio
class TestCorrelationMatrixForTickers:

    async def test_computes_symmetric_matrix_for_correlated_prices(self, session):
        sec_a = await _seed_security(session, "AAPL")
        sec_b = await _seed_security(session, "MSFT")
        closes = [100.0 + i + (i % 3) for i in range(40)]
        await _seed_eod_prices(session, sec_a, closes)
        await _seed_eod_prices(session, sec_b, [c * 2.0 for c in closes])

        matrix = await portfolio_advisory._correlation_matrix_for_tickers(
            session, {"AAPL": sec_a.security_id, "MSFT": sec_b.security_id},
        )
        assert matrix["AAPL"]["MSFT"] == pytest.approx(matrix["MSFT"]["AAPL"])
        assert matrix["AAPL"]["MSFT"] == pytest.approx(1.0, abs=1e-6)

    async def test_single_ticker_produces_empty_matrix(self, session):
        sec_a = await _seed_security(session, "AAPL")
        await _seed_eod_prices(session, sec_a, [100.0 + i for i in range(30)])

        matrix = await portfolio_advisory._correlation_matrix_for_tickers(
            session, {"AAPL": sec_a.security_id},
        )
        assert matrix == {}

    async def test_too_few_price_points_omits_pair(self, session):
        sec_a = await _seed_security(session, "AAPL")
        sec_b = await _seed_security(session, "MSFT")
        await _seed_eod_prices(session, sec_a, [100.0, 101.0, 102.0])
        await _seed_eod_prices(session, sec_b, [200.0, 201.0, 202.0])

        matrix = await portfolio_advisory._correlation_matrix_for_tickers(
            session, {"AAPL": sec_a.security_id, "MSFT": sec_b.security_id},
        )
        assert matrix == {}


@pytest.mark.asyncio
class TestComputeDrift:

    async def test_returns_none_for_missing_portfolio(self, session):
        result = await portfolio_advisory.compute_drift(session, uuid.uuid4())
        assert result is None

    async def test_returns_none_when_no_target_allocation_set(self, session):
        p = await _seed_portfolio(session)
        await _seed_position(session, p.id)
        result = await portfolio_advisory.compute_drift(session, p.id)
        assert result is None

    async def test_computes_drift_against_target_allocation(self, session):
        p = await _seed_portfolio(session)
        await _seed_position(session, p.id, ticker="AAPL", weight=Decimal("0.80"), market_value=Decimal("80000"))
        session.add(DriftSnapshot(
            id=uuid.uuid4(), portfolio_id=p.id, snapshot_date=date(2026, 1, 1),
            target_allocation={"AAPL": 50.0},
        ))
        await session.flush()

        analysis = await portfolio_advisory.compute_drift(session, p.id)
        assert analysis is not None
        assert analysis.result.rebalance_needed is True
        assert any(t["ticker"] == "AAPL" for t in analysis.rebalance_trades)

    async def test_uses_most_recent_target_allocation(self, session):
        p = await _seed_portfolio(session)
        await _seed_position(session, p.id, ticker="AAPL", weight=Decimal("0.50"), market_value=Decimal("50000"))
        session.add(DriftSnapshot(
            id=uuid.uuid4(), portfolio_id=p.id, snapshot_date=date(2026, 1, 1),
            target_allocation={"AAPL": 20.0},
        ))
        session.add(DriftSnapshot(
            id=uuid.uuid4(), portfolio_id=p.id, snapshot_date=date(2026, 2, 1),
            target_allocation={"AAPL": 50.0},
        ))
        await session.flush()

        analysis = await portfolio_advisory.compute_drift(session, p.id)
        assert analysis.target_allocation == {"AAPL": 50.0}
        assert analysis.result.rebalance_needed is False


@pytest.mark.asyncio
class TestBuildTradeList:

    async def test_returns_none_for_missing_portfolio(self, session):
        result = await portfolio_advisory.build_trade_list(session, uuid.uuid4(), [])
        assert result is None

    async def test_generates_trade_list_from_rebalance_trades(self, session):
        p = await _seed_portfolio(session)
        await _seed_position(session, p.id, ticker="AAPL", shares=Decimal("100"), closing_price=Decimal("400.00"))

        trade_list = await portfolio_advisory.build_trade_list(
            session, p.id, [{"ticker": "AAPL", "action": "SELL", "weight_delta": 10.0, "notional_amount": 12000.0}],
        )
        assert trade_list is not None
        assert len(trade_list.orders) >= 1


@pytest.mark.asyncio
class TestCheckPretradeCompliance:

    async def test_returns_none_for_missing_portfolio(self, session):
        result = await portfolio_advisory.check_pretrade_compliance(
            session, uuid.uuid4(), ticker="AAPL", action="BUY", shares=10, price=100.0,
        )
        assert result is None

    async def test_approved_with_no_rules(self, session):
        p = await _seed_portfolio(session)
        result = await portfolio_advisory.check_pretrade_compliance(
            session, p.id, ticker="AAPL", action="BUY", shares=10, price=150.0,
        )
        assert result.approved is True
        assert result.violations == []

    async def test_violation_when_over_position_limit(self, session):
        p = await _seed_portfolio(session)
        await _seed_compliance_rule(session, p.id, rule_type="POSITION_LIMIT", threshold=Decimal("1000.000000"))
        result = await portfolio_advisory.check_pretrade_compliance(
            session, p.id, ticker="AAPL", action="BUY", shares=100, price=150.0,
        )
        assert result.approved is False
        assert len(result.violations) >= 1
