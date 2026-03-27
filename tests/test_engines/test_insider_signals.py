"""Tests for Pillar 3 Phase 1 — Part 5: Insider Trading Signal Engine."""

import pytest

from src.engines.insider_signals import (
    OPEN_MARKET_CODES,
    SENIORITY_WEIGHTS,
    classify_transaction,
    compute_rolling_aggregates,
    compute_signal_strength,
    detect_cluster_buy,
    detect_ceo_purchase,
    detect_unusual_sale,
    screen_by_insider_activity,
)


# ── Helpers: Realistic Transaction Factories ─────────────────────────────


def _make_txn(
    person: str = "John Smith",
    cik: str = "0001234567",
    relationship: str = "CEO",
    transaction_code: str = "P",
    transaction_date: str = "2025-06-15",
    shares: float = 10_000,
    price_per_share: float = 50.0,
    total_value: float | None = None,
    is_10b5_1: bool = False,
) -> dict:
    """Build a realistic insider transaction dict."""
    if total_value is None:
        total_value = abs(shares) * price_per_share
    return {
        "person": person,
        "cik": cik,
        "relationship": relationship,
        "transaction_code": transaction_code,
        "transaction_date": transaction_date,
        "shares": shares,
        "price_per_share": price_per_share,
        "total_value": total_value,
        "is_10b5_1": is_10b5_1,
    }


# ── classify_transaction Tests ───────────────────────────────────────────


class TestClassifyTransaction:
    """Tests for classify_transaction()."""

    def test_classify_transaction_ceo_purchase(self):
        """CEO open-market purchase gets weight 1.0 and is_open_market True."""
        txn = _make_txn(relationship="CEO", transaction_code="P")
        result = classify_transaction(txn)
        assert result["signal_weight"] == 1.0
        assert result["is_open_market"] is True

    def test_classify_transaction_director_option(self):
        """Director option exercise (code M) gets weight 0.6, is_open_market False."""
        txn = _make_txn(
            person="Jane Doe",
            relationship="Director",
            transaction_code="M",  # Option exercise
            shares=5_000,
        )
        result = classify_transaction(txn)
        assert result["signal_weight"] == 0.6
        assert result["is_open_market"] is False

    def test_classify_cfo_sale(self):
        """CFO sale (code S) is open-market with weight 0.9."""
        txn = _make_txn(relationship="CFO", transaction_code="S", shares=-20_000)
        result = classify_transaction(txn)
        assert result["signal_weight"] == 0.9
        assert result["is_open_market"] is True

    def test_classify_unknown_relationship(self):
        """Unknown relationship defaults to weight 0.2."""
        txn = _make_txn(relationship="Consultant", transaction_code="P")
        result = classify_transaction(txn)
        assert result["signal_weight"] == 0.2

    def test_classify_preserves_original_fields(self):
        """Classification adds fields but keeps originals."""
        txn = _make_txn(person="Alice", relationship="CTO", transaction_code="P")
        result = classify_transaction(txn)
        assert result["person"] == "Alice"
        assert result["relationship"] == "CTO"
        assert result["transaction_code"] == "P"

    def test_classify_10pct_owner(self):
        """10% Owner gets weight 0.5."""
        txn = _make_txn(relationship="10%_Owner", transaction_code="P")
        result = classify_transaction(txn)
        assert result["signal_weight"] == 0.5


# ── detect_cluster_buy Tests ─────────────────────────────────────────────


