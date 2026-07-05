"""Pillar 3 Phase 1 — Part 5: Insider Trading Signal Engine.

Pure computation engine for insider trading signal analysis.
Detects cluster buys, CEO purchases, unusual sales, and computes
rolling aggregates and composite signal strength scores.

No database access — all functions accept and return plain data.
"""

from __future__ import annotations

from datetime import date, timedelta


# ── Constants ────────────────────────────────────────────────────────────

SENIORITY_WEIGHTS: dict[str, float] = {
    "CEO": 1.0,
    "CFO": 0.9,
    "COO": 0.8,
    "CTO": 0.7,
    "Director": 0.6,
    "10%_Owner": 0.5,
    "VP": 0.4,
    "Other_Officer": 0.3,
    "Other": 0.2,
}

OPEN_MARKET_CODES: set[str] = {"P", "S"}  # Purchase, Sale


# ── Transaction Classification ───────────────────────────────────────────


def classify_transaction(transaction: dict) -> dict:
    """Annotate a transaction with signal metadata.

    Adds:
      - signal_weight: float from SENIORITY_WEIGHTS based on relationship
      - is_open_market: bool based on transaction_code being in OPEN_MARKET_CODES

    Parameters
    ----------
    transaction : dict
        Must contain at least ``relationship`` (str) and ``transaction_code`` (str).

    Returns
    -------
    dict
        A copy of the transaction with ``signal_weight`` and ``is_open_market`` added.
    """
    result = dict(transaction)
    relationship = transaction.get("relationship", "Other")
    result["signal_weight"] = SENIORITY_WEIGHTS.get(relationship, 0.2)
    result["is_open_market"] = transaction.get("transaction_code", "") in OPEN_MARKET_CODES
    return result


# ── Signal Detection ─────────────────────────────────────────────────────


def detect_cluster_buy(
    transactions: list[dict],
    window_days: int = 30,
    min_insiders: int = 3,
) -> dict | None:
    """Detect cluster buying: 3+ distinct insiders purchasing open-market within a window.

    Parameters
    ----------
    transactions : list[dict]
        Each must have: transaction_date (str YYYY-MM-DD), transaction_code,
        person, total_value.  ``is_open_market`` is computed if missing.
    window_days : int
        Maximum span in days for a cluster.
    min_insiders : int
        Minimum distinct insiders required.

    Returns
    -------
    dict | None
        Signal dict with signal_type, insiders, total_value, window_start,
        window_end — or ``None`` if no cluster detected.
    """
    # Filter to open-market purchases with parseable dates only. Form 4
    # feeds occasionally arrive with formats other than ISO 8601 (e.g.
    # "20240115" or "01/15/2024"); silently dropping those rows is safer
    # than crashing the whole signal extraction.
    def _parse_txn_date(raw) -> date | None:
        if isinstance(raw, date):
            return raw
        if not raw:
            return None
        try:
            return date.fromisoformat(str(raw))
        except (ValueError, TypeError):
            pass
        for fmt in ("%Y%m%d", "%m/%d/%Y", "%d-%m-%Y"):
            try:
                from datetime import datetime as _dt
                return _dt.strptime(str(raw), fmt).date()
            except (ValueError, TypeError):
                continue
        return None

    buys: list[dict] = []
    for txn in transactions:
        is_open = txn.get("is_open_market")
        if is_open is None:
            is_open = txn.get("transaction_code", "") in OPEN_MARKET_CODES
        code = txn.get("transaction_code", "")
        if not (is_open and code == "P"):
            continue
        parsed = _parse_txn_date(txn.get("transaction_date"))
        if parsed is None:
            continue
        # Cache the parsed date so we don't re-parse below.
        buys.append({**txn, "_parsed_date": parsed})

    if len(buys) < min_insiders:
        return None

    # Sort by parsed date
    buys.sort(key=lambda t: t["_parsed_date"])

    # Sliding window: find a window of <= window_days with >= min_insiders distinct persons
    best_cluster: dict | None = None
    for i in range(len(buys)):
        start_date = buys[i]["_parsed_date"]
        window_txns: list[dict] = []
        persons: set[str] = set()
        for j in range(i, len(buys)):
            txn_date = buys[j]["_parsed_date"]
            if (txn_date - start_date).days <= window_days:
                window_txns.append(buys[j])
                persons.add(buys[j].get("person", buys[j].get("insider_name", "")))
            else:
                break

        if len(persons) >= min_insiders:
            total_value = sum(abs(t.get("total_value", 0)) for t in window_txns)
            end_date = window_txns[-1]["_parsed_date"]
            cluster = {
                "signal_type": "CLUSTER_BUY",
                "insiders": sorted(persons),
                "total_value": total_value,
                "window_start": start_date.isoformat(),
                "window_end": end_date.isoformat(),
            }
            # Keep the cluster with the most insiders (or first found)
            if best_cluster is None or len(persons) > len(best_cluster["insiders"]):
                best_cluster = cluster

    return best_cluster


