"""Tests for Pillar 4 Phase 3 — Compliance Engine."""

from __future__ import annotations

import pytest

from src.engines.compliance_engine import (
    COMPARISONS,
    RULE_TYPES,
    SEVERITIES,
    STATUSES,
    ComplianceCheck,
    ComplianceSummary,
    PreTradeResult,
    check_position_limit,
    check_quality_constraint,
    check_risk_constraint,
    check_sector_limit,
    check_valuation_constraint,
    evaluate_all_rules,
    evaluate_comparison,
    generate_compliance_report,
    pre_trade_check,
    simulate_trade,
)


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def sample_positions():
    return [
        {"ticker": "AAPL", "weight": 15.0, "sector": "Technology", "market_value": 150_000},
        {"ticker": "MSFT", "weight": 12.0, "sector": "Technology", "market_value": 120_000},
        {"ticker": "JPM", "weight": 10.0, "sector": "Financials", "market_value": 100_000},
        {"ticker": "JNJ", "weight": 8.0, "sector": "Healthcare", "market_value": 80_000},
        {"ticker": "XOM", "weight": 5.0, "sector": "Energy", "market_value": 50_000},
    ]


@pytest.fixture
def quality_scores():
    return {"AAPL": 8, "MSFT": 7, "JPM": 5, "JNJ": 6, "XOM": 3}


@pytest.fixture
def pe_valuations():
    return {"AAPL": 28.0, "MSFT": 32.0, "JPM": 12.0, "JNJ": 18.0, "XOM": 9.0}


@pytest.fixture
def risk_data():
    return {"var_95": 0.025, "beta": 1.05, "volatility": 0.18}


# ── Constants Tests ──────────────────────────────────────────────────────


class TestConstants:
    def test_rule_types_contents(self):
        assert "POSITION_LIMIT" in RULE_TYPES
        assert "SECTOR_LIMIT" in RULE_TYPES
        assert "QUALITY" in RULE_TYPES
        assert "VALUATION" in RULE_TYPES
        assert "RISK" in RULE_TYPES
        assert "CUSTOM" in RULE_TYPES

    def test_comparisons_contents(self):
        assert COMPARISONS == {"LT", "GT", "LTE", "GTE", "EQ", "BETWEEN"}

    def test_severities_contents(self):
        assert SEVERITIES == {"WARNING", "BREACH"}

    def test_statuses_contents(self):
        assert STATUSES == {"PASS", "WARNING", "BREACH", "N_A"}


# ── evaluate_comparison Tests ────────────────────────────────────────────


class TestEvaluateComparison:
    def test_lt_true(self):
        assert evaluate_comparison(5.0, "LT", 10.0) is True

    def test_lt_false(self):
        assert evaluate_comparison(10.0, "LT", 10.0) is False

    def test_gt_true(self):
        assert evaluate_comparison(15.0, "GT", 10.0) is True

    def test_gt_false(self):
        assert evaluate_comparison(10.0, "GT", 10.0) is False

    def test_lte_equal(self):
        assert evaluate_comparison(10.0, "LTE", 10.0) is True

    def test_lte_less(self):
        assert evaluate_comparison(9.0, "LTE", 10.0) is True

    def test_gte_equal(self):
        assert evaluate_comparison(10.0, "GTE", 10.0) is True

    def test_gte_greater(self):
        assert evaluate_comparison(11.0, "GTE", 10.0) is True

    def test_eq_true(self):
        assert evaluate_comparison(10.0, "EQ", 10.0) is True

    def test_eq_false(self):
        assert evaluate_comparison(10.1, "EQ", 10.0) is False

    def test_between_inside(self):
        assert evaluate_comparison(5.0, "BETWEEN", 1.0, 10.0) is True

    def test_between_on_boundary(self):
        assert evaluate_comparison(1.0, "BETWEEN", 1.0, 10.0) is True
        assert evaluate_comparison(10.0, "BETWEEN", 1.0, 10.0) is True

    def test_between_outside(self):
        assert evaluate_comparison(11.0, "BETWEEN", 1.0, 10.0) is False

    def test_between_no_upper(self):
        assert evaluate_comparison(5.0, "BETWEEN", 1.0) is False

    def test_invalid_comparison(self):
        assert evaluate_comparison(5.0, "INVALID", 10.0) is False

    def test_case_insensitive(self):
        assert evaluate_comparison(5.0, "lt", 10.0) is True


# ── check_position_limit Tests ───────────────────────────────────────────


