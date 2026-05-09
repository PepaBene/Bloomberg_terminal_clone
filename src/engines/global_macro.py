"""Pillar 3 Phase 3B — Global Macro Engine.

Pure computation engine for global macroeconomic analysis.
Evaluates central bank policy, inflation trends, recession probability,
and global growth rankings.

No database access — all functions accept and return plain data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median


# ── Constants ────────────────────────────────────────────────────────────

CENTRAL_BANKS = {
    "FED": "Federal Reserve",
    "ECB": "European Central Bank",
    "BOJ": "Bank of Japan",
    "BOE": "Bank of England",
    "PBOC": "People's Bank of China",
    "RBA": "Reserve Bank of Australia",
    "BOC": "Bank of Canada",
    "SNB": "Swiss National Bank",
    "RBI": "Reserve Bank of India",
}

STANCE_KEYWORDS = {
    "HAWKISH": ["tighten", "inflation concern", "restrictive", "rate hike"],
    "DOVISH": ["accommodate", "support growth", "rate cut", "easing"],
    "NEUTRAL": ["data-dependent", "monitor", "balanced"],
}

RECESSION_WEIGHTS = {
    "yield_curve": 0.35,
    "pmi": 0.30,
    "credit_spreads": 0.20,
    "unemployment_trend": 0.15,
}


# ── Dataclasses ──────────────────────────────────────────────────────────


@dataclass
class CentralBankSnapshot:
    """Point-in-time snapshot of a central bank's policy."""

    bank_code: str
    bank_name: str
    current_rate: float
    policy_stance: str  # HAWKISH/NEUTRAL/DOVISH
    last_action: str  # HIKE/CUT/HOLD
    last_action_date: str | None
    rate_change_ytd_bps: int


@dataclass
class GlobalRateEnvironment:
    """Aggregate view of global central bank policy direction."""

    hiking_count: int
    cutting_count: int
    holding_count: int
    direction: str  # TIGHTENING/NEUTRAL/EASING
    banks: list[CentralBankSnapshot] = field(default_factory=list)


@dataclass
class InflationComparison:
    """Cross-country inflation comparison."""

    country_data: list[dict]  # [{country, headline, core, trend}]
    global_median_headline: float
    countries_accelerating: int
    countries_decelerating: int
    countries_stable: int


@dataclass
class RecessionIndicator:
    """Recession probability assessment."""

    probability: float  # 0-100
    yield_curve_signal: str  # INVERTED/FLAT/NORMAL
    pmi_signal: str  # CONTRACTION/EXPANSION
    credit_signal: str  # STRESS/NORMAL
    classification: str  # LOW/MODERATE/ELEVATED/HIGH


# ── Policy Stance ────────────────────────────────────────────────────────


def classify_policy_stance(
    rate_changes: list[dict],
    keywords: list[str] | None = None,
) -> str:
    """Classify central bank policy stance.

    Parameters
    ----------
    rate_changes : list[dict]
        Recent rate decisions: [{action: "HIKE"|"CUT"|"HOLD", bps: int}].
    keywords : list[str] | None
        Statement keywords that override action-based classification.

    Returns
    -------
    str
        HAWKISH, DOVISH, or NEUTRAL.
    """
    # Keywords override if provided
    if keywords:
        lower_keywords = [k.lower() for k in keywords]
        for stance, stance_words in STANCE_KEYWORDS.items():
            for sw in stance_words:
                if any(sw in kw for kw in lower_keywords):
                    return stance

    # Action-based classification
    if not rate_changes:
        return "NEUTRAL"

    hikes = sum(1 for rc in rate_changes if rc.get("action") == "HIKE")
    cuts = sum(1 for rc in rate_changes if rc.get("action") == "CUT")

    if hikes > cuts:
        return "HAWKISH"
    if cuts > hikes:
        return "DOVISH"
    return "NEUTRAL"


# ── Global Rate Environment ──────────────────────────────────────────────