def detect_ceo_purchase(transactions: list[dict]) -> list[dict]:
    """Find open-market purchases by CEO or CFO.

    Parameters
    ----------
    transactions : list[dict]
        Each must have: relationship, transaction_code.
        ``is_open_market`` is computed if missing.

    Returns
    -------
    list[dict]
        List of signal dicts: {signal_type, transaction, relationship}.
    """
    signals: list[dict] = []
    for txn in transactions:
        relationship = txn.get("relationship", "")
        if relationship not in ("CEO", "CFO"):
            continue
        is_open = txn.get("is_open_market")
        if is_open is None:
            is_open = txn.get("transaction_code", "") in OPEN_MARKET_CODES
        code = txn.get("transaction_code", "")
        if is_open and code == "P":
            signals.append({
                "signal_type": "CEO_PURCHASE" if relationship == "CEO" else "CFO_PURCHASE",
                "transaction": txn,
                "relationship": relationship,
            })
    return signals


def detect_unusual_sale(
    transactions: list[dict],
    min_value: float = 1_000_000,
) -> list[dict]:
    """Detect large open-market sales NOT under a 10b5-1 plan.

    Parameters
    ----------
    transactions : list[dict]
        Each must have: transaction_code, total_value.
        Optional: is_10b5_1 (bool), is_open_market (bool).
    min_value : float
        Minimum total_value to flag.

    Returns
    -------
    list[dict]
        List of {transaction, reason} dicts for flagged sales.
    """
    flagged: list[dict] = []
    for txn in transactions:
        is_open = txn.get("is_open_market")
        if is_open is None:
            is_open = txn.get("transaction_code", "") in OPEN_MARKET_CODES
        code = txn.get("transaction_code", "")
        if not (is_open and code == "S"):
            continue
        if txn.get("is_10b5_1", False):
            continue
        value = abs(txn.get("total_value", 0))
        if value > min_value:
            flagged.append({
                "transaction": txn,
                "reason": f"Large open-market sale of ${value:,.0f} outside 10b5-1 plan",
            })
    return flagged


# ── Rolling Aggregates ───────────────────────────────────────────────────


def compute_rolling_aggregates(
    transactions: list[dict],
    as_of_date_str: str,
) -> dict:
    """Compute rolling net buying/selling over 30/90/365 day windows.

    Each transaction must have:
      - transaction_date: str (YYYY-MM-DD)
      - shares: int/float (positive = buy, negative = sell)
      - total_value: float
      - is_open_market: bool

    Optionally:
      - person or insider_name: str (for distinct insider counting)

    Parameters
    ----------
    transactions : list[dict]
        Transaction records.
    as_of_date_str : str
        Reference date (YYYY-MM-DD).

    Returns
    -------
    dict
        Rolling aggregates with keys: net_shares_30d, net_value_30d,
        net_shares_90d, net_value_90d, net_shares_365d, net_value_365d,
        open_market_buy_count_90d, insider_count_buying_30d,
        insider_count_selling_30d.
    """
    as_of = date.fromisoformat(as_of_date_str)

    windows = {
        "30d": timedelta(days=30),
        "90d": timedelta(days=90),
        "365d": timedelta(days=365),
    }

    net_shares: dict[str, float] = {"30d": 0.0, "90d": 0.0, "365d": 0.0}
    net_value: dict[str, float] = {"30d": 0.0, "90d": 0.0, "365d": 0.0}
    open_market_buy_count_90d = 0
    buyers_30d: set[str] = set()
    sellers_30d: set[str] = set()

    for txn in transactions:
        try:
            txn_date = date.fromisoformat(txn["transaction_date"])
        except (ValueError, KeyError):
            continue  # Skip entries with malformed or missing dates
        shares = txn.get("shares", 0)
        value = txn.get("total_value", 0)
        is_open = txn.get("is_open_market", False)
        person = txn.get("person", txn.get("insider_name", "unknown"))

        for label, delta in windows.items():
            if (as_of - txn_date).days <= delta.days and txn_date <= as_of:
                net_shares[label] += shares
                net_value[label] += value

        # 90-day open market buy count
        if (as_of - txn_date).days <= 90 and txn_date <= as_of:
            if is_open and shares > 0:
                open_market_buy_count_90d += 1

        # 30-day buyer/seller counts by distinct person
        if (as_of - txn_date).days <= 30 and txn_date <= as_of:
            if shares > 0:
                buyers_30d.add(person)
            elif shares < 0:
                sellers_30d.add(person)

    return {
        "net_shares_30d": net_shares["30d"],
        "net_value_30d": net_value["30d"],
        "net_shares_90d": net_shares["90d"],
        "net_value_90d": net_value["90d"],
        "net_shares_365d": net_shares["365d"],
        "net_value_365d": net_value["365d"],
        "open_market_buy_count_90d": open_market_buy_count_90d,
        "insider_count_buying_30d": len(buyers_30d),
        "insider_count_selling_30d": len(sellers_30d),
    }


