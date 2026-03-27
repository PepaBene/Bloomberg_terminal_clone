"""Tests for Pillar 4 Phase 1 — Corporate Action Processing Engine."""

import pytest

from src.engines.corporate_action_engine import (
    DividendResult,
    MergerResult,
    SpinOffResult,
    SplitResult,
    compute_transaction_cash_impact,
    match_corporate_actions_to_holdings,
    process_cash_dividend,
    process_merger_cash,
    process_merger_mixed,
    process_merger_stock,
    process_reverse_split,
    process_spin_off,
    process_stock_split,
    validate_sell,
)


# ── TestDividend ───────────────────────────────────────────────────────


class TestDividend:
    """Tests for process_cash_dividend."""

    def test_cash_dividend(self):
        """1000 shares, $1.50/share → $1500 cash."""
        result = process_cash_dividend(1000, 1.50)
        assert result.cash_amount == 1500.0
        assert result.is_drip is False
        assert result.drip_shares is None

    def test_drip_enabled(self):
        """DRIP: 1000 shares, $1.50/share at $150/share → 10 shares."""
        result = process_cash_dividend(1000, 1.50, drip_enabled=True, current_price=150.0)
        assert result.is_drip is True
        assert result.cash_amount == 0.0
        assert result.drip_shares == pytest.approx(10.0, abs=0.01)
        assert result.drip_cost_basis == pytest.approx(1500.0, abs=0.01)

    def test_zero_dividend(self):
        """Zero dividend per share → $0."""
        result = process_cash_dividend(500, 0.0)
        assert result.cash_amount == 0.0

    def test_drip_no_price(self):
        """DRIP enabled but no current price → falls back to cash."""
        result = process_cash_dividend(100, 2.0, drip_enabled=True, current_price=None)
        assert result.is_drip is False
        assert result.cash_amount == 200.0


# ── TestStockSplit ─────────────────────────────────────────────────────


class TestStockSplit:
    """Tests for process_stock_split."""

    def test_two_for_one(self):
        """2-for-1 split: 100 shares at $200 → 200 shares at $100."""
        result = process_stock_split(100, 200.0, 2.0)
        assert result.new_shares == 200.0
        assert result.new_cost_per_share == pytest.approx(100.0, abs=0.01)
        assert result.split_ratio == 2.0

    def test_three_for_one(self):
        """3-for-1 split: 300 shares at $150 → 900 shares at $50."""
        result = process_stock_split(300, 150.0, 3.0)
        assert result.new_shares == 900.0
        assert result.new_cost_per_share == pytest.approx(50.0, abs=0.01)

    def test_four_for_three(self):
        """4-for-3 split: 300 shares at $120 → 400 shares at $90."""
        result = process_stock_split(300, 120.0, 4.0 / 3.0)
        assert result.new_shares == pytest.approx(400.0, abs=0.01)
        assert result.new_cost_per_share == pytest.approx(90.0, abs=0.01)


# ── TestReverseSplit ───────────────────────────────────────────────────


class TestReverseSplit:
    """Tests for process_reverse_split."""

    def test_one_for_ten(self):
        """1-for-10 reverse: 1000 shares at $5 → 100 shares at $50."""
        result = process_reverse_split(1000, 5.0, 10)
        assert result.new_shares == pytest.approx(100.0, abs=0.01)
        assert result.new_cost_per_share == pytest.approx(50.0, abs=0.01)
        assert result.split_ratio == pytest.approx(0.1, abs=0.01)

    def test_one_for_four(self):
        """1-for-4 reverse: 400 shares at $8 → 100 shares at $32."""
        result = process_reverse_split(400, 8.0, 4)
        assert result.new_shares == pytest.approx(100.0, abs=0.01)
        assert result.new_cost_per_share == pytest.approx(32.0, abs=0.01)


# ── TestSpinOff ────────────────────────────────────────────────────────


class TestSpinOff:
    """Tests for process_spin_off."""

    def test_eighty_twenty_allocation(self):
        """80/20 allocation: $10000 total → parent $8000, child $2000."""
        result = process_spin_off(100, 10000.0, 20.0, "CHILD")
        assert result.parent_new_cost == pytest.approx(8000.0, abs=0.01)
        assert result.child_cost_basis == pytest.approx(2000.0, abs=0.01)
        assert result.child_shares == 100.0
        assert result.child_ticker == "CHILD"

    def test_fifty_fifty_allocation(self):
        """50/50 allocation."""
        result = process_spin_off(200, 20000.0, 50.0, "SPINCO")
        assert result.parent_new_cost == pytest.approx(10000.0, abs=0.01)
        assert result.child_cost_basis == pytest.approx(10000.0, abs=0.01)
        assert result.child_shares == 200.0

    def test_two_child_shares_per_parent(self):
        """2 child shares per parent share."""
        result = process_spin_off(100, 10000.0, 30.0, "NEWCO", shares_per_parent=2.0)
        assert result.child_shares == 200.0
        assert result.child_cost_basis == pytest.approx(3000.0, abs=0.01)
        assert result.parent_new_cost == pytest.approx(7000.0, abs=0.01)


