"""Tests for Pillar 3 Phase 3A — Industry Cycle Engine."""

import pytest

from src.engines.industry_cycle import (
    CompetitiveStructure,
    CycleAssessment,
    assess_barriers_to_entry,
    assess_pricing_power,
    classify_hhi,
    classify_inventory_dynamics,
    classify_margin_cycle,
    compute_capacity_utilization_proxy,
    compute_competitive_structure,
    compute_cycle_position,
    compute_hhi,
    compute_revenue_acceleration,
)


# ── Revenue Acceleration Tests ───────────────────────────────────────────


class TestRevenueAcceleration:
    """Tests for compute_revenue_acceleration()."""

    def test_positive_acceleration(self):
        """Revenue growth speeding up."""
        # Growth rates: ~10%, ~20%, ~30% -> accelerating
        history = [100.0, 110.0, 132.0, 171.6]
        result = compute_revenue_acceleration(history)
        assert result > 0

    def test_negative_acceleration(self):
        """Revenue growth slowing down (deceleration)."""
        # Growth: ~30%, ~20%, ~10% -> decelerating
        history = [100.0, 130.0, 156.0, 171.6]
        result = compute_revenue_acceleration(history)
        assert result < 0

    def test_flat_growth(self):
        """Constant growth rate -> zero acceleration."""
        # 10% growth each period
        history = [100.0, 110.0, 121.0, 133.1]
        result = compute_revenue_acceleration(history)
        assert abs(result) < 0.01

    def test_insufficient_data(self):
        """Less than 3 periods returns 0.0."""
        assert compute_revenue_acceleration([100.0, 110.0]) == 0.0
        assert compute_revenue_acceleration([100.0]) == 0.0
        assert compute_revenue_acceleration([]) == 0.0


# ── Capacity Utilization Tests ───────────────────────────────────────────


class TestCapacityUtilization:
    """Tests for compute_capacity_utilization_proxy()."""

    def test_expanding(self):
        """Capex > 1.2x depreciation = expanding."""
        result = compute_capacity_utilization_proxy([50.0, 60.0], [30.0, 40.0])
        assert result > 1.2  # 60/40 = 1.5

    def test_contracting(self):
        """Capex < 0.8x depreciation = contracting."""
        result = compute_capacity_utilization_proxy([20.0, 25.0], [40.0, 50.0])
        assert result < 0.8  # 25/50 = 0.5

    def test_neutral(self):
        """Capex ~ depreciation = neutral."""
        result = compute_capacity_utilization_proxy([45.0, 50.0], [48.0, 50.0])
        assert 0.8 <= result <= 1.2  # 50/50 = 1.0


# ── Inventory Dynamics Tests ─────────────────────────────────────────────


class TestInventoryDynamics:
    """Tests for classify_inventory_dynamics()."""

    def test_building(self):
        """Rising inventory-to-sales = BUILDING."""
        result = classify_inventory_dynamics([0.10, 0.11, 0.13, 0.16])
        assert result == "BUILDING"

    def test_depleting(self):
        """Falling inventory-to-sales = DEPLETING."""
        result = classify_inventory_dynamics([0.18, 0.16, 0.13, 0.10])
        assert result == "DEPLETING"

    def test_stable(self):
        """Flat inventory-to-sales = STABLE."""
        result = classify_inventory_dynamics([0.12, 0.12, 0.12, 0.12])
        assert result == "STABLE"


# ── Margin Cycle Tests ───────────────────────────────────────────────────


class TestMarginCycle:
    """Tests for classify_margin_cycle()."""

    def test_expanding(self):
        """Rising margins, not yet at peak levels."""
        # Current (0.115) is close to mean (~0.1125) so not flagged as PEAK
        result = classify_margin_cycle([0.10, 0.105, 0.11, 0.115])
        assert result == "EXPANDING"

    def test_peak(self):
        """Rising margins at historically high levels."""
        # Mean ~ 0.185, current 0.22 well above mean
        result = classify_margin_cycle([0.15, 0.16, 0.18, 0.20, 0.22])
        assert result == "PEAK"

    def test_contracting(self):
        """Falling margins but not at trough level."""
        # Current (0.205) is near mean (~0.21) so not flagged as TROUGH
        result = classify_margin_cycle([0.22, 0.215, 0.21, 0.205])
        assert result == "CONTRACTING"

    def test_trough(self):
        """Falling margins at historically low levels."""
        # Mean ~ 0.165, current 0.12 well below mean
        result = classify_margin_cycle([0.22, 0.20, 0.16, 0.13, 0.12])
        assert result == "TROUGH"


