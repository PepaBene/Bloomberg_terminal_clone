"""Tests for the company primer engine (Pillar 2 Supplement – Part 7)."""

import pytest

from src.engines.company_primer import (
    PrimerData,
    compute_financial_summary,
    compute_valuation_summary,
    compute_ownership_summary,
    extract_key_risks,
    generate_primer,
)


class TestComputeFinancialSummary:
    def test_full_data(self):
        data = {
            "revenue": 50000.0,
            "revenue_growth": 12.5,
            "ebitda": 10000.0,
            "net_income": 5000.0,
            "eps": 5.0,
            "free_cash_flow": 8000.0,
            "total_debt": 20000.0,
            "total_equity": 30000.0,
        }
        summary = compute_financial_summary(data)
        assert summary["revenue"] == 50000.0
        assert summary["revenue_growth_pct"] == 12.5
        assert summary["ebitda"] == 10000.0
        assert summary["ebitda_margin_pct"] == pytest.approx(20.0)
        assert summary["net_margin_pct"] == pytest.approx(10.0)
        assert summary["debt_to_equity"] == pytest.approx(0.67, abs=0.01)

    def test_empty_data(self):
        summary = compute_financial_summary({})
        assert summary == {}

    def test_partial_data(self):
        summary = compute_financial_summary({"revenue": 1000.0, "eps": 2.5})
        assert summary["revenue"] == 1000.0
        assert summary["eps"] == 2.5
        assert "ebitda" not in summary


class TestComputeValuationSummary:
    def test_full_data(self):
        data = {
            "market_cap": 500000.0,
            "pe_ratio": 25.0,
            "ev_ebitda": 12.0,
            "pb_ratio": 3.5,
            "price_to_sales": 5.0,
            "dividend_yield": 1.8,
        }
        summary = compute_valuation_summary(data)
        assert len(summary) == 6
        assert summary["pe_ratio"] == 25.0

    def test_empty_data(self):
        summary = compute_valuation_summary({})
        assert summary == {}


class TestComputeOwnershipSummary:
    def test_full_data(self):
        data = {
            "institutional_pct": 75.5,
            "insider_pct": 5.2,
            "top_holders": [
                {"name": "Vanguard", "pct": 8.0},
                {"name": "BlackRock", "pct": 7.5},
                {"name": "Fidelity", "pct": 5.0},
            ],
        }
        summary = compute_ownership_summary(data)
        assert summary["institutional_pct"] == 75.5
        assert summary["insider_pct"] == 5.2
        assert len(summary["top_holders"]) == 3

    def test_empty_data(self):
        summary = compute_ownership_summary({})
        assert summary == {}

    def test_top_holders_capped_at_5(self):
        holders = [{"name": f"Fund {i}", "pct": 1.0} for i in range(10)]
        summary = compute_ownership_summary({"top_holders": holders})
        assert len(summary["top_holders"]) == 5


class TestExtractKeyRisks:
    def test_no_risks(self):
        risks = extract_key_risks({})
        assert risks == []

    def test_high_leverage(self):
        risks = extract_key_risks({"debt_to_equity": 3.0})
        assert len(risks) == 1
        assert "leverage" in risks[0].lower()

    def test_low_coverage(self):
        risks = extract_key_risks({"interest_coverage": 1.5})
        assert len(risks) == 1
        assert "coverage" in risks[0].lower()

    def test_concentration(self):
        risks = extract_key_risks({"revenue_concentration": 60.0})
        assert len(risks) == 1
        assert "concentration" in risks[0].lower()

    def test_regulatory_risk(self):
        risks = extract_key_risks({"regulatory_risk": True})
        assert len(risks) == 1
        assert "regulatory" in risks[0].lower()

    def test_multiple_risks(self):
        data = {
            "debt_to_equity": 4.0,
            "interest_coverage": 1.0,
            "regulatory_risk": True,
            "litigation_pending": True,
            "currency_exposure": True,
        }
        risks = extract_key_risks(data)
        assert len(risks) == 5


class TestGeneratePrimer:
    def test_without_ai(self):
        primer = generate_primer(
            entity_id="test-id",
            entity_name="Test Corp",
            financial_data={"revenue": 1000.0},
            valuation_data={"pe_ratio": 20.0},
            ownership_data={"institutional_pct": 70.0},
            risk_data={"debt_to_equity": 3.0},
        )
        assert isinstance(primer, PrimerData)
        assert primer.ai_enabled is False
        assert primer.business_description is None
        assert primer.competitive_position is None
        assert primer.financial_summary["revenue"] == 1000.0
        assert primer.valuation_summary["pe_ratio"] == 20.0
        assert primer.ownership_summary["institutional_pct"] == 70.0
        assert len(primer.key_risks) >= 1

    def test_with_ai(self):
        primer = generate_primer(
            entity_id="test-id",
            entity_name="Test Corp",
            financial_data={},
            valuation_data={},
            ownership_data={},
            risk_data={},
            ai_description="AI description.",
            ai_competitive="Strong competitive position.",
        )
        assert primer.ai_enabled is True
        assert primer.business_description == "AI description."
        assert primer.competitive_position == "Strong competitive position."

    def test_recent_events(self):
        events = [{"date": "2024-07-01", "title": "Q3 Earnings"}]
        primer = generate_primer(
            entity_id="test-id",
            entity_name="Test Corp",
            financial_data={},
            valuation_data={},
            ownership_data={},
            risk_data={},
            recent_events=events,
        )
        assert len(primer.recent_developments) == 1