# ── TestMergerCash ─────────────────────────────────────────────────────


class TestMergerCash:
    """Tests for process_merger_cash."""

    def test_cash_merger(self):
        """500 shares at $50/share → $25000 cash."""
        result = process_merger_cash(500, 50.0)
        assert result.result_type == "CASH"
        assert result.cash_received == 25000.0
        assert result.close_parent is True
        assert result.new_ticker is None

    def test_cash_merger_small(self):
        """10 shares at $100/share → $1000."""
        result = process_merger_cash(10, 100.0)
        assert result.cash_received == 1000.0


# ── TestMergerStock ────────────────────────────────────────────────────


class TestMergerStock:
    """Tests for process_merger_stock."""

    def test_stock_merger(self):
        """1000 shares at 0.5 exchange ratio → 500 new shares."""
        result = process_merger_stock(1000, 0.5, "ACQR")
        assert result.result_type == "STOCK"
        assert result.new_shares == pytest.approx(500.0, abs=0.01)
        assert result.new_ticker == "ACQR"
        assert result.cash_received == 0.0

    def test_stock_merger_fractional(self):
        """Fractional exchange ratio."""
        result = process_merger_stock(333, 0.75, "BUYER")
        assert result.new_shares == pytest.approx(249.75, abs=0.01)


# ── TestMergerMixed ────────────────────────────────────────────────────


class TestMergerMixed:
    """Tests for process_merger_mixed."""

    def test_mixed_merger(self):
        """1000 shares: $20 cash + 0.3 stock."""
        result = process_merger_mixed(1000, 20.0, 0.3, "MEGA")
        assert result.result_type == "MIXED"
        assert result.cash_received == 20000.0
        assert result.new_shares == pytest.approx(300.0, abs=0.01)
        assert result.new_ticker == "MEGA"

    def test_mixed_merger_small(self):
        """50 shares: $10 cash + 0.5 stock."""
        result = process_merger_mixed(50, 10.0, 0.5, "BIG")
        assert result.cash_received == 500.0
        assert result.new_shares == pytest.approx(25.0, abs=0.01)


# ── TestValidateSell ──────────────────────────────────────────────────


class TestValidateSell:
    """Tests for validate_sell."""

    def test_valid_sell(self):
        """Sell 50 of 200 shares → OK."""
        ok, msg = validate_sell(200, 50)
        assert ok is True
        assert msg == "OK"

    def test_oversell(self):
        """Sell 500 of 200 shares → fail."""
        ok, msg = validate_sell(200, 500)
        assert ok is False
        assert "Cannot sell" in msg

    def test_exact_sell(self):
        """Sell all shares → OK."""
        ok, msg = validate_sell(100, 100)
        assert ok is True

    def test_sell_zero(self):
        """Sell 0 shares → fail."""
        ok, msg = validate_sell(100, 0)
        assert ok is False
        assert "positive" in msg.lower()


# ── TestCashImpact ────────────────────────────────────────────────────


class TestCashImpact:
    """Tests for compute_transaction_cash_impact."""

    def test_buy(self):
        """BUY 100 shares at $50 → -$5000."""
        impact = compute_transaction_cash_impact("BUY", 100, 50.0)
        assert impact == -5000.0

    def test_sell(self):
        """SELL 100 shares at $60 → +$6000."""
        impact = compute_transaction_cash_impact("SELL", 100, 60.0)
        assert impact == 6000.0

    def test_dividend(self):
        """DIVIDEND 500 shares at $1.50 → +$750."""
        impact = compute_transaction_cash_impact("DIVIDEND", 500, 1.50)
        assert impact == 750.0

    def test_cash_deposit(self):
        """CASH_DEPOSIT $10000 → +$10000."""
        impact = compute_transaction_cash_impact("CASH_DEPOSIT", 10000, 1.0)
        assert impact == 10000.0

    def test_cash_withdrawal(self):
        """CASH_WITHDRAWAL $5000 → -$5000."""
        impact = compute_transaction_cash_impact("CASH_WITHDRAWAL", 5000, 1.0)
        assert impact == -5000.0

    def test_buy_with_commission(self):
        """BUY with $9.99 commission."""
        impact = compute_transaction_cash_impact("BUY", 100, 50.0, commission=9.99)
        assert impact == pytest.approx(-5009.99, abs=0.01)


