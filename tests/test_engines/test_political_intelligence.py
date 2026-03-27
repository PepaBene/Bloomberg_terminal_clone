"""Tests for Pillar 3 Phase 3B — Political Intelligence Engine."""

import pytest

from src.engines.political_intelligence import (
    BILL_TYPE_SECTOR_MAP,
    SEVERITY_SCORES,
    STATUS_WEIGHTS,
    BillAssessment,
    RegulatoryImpact,
    SanctionsAssessment,
    assess_bill,
    assess_bill_market_relevance,
    assess_bill_passage_probability,
    assess_regulatory_impact,
    assess_regulatory_precedent,
    assess_sanctions_impact,
    classify_bill_sector_impact,
    classify_regulatory_severity,
    detect_policy_momentum,
    track_regulatory_pipeline,
)


# ── TestBillProbability ──────────────────────────────────────────────


class TestBillProbability:
    """Tests for assess_bill_passage_probability()."""

    def test_many_sponsors_bipartisan_committee(self):
        """High sponsors + bipartisan + COMMITTEE → elevated probability."""
        prob = assess_bill_passage_probability(
            sponsor_count=40, committee_status="COMMITTEE", bipartisan=True,
        )
        # base=20 + sponsors=min(25,20) + bipartisan=15 = 55
        assert prob >= 50.0

    def test_few_sponsors_low_prob(self):
        """Few sponsors, introduced, not bipartisan → low."""
        prob = assess_bill_passage_probability(
            sponsor_count=2, committee_status="INTRODUCED", bipartisan=False,
        )
        # base=10 + sponsors=1.0 = 11
        assert prob < 20.0

    def test_signed_bill(self):
        """SIGNED status → base is 100, always high."""
        prob = assess_bill_passage_probability(
            sponsor_count=0, committee_status="SIGNED", bipartisan=False,
        )
        assert prob == 100.0

    def test_historical_rate_blending(self):
        """Historical rate blends into score at 30% weight."""
        without = assess_bill_passage_probability(
            sponsor_count=10, committee_status="COMMITTEE", bipartisan=False,
        )
        with_hist = assess_bill_passage_probability(
            sponsor_count=10, committee_status="COMMITTEE", bipartisan=False,
            historical_rate=80.0,
        )
        # Historical rate of 80 should pull the score up
        assert with_hist > without


# ── TestBillSectorImpact ─────────────────────────────────────────────


class TestBillSectorImpact:
    """Tests for classify_bill_sector_impact()."""

    def test_tax_bill_all_sectors(self):
        """TAX type → ALL sectors."""
        result = classify_bill_sector_impact("TAX", "Tax Reform Act")
        sector_names = [s["sector_name"] for s in result]
        assert "ALL" in sector_names

    def test_healthcare_bill(self):
        """HEALTHCARE_REGULATION → HEALTH_CARE sector."""
        result = classify_bill_sector_impact(
            "HEALTHCARE_REGULATION", "Drug Pricing Reform",
        )
        sector_names = [s["sector_name"] for s in result]
        assert "HEALTH_CARE" in sector_names

    def test_trade_bill_industrials_materials(self):
        """TRADE type → INDUSTRIALS + MATERIALS + CONSUMER_STAPLES."""
        result = classify_bill_sector_impact("TRADE", "Trade Act")
        sector_names = [s["sector_name"] for s in result]
        assert "INDUSTRIALS" in sector_names
        assert "MATERIALS" in sector_names


# ── TestBillRelevance ────────────────────────────────────────────────


class TestBillRelevance:
    """Tests for assess_bill_market_relevance()."""

    def test_high_relevance(self):
        """High probability + many sectors = HIGH."""
        assert assess_bill_market_relevance(50.0, 4) == "HIGH"

    def test_low_relevance(self):
        """Low probability = LOW regardless of sectors."""
        assert assess_bill_market_relevance(10.0, 5) == "LOW"

    def test_medium_relevance(self):
        """Moderate probability with few sectors = MEDIUM."""
        assert assess_bill_market_relevance(30.0, 2) == "MEDIUM"


# ── TestAssessBill ───────────────────────────────────────────────────