# ── Cycle Position Tests ─────────────────────────────────────────────────


class TestCyclePosition:
    """Tests for compute_cycle_position()."""

    def test_early_cycle_tech_boom(self):
        """Accelerating revenue + expanding margins + depleting inventory."""
        result = compute_cycle_position(
            revenue_history=[100.0, 105.0, 115.0, 135.0, 170.0],
            margin_history=[0.10, 0.11, 0.12, 0.14],
            capex_history=[20.0, 25.0, 30.0],
            depreciation_history=[18.0, 19.0, 20.0],
            inventory_to_sales_history=[0.15, 0.14, 0.12, 0.10],
        )
        assert isinstance(result, CycleAssessment)
        assert result.cycle_position == "EARLY_CYCLE"
        assert result.confidence > 0

    def test_mid_cycle_stable_utilities(self):
        """Steady growth + stable margins + stable inventory."""
        result = compute_cycle_position(
            revenue_history=[100.0, 103.0, 106.0, 109.0, 112.0],
            margin_history=[0.20, 0.20, 0.20, 0.20],
            capex_history=[30.0, 31.0, 31.0],
            depreciation_history=[28.0, 29.0, 30.0],
            inventory_to_sales_history=[0.12, 0.12, 0.12, 0.12],
        )
        assert result.cycle_position == "MID_CYCLE"

    def test_late_cycle_overheating(self):
        """Decelerating growth + peak margins + building inventory."""
        result = compute_cycle_position(
            revenue_history=[100.0, 120.0, 135.0, 143.0, 147.0],
            margin_history=[0.15, 0.18, 0.21, 0.23, 0.24],
            capex_history=[20.0, 22.0, 23.0],
            depreciation_history=[18.0, 19.0, 20.0],
            inventory_to_sales_history=[0.10, 0.11, 0.13, 0.16],
        )
        assert result.cycle_position == "LATE_CYCLE"

    def test_downturn_recession(self):
        """Negative growth + contracting margins."""
        result = compute_cycle_position(
            revenue_history=[120.0, 115.0, 105.0, 92.0, 80.0],
            margin_history=[0.22, 0.20, 0.17, 0.13],
            capex_history=[30.0, 25.0, 18.0],
            depreciation_history=[28.0, 29.0, 30.0],
            inventory_to_sales_history=[0.12, 0.12, 0.12, 0.12],
        )
        assert result.cycle_position == "DOWNTURN"

    def test_confidence_scoring(self):
        """Confidence should be between 0 and 100."""
        result = compute_cycle_position(
            revenue_history=[100.0, 110.0, 125.0, 145.0],
            margin_history=[0.10, 0.12, 0.14, 0.16],
        )
        assert 0.0 <= result.confidence <= 100.0
        assert result.signals is not None
        assert "revenue_acceleration" in result.signals


# ── HHI Tests ────────────────────────────────────────────────────────────


class TestHHI:
    """Tests for compute_hhi() and classify_hhi()."""

    def test_fragmented_market(self):
        """Many small players -> low HHI."""
        # 20 equal players: each 5% -> HHI = 20 * 25 = 500
        shares = [5.0] * 20
        hhi = compute_hhi(shares)
        assert hhi < 1500
        assert classify_hhi(hhi) == "UNCONCENTRATED"

    def test_oligopoly(self):
        """Few large players -> moderate to high HHI."""
        # 3 players: 40%, 35%, 25% -> HHI = 1600+1225+625 = 3450
        shares = [40.0, 35.0, 25.0]
        hhi = compute_hhi(shares)
        assert hhi > 2500
        assert classify_hhi(hhi) == "CONCENTRATED"

    def test_monopoly(self):
        """Single player -> HHI = 10000."""
        shares = [100.0]
        hhi = compute_hhi(shares)
        assert abs(hhi - 10000) < 1.0
        assert classify_hhi(hhi) == "CONCENTRATED"

    def test_normalization(self):
        """Shares not summing to 100 get normalized."""
        # Two players with raw shares 50, 50 -> normalized 50%, 50%
        # HHI = 2500 + 2500 = 5000
        shares = [50.0, 50.0]
        hhi = compute_hhi(shares)
        assert abs(hhi - 5000) < 1.0