# ── TestMatchActions ──────────────────────────────────────────────────


class TestMatchActions:
    """Tests for match_corporate_actions_to_holdings."""

    def test_three_actions_two_holdings(self):
        """3 actions, 2 holdings → 2 matches."""
        actions = [
            {"ticker": "AAPL", "action_type": "DIVIDEND"},
            {"ticker": "MSFT", "action_type": "SPLIT"},
            {"ticker": "GOOG", "action_type": "DIVIDEND"},
        ]
        holdings = [
            {"ticker": "AAPL", "shares": 100},
            {"ticker": "GOOG", "shares": 50},
        ]
        matches = match_corporate_actions_to_holdings(actions, holdings)
        assert len(matches) == 2
        matched_tickers = [m["action"]["ticker"] for m in matches]
        assert "AAPL" in matched_tickers
        assert "GOOG" in matched_tickers

    def test_no_matches(self):
        """No overlapping tickers."""
        actions = [{"ticker": "XYZ", "action_type": "SPLIT"}]
        holdings = [{"ticker": "ABC", "shares": 100}]
        matches = match_corporate_actions_to_holdings(actions, holdings)
        assert len(matches) == 0

    def test_partial_match(self):
        """Only some tickers overlap."""
        actions = [
            {"ticker": "AAPL", "action_type": "DIVIDEND"},
            {"ticker": "TSLA", "action_type": "SPLIT"},
        ]
        holdings = [
            {"ticker": "AAPL", "shares": 100},
            {"ticker": "MSFT", "shares": 200},
        ]
        matches = match_corporate_actions_to_holdings(actions, holdings)
        assert len(matches) == 1
        assert matches[0]["action"]["ticker"] == "AAPL"


# ── TestIntegration ───────────────────────────────────────────────────


class TestIntegration:
    """Integration: full lifecycle buy → dividend → split → sell."""

    def test_full_lifecycle(self):
        """Buy 100 shares, receive dividend, 2-for-1 split, sell half."""
        # 1. Buy 100 shares at $100
        shares = 100.0
        cost_per_share = 100.0
        cash = 100_000.0

        buy_impact = compute_transaction_cash_impact("BUY", shares, cost_per_share)
        cash += buy_impact
        assert cash == 90_000.0

        # 2. Receive $2/share dividend
        div_result = process_cash_dividend(shares, 2.0)
        cash += div_result.cash_amount
        assert cash == 90_200.0

        # 3. 2-for-1 split
        split_result = process_stock_split(shares, cost_per_share, 2.0)
        shares = split_result.new_shares
        cost_per_share = split_result.new_cost_per_share
        assert shares == 200.0
        assert cost_per_share == pytest.approx(50.0, abs=0.01)

        # 4. Sell half at $60/share
        ok, msg = validate_sell(shares, 100)
        assert ok is True
        sell_impact = compute_transaction_cash_impact("SELL", 100, 60.0)
        cash += sell_impact
        shares -= 100
        assert shares == 100.0
        assert cash == pytest.approx(96_200.0, abs=0.01)

    def test_drip_then_split(self):
        """DRIP dividend then stock split."""
        shares = 500.0
        cost_per_share = 80.0

        # DRIP: $1/share at $100/share → 5 new shares
        div = process_cash_dividend(shares, 1.0, drip_enabled=True, current_price=100.0)
        shares += div.drip_shares  # 505
        assert shares == pytest.approx(505.0, abs=0.01)

        # 3-for-1 split
        split = process_stock_split(shares, cost_per_share, 3.0)
        assert split.new_shares == pytest.approx(1515.0, abs=0.01)

    def test_merger_closes_position(self):
        """Cash merger closes the position."""
        shares = 200.0
        result = process_merger_cash(shares, 75.0)
        assert result.close_parent is True
        assert result.cash_received == 15000.0

    def test_spinoff_preserves_total_cost(self):
        """Spin-off: parent + child cost = original total cost."""
        total_cost = 50000.0
        result = process_spin_off(500, total_cost, 25.0, "NEWCO")
        assert result.parent_new_cost + result.child_cost_basis == pytest.approx(
            total_cost, abs=0.01,
        )