class TestDetectClusterBuy:
    """Tests for detect_cluster_buy()."""

    def test_detect_cluster_buy_triggered(self):
        """4 distinct insiders buying within 20 days triggers a cluster signal."""
        transactions = [
            _make_txn(person="CEO Alice", relationship="CEO", transaction_code="P",
                      transaction_date="2025-06-01", total_value=500_000),
            _make_txn(person="CFO Bob", relationship="CFO", transaction_code="P",
                      transaction_date="2025-06-05", total_value=300_000),
            _make_txn(person="Dir Carol", relationship="Director", transaction_code="P",
                      transaction_date="2025-06-10", total_value=200_000),
            _make_txn(person="VP Dave", relationship="VP", transaction_code="P",
                      transaction_date="2025-06-20", total_value=150_000),
        ]
        result = detect_cluster_buy(transactions)
        assert result is not None
        assert result["signal_type"] == "CLUSTER_BUY"
        assert len(result["insiders"]) == 4
        assert result["total_value"] == 1_150_000
        assert result["window_start"] == "2025-06-01"
        assert result["window_end"] == "2025-06-20"

    def test_detect_cluster_buy_not_triggered(self):
        """Only 2 insiders buying does not trigger a cluster (min 3)."""
        transactions = [
            _make_txn(person="CEO Alice", relationship="CEO", transaction_code="P",
                      transaction_date="2025-06-01"),
            _make_txn(person="CFO Bob", relationship="CFO", transaction_code="P",
                      transaction_date="2025-06-05"),
        ]
        result = detect_cluster_buy(transactions)
        assert result is None

    def test_detect_cluster_buy_outside_window(self):
        """3 insiders but spread over >30 days does not trigger."""
        transactions = [
            _make_txn(person="CEO Alice", transaction_code="P",
                      transaction_date="2025-01-01"),
            _make_txn(person="CFO Bob", transaction_code="P",
                      transaction_date="2025-01-20"),
            _make_txn(person="Dir Carol", transaction_code="P",
                      transaction_date="2025-02-15"),  # 45 days from first
        ]
        result = detect_cluster_buy(transactions)
        assert result is None

    def test_detect_cluster_buy_only_open_market(self):
        """Option exercises (code M) are excluded from cluster detection."""
        transactions = [
            _make_txn(person="CEO Alice", transaction_code="P",
                      transaction_date="2025-06-01"),
            _make_txn(person="CFO Bob", transaction_code="P",
                      transaction_date="2025-06-05"),
            # These two are option exercises, not open market — should be excluded
            _make_txn(person="Dir Carol", transaction_code="M",
                      transaction_date="2025-06-10"),
            _make_txn(person="VP Dave", transaction_code="M",
                      transaction_date="2025-06-12"),
        ]
        result = detect_cluster_buy(transactions)
        assert result is None  # Only 2 open-market buyers

    def test_detect_cluster_buy_sales_excluded(self):
        """Open-market sales (code S) don't count toward cluster buy."""
        transactions = [
            _make_txn(person="CEO Alice", transaction_code="P",
                      transaction_date="2025-06-01"),
            _make_txn(person="CFO Bob", transaction_code="P",
                      transaction_date="2025-06-05"),
            _make_txn(person="Dir Carol", transaction_code="S",
                      transaction_date="2025-06-10"),
        ]
        result = detect_cluster_buy(transactions)
        assert result is None  # Only 2 purchases

    def test_detect_cluster_buy_duplicate_person(self):
        """Same person buying twice counts as 1 insider, not 2."""
        transactions = [
            _make_txn(person="CEO Alice", transaction_code="P",
                      transaction_date="2025-06-01"),
            _make_txn(person="CEO Alice", transaction_code="P",
                      transaction_date="2025-06-10"),
            _make_txn(person="CFO Bob", transaction_code="P",
                      transaction_date="2025-06-15"),
        ]
        result = detect_cluster_buy(transactions)
        assert result is None  # Only 2 distinct persons


# ── detect_ceo_purchase Tests ────────────────────────────────────────────


class TestDetectCeoPurchase:
    """Tests for detect_ceo_purchase()."""

    def test_detect_ceo_purchase(self):
        """CEO open-market purchase is flagged."""
        transactions = [
            _make_txn(person="CEO Alice", relationship="CEO", transaction_code="P",
                      transaction_date="2025-07-01", shares=25_000, total_value=1_250_000),
        ]
        signals = detect_ceo_purchase(transactions)
        assert len(signals) == 1
        assert signals[0]["signal_type"] == "CEO_PURCHASE"
        assert signals[0]["relationship"] == "CEO"

    def test_detect_ceo_purchase_option_ignored(self):
        """CEO exercising options (code M) is NOT flagged as a purchase signal."""
        transactions = [
            _make_txn(person="CEO Alice", relationship="CEO", transaction_code="M",
                      shares=50_000),
        ]
        signals = detect_ceo_purchase(transactions)
        assert len(signals) == 0

    def test_detect_cfo_purchase(self):
        """CFO open-market purchase is also flagged."""
        transactions = [
            _make_txn(person="CFO Bob", relationship="CFO", transaction_code="P",
                      shares=10_000, total_value=500_000),
        ]
        signals = detect_ceo_purchase(transactions)
        assert len(signals) == 1
        assert signals[0]["signal_type"] == "CFO_PURCHASE"

    def test_detect_director_purchase_not_flagged(self):
        """Director purchase is NOT flagged by detect_ceo_purchase."""
        transactions = [
            _make_txn(person="Dir Carol", relationship="Director", transaction_code="P"),
        ]
        signals = detect_ceo_purchase(transactions)
        assert len(signals) == 0


# ── detect_unusual_sale Tests ────────────────────────────────────────────