def compute_global_rate_environment(
    bank_data: list[dict],
) -> GlobalRateEnvironment:
    """Aggregate central bank data into a global rate environment view.

    Parameters
    ----------
    bank_data : list[dict]
        Each dict: {bank_code, current_rate, last_action,
        last_action_date, rate_change_ytd_bps}.

    Returns
    -------
    GlobalRateEnvironment
    """
    snapshots: list[CentralBankSnapshot] = []
    hiking = 0
    cutting = 0
    holding = 0

    for bd in bank_data:
        code = bd["bank_code"]
        action = bd.get("last_action", "HOLD")
        ytd_bps = int(bd.get("rate_change_ytd_bps", 0))

        # Stance reflects the *current* policy, which is best inferred from
        # the last action (HIKE / CUT / HOLD) rather than the cumulative
        # YTD bps. A bank that hiked +300bps then paused for six months is
        # not "HAWKISH" today — it is on hold. We fall back to YTD only
        # when no last_action is available.
        action_upper = (action or "").upper()
        if action_upper == "HIKE":
            stance = "HAWKISH"
        elif action_upper == "CUT":
            stance = "DOVISH"
        elif action_upper in ("HOLD", "PAUSE", ""):
            if ytd_bps > 50:
                stance = "HAWKISH"
            elif ytd_bps < -50:
                stance = "DOVISH"
            else:
                stance = "NEUTRAL"
        else:
            stance = "NEUTRAL"

        # Count by last action
        if action_upper == "HIKE":
            hiking += 1
        elif action_upper == "CUT":
            cutting += 1
        else:
            holding += 1

        snapshots.append(CentralBankSnapshot(
            bank_code=code,
            bank_name=CENTRAL_BANKS.get(code, code),
            current_rate=float(bd.get("current_rate", 0.0)),
            policy_stance=stance,
            last_action=action,
            last_action_date=bd.get("last_action_date"),
            rate_change_ytd_bps=ytd_bps,
        ))

    # Determine direction
    if hiking > cutting and hiking > holding:
        direction = "TIGHTENING"
    elif cutting > hiking and cutting > holding:
        direction = "EASING"
    else:
        direction = "NEUTRAL"

    return GlobalRateEnvironment(
        hiking_count=hiking,
        cutting_count=cutting,
        holding_count=holding,
        direction=direction,
        banks=snapshots,
    )


# ── Inflation ────────────────────────────────────────────────────────────


def classify_inflation_trend(values: list[float]) -> str:
    """Classify inflation trend from a time series.

    Parameters
    ----------
    values : list[float]
        Monthly inflation readings, oldest first.
        Requires at least 4 values.

    Returns
    -------
    str
        ACCELERATING if latest > prior 3-month avg + 0.3pp,
        DECELERATING if latest < prior 3-month avg - 0.3pp,
        STABLE otherwise.
    """
    if len(values) < 4:
        return "STABLE"

    latest = values[-1]
    prior_avg = sum(values[-4:-1]) / 3.0
    diff = latest - prior_avg

    if diff > 0.3:
        return "ACCELERATING"
    if diff < -0.3:
        return "DECELERATING"
    return "STABLE"


def compute_inflation_comparison(
    country_inflation: list[dict],
) -> InflationComparison:
    """Compare inflation across countries.

    Parameters
    ----------
    country_inflation : list[dict]
        Each dict: {country, headline, core, history: [last 6 months]}.

    Returns
    -------
    InflationComparison
    """
    country_data: list[dict] = []
    headlines: list[float] = []
    accelerating = 0
    decelerating = 0
    stable = 0

    for ci in country_inflation:
        country = ci["country"]
        headline = float(ci["headline"])
        core = float(ci["core"])
        history = ci.get("history", [])
        trend = classify_inflation_trend(history)

        if trend == "ACCELERATING":
            accelerating += 1
        elif trend == "DECELERATING":
            decelerating += 1
        else:
            stable += 1

        headlines.append(headline)
        country_data.append({
            "country": country,
            "headline": headline,
            "core": core,
            "trend": trend,
        })

    global_median = round(median(headlines), 2) if headlines else 0.0

    return InflationComparison(
        country_data=country_data,
        global_median_headline=global_median,
        countries_accelerating=accelerating,
        countries_decelerating=decelerating,
        countries_stable=stable,
    )


# ── Recession Probability ────────────────────────────────────────────────