class TestCheckPositionLimit:
    def test_pass(self, sample_positions):
        rule = {"rule_name": "Max Position", "max_weight": 20.0}
        result = check_position_limit(sample_positions, rule)
        assert result.status == "PASS"
        assert result.current_value == 15.0
        assert result.breach_positions is None

    def test_breach(self, sample_positions):
        rule = {"rule_name": "Max Position", "max_weight": 10.0}
        result = check_position_limit(sample_positions, rule)
        assert result.status == "BREACH"
        assert len(result.breach_positions) == 2  # AAPL (15) and MSFT (12)

    def test_warning_severity(self, sample_positions):
        rule = {"rule_name": "Max Position", "max_weight": 10.0, "severity": "WARNING"}
        result = check_position_limit(sample_positions, rule)
        assert result.status == "WARNING"

    def test_empty_positions(self):
        rule = {"rule_name": "Max Position", "max_weight": 10.0}
        result = check_position_limit([], rule)
        assert result.status == "N_A"

    def test_default_rule_name(self):
        rule = {"max_weight": 10.0}
        result = check_position_limit([], rule)
        assert result.rule_name == "Position Limit"


# ── check_sector_limit Tests ────────────────────────────────────────────


class TestCheckSectorLimit:
    def test_pass(self, sample_positions):
        rule = {"rule_name": "Sector Cap", "max_sector_weight": 30.0}
        result = check_sector_limit(sample_positions, rule)
        assert result.status == "PASS"

    def test_breach(self, sample_positions):
        rule = {"rule_name": "Sector Cap", "max_sector_weight": 20.0}
        result = check_sector_limit(sample_positions, rule)
        assert result.status == "BREACH"
        assert any(bp["sector"] == "Technology" for bp in result.breach_positions)

    def test_target_sector_pass(self, sample_positions):
        rule = {
            "rule_name": "Tech Cap",
            "max_sector_weight": 30.0,
            "target_sector": "Technology",
        }
        result = check_sector_limit(sample_positions, rule)
        assert result.status == "PASS"

    def test_target_sector_breach(self, sample_positions):
        rule = {
            "rule_name": "Tech Cap",
            "max_sector_weight": 20.0,
            "target_sector": "Technology",
        }
        result = check_sector_limit(sample_positions, rule)
        assert result.status == "BREACH"

    def test_empty_positions(self):
        rule = {"max_sector_weight": 10.0}
        result = check_sector_limit([], rule)
        assert result.status == "N_A"


# ── check_quality_constraint Tests ───────────────────────────────────────


class TestCheckQualityConstraint:
    def test_pass_all(self, sample_positions, quality_scores):
        rule = {
            "rule_name": "Min Piotroski",
            "metric": "piotroski",
            "comparison": "GTE",
            "threshold": 3,
        }
        result = check_quality_constraint(sample_positions, quality_scores, rule)
        assert result.status == "PASS"

    def test_breach(self, sample_positions, quality_scores):
        rule = {
            "rule_name": "Min Piotroski",
            "metric": "piotroski",
            "comparison": "GTE",
            "threshold": 6,
        }
        result = check_quality_constraint(sample_positions, quality_scores, rule)
        assert result.status == "BREACH"
        assert any(bp["ticker"] == "XOM" for bp in result.breach_positions)

    def test_no_scores(self, sample_positions):
        rule = {"metric": "piotroski", "comparison": "GTE", "threshold": 5}
        result = check_quality_constraint(sample_positions, {}, rule)
        assert result.status == "N_A"

    def test_no_positions(self, quality_scores):
        rule = {"metric": "piotroski", "comparison": "GTE", "threshold": 5}
        result = check_quality_constraint([], quality_scores, rule)
        assert result.status == "N_A"

    def test_partial_scores(self, sample_positions):
        scores = {"AAPL": 8}  # only one ticker has score
        rule = {"metric": "piotroski", "comparison": "GTE", "threshold": 5}
        result = check_quality_constraint(sample_positions, scores, rule)
        assert result.status == "PASS"
        assert result.current_value == 8.0


# ── check_valuation_constraint Tests ─────────────────────────────────────


class TestCheckValuationConstraint:
    def test_pass_pe_limit(self, sample_positions, pe_valuations):
        rule = {
            "rule_name": "Max PE",
            "metric": "pe_ratio",
            "comparison": "LTE",
            "threshold": 35.0,
        }
        result = check_valuation_constraint(sample_positions, pe_valuations, rule)
        assert result.status == "PASS"

    def test_breach_pe_limit(self, sample_positions, pe_valuations):
        rule = {
            "rule_name": "Max PE",
            "metric": "pe_ratio",
            "comparison": "LTE",
            "threshold": 20.0,
        }
        result = check_valuation_constraint(sample_positions, pe_valuations, rule)
        assert result.status == "BREACH"
        breach_tickers = [bp["ticker"] for bp in result.breach_positions]
        assert "AAPL" in breach_tickers  # 28
        assert "MSFT" in breach_tickers  # 32

    def test_between_range(self, sample_positions, pe_valuations):
        rule = {
            "rule_name": "PE Range",
            "metric": "pe_ratio",
            "comparison": "BETWEEN",
            "threshold": 10.0,
            "upper_threshold": 30.0,
        }
        result = check_valuation_constraint(sample_positions, pe_valuations, rule)
        assert result.status == "BREACH"
        # XOM (9) and MSFT (32) are outside range
        breach_tickers = [bp["ticker"] for bp in result.breach_positions]
        assert "XOM" in breach_tickers
        assert "MSFT" in breach_tickers

    def test_no_valuations(self, sample_positions):
        rule = {"metric": "pe_ratio", "comparison": "LTE", "threshold": 30.0}
        result = check_valuation_constraint(sample_positions, {}, rule)
        assert result.status == "N_A"

    def test_empty_positions(self, pe_valuations):
        rule = {"metric": "pe_ratio", "comparison": "LTE", "threshold": 30.0}
        result = check_valuation_constraint([], pe_valuations, rule)
        assert result.status == "N_A"