class TestDetectUnusualSale:
    """Tests for detect_unusual_sale()."""

    def test_detect_unusual_sale_flagged(self):
        """Large non-10b5-1 open-market sale is flagged."""
        transactions = [
            _make_txn(
                person="CEO Alice", relationship="CEO", transaction_code="S",
                shares=-100_000, total_value=5_000_000,
                is_10b5_1=False,
            ),
        ]
        result = detect_unusual_sale(transactions)
        assert len(result) == 1
        assert "$5,000,000" in result[0]["reason"]

    def test_detect_unusual_sale_10b5_1_ignored(self):
        """10b5-1 planned sale is NOT flagged even if large."""
        transactions = [
            _make_txn(
                person="CEO Alice", relationship="CEO", transaction_code="S",
                shares=-100_000, total_value=5_000_000,
                is_10b5_1=True,
            ),
        ]
        result = detect_unusual_sale(transactions)
        assert len(result) == 0

    def test_detect_unusual_sale_small_ignored(self):
        """Sale below threshold is NOT flagged."""
        transactions = [
            _make_txn(
                person="VP Dave", relationship="VP", transaction_code="S",
                shares=-5_000, total_value=250_000,
                is_10b5_1=False,
            ),
        ]
        result = detect_unusual_sale(transactions)
        assert len(result) == 0

    def test_detect_unusual_sale_option_exercise_ignored(self):
        """Option exercise (code M) is not an open-market sale."""
        transactions = [
            _make_txn(
                person="CEO Alice", transaction_code="M",
                shares=-50_000, total_value=2_500_000,
                is_10b5_1=False,
            ),
        ]
        result = detect_unusual_sale(transactions)
        assert len(result) == 0


# ── compute_rolling_aggregates Tests ─────────────────────────────────────


class TestRollingAggregates:
    """Tests for compute_rolling_aggregates()."""

    def test_rolling_aggregates_30d(self):
        """3 transactions within 30-day window are aggregated."""
        transactions = [
            _make_txn(person="CEO Alice", shares=10_000, total_value=500_000,
                      transaction_date="2025-06-01", transaction_code="P"),
            _make_txn(person="CFO Bob", shares=5_000, total_value=250_000,
                      transaction_date="2025-06-10", transaction_code="P"),
            _make_txn(person="Dir Carol", shares=-3_000, total_value=-150_000,
                      transaction_date="2025-06-20", transaction_code="S"),
        ]
        # Classify to add is_open_market
        classified = [classify_transaction(t) for t in transactions]
        agg = compute_rolling_aggregates(classified, "2025-06-25")
        assert agg["net_shares_30d"] == 12_000  # 10000 + 5000 - 3000
        assert agg["net_value_30d"] == 600_000  # 500k + 250k - 150k

    def test_rolling_aggregates_90d(self):
        """Transactions within 90 days but outside 30 days counted correctly."""
        transactions = [
            _make_txn(person="CEO Alice", shares=20_000, total_value=1_000_000,
                      transaction_date="2025-04-01", transaction_code="P"),
            _make_txn(person="CFO Bob", shares=5_000, total_value=250_000,
                      transaction_date="2025-06-10", transaction_code="P"),
        ]
        classified = [classify_transaction(t) for t in transactions]
        agg = compute_rolling_aggregates(classified, "2025-06-25")
        # 30d: only Bob's txn (June 10 is within 30d of June 25)
        assert agg["net_shares_30d"] == 5_000
        assert agg["net_value_30d"] == 250_000
        # 90d: both txns (April 1 is ~85 days before June 25)
        assert agg["net_shares_90d"] == 25_000
        assert agg["net_value_90d"] == 1_250_000

    def test_rolling_aggregates_365d(self):
        """Full-year window captures older transactions."""
        transactions = [
            _make_txn(person="CEO Alice", shares=50_000, total_value=2_500_000,
                      transaction_date="2024-09-01", transaction_code="P"),
            _make_txn(person="CFO Bob", shares=5_000, total_value=250_000,
                      transaction_date="2025-06-10", transaction_code="P"),
        ]
        classified = [classify_transaction(t) for t in transactions]
        agg = compute_rolling_aggregates(classified, "2025-06-25")
        # 365d includes both
        assert agg["net_shares_365d"] == 55_000
        assert agg["net_value_365d"] == 2_750_000
        # 90d only includes Bob
        assert agg["net_shares_90d"] == 5_000

    def test_rolling_aggregates_empty(self):
        """No transactions yields all zeros."""
        agg = compute_rolling_aggregates([], "2025-06-25")
        assert agg["net_shares_30d"] == 0
        assert agg["net_value_30d"] == 0
        assert agg["net_shares_90d"] == 0
        assert agg["net_value_90d"] == 0
        assert agg["net_shares_365d"] == 0
        assert agg["net_value_365d"] == 0
        assert agg["open_market_buy_count_90d"] == 0
        assert agg["insider_count_buying_30d"] == 0
        assert agg["insider_count_selling_30d"] == 0

    def test_rolling_aggregates_counts(self):
        """Distinct insider buying/selling counts are correct."""
        transactions = [
            _make_txn(person="CEO Alice", shares=10_000, total_value=500_000,
                      transaction_date="2025-06-15", transaction_code="P"),
            _make_txn(person="CEO Alice", shares=5_000, total_value=250_000,
                      transaction_date="2025-06-18", transaction_code="P"),
            _make_txn(person="CFO Bob", shares=8_000, total_value=400_000,
                      transaction_date="2025-06-20", transaction_code="P"),
            _make_txn(person="Dir Carol", shares=-3_000, total_value=-150_000,
                      transaction_date="2025-06-22", transaction_code="S"),
        ]
        classified = [classify_transaction(t) for t in transactions]
        agg = compute_rolling_aggregates(classified, "2025-06-25")
        # Alice buys twice but counts as 1 distinct buyer
        assert agg["insider_count_buying_30d"] == 2   # Alice + Bob
        assert agg["insider_count_selling_30d"] == 1   # Carol
        assert agg["open_market_buy_count_90d"] == 3   # 3 open-market buy txns

    def test_rolling_aggregates_future_excluded(self):
        """Transactions after as_of_date are excluded."""
        transactions = [
            _make_txn(person="CEO Alice", shares=10_000, total_value=500_000,
                      transaction_date="2025-07-01", transaction_code="P"),  # Future
        ]
        classified = [classify_transaction(t) for t in transactions]
        agg = compute_rolling_aggregates(classified, "2025-06-25")
        assert agg["net_shares_30d"] == 0
        assert agg["net_shares_90d"] == 0
        assert agg["net_shares_365d"] == 0