def compute_recession_probability(
    yield_curve_spread: float,
    pmi: float,
    credit_spreads_bps: float,
    unemployment_change: float | None = None,
) -> RecessionIndicator:
    """Compute recession probability from leading indicators.

    Parameters
    ----------
    yield_curve_spread : float
        10Y-2Y treasury spread in percentage points.
        Negative = inverted.
    pmi : float
        Manufacturing PMI (50 = neutral threshold).
    credit_spreads_bps : float
        High-yield credit spreads in basis points.
    unemployment_change : float | None
        Year-over-year change in unemployment rate (pp).

    Returns
    -------
    RecessionIndicator
    """
    # Yield curve signal
    if yield_curve_spread < -0.5:
        yc_signal = "INVERTED"
        yc_prob = 80.0 + min(20.0, abs(yield_curve_spread) * 10)
    elif yield_curve_spread < 0.0:
        yc_signal = "INVERTED"
        yc_prob = 60.0 + abs(yield_curve_spread) * 40
    elif yield_curve_spread < 0.25:
        yc_signal = "FLAT"
        yc_prob = 40.0
    else:
        yc_signal = "NORMAL"
        yc_prob = max(5.0, 30.0 - yield_curve_spread * 10)

    # PMI signal
    if pmi < 45.0:
        pmi_signal = "CONTRACTION"
        pmi_prob = 80.0 + (45.0 - pmi) * 2
    elif pmi < 50.0:
        pmi_signal = "CONTRACTION"
        pmi_prob = 50.0 + (50.0 - pmi) * 6
    else:
        pmi_signal = "EXPANSION"
        pmi_prob = max(5.0, 40.0 - (pmi - 50.0) * 4)

    # Credit spreads signal
    if credit_spreads_bps > 500:
        credit_signal = "STRESS"
        credit_prob = 80.0 + min(20.0, (credit_spreads_bps - 500) * 0.04)
    elif credit_spreads_bps > 350:
        credit_signal = "STRESS"
        credit_prob = 50.0 + (credit_spreads_bps - 350) * 0.2
    else:
        credit_signal = "NORMAL"
        credit_prob = max(5.0, credit_spreads_bps * 0.1)

    # Unemployment trend
    if unemployment_change is not None:
        if unemployment_change > 1.0:
            unemp_prob = 80.0 + min(20.0, unemployment_change * 10)
        elif unemployment_change > 0.5:
            unemp_prob = 50.0 + (unemployment_change - 0.5) * 60
        elif unemployment_change > 0.0:
            unemp_prob = 20.0 + unemployment_change * 60
        else:
            unemp_prob = max(5.0, 15.0 + unemployment_change * 10)
    else:
        unemp_prob = 30.0  # neutral assumption

    # Weighted probability
    probability = (
        yc_prob * RECESSION_WEIGHTS["yield_curve"]
        + pmi_prob * RECESSION_WEIGHTS["pmi"]
        + credit_prob * RECESSION_WEIGHTS["credit_spreads"]
        + unemp_prob * RECESSION_WEIGHTS["unemployment_trend"]
    )
    probability = round(max(0.0, min(100.0, probability)), 2)

    # Classification
    if probability >= 70:
        classification = "HIGH"
    elif probability >= 50:
        classification = "ELEVATED"
    elif probability >= 30:
        classification = "MODERATE"
    else:
        classification = "LOW"

    return RecessionIndicator(
        probability=probability,
        yield_curve_signal=yc_signal,
        pmi_signal=pmi_signal,
        credit_signal=credit_signal,
        classification=classification,
    )


# ── Growth Ranking ───────────────────────────────────────────────────────


def compute_global_growth_ranking(gdp_data: list[dict]) -> list[dict]:
    """Rank countries by GDP growth.

    Parameters
    ----------
    gdp_data : list[dict]
        Each dict: {country, gdp_growth, forecast, prior}.

    Returns
    -------
    list[dict]
        Sorted by gdp_growth descending, with added rank field.
    """
    sorted_data = sorted(gdp_data, key=lambda d: -d.get("gdp_growth", 0.0))
    result = []
    for i, item in enumerate(sorted_data, start=1):
        entry = dict(item)
        entry["rank"] = i
        result.append(entry)
    return result


# ── Rate Surprise ────────────────────────────────────────────────────────


def detect_rate_surprise(expected_bps: int, actual_bps: int) -> bool:
    """Detect whether a rate decision was a surprise.

    Parameters
    ----------
    expected_bps : int
        Market-expected rate change in basis points.
    actual_bps : int
        Actual rate change in basis points.

    Returns
    -------
    bool
        True if |actual - expected| >= 25bps.
    """
    return abs(actual_bps - expected_bps) >= 25


# ── Rate Differential ────────────────────────────────────────────────────


def compute_rate_differential(bank_a_rate: float, bank_b_rate: float) -> float:
    """Compute rate differential between two central banks.

    Parameters
    ----------
    bank_a_rate : float
        Policy rate of bank A.
    bank_b_rate : float
        Policy rate of bank B.

    Returns
    -------
    float
        bank_a_rate - bank_b_rate. Useful for FX analysis.
    """
    return round(bank_a_rate - bank_b_rate, 4)
