"""E3 Altman Z-Score Engine.

Computes the Altman Z-Score for bankruptcy-risk assessment, selecting the
appropriate model variant based on the entity's GICS sector classification.

**Original Z-Score (Manufacturing)**:
    Z = 1.2*(WC/TA) + 1.4*(RE/TA) + 3.3*(EBIT/TA) + 0.6*(MVE/TL) + 1.0*(Sales/TA)

**Z'-Score (Non-Manufacturing)**:
    Z' = 6.56*(WC/TA) + 3.26*(RE/TA) + 6.72*(EBIT/TA) + 1.05*(BVE/TL)
    (Removes Sales/TA to eliminate asset-turnover bias for service companies;
     uses Book Value of Equity instead of Market Value.)

Model selection is driven by GICS sector:
    - Industrials (20), Materials (15), Consumer Staples (30), Energy (10) → Original
    - Financials (40) → NOT_APPLICABLE (model invalid for banks/insurance)
    - All other sectors → Z'-Score (non-manufacturing)

Part of Pillar 2 analytics — consumes Pillar 1 fundamentals (income
statement + balance sheet), entity classification, equity details, and
EOD price data.  Produces 10 composable EngineOutput metrics.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.engines.base import BaseEngine, EngineOutput, make_input, safe_divide
from src.models.entity import Entity
from src.models.fundamentals import (
    BalanceSheet,
    FinancialPeriod,
    IncomeStatement,
)
from src.models.security import EODPrice, EquityDetails, Security

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# GICS sector sets for model selection
# ---------------------------------------------------------------------------
_MANUFACTURING_SECTORS: frozenset[str] = frozenset({"10", "15", "20", "30"})
_FINANCIAL_SECTORS: frozenset[str] = frozenset({"40"})

# ---------------------------------------------------------------------------
# Altman coefficient vectors
# ---------------------------------------------------------------------------
_ORIGINAL_COEFFICIENTS = {
    "x1": 1.2,
    "x2": 1.4,
    "x3": 3.3,
    "x4": 0.6,
    "x5": 1.0,
}

_NON_MFG_COEFFICIENTS = {
    "x1": 6.56,
    "x2": 3.26,
    "x3": 6.72,
    "x4": 1.05,
    # No x5 term
}

# ---------------------------------------------------------------------------
# Zone thresholds
# ---------------------------------------------------------------------------
_ORIGINAL_THRESHOLDS = {"safe": 2.99, "grey_low": 1.81}
_NON_MFG_THRESHOLDS = {"safe": 2.60, "grey_low": 1.10}

# Zone → implied default probability (rough mapping)
_IMPLIED_PD = {"SAFE": 0.01, "GREY": 0.10, "DISTRESS": 0.30}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _classify_zone(
    z_score: float | None,
    thresholds: dict[str, float],
) -> str:
    """Map a Z-Score to SAFE / GREY / DISTRESS."""
    if z_score is None:
        return "INSUFFICIENT_DATA"
    if z_score > thresholds["safe"]:
        return "SAFE"
    if z_score >= thresholds["grey_low"]:
        return "GREY"
    return "DISTRESS"


def _to_float(val: Any) -> float | None:
    """Safely cast a Decimal / numeric column value to float."""
    if val is None:
        return None
    return float(val)


def _build_output(
    security_id: UUID,
    entity_id: UUID,
    metric_name: str,
    value: float | None,
    period_label: str,
    period_end_date: Any,
    inputs: list[dict],
    *,
    data_quality: str = "COMPLETE",
    unit: str = "RATIO",
) -> EngineOutput:
    """Convenience factory for an Altman EngineOutput."""
    return EngineOutput(
        security_id=security_id,
        entity_id=entity_id,
        engine_id="E3",
        metric_name=metric_name,
        metric_category="QUALITY",
        value=value,
        unit=unit,
        period=period_label,
        period_end_date=period_end_date,
        data_quality=data_quality,
        inputs=inputs,
    )


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class AltmanZScoreEngine(BaseEngine):
    """Altman Z-Score engine (E3).

    Reads the most recent *annual* financial period with both an income
    statement and a balance sheet, resolves the entity's GICS sector to
    choose a model variant, and computes 10 output metrics:

        - ``altman_z_score``      — the composite Z or Z' value
        - ``altman_zone``         — SAFE / GREY / DISTRESS / NOT_APPLICABLE
        - ``altman_model``        — ORIGINAL / NON_MANUFACTURING / NOT_APPLICABLE
        - ``altman_x1_wc_ta``     — Working Capital / Total Assets
        - ``altman_x2_re_ta``     — Retained Earnings / Total Assets
        - ``altman_x3_ebit_ta``   — EBIT / Total Assets
        - ``altman_x4_mve_tl``    — MVE / TL (original) or BVE / TL (Z')
        - ``altman_x5_sales_ta``  — Sales / Total Assets (original only)
        - ``altman_implied_pd``   — rough PD from zone mapping
        - ``altman_gics_sector``  — GICS sector used for model selection

    Edge cases:
        - Financial sector (GICS 40) → zone=NOT_APPLICABLE, score=None
        - Missing financial data → data_quality=INSUFFICIENT_DATA
        - Total assets = 0 → all ratios None
        - Total liabilities = 0 → X4 = None, flagged
        - No EOD price for market cap → falls back to Z' using book value
    """

    engine_id = "E3"
    engine_name = "Altman Z-Score"
    engine_version = "1.0.0"

    async def compute(
        self,
        session: AsyncSession,
        security_id: UUID,
        **kwargs: Any,
    ) -> list[EngineOutput]:
        # ------------------------------------------------------------------
        # 1. Resolve security → entity (with entity eager-loaded)
        # ------------------------------------------------------------------
        sec_stmt = (
            select(Security)
            .options(selectinload(Security.equity_details))
            .where(Security.security_id == security_id)
        )
        sec_result = await session.execute(sec_stmt)
        security = sec_result.scalar_one_or_none()

        if security is None or security.issuer_entity_id is None:
            logger.warning(
                "Altman: security %s not found or has no issuer", security_id
            )
            return []

        entity_id: UUID = security.issuer_entity_id

        # Load the entity for GICS classification
        ent_result = await session.execute(
            select(Entity).where(Entity.entity_id == entity_id)
        )
        entity: Entity | None = ent_result.scalar_one_or_none()
        if entity is None:
            logger.warning("Altman: entity %s not found", entity_id)
            return []

        gics_sector: str | None = entity.gics_sector

        # ------------------------------------------------------------------
        # 2. Financial sector early exit
        # ------------------------------------------------------------------
        if gics_sector is not None and gics_sector in _FINANCIAL_SECTORS:
            return self._financial_sector_outputs(
                security_id, entity_id, gics_sector
            )

        # ------------------------------------------------------------------
        # 3. Determine model variant
        # ------------------------------------------------------------------
        is_manufacturing = (
            gics_sector is not None and gics_sector in _MANUFACTURING_SECTORS
        )
        model_name = "ORIGINAL" if is_manufacturing else "NON_MANUFACTURING"

        # ------------------------------------------------------------------
        # 4. Find the latest ANNUAL period with IS + BS
        # ------------------------------------------------------------------
        fp_stmt = (
            select(FinancialPeriod)
            .where(
                FinancialPeriod.entity_id == entity_id,
                FinancialPeriod.period_type == "ANNUAL",
            )
            .order_by(FinancialPeriod.period_end_date.desc())
            .limit(4)
        )
        fp_result = await session.execute(fp_stmt)
        periods: list[FinancialPeriod] = list(fp_result.scalars().all())

        period: FinancialPeriod | None = None
        inc: IncomeStatement | None = None
        bs: BalanceSheet | None = None

        for p in periods:
            if p.income_statement is not None and p.balance_sheet is not None:
                period = p
                inc = p.income_statement
                bs = p.balance_sheet
                break

        if period is None or inc is None or bs is None:
            logger.info(
                "Altman: no annual period with IS+BS for entity %s", entity_id
            )
            return self._insufficient_data_outputs(
                security_id, entity_id, gics_sector, model_name
            )

        period_label = f"FY_{period.fiscal_year}"

        # ------------------------------------------------------------------
        # 5. Extract raw values
        # ------------------------------------------------------------------
        total_assets = _to_float(bs.total_assets)
        total_liabilities = _to_float(bs.total_liabilities)
        total_current_assets = _to_float(bs.total_current_assets)
        total_current_liabilities = _to_float(bs.total_current_liabilities)
        retained_earnings = _to_float(bs.retained_earnings)
        total_equity = _to_float(bs.total_equity)
        total_revenue = _to_float(inc.total_revenue)
        operating_income = _to_float(inc.operating_income)  # proxy for EBIT

        # Working Capital: prefer the derived field, fall back to computation
        working_capital = _to_float(bs.working_capital)
        if working_capital is None and total_current_assets is not None and total_current_liabilities is not None:
            working_capital = total_current_assets - total_current_liabilities

        # ------------------------------------------------------------------
        # 6. Market value of equity (for Original model)
        # ------------------------------------------------------------------
        shares_outstanding: float | None = None
        close_price: float | None = None
        market_cap: float | None = None
        fallback_to_book = False

        # Try EquityDetails first for shares_outstanding
        if security.equity_details is not None:
            shares_outstanding = _to_float(security.equity_details.shares_outstanding)

        # If no EquityDetails, try diluted_shares_outstanding from IS
        if shares_outstanding is None:
            shares_outstanding = _to_float(inc.diluted_shares_outstanding)
        if shares_outstanding is None:
            shares_outstanding = _to_float(inc.basic_shares_outstanding)

        # Query latest EOD price
        eod_stmt = (
            select(EODPrice)
            .where(EODPrice.security_id == security_id)
            .order_by(EODPrice.price_date.desc())
            .limit(1)
        )
        eod_result = await session.execute(eod_stmt)
        eod: EODPrice | None = eod_result.scalar_one_or_none()

        if eod is not None:
            close_price = _to_float(eod.close)

        if shares_outstanding is not None and close_price is not None:
            market_cap = shares_outstanding * close_price

        # If Original model but we cannot compute market cap, fall back to Z'
        if is_manufacturing and market_cap is None:
            fallback_to_book = True
            model_name = "NON_MANUFACTURING"
            logger.info(
                "Altman: no market cap for %s — falling back to Z' model",
                security_id,
            )

        # ------------------------------------------------------------------
        # 7. Compute the five component ratios
        # ------------------------------------------------------------------
        # Lineage helper
        def _inp(name: str, source: str, value: float | None, per: str = "") -> dict:
            return make_input(
                name=name,
                source=source,
                value=value,
                period=per or period_label,
            )

        # X1: Working Capital / Total Assets
        x1 = safe_divide(working_capital, total_assets)

        # X2: Retained Earnings / Total Assets
        x2 = safe_divide(retained_earnings, total_assets)

        # X3: EBIT / Total Assets  (operating_income as EBIT proxy)
        x3 = safe_divide(operating_income, total_assets)

        # X4: depends on model
        # Original:        Market Value Equity / Total Liabilities
        # Non-Manufacturing: Book Value Equity / Total Liabilities
        x4: float | None
        x4_numerator_name: str
        x4_numerator_value: float | None
        x4_numerator_source: str

        use_original = is_manufacturing and not fallback_to_book

        if use_original:
            x4 = safe_divide(market_cap, total_liabilities)
            x4_numerator_name = "market_cap"
            x4_numerator_value = market_cap
            x4_numerator_source = "derived(shares_outstanding*close)"
        else:
            x4 = safe_divide(total_equity, total_liabilities)
            x4_numerator_name = "total_equity"
            x4_numerator_value = total_equity
            x4_numerator_source = "balance_sheets"

        # X5: Sales / Total Assets (Original only)
        x5: float | None = None
        if use_original:
            x5 = safe_divide(total_revenue, total_assets)

        # ------------------------------------------------------------------
        # 8. Data quality flags
        # ------------------------------------------------------------------
        data_quality = "COMPLETE"
        quality_notes: list[str] = []

        if total_assets is None or total_assets == 0:
            data_quality = "INSUFFICIENT_DATA"
            quality_notes.append("total_assets_zero_or_missing")

        if total_liabilities is None or total_liabilities == 0:
            quality_notes.append("total_liabilities_zero_or_missing")

        if fallback_to_book:
            data_quality = "MARKET_DATA_FALLBACK"
            quality_notes.append("no_eod_price_or_shares")

        # ------------------------------------------------------------------
        # 9. Compute composite Z-Score
        # ------------------------------------------------------------------
        z_score: float | None = None

        if use_original:
            # Original: Z = 1.2*X1 + 1.4*X2 + 3.3*X3 + 0.6*X4 + 1.0*X5
            c = _ORIGINAL_COEFFICIENTS
            if all(v is not None for v in (x1, x2, x3, x4, x5)):
                z_score = (
                    c["x1"] * x1  # type: ignore[operator]
                    + c["x2"] * x2  # type: ignore[operator]
                    + c["x3"] * x3  # type: ignore[operator]
                    + c["x4"] * x4  # type: ignore[operator]
                    + c["x5"] * x5  # type: ignore[operator]
                )
            thresholds = _ORIGINAL_THRESHOLDS
        else:
            # Non-Mfg: Z' = 6.56*X1 + 3.26*X2 + 6.72*X3 + 1.05*X4
            c = _NON_MFG_COEFFICIENTS
            if all(v is not None for v in (x1, x2, x3, x4)):
                z_score = (
                    c["x1"] * x1  # type: ignore[operator]
                    + c["x2"] * x2  # type: ignore[operator]
                    + c["x3"] * x3  # type: ignore[operator]
                    + c["x4"] * x4  # type: ignore[operator]
                )
            thresholds = _NON_MFG_THRESHOLDS

        zone = _classify_zone(z_score, thresholds)

        if z_score is None and data_quality == "COMPLETE":
            data_quality = "INSUFFICIENT_DATA"

        implied_pd = _IMPLIED_PD.get(zone)

        # ------------------------------------------------------------------
        # 10. Build outputs
        # ------------------------------------------------------------------
        outputs: list[EngineOutput] = []

        # --- altman_z_score ---
        z_inputs = [
            _inp("working_capital", "balance_sheets", working_capital),
            _inp("retained_earnings", "balance_sheets", retained_earnings),
            _inp("operating_income", "income_statements", operating_income),
            _inp(x4_numerator_name, x4_numerator_source, x4_numerator_value),
            _inp("total_assets", "balance_sheets", total_assets),
            _inp("total_liabilities", "balance_sheets", total_liabilities),
        ]
        if use_original:
            z_inputs.append(
                _inp("total_revenue", "income_statements", total_revenue)
            )
            z_inputs.append(
                _inp("shares_outstanding", "equity_details", shares_outstanding)
            )
            z_inputs.append(
                _inp("close_price", "eod_prices", close_price,
                     per=str(eod.price_date) if eod else "")
            )

        outputs.append(
            _build_output(
                security_id, entity_id,
                "altman_z_score",
                z_score,
                period_label, period.period_end_date,
                z_inputs,
                data_quality=data_quality,
                unit="SCORE",
            )
        )

        # --- altman_zone ---
        outputs.append(
            _build_output(
                security_id, entity_id,
                "altman_zone",
                None,  # classification — no numeric value
                period_label, period.period_end_date,
                [_inp("altman_z_score", "E3", z_score)],
                data_quality=zone,
                unit="CLASSIFICATION",
            )
        )

        # --- altman_model ---
        outputs.append(
            _build_output(
                security_id, entity_id,
                "altman_model",
                None,
                period_label, period.period_end_date,
                [_inp("gics_sector", "entities", gics_sector)],
                data_quality=model_name,
                unit="CLASSIFICATION",
            )
        )

        # --- altman_x1_wc_ta ---
        x1_quality = data_quality
        if working_capital is None:
            x1_quality = "INSUFFICIENT_DATA"
        outputs.append(
            _build_output(
                security_id, entity_id,
                "altman_x1_wc_ta",
                x1,
                period_label, period.period_end_date,
                [
                    _inp("working_capital", "balance_sheets", working_capital),
                    _inp("total_assets", "balance_sheets", total_assets),
                ],
                data_quality=x1_quality,
            )
        )

        # --- altman_x2_re_ta ---
        x2_quality = data_quality
        if retained_earnings is None:
            x2_quality = "INSUFFICIENT_DATA"
        outputs.append(
            _build_output(
                security_id, entity_id,
                "altman_x2_re_ta",
                x2,
                period_label, period.period_end_date,
                [
                    _inp("retained_earnings", "balance_sheets", retained_earnings),
                    _inp("total_assets", "balance_sheets", total_assets),
                ],
                data_quality=x2_quality,
            )
        )

        # --- altman_x3_ebit_ta ---
        x3_quality = data_quality
        if operating_income is None:
            x3_quality = "INSUFFICIENT_DATA"
        outputs.append(
            _build_output(
                security_id, entity_id,
                "altman_x3_ebit_ta",
                x3,
                period_label, period.period_end_date,
                [
                    _inp("operating_income", "income_statements", operating_income),
                    _inp("total_assets", "balance_sheets", total_assets),
                ],
                data_quality=x3_quality,
            )
        )

        # --- altman_x4_mve_tl ---
        x4_quality = data_quality
        if total_liabilities is None or total_liabilities == 0:
            x4_quality = "ZERO_DENOMINATOR"
        x4_inputs = [
            _inp(x4_numerator_name, x4_numerator_source, x4_numerator_value),
            _inp("total_liabilities", "balance_sheets", total_liabilities),
        ]
        if use_original:
            x4_inputs.extend([
                _inp("shares_outstanding", "equity_details", shares_outstanding),
                _inp("close_price", "eod_prices", close_price,
                     per=str(eod.price_date) if eod else ""),
            ])
        outputs.append(
            _build_output(
                security_id, entity_id,
                "altman_x4_mve_tl",
                x4,
                period_label, period.period_end_date,
                x4_inputs,
                data_quality=x4_quality,
            )
        )

        # --- altman_x5_sales_ta ---
        x5_quality = data_quality if use_original else "NOT_APPLICABLE"
        outputs.append(
            _build_output(
                security_id, entity_id,
                "altman_x5_sales_ta",
                x5,
                period_label, period.period_end_date,
                [
                    _inp("total_revenue", "income_statements", total_revenue),
                    _inp("total_assets", "balance_sheets", total_assets),
                ],
                data_quality=x5_quality,
            )
        )

        # --- altman_implied_pd ---
        outputs.append(
            _build_output(
                security_id, entity_id,
                "altman_implied_pd",
                implied_pd,
                period_label, period.period_end_date,
                [_inp("altman_zone", "E3", None)],
                data_quality=data_quality if implied_pd is not None else "INSUFFICIENT_DATA",
            )
        )

        # --- altman_gics_sector ---
        outputs.append(
            _build_output(
                security_id, entity_id,
                "altman_gics_sector",
                None,
                period_label, period.period_end_date,
                [_inp("gics_sector", "entities", gics_sector)],
                data_quality=gics_sector or "MISSING",
                unit="CLASSIFICATION",
            )
        )

        logger.info(
            "Altman: computed %d metrics for security %s "
            "(model=%s, zone=%s, z=%.4f, period=%s)",
            len(outputs), security_id, model_name, zone,
            z_score if z_score is not None else 0.0, period_label,
        )
        return outputs

    # ------------------------------------------------------------------
    # Private helpers for short-circuit outputs
    # ------------------------------------------------------------------

    @staticmethod
    def _financial_sector_outputs(
        security_id: UUID,
        entity_id: UUID,
        gics_sector: str,
    ) -> list[EngineOutput]:
        """Return NOT_APPLICABLE outputs for financial-sector entities."""
        logger.info(
            "Altman: GICS sector %s is financial — model not applicable "
            "for security %s", gics_sector, security_id,
        )
        base_inputs = [
            make_input("gics_sector", "entities", gics_sector),
        ]
        names_and_units: list[tuple[str, str]] = [
            ("altman_z_score", "SCORE"),
            ("altman_zone", "CLASSIFICATION"),
            ("altman_model", "CLASSIFICATION"),
            ("altman_x1_wc_ta", "RATIO"),
            ("altman_x2_re_ta", "RATIO"),
            ("altman_x3_ebit_ta", "RATIO"),
            ("altman_x4_mve_tl", "RATIO"),
            ("altman_x5_sales_ta", "RATIO"),
            ("altman_implied_pd", "RATIO"),
            ("altman_gics_sector", "CLASSIFICATION"),
        ]
        outputs: list[EngineOutput] = []
        for metric_name, unit in names_and_units:
            outputs.append(
                _build_output(
                    security_id, entity_id,
                    metric_name,
                    None,
                    "LATEST", None,
                    list(base_inputs),
                    data_quality="NOT_APPLICABLE",
                    unit=unit,
                )
            )
        return outputs

    @staticmethod
    def _insufficient_data_outputs(
        security_id: UUID,
        entity_id: UUID,
        gics_sector: str | None,
        model_name: str,
    ) -> list[EngineOutput]:
        """Return INSUFFICIENT_DATA outputs when no financial period found."""
        base_inputs = [
            make_input("gics_sector", "entities", gics_sector),
        ]
        names_and_units: list[tuple[str, str]] = [
            ("altman_z_score", "SCORE"),
            ("altman_zone", "CLASSIFICATION"),
            ("altman_model", "CLASSIFICATION"),
            ("altman_x1_wc_ta", "RATIO"),
            ("altman_x2_re_ta", "RATIO"),
            ("altman_x3_ebit_ta", "RATIO"),
            ("altman_x4_mve_tl", "RATIO"),
            ("altman_x5_sales_ta", "RATIO"),
            ("altman_implied_pd", "RATIO"),
            ("altman_gics_sector", "CLASSIFICATION"),
        ]
        outputs: list[EngineOutput] = []
        for metric_name, unit in names_and_units:
            dq = "INSUFFICIENT_DATA"
            # Model and sector are still known even without financials
            if metric_name == "altman_model":
                dq = model_name
            elif metric_name == "altman_gics_sector":
                dq = gics_sector or "MISSING"
            outputs.append(
                _build_output(
                    security_id, entity_id,
                    metric_name,
                    None,
                    "LATEST", None,
                    list(base_inputs),
                    data_quality=dq,
                    unit=unit,
                )
            )
        return outputs