# ── compute_signal_strength Tests ────────────────────────────────────────


class TestSignalStrength:
    """Tests for compute_signal_strength()."""

    def test_signal_strength_ceo_open_market(self):
        """CEO + open market + large value = high score (~70+)."""
        transactions = [
            classify_transaction(_make_txn(
                person="CEO Alice", relationship="CEO", transaction_code="P",
                shares=50_000, total_value=5_000_000,
            )),
        ]
        agg = compute_rolling_aggregates(transactions, "2025-06-25")
        score = compute_signal_strength(transactions, agg)
        # CEO=30pts, size $5M=20pts, open_market=15pts = 65 pts minimum
        assert score >= 65
        assert score <= 100

    def test_signal_strength_director_10b5_1(self):
        """Director + 10b5-1 plan + small value = low score (~20)."""
        txn = _make_txn(
            person="Dir Carol", relationship="Director", transaction_code="P",
            shares=1_000, total_value=50_000, is_10b5_1=True,
        )
        transactions = [classify_transaction(txn)]
        agg = compute_rolling_aggregates(transactions, "2025-06-25")
        score = compute_signal_strength(transactions, agg)
        # Director=0.6*30=18, size<100k=0, open_market=15, 10b5-1=-20 = ~13
        assert score <= 30

    def test_signal_strength_cluster(self):
        """Cluster buy scenario adds 20 points."""
        txns_raw = [
            _make_txn(person="CEO Alice", relationship="CEO", transaction_code="P",
                      transaction_date="2025-06-01", shares=10_000, total_value=500_000),
            _make_txn(person="CFO Bob", relationship="CFO", transaction_code="P",
                      transaction_date="2025-06-05", shares=5_000, total_value=250_000),
            _make_txn(person="Dir Carol", relationship="Director", transaction_code="P",
                      transaction_date="2025-06-10", shares=3_000, total_value=150_000),
        ]
        transactions = [classify_transaction(t) for t in txns_raw]
        agg = compute_rolling_aggregates(transactions, "2025-06-25")
        # Should have insider_count_buying_30d = 3 -> cluster bonus
        score = compute_signal_strength(transactions, agg)
        # CEO=30, size$500k=10, open_market=15, cluster=20 = 75
        assert score >= 70

    def test_signal_strength_zero(self):
        """Empty transaction list gives 0."""
        score = compute_signal_strength([], {})
        assert score == 0

    def test_signal_strength_caps_at_100(self):
        """Score cannot exceed 100."""
        txns_raw = [
            _make_txn(person=f"Insider_{i}", relationship="CEO", transaction_code="P",
                      transaction_date=f"2025-06-{i+1:02d}",
                      shares=100_000, total_value=15_000_000)
            for i in range(5)
        ]
        transactions = [classify_transaction(t) for t in txns_raw]
        agg = compute_rolling_aggregates(transactions, "2025-06-25")
        score = compute_signal_strength(transactions, agg)
        assert score <= 100

    def test_signal_strength_floor_at_zero(self):
        """Score cannot go below 0 even with heavy discounts."""
        txn = _make_txn(
            person="Other Joe", relationship="Other", transaction_code="P",
            shares=100, total_value=500, is_10b5_1=True,
        )
        transactions = [classify_transaction(txn)]
        agg = compute_rolling_aggregates(transactions, "2025-06-25")
        score = compute_signal_strength(transactions, agg)
        assert score >= 0