# ── Signal Strength ──────────────────────────────────────────────────────


def compute_signal_strength(
    transactions: list[dict],
    aggregates: dict,
) -> int:
    """Compute composite insider signal strength score (0-100).

    Components:
      - Buyer seniority: max 30 pts (highest signal_weight among buyers)
      - Transaction size: max 25 pts (based on largest absolute total_value)
      - Open-market flag: +15 pts (if any open-market purchase)
      - Cluster factor: +20 pts (if 3+ distinct insiders buying)
      - 10b5-1 discount: -20 pts (if any transaction is 10b5-1 planned)

    Parameters
    ----------
    transactions : list[dict]
        Classified transactions (with signal_weight, is_open_market).
    aggregates : dict
        Output from compute_rolling_aggregates.

    Returns
    -------
    int
        Score from 0 to 100.
    """
    if not transactions:
        return 0

    score = 0.0

    # 1. Buyer seniority: max 30 pts
    buy_weights = [
        t.get("signal_weight", 0.2)
        for t in transactions
        if t.get("shares", 0) > 0
    ]
    if buy_weights:
        score += max(buy_weights) * 30  # e.g. CEO = 1.0 * 30 = 30

    # 2. Transaction size: max 25 pts
    max_value = max(abs(t.get("total_value", 0)) for t in transactions)
    if max_value >= 10_000_000:
        score += 25
    elif max_value >= 5_000_000:
        score += 20
    elif max_value >= 1_000_000:
        score += 15
    elif max_value >= 500_000:
        score += 10
    elif max_value >= 100_000:
        score += 5

    # 3. Open-market flag: +15 pts if any open-market purchase
    has_open_market_buy = any(
        t.get("is_open_market", False) and t.get("shares", 0) > 0
        for t in transactions
    )
    if has_open_market_buy:
        score += 15

    # 4. Cluster factor: +20 pts if 3+ distinct insiders buying in 30d
    insider_count = aggregates.get("insider_count_buying_30d", 0)
    if insider_count >= 3:
        score += 20

    # 5. 10b5-1 discount: -20 pts if any transaction is 10b5-1 planned
    has_10b5_1 = any(t.get("is_10b5_1", False) for t in transactions)
    if has_10b5_1:
        score -= 20

    return max(0, min(100, int(round(score))))


# ── Screening ────────────────────────────────────────────────────────────


def screen_by_insider_activity(
    all_entity_signals: list[dict],
    filters: dict,
) -> list[dict]:
    """Filter entities by insider activity criteria.

    Each entity signal dict should have:
      - signal_strength: int
      - signal_types: list[str]  (e.g. ["CLUSTER_BUY", "CEO_PURCHASE"])
      - net_value_90d: float
      - relationships: list[str]  (e.g. ["CEO", "CFO", "Director"])
      - (plus any other entity-level data)

    Parameters
    ----------
    all_entity_signals : list[dict]
        List of entity-level insider signal summaries.
    filters : dict
        Filter criteria. Supported keys:
        - min_signal_strength: int
        - signal_types: list[str] — entity must have at least one matching
        - min_net_value_90d: float
        - relationship_filter: list[str] — entity must have at least one matching

    Returns
    -------
    list[dict]
        Entities that pass all filters.
    """
    results: list[dict] = []

    min_strength = filters.get("min_signal_strength")
    required_types = filters.get("signal_types")
    min_net_value = filters.get("min_net_value_90d")
    rel_filter = filters.get("relationship_filter")

    for entity in all_entity_signals:
        # Signal strength filter
        if min_strength is not None:
            if entity.get("signal_strength", 0) < min_strength:
                continue

        # Signal type filter
        if required_types is not None:
            entity_types = set(entity.get("signal_types", []))
            if not entity_types.intersection(required_types):
                continue

        # Net value 90d filter
        if min_net_value is not None:
            if entity.get("net_value_90d", 0) < min_net_value:
                continue

        # Relationship filter
        if rel_filter is not None:
            entity_rels = set(entity.get("relationships", []))
            if not entity_rels.intersection(rel_filter):
                continue

        results.append(entity)

    return results