class TestAssessBill:
    """Tests for assess_bill() orchestrator."""

    def test_infrastructure_bill(self):
        """Realistic infrastructure bill assessment."""
        result = assess_bill(
            bill_id="HR-1234",
            title="Infrastructure Investment and Jobs Act",
            bill_type="TRADE",
            sponsor_count=30,
            status="PASSED_HOUSE",
            bipartisan=True,
            summary="Invests in roads, bridges, broadband, and grid modernization",
        )
        assert isinstance(result, BillAssessment)
        assert result.bill_id == "HR-1234"
        assert result.passage_probability > 40.0
        assert len(result.affected_sectors) >= 3  # TRADE sectors + keywords

    def test_tax_bill(self):
        """Tax bill affects all sectors."""
        result = assess_bill(
            bill_id="S-5678",
            title="Corporate Tax Simplification Act",
            bill_type="TAX",
            sponsor_count=5,
            status="COMMITTEE",
            bipartisan=False,
        )
        assert isinstance(result, BillAssessment)
        sector_names = [s["sector_name"] for s in result.affected_sectors]
        assert "ALL" in sector_names


# ── TestRegulatorySeverity ───────────────────────────────────────────


class TestRegulatorySeverity:
    """Tests for classify_regulatory_severity()."""

    def test_fine_base_score(self):
        """FINE action → base 70."""
        score = classify_regulatory_severity("FINE")
        assert score == 70.0

    def test_inquiry_low(self):
        """INQUIRY → base 10."""
        score = classify_regulatory_severity("INQUIRY")
        assert score == 10.0

    def test_enforcement_plus_large_impact(self):
        """ENFORCEMENT + $2B impact → 60 + 20 = 80."""
        score = classify_regulatory_severity(
            "ENFORCEMENT", financial_impact=2_000_000_000,
        )
        assert score >= 80.0


# ── TestRegulatoryPrecedent ──────────────────────────────────────────


class TestRegulatoryPrecedent:
    """Tests for assess_regulatory_precedent()."""

    def test_novel_action(self):
        """No prior actions → NOVEL."""
        result = assess_regulatory_precedent("SEC", "FINE", prior_actions=None)
        assert result == "NOVEL"

    def test_routine_action(self):
        """Same type, same severity → ROUTINE."""
        priors = [
            {"agency": "SEC", "action_type": "FINE", "severity_score": 70},
        ]
        result = assess_regulatory_precedent("SEC", "FINE", prior_actions=priors)
        assert result == "ROUTINE"

    def test_escalation(self):
        """Current severity exceeds max prior → ESCALATION."""
        priors = [
            {"agency": "SEC", "action_type": "FINE", "severity_score": 30},
        ]
        result = assess_regulatory_precedent("SEC", "FINE", prior_actions=priors)
        # FINE has base severity of 70, prior max is 30 → ESCALATION
        assert result == "ESCALATION"


# ── TestRegulatoryImpact ─────────────────────────────────────────────


class TestRegulatoryImpact:
    """Tests for assess_regulatory_impact()."""

    def test_sec_enforcement(self):
        """SEC enforcement action with financial impact."""
        result = assess_regulatory_impact(
            agency="SEC",
            action_type="ENFORCEMENT",
            title="SEC Charges Firm for Crypto Fraud",
            financial_impact=500_000_000,
            prior_actions=None,
        )
        assert isinstance(result, RegulatoryImpact)
        assert result.agency == "SEC"
        assert result.severity_score >= 60
        assert result.precedent_assessment == "NOVEL"
        assert "FINANCIALS" in result.affected_sectors

    def test_epa_rulemaking(self):
        """EPA rulemaking on emissions."""
        result = assess_regulatory_impact(
            agency="EPA",
            action_type="RULEMAKING",
            title="New emission standards for power plants",
            financial_impact=None,
            prior_actions=None,
        )
        assert isinstance(result, RegulatoryImpact)
        assert result.severity_score == 40.0
        assert "ENERGY" in result.affected_sectors


# ── TestSanctionsImpact ──────────────────────────────────────────────