# ── screen_by_insider_activity Tests ─────────────────────────────────────


class TestScreenByInsiderActivity:
    """Tests for screen_by_insider_activity()."""

    @pytest.fixture()
    def entity_signals(self) -> list[dict]:
        """Sample entity-level insider signal summaries."""
        return [
            {
                "entity_id": "AAPL",
                "signal_strength": 80,
                "signal_types": ["CLUSTER_BUY", "CEO_PURCHASE"],
                "net_value_90d": 5_000_000,
                "relationships": ["CEO", "CFO", "Director"],
            },
            {
                "entity_id": "MSFT",
                "signal_strength": 45,
                "signal_types": ["CEO_PURCHASE"],
                "net_value_90d": 2_000_000,
                "relationships": ["CEO"],
            },
            {
                "entity_id": "GOOG",
                "signal_strength": 25,
                "signal_types": ["UNUSUAL_SALE"],
                "net_value_90d": -3_000_000,
                "relationships": ["Director", "10%_Owner"],
            },
            {
                "entity_id": "AMZN",
                "signal_strength": 60,
                "signal_types": ["CLUSTER_BUY"],
                "net_value_90d": 8_000_000,
                "relationships": ["VP", "Director", "CFO"],
            },
        ]

    def test_screen_by_strength(self, entity_signals):
        """Filter min_signal_strength=50 returns AAPL and AMZN."""
        result = screen_by_insider_activity(entity_signals, {"min_signal_strength": 50})
        ids = [e["entity_id"] for e in result]
        assert "AAPL" in ids
        assert "AMZN" in ids
        assert "MSFT" not in ids
        assert "GOOG" not in ids

    def test_screen_by_signal_type(self, entity_signals):
        """Filter signal_types CLUSTER_BUY returns AAPL and AMZN."""
        result = screen_by_insider_activity(
            entity_signals, {"signal_types": ["CLUSTER_BUY"]},
        )
        ids = [e["entity_id"] for e in result]
        assert "AAPL" in ids
        assert "AMZN" in ids
        assert "MSFT" not in ids

    def test_screen_by_relationship(self, entity_signals):
        """Filter relationship_filter CEO returns AAPL and MSFT."""
        result = screen_by_insider_activity(
            entity_signals, {"relationship_filter": ["CEO"]},
        )
        ids = [e["entity_id"] for e in result]
        assert "AAPL" in ids
        assert "MSFT" in ids
        assert "GOOG" not in ids

    def test_screen_by_value(self, entity_signals):
        """Filter min_net_value_90d=4_000_000 returns AAPL and AMZN."""
        result = screen_by_insider_activity(
            entity_signals, {"min_net_value_90d": 4_000_000},
        )
        ids = [e["entity_id"] for e in result]
        assert "AAPL" in ids
        assert "AMZN" in ids
        assert "MSFT" not in ids
        assert "GOOG" not in ids

    def test_screen_combined_filters(self, entity_signals):
        """Multiple filters applied together (AND logic)."""
        result = screen_by_insider_activity(entity_signals, {
            "min_signal_strength": 50,
            "signal_types": ["CLUSTER_BUY"],
            "min_net_value_90d": 6_000_000,
        })
        ids = [e["entity_id"] for e in result]
        assert ids == ["AMZN"]

    def test_screen_empty_filters(self, entity_signals):
        """No filters returns all entities."""
        result = screen_by_insider_activity(entity_signals, {})
        assert len(result) == 4

    def test_screen_no_matches(self, entity_signals):
        """Impossible filter returns empty list."""
        result = screen_by_insider_activity(
            entity_signals, {"min_signal_strength": 999},
        )
        assert len(result) == 0
