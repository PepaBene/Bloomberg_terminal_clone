"""E4 Pre-built Screens Library.

Twelve ready-to-run screen definitions inspired by classic quantitative
value, quality, and income strategies.  Each entry is a plain dict that
can be passed directly to :pymethod:`ScreeningEngine.run_screen_from_dict`.

Screens are stored in ``PREBUILT_SCREENS`` keyed by a URL-safe slug.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Pre-built screen definitions
# ---------------------------------------------------------------------------

PREBUILT_SCREENS: dict[str, dict] = {

    # ------------------------------------------------------------------
    # Classic Value
    # ------------------------------------------------------------------

    # 1. Graham Net-Net
    "graham-net-net": {
        "name": "Graham Net-Net",
        "description": (
            "Benjamin Graham's net-net strategy: buy stocks trading below "
            "two-thirds of their net current asset value (NCAV).  Uses "
            "ncav_per_share > 0 and P/B < 0.67 as a proxy for Market Cap "
            "< NCAV x 0.67."
        ),
        "filters": {
            "logic": "AND",
            "filters": [
                {"field": "ncav_per_share", "source": "ANALYTICS_RESULT", "op": "GT", "value": 0},
                {"field": "pb", "source": "ANALYTICS_RESULT", "op": "LT", "value": 0.67},
            ],
        },
        "tags": ["value", "graham", "deep_value"],
    },

    # 2. Graham Defensive Investor
    "graham-defensive": {
        "name": "Graham Defensive Investor",
        "description": (
            "Benjamin Graham's criteria for the defensive investor from "
            "'The Intelligent Investor': PE < 15, P/B < 1.5, and current "
            "ratio > 2.  Targets financially sound, reasonably priced companies."
        ),
        "filters": {
            "logic": "AND",
            "filters": [
                {"field": "pe_trailing", "source": "ANALYTICS_RESULT", "op": "LT", "value": 15},
                {"field": "pb", "source": "ANALYTICS_RESULT", "op": "LT", "value": 1.5},
                {"field": "current_ratio", "source": "ANALYTICS_RESULT", "op": "GT", "value": 2},
            ],
        },
        "tags": ["value", "graham", "conservative"],
    },

    # 3. Deep Value
    "deep-value": {
        "name": "Deep Value",
        "description": (
            "Multi-factor deep value screen combining cheap valuation "
            "(EV/EBITDA < 8, PE < 12, FCF yield > 8%) with financial "
            "quality gates (Piotroski F >= 6, not in Altman distress zone)."
        ),
        "filters": {
            "logic": "AND",
            "filters": [
                {"field": "ev_ebitda", "source": "ANALYTICS_RESULT", "op": "LT", "value": 8},
                {"field": "pe_trailing", "source": "ANALYTICS_RESULT", "op": "LT", "value": 12},
                {"field": "fcf_yield", "source": "ANALYTICS_RESULT", "op": "GT", "value": 0.08},
                {"field": "piotroski_f_score", "source": "ANALYTICS_RESULT", "op": "GTE", "value": 6},
                {"field": "altman_zone", "source": "ANALYTICS_RESULT", "op": "NEQ", "value": "DISTRESS"},
            ],
        },
        "tags": ["value", "deep_value"],
    },

    # 4. Magic Formula (Greenblatt)
    "magic-formula": {
        "name": "Magic Formula (Greenblatt)",
        "description": (
            "Joel Greenblatt's Magic Formula: rank the universe by the "
            "combination of highest earnings yield (EBIT/EV) and highest "
            "return on invested capital.  Financials excluded (GICS sector "
            "40).  Equal-weight ranking on both factors."
        ),
        "filters": {
            "logic": "AND",
            "filters": [
                {"field": "gics_sector", "source": "ENTITY", "op": "NOT_IN", "value": ["40"]},
            ],
        },
        "ranking": [
            {"field": "earnings_yield", "weight": 1.0, "ascending": False},
            {"field": "roic", "weight": 1.0, "ascending": False},
        ],
        "tags": ["value", "greenblatt", "quant"],
    },

    # ------------------------------------------------------------------
    # Quality at a Reasonable Price (QARP)
    # ------------------------------------------------------------------

    # 5. Quality Value
    "quality-value": {
        "name": "Quality at a Reasonable Price",
        "description": (
            "QARP screen: high-quality companies (ROIC > 15%, revenue "
            "growing, Piotroski F >= 7) with moderate leverage (Net Debt / "
            "EBITDA < 2) at a reasonable valuation (PE < 20)."
        ),
        "filters": {
            "logic": "AND",
            "filters": [
                {"field": "roic", "source": "ANALYTICS_RESULT", "op": "GT", "value": 0.15},
                {"field": "net_debt_to_ebitda", "source": "ANALYTICS_RESULT", "op": "LT", "value": 2},
                {"field": "pe_trailing", "source": "ANALYTICS_RESULT", "op": "LT", "value": 20},
                {"field": "revenue_3y_cagr", "source": "ANALYTICS_RESULT", "op": "GT", "value": 0.05},
                {"field": "piotroski_f_score", "source": "ANALYTICS_RESULT", "op": "GTE", "value": 7},
            ],
        },
        "tags": ["value", "quality", "QARP"],
    },

    # 6. Wide Moat at a Discount
    "wide-moat-discount": {
        "name": "Wide Moat at a Discount",
        "description": (
            "Companies exhibiting durable competitive advantages (ROIC > "
            "15%, gross margin > 40%, FCF margin > 10%) trading at a "
            "discount to the broad market (PE < 20 as proxy for below "
            "industry median)."
        ),
        "filters": {
            "logic": "AND",
            "filters": [
                {"field": "roic", "source": "ANALYTICS_RESULT", "op": "GT", "value": 0.15},
                {"field": "gross_margin", "source": "ANALYTICS_RESULT", "op": "GT", "value": 0.40},
                {"field": "fcf_margin", "source": "ANALYTICS_RESULT", "op": "GT", "value": 0.10},
                {"field": "pe_trailing", "source": "ANALYTICS_RESULT", "op": "LT", "value": 20},
            ],
        },
        "tags": ["quality", "moat"],
    },

    # 7. Buffett-Style
    "buffett-style": {
        "name": "Buffett-Style Quality Value",
        "description": (
            "Inspired by Warren Buffett's investing principles: high return "
            "on equity (> 15%), conservative leverage (D/E < 0.5), solid "
            "profitability (net margin > 10%), and not excessively priced "
            "(PE < 25)."
        ),
        "filters": {
            "logic": "AND",
            "filters": [
                {"field": "roe", "source": "ANALYTICS_RESULT", "op": "GT", "value": 0.15},
                {"field": "debt_to_equity", "source": "ANALYTICS_RESULT", "op": "LT", "value": 0.5},
                {"field": "net_margin", "source": "ANALYTICS_RESULT", "op": "GT", "value": 0.10},
                {"field": "pe_trailing", "source": "ANALYTICS_RESULT", "op": "LT", "value": 25},
            ],
        },
        "tags": ["value", "quality", "buffett"],
    },

    # ------------------------------------------------------------------
    # Income / Dividend
    # ------------------------------------------------------------------

    # 8. Dividend Aristocrats
    "dividend-aristocrats": {
        "name": "Dividend Aristocrats",
        "description": (
            "Companies with a track record of consistent dividend growth "
            "(5-year growth > 0), a sustainable payout ratio (< 75%), and "
            "a meaningful current yield (> 2%)."
        ),
        "filters": {
            "logic": "AND",
            "filters": [
                {"field": "consecutive_dividend_years", "source": "ANALYTICS_RESULT", "op": "GTE", "value": 25},
                {"field": "dividend_growth_1y", "source": "ANALYTICS_RESULT", "op": "GT", "value": 0},
                {"field": "dividend_growth_3y", "source": "ANALYTICS_RESULT", "op": "GT", "value": 0},
                {"field": "dividend_growth_5y", "source": "ANALYTICS_RESULT", "op": "GT", "value": 0},
                {"field": "payout_ratio", "source": "ANALYTICS_RESULT", "op": "LT", "value": 0.75},
                {"field": "dividend_yield", "source": "ANALYTICS_RESULT", "op": "GT", "value": 0.02},
            ],
        },
        "tags": ["income", "dividend", "aristocrat"],
    },

    # 9. High Yield Safe Dividend
    "high-yield-safe": {
        "name": "High Yield Safe Dividend",
        "description": (
            "High-yield dividend stocks (yield > 4%) with safety checks: "
            "FCF payout ratio below 70% ensures dividends are covered by "
            "cash flow, and Net Debt/EBITDA < 3 guards against over-leverage."
        ),
        "filters": {
            "logic": "AND",
            "filters": [
                {"field": "dividend_yield", "source": "ANALYTICS_RESULT", "op": "GT", "value": 0.04},
                {"field": "fcf_payout_ratio", "source": "ANALYTICS_RESULT", "op": "LT", "value": 0.70},
                {"field": "net_debt_to_ebitda", "source": "ANALYTICS_RESULT", "op": "LT", "value": 3},
            ],
        },
        "tags": ["income", "dividend", "high_yield"],
    },

    # 10. Shareholder Yield
    "shareholder-yield": {
        "name": "Shareholder Yield",
        "description": (
            "Mebane Faber's shareholder yield concept: total cash returned "
            "to shareholders (dividends + buybacks) exceeds 5%, with FCF "
            "yield > 6% confirming the capital return is backed by real "
            "cash generation."
        ),
        "filters": {
            "logic": "AND",
            "filters": [
                {"field": "shareholder_yield", "source": "ANALYTICS_RESULT", "op": "GT", "value": 0.05},
                {"field": "fcf_yield", "source": "ANALYTICS_RESULT", "op": "GT", "value": 0.06},
            ],
        },
        "tags": ["income", "buyback"],
    },

    # ------------------------------------------------------------------
    # Turnaround / Special Situations
    # ------------------------------------------------------------------

    # 11. Improving Fundamentals
    "improving-fundamentals": {
        "name": "Improving Fundamentals",
        "description": (
            "Turnaround candidates: strong recent operational improvement "
            "(Piotroski F >= 7) in companies still priced cheaply (P/B < "
            "1.5) with positive profitability (ROE > 5% as proxy for "
            "improving trend)."
        ),
        "filters": {
            "logic": "AND",
            "filters": [
                {"field": "piotroski_f_score", "source": "ANALYTICS_RESULT", "op": "GTE", "value": 7},
                {"field": "pb", "source": "ANALYTICS_RESULT", "op": "LT", "value": 1.5},
                {"field": "roe", "source": "ANALYTICS_RESULT", "op": "GT", "value": 0.05},
            ],
        },
        "tags": ["turnaround", "improving"],
    },

    # 12. Hidden Value
    "hidden-value": {
        "name": "Hidden Value",
        "description": (
            "Contrarian deep-value screen for overlooked bargains: cheap on "
            "both earnings (PE < 10) and book (P/B < 1), positive FCF "
            "margin, and a Beneish M-Score below -1.78 to exclude "
            "companies likely manipulating earnings."
        ),
        "filters": {
            "logic": "AND",
            "filters": [
                {"field": "pe_trailing", "source": "ANALYTICS_RESULT", "op": "LT", "value": 10},
                {"field": "pb", "source": "ANALYTICS_RESULT", "op": "LT", "value": 1},
                {"field": "fcf_margin", "source": "ANALYTICS_RESULT", "op": "GT", "value": 0},
                {"field": "beneish_m_score", "source": "ANALYTICS_RESULT", "op": "LT", "value": -1.78},
            ],
        },
        "tags": ["value", "hidden", "contrarian"],
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_all_prebuilt_screens() -> dict[str, dict]:
    """Return the full library of pre-built screen definitions."""
    return PREBUILT_SCREENS


def get_prebuilt_screen(screen_id: str) -> dict | None:
    """Look up a single pre-built screen by its slug ID.

    Parameters
    ----------
    screen_id:
        URL-safe slug such as ``"graham-net-net"`` or ``"magic-formula"``.

    Returns
    -------
    dict | None
        The screen definition dict, or ``None`` if the slug is unknown.
    """
    return PREBUILT_SCREENS.get(screen_id)