class TestSanctionsImpact:
    """Tests for assess_sanctions_impact()."""

    def test_russia_sanctions(self):
        """Russia with 20 exposed companies across sectors."""
        sanctions = [
            {"program_name": f"SDN-{i}", "severity": "HIGH",
             "date_imposed": f"2022-0{min(i+1, 9):d}-01"}
            for i in range(5)
        ]
        exposures = [
            {"entity_id": f"E{i}", "entity_name": f"Co{i}",
             "sector": "ENERGY" if i < 10 else "FINANCIALS",
             "revenue_exposure_pct": 5.0 + i}
            for i in range(20)
        ]
        result = assess_sanctions_impact("RU", sanctions, exposures)
        assert isinstance(result, SanctionsAssessment)
        assert result.country_code == "RU"
        assert result.program_count == 5
        assert result.total_companies_affected == 20
        assert len(result.most_exposed_sectors) >= 1

    def test_no_exposure(self):
        """No company exposures → zero affected."""
        sanctions = [{"program_name": "SDN-1", "severity": "LOW"}]
        result = assess_sanctions_impact("CN", sanctions, [])
        assert result.total_companies_affected == 0
        assert result.most_exposed_sectors == []


# ── TestPolicyMomentum ───────────────────────────────────────────────


class TestPolicyMomentum:
    """Tests for detect_policy_momentum()."""

    def test_accelerating(self):
        """More bills in second half → ACCELERATING."""
        # 7 bills total: mid=3, first_half=3, second_half=4.
        # 4 > 3*1.3=3.9 → ACCELERATING
        bills = [
            {"topic": "tech regulation", "date_introduced": "2024-01-01"},
            {"topic": "tech regulation", "date_introduced": "2024-03-01"},
            {"topic": "tech regulation", "date_introduced": "2024-05-01"},
            {"topic": "tech regulation", "date_introduced": "2024-08-01"},
            {"topic": "tech regulation", "date_introduced": "2024-09-01"},
            {"topic": "tech regulation", "date_introduced": "2024-10-01"},
            {"topic": "tech regulation", "date_introduced": "2024-11-01"},
        ]
        result = detect_policy_momentum(bills, "tech regulation")
        assert result == "ACCELERATING"

    def test_stable(self):
        """Even distribution → STABLE."""
        bills = [
            {"topic": "trade", "date_introduced": f"2024-{i+1:02d}-01"}
            for i in range(6)
        ]
        result = detect_policy_momentum(bills, "trade")
        assert result == "STABLE"

    def test_decelerating(self):
        """More bills early, fewer later → DECELERATING."""
        # 8 bills total: 7 in first quarter, 1 in last quarter.
        # Midpoint of Jan-Dec range is ~July, so 7 in first half vs 1 in second.
        # second_half (1) < first_half (7) * 0.7 = 4.9 → DECELERATING.
        bills = [
            {"topic": "energy", "date_introduced": "2024-01-01"},
            {"topic": "energy", "date_introduced": "2024-01-10"},
            {"topic": "energy", "date_introduced": "2024-01-20"},
            {"topic": "energy", "date_introduced": "2024-02-01"},
            {"topic": "energy", "date_introduced": "2024-02-15"},
            {"topic": "energy", "date_introduced": "2024-03-01"},
            {"topic": "energy", "date_introduced": "2024-03-15"},
            {"topic": "energy", "date_introduced": "2024-12-15"},
        ]
        result = detect_policy_momentum(bills, "energy")
        assert result == "DECELERATING"


# ── TestRegulatoryPipeline ───────────────────────────────────────────


class TestRegulatoryPipeline:
    """Tests for track_regulatory_pipeline()."""

    def test_multiple_agencies(self):
        """10 actions across 3 agencies → correct grouping."""
        actions = [
            {"agency": "SEC", "action_type": "FINE", "date": "2024-01-01",
             "title": "Fine A"},
            {"agency": "SEC", "action_type": "INVESTIGATION", "date": "2024-02-01",
             "title": "Inv B"},
            {"agency": "SEC", "action_type": "FINE", "date": "2024-03-01",
             "title": "Fine C"},
            {"agency": "SEC", "action_type": "ENFORCEMENT", "date": "2024-04-01",
             "title": "Enf D"},
            {"agency": "FDA", "action_type": "RULEMAKING", "date": "2024-05-01",
             "title": "Rule E"},
            {"agency": "FDA", "action_type": "RULEMAKING", "date": "2024-06-01",
             "title": "Rule F"},
            {"agency": "EPA", "action_type": "INQUIRY", "date": "2024-07-01",
             "title": "Inq G"},
            {"agency": "EPA", "action_type": "ENFORCEMENT", "date": "2024-08-01",
             "title": "Enf H"},
            {"agency": "EPA", "action_type": "FINE", "date": "2024-09-01",
             "title": "Fine I"},
            {"agency": "EPA", "action_type": "FINE", "date": "2024-10-01",
             "title": "Fine J"},
        ]
        result = track_regulatory_pipeline(actions)
        assert result["total"] == 10
        assert "SEC" in result["by_agency"]
        assert "FDA" in result["by_agency"]
        assert "EPA" in result["by_agency"]
        assert result["by_agency"]["SEC"]["count"] == 4
        assert result["most_active_agency"] in ("SEC", "EPA")

    def test_empty_pipeline(self):
        """No actions → empty pipeline."""
        result = track_regulatory_pipeline([])
        assert result["total"] == 0
        assert result["most_active_agency"] is None
        assert result["trend"] == "STABLE"