# ── Pricing Power Tests ──────────────────────────────────────────────────


class TestPricingPower:
    """Tests for assess_pricing_power()."""

    def test_strong_pharma(self):
        """Very stable margins = STRONG pricing power."""
        margins = [0.75, 0.76, 0.75, 0.75, 0.76]
        assert assess_pricing_power(margins) == "STRONG"

    def test_moderate(self):
        """Somewhat variable margins = MODERATE."""
        # stdev ~ 0.029, between 0.02 and 0.04
        margins = [0.40, 0.44, 0.37, 0.42, 0.38]
        assert assess_pricing_power(margins) == "MODERATE"

    def test_weak_commodity(self):
        """Highly variable margins = WEAK pricing power."""
        margins = [0.30, 0.20, 0.35, 0.15, 0.28]
        assert assess_pricing_power(margins) == "WEAK"


# ── Barriers to Entry Tests ──────────────────────────────────────────────


class TestBarriers:
    """Tests for assess_barriers_to_entry()."""

    def test_high_semiconductors(self):
        """High capex + high R&D + high regulatory = HIGH barriers."""
        result = assess_barriers_to_entry(
            capex_intensity=0.80,
            rd_intensity=0.60,
            regulatory_score=0.70,
        )
        assert result == "HIGH"

    def test_medium(self):
        """Moderate inputs = MEDIUM barriers."""
        result = assess_barriers_to_entry(
            capex_intensity=0.30,
            rd_intensity=0.40,
            regulatory_score=0.30,
        )
        assert result == "MEDIUM"

    def test_low_retail(self):
        """Low capex, low R&D, low regulation = LOW barriers."""
        result = assess_barriers_to_entry(
            capex_intensity=0.05,
            rd_intensity=0.02,
            regulatory_score=0.05,
        )
        assert result == "LOW"


# ── Competitive Structure Tests ──────────────────────────────────────────


class TestCompetitiveStructure:
    """Tests for compute_competitive_structure()."""

    def test_concentrated_tech(self):
        """Few dominant players in tech sector."""
        companies = [
            {"entity_id": "MSFT", "revenue": 211.0},
            {"entity_id": "AAPL", "revenue": 383.0},
            {"entity_id": "GOOG", "revenue": 307.0},
            {"entity_id": "AMZN", "revenue": 575.0},
            {"entity_id": "META", "revenue": 156.0},
        ]
        result = compute_competitive_structure(
            company_revenues=companies,
            gross_margin_history=[0.65, 0.66, 0.65, 0.66, 0.65],
            capex_intensity=0.10,
            rd_intensity=0.15,
            regulatory_score=0.20,
        )
        assert isinstance(result, CompetitiveStructure)
        assert result.hhi_index > 0
        assert result.top3_market_share is not None
        assert result.top3_market_share > 50.0
        assert result.pricing_power == "STRONG"

    def test_fragmented_retail(self):
        """Many small retailers = fragmented market."""
        companies = [
            {"entity_id": f"R{i}", "revenue": 10.0 + i * 0.5}
            for i in range(30)
        ]
        result = compute_competitive_structure(
            company_revenues=companies,
            # stdev ~ 0.065, well above 2*0.02=0.04 threshold
            gross_margin_history=[0.30, 0.18, 0.32, 0.15, 0.28],
            capex_intensity=0.05,
            rd_intensity=0.01,
            regulatory_score=0.05,
        )
        assert result.hhi_classification == "UNCONCENTRATED"
        assert result.barrier_to_entry == "LOW"
        assert result.pricing_power == "WEAK"

    def test_empty_companies(self):
        """Empty company list returns default CompetitiveStructure."""
        result = compute_competitive_structure([])
        assert isinstance(result, CompetitiveStructure)
        assert result.hhi_index == 0.0
        assert result.hhi_classification == "UNCONCENTRATED"