# ── check_risk_constraint Tests ──────────────────────────────────────────


class TestCheckRiskConstraint:
    def test_pass_var(self, risk_data):
        rule = {
            "rule_name": "VaR Limit",
            "metric": "var_95",
            "comparison": "LTE",
            "threshold": 0.05,
        }
        result = check_risk_constraint(risk_data, rule)
        assert result.status == "PASS"

    def test_breach_var(self, risk_data):
        rule = {
            "rule_name": "VaR Limit",
            "metric": "var_95",
            "comparison": "LTE",
            "threshold": 0.02,
        }
        result = check_risk_constraint(risk_data, rule)
        assert result.status == "BREACH"

    def test_pass_beta(self, risk_data):
        rule = {
            "rule_name": "Beta Limit",
            "metric": "beta",
            "comparison": "LTE",
            "threshold": 1.2,
        }
        result = check_risk_constraint(risk_data, rule)
        assert result.status == "PASS"

    def test_missing_metric(self, risk_data):
        rule = {
            "rule_name": "CVaR Limit",
            "metric": "cvar_99",
            "comparison": "LTE",
            "threshold": 0.10,
        }
        result = check_risk_constraint(risk_data, rule)
        assert result.status == "N_A"

    def test_empty_risk_data(self):
        rule = {"metric": "var_95", "comparison": "LTE", "threshold": 0.05}
        result = check_risk_constraint({}, rule)
        assert result.status == "N_A"

    def test_warning_severity(self, risk_data):
        rule = {
            "rule_name": "Beta Warning",
            "metric": "beta",
            "comparison": "LTE",
            "threshold": 1.0,
            "severity": "WARNING",
        }
        result = check_risk_constraint(risk_data, rule)
        assert result.status == "WARNING"


# ── simulate_trade Tests ─────────────────────────────────────────────────


class TestSimulateTrade:
    def test_buy_existing(self, sample_positions):
        trade = {"ticker": "AAPL", "action": "BUY", "weight_delta": 3.0}
        new_pos = simulate_trade(sample_positions, trade)
        aapl = next(p for p in new_pos if p["ticker"] == "AAPL")
        assert aapl["weight"] == 18.0

    def test_sell_existing(self, sample_positions):
        trade = {"ticker": "XOM", "action": "SELL", "weight_delta": 3.0}
        new_pos = simulate_trade(sample_positions, trade)
        xom = next(p for p in new_pos if p["ticker"] == "XOM")
        assert xom["weight"] == 2.0

    def test_sell_to_zero(self, sample_positions):
        trade = {"ticker": "XOM", "action": "SELL", "weight_delta": 10.0}
        new_pos = simulate_trade(sample_positions, trade)
        xom_list = [p for p in new_pos if p["ticker"] == "XOM"]
        assert len(xom_list) == 0  # removed

    def test_buy_new_position(self, sample_positions):
        trade = {"ticker": "GOOG", "action": "BUY", "weight_delta": 5.0, "sector": "Technology"}
        new_pos = simulate_trade(sample_positions, trade)
        goog = next(p for p in new_pos if p["ticker"] == "GOOG")
        assert goog["weight"] == 5.0

    def test_does_not_mutate_original(self, sample_positions):
        original_aapl_weight = sample_positions[0]["weight"]
        trade = {"ticker": "AAPL", "action": "BUY", "weight_delta": 5.0}
        simulate_trade(sample_positions, trade)
        assert sample_positions[0]["weight"] == original_aapl_weight


# ── evaluate_all_rules Tests ─────────────────────────────────────────────