# ── Integration Tests ────────────────────────────────────────────────


class TestIntegration:
    """End-to-end political intelligence pipeline tests."""

    def test_full_landscape_analysis(self):
        """Simulate analyzing multiple bills and regulatory actions."""
        # Assess two bills
        bill1 = assess_bill(
            bill_id="HR-100",
            title="Clean Energy Investment Act",
            bill_type="ENERGY_POLICY",
            sponsor_count=25,
            status="PASSED_HOUSE",
            bipartisan=True,
            summary="Incentives for solar, wind, and grid modernization",
        )
        assert bill1.passage_probability > 40.0
        assert bill1.market_relevance in ("HIGH", "MEDIUM")

        bill2 = assess_bill(
            bill_id="S-200",
            title="Data Privacy Protection Act",
            bill_type="TECH_REGULATION",
            sponsor_count=3,
            status="INTRODUCED",
            bipartisan=False,
            summary="Regulates data collection by social media companies",
        )
        assert bill2.passage_probability < bill1.passage_probability

    def test_regulatory_combined(self):
        """Combine regulatory severity + precedent + impact."""
        severity = classify_regulatory_severity("FINE", 100_000_000)
        assert severity >= 80.0

        precedent = assess_regulatory_precedent(
            "SEC", "FINE",
            prior_actions=[
                {"agency": "SEC", "action_type": "FINE", "severity_score": 50},
            ],
        )
        assert precedent == "ESCALATION"

        impact = assess_regulatory_impact(
            agency="SEC",
            action_type="FINE",
            title="SEC fines bank for crypto violations",
            financial_impact=100_000_000,
            prior_actions=[
                {"agency": "SEC", "action_type": "FINE", "severity_score": 50},
            ],
        )
        assert impact.severity_score >= 80.0
        assert impact.precedent_assessment == "ESCALATION"

    def test_sanctions_with_momentum(self):
        """Combine sanctions assessment with policy momentum."""
        sanctions = [
            {"program_name": "SDN-1", "severity": "HIGH",
             "date_imposed": "2022-03-01"},
            {"program_name": "SDN-2", "severity": "HIGH",
             "date_imposed": "2023-06-01"},
            {"program_name": "SDN-3", "severity": "HIGH",
             "date_imposed": "2024-01-01"},
        ]
        exposures = [
            {"entity_id": "E1", "entity_name": "OilCo",
             "sector": "ENERGY", "revenue_exposure_pct": 15.0},
            {"entity_id": "E2", "entity_name": "BankA",
             "sector": "FINANCIALS", "revenue_exposure_pct": 8.0},
        ]
        sa = assess_sanctions_impact("RU", sanctions, exposures)
        assert sa.total_companies_affected == 2
        assert sa.program_count == 3

        # Policy momentum
        bills = [
            {"topic": "sanctions", "date_introduced": "2022-03-15"},
            {"topic": "sanctions", "date_introduced": "2023-07-01"},
            {"topic": "sanctions", "date_introduced": "2024-01-15"},
            {"topic": "sanctions", "date_introduced": "2024-06-01"},
            {"topic": "sanctions", "date_introduced": "2024-09-01"},
            {"topic": "sanctions", "date_introduced": "2024-11-01"},
        ]
        momentum = detect_policy_momentum(bills, "sanctions")
        assert momentum in ("ACCELERATING", "STABLE")