class TestEvaluateAllRules:
    def test_all_pass(self, sample_positions, quality_scores, pe_valuations, risk_data):
        rules = [
            {"rule_type": "POSITION_LIMIT", "rule_name": "Pos Limit", "max_weight": 20.0},
            {"rule_type": "SECTOR_LIMIT", "rule_name": "Sec Limit", "max_sector_weight": 30.0},
        ]
        context = {}
        summary = evaluate_all_rules(sample_positions, rules, context)
        assert summary.total_rules == 2
        assert summary.passed == 2
        assert summary.breaches == 0

    def test_mixed_results(self, sample_positions, quality_scores, risk_data):
        rules = [
            {"rule_type": "POSITION_LIMIT", "rule_name": "Pos", "max_weight": 20.0},
            {"rule_type": "QUALITY", "rule_name": "Quality", "metric": "piotroski",
             "comparison": "GTE", "threshold": 6},
        ]
        context = {"scores": quality_scores}
        summary = evaluate_all_rules(sample_positions, rules, context)
        assert summary.passed == 1
        assert summary.breaches == 1

    def test_unknown_rule_type(self, sample_positions):
        rules = [{"rule_type": "UNKNOWN", "rule_name": "Mystery"}]
        summary = evaluate_all_rules(sample_positions, rules, {})
        assert summary.na == 1

    def test_empty_rules(self, sample_positions):
        summary = evaluate_all_rules(sample_positions, [], {})
        assert summary.total_rules == 0
        assert summary.passed == 0

    def test_risk_rule(self, sample_positions, risk_data):
        rules = [
            {"rule_type": "RISK", "rule_name": "VaR", "metric": "var_95",
             "comparison": "LTE", "threshold": 0.05},
        ]
        context = {"risk_data": risk_data}
        summary = evaluate_all_rules(sample_positions, rules, context)
        assert summary.passed == 1

    def test_valuation_rule(self, sample_positions, pe_valuations):
        rules = [
            {"rule_type": "VALUATION", "rule_name": "PE", "metric": "pe_ratio",
             "comparison": "LTE", "threshold": 35.0},
        ]
        context = {"valuations": pe_valuations}
        summary = evaluate_all_rules(sample_positions, rules, context)
        assert summary.passed == 1


# ── pre_trade_check Tests ────────────────────────────────────────────────


class TestPreTradeCheck:
    def test_trade_allowed(self, sample_positions):
        trade = {"ticker": "GOOG", "action": "BUY", "weight_delta": 5.0, "sector": "Technology"}
        rules = [
            {"rule_type": "POSITION_LIMIT", "rule_name": "Pos", "max_weight": 20.0},
        ]
        result = pre_trade_check(sample_positions, trade, rules, {})
        assert result.can_proceed is True
        assert len(result.breaches) == 0

    def test_trade_blocked(self, sample_positions):
        trade = {"ticker": "AAPL", "action": "BUY", "weight_delta": 10.0}
        rules = [
            {"rule_type": "POSITION_LIMIT", "rule_name": "Pos", "max_weight": 20.0},
        ]
        result = pre_trade_check(sample_positions, trade, rules, {})
        assert result.can_proceed is False
        assert len(result.breaches) == 1

    def test_trade_with_warning(self, sample_positions):
        trade = {"ticker": "AAPL", "action": "BUY", "weight_delta": 10.0}
        rules = [
            {"rule_type": "POSITION_LIMIT", "rule_name": "Pos", "max_weight": 20.0,
             "severity": "WARNING"},
        ]
        result = pre_trade_check(sample_positions, trade, rules, {})
        assert result.can_proceed is True
        assert len(result.warnings) == 1


# ── generate_compliance_report Tests ─────────────────────────────────────


class TestGenerateComplianceReport:
    def test_report_contains_header(self, sample_positions):
        rules = [
            {"rule_type": "POSITION_LIMIT", "rule_name": "Pos Limit", "max_weight": 20.0},
        ]
        summary = evaluate_all_rules(sample_positions, rules, {})
        report = generate_compliance_report(summary)
        assert "COMPLIANCE REPORT" in report
        assert "Total Rules: 1" in report

    def test_report_shows_breach(self, sample_positions):
        rules = [
            {"rule_type": "POSITION_LIMIT", "rule_name": "Pos Limit", "max_weight": 10.0},
        ]
        summary = evaluate_all_rules(sample_positions, rules, {})
        report = generate_compliance_report(summary)
        assert "[BREACH]" in report
        assert "Breaches: 1" in report

    def test_report_shows_pass(self, sample_positions):
        rules = [
            {"rule_type": "POSITION_LIMIT", "rule_name": "Pos Limit", "max_weight": 20.0},
        ]
        summary = evaluate_all_rules(sample_positions, rules, {})
        report = generate_compliance_report(summary)
        assert "[PASS]" in report
        assert "Passed:   1" in report

    def test_empty_summary(self):
        summary = ComplianceSummary(
            total_rules=0, passed=0, warnings=0, breaches=0, na=0, results=[],
        )
        report = generate_compliance_report(summary)
        assert "Total Rules: 0" in report
