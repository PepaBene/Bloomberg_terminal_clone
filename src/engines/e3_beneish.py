"""E3 Beneish M-Score Engine.

Computes the Beneish M-Score, a probabilistic model for detecting
earnings manipulation.  The model uses eight financial ratios that compare
current-year to prior-year figures, producing a composite score:

    M = -4.84 + 0.920*DSRI + 0.528*GMI + 0.404*AQI + 0.892*SGI
        + 0.115*DEPI - 0.172*SGAI + 4.679*TATA - 0.327*LVGI

Interpretation:
    M > -1.78  =>  POSSIBLE_MANIPULATOR  (flag for deeper review)
    M <= -1.78 =>  UNLIKELY_MANIPULATOR

Part of Pillar 2 analytics -- consumes Pillar 1 fundamentals (income
statement + balance sheet + cash flow) from two consecutive annual
periods and produces composable EngineOutput metrics.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.engines.base import BaseEngine, EngineOutput, make_input, safe_divide
from src.models.fundamentals import (
    BalanceSheet,
    CashFlowStatement,
    FinancialPeriod,
    IncomeStatement,
)
from src.models.security import Security

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# M-Score coefficients (Beneish 1999)
# ---------------------------------------------------------------------------
_INTERCEPT = -4.84
_COEFF_DSRI = 0.920
_COEFF_GMI = 0.528
_COEFF_AQI = 0.404
_COEFF_SGI = 0.892
_COEFF_DEPI = 0.115
_COEFF_SGAI = -0.172
_COEFF_TATA = 4.679
_COEFF_LVGI = -0.327

# Threshold
_MANIPULATION_THRESHOLD = -1.78

# Minimum components required to compute a partial M-Score
_MIN_COMPONENTS = 6


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _f(val: Any) -> float | None:
    """Convert a Decimal/numeric column value to float, or None."""
    return float(val) if val is not None else None


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
    """Convenience factory for a Beneish EngineOutput."""
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

class BeneishEngine(BaseEngine):
    """Beneish M-Score engine (E3).

    Reads the two most recent annual financial periods that each have an
    income statement, balance sheet, and cash-flow statement, then computes
    eight component ratios and the composite M-Score.

    **Output metrics** (12 total):

    - ``beneish_m_score``             -- composite M-Score (SCORE)
    - ``beneish_flag``                -- POSSIBLE_MANIPULATOR / UNLIKELY_MANIPULATOR (CLASSIFICATION)
    - ``beneish_dsri``                -- Days Sales in Receivables Index (RATIO)
    - ``beneish_gmi``                 -- Gross Margin Index (RATIO)
    - ``beneish_aqi``                 -- Asset Quality Index (RATIO)
    - ``beneish_sgi``                 -- Sales Growth Index (RATIO)
    - ``beneish_depi``                -- Depreciation Index (RATIO)
    - ``beneish_sgai``                -- SGA Index (RATIO)
    - ``beneish_tata``                -- Total Accruals to Total Assets (RATIO)
    - ``beneish_lvgi``                -- Leverage Index (RATIO)
    - ``beneish_accruals_quality``    -- TATA absolute-value classification (CLASSIFICATION)
    - ``beneish_components_available``-- count of non-None components out of 8 (SCORE)

    Edge cases:
        - Missing prior year: ``INSUFFICIENT_DATA``, m_score=None
        - Division by zero in any component: that component = None
        - >2 components missing: m_score=None, ``INSUFFICIENT_DATA``
        - Partial components: M-Score computed with available, flagged ``PARTIAL``
    """

    engine_id = "E3"
    engine_name = "Beneish M-Score"
    engine_version = "1.0.0"

    async def compute(
        self,
        session: AsyncSession,
        security_id: UUID,
        **kwargs: Any,
    ) -> list[EngineOutput]:
        # ------------------------------------------------------------------
        # 1. Resolve security -> entity
        # ------------------------------------------------------------------
        sec_result = await session.execute(
            select(Security).where(Security.security_id == security_id)
        )
        security = sec_result.scalar_one_or_none()
        if security is None or security.issuer_entity_id is None:
            logger.warning("Beneish: security %s not found or has no issuer", security_id)
            return []

        entity_id: UUID = security.issuer_entity_id

        # ------------------------------------------------------------------
        # 2. Find two most recent ANNUAL periods with IS + BS + CF
        # ------------------------------------------------------------------
        stmt = (
            select(FinancialPeriod)
            .where(
                FinancialPeriod.entity_id == entity_id,
                FinancialPeriod.period_type == "ANNUAL",
            )
            .order_by(FinancialPeriod.period_end_date.desc())
            .limit(8)  # look further back in case some periods lack data
        )
        result = await session.execute(stmt)
        periods: list[FinancialPeriod] = list(result.scalars().all())

        # Collect the two most recent periods that have all three statements
        usable: list[FinancialPeriod] = []
        for p in periods:
            if (
                p.income_statement is not None
                and p.balance_sheet is not None
                and p.cash_flow is not None
            ):
                usable.append(p)
                if len(usable) == 2:
                    break

        # Current = usable[0], Prior = usable[1]
        if len(usable) < 1:
            logger.info(
                "Beneish: no annual period with IS+BS+CF for entity %s", entity_id
            )
            return []

        curr_period = usable[0]
        period_label = f"FY_{curr_period.fiscal_year}"
        period_end = curr_period.period_end_date

        # If we don't have a prior year, emit INSUFFICIENT_DATA outputs
        if len(usable) < 2:
            return self._insufficient_data_outputs(
                security_id, entity_id, period_label, period_end
            )

        prior_period = usable[1]
        prior_label = f"FY_{prior_period.fiscal_year}"

        # ------------------------------------------------------------------
        # 3. Extract raw values
        # ------------------------------------------------------------------
        curr_is: IncomeStatement = curr_period.income_statement  # type: ignore[assignment]
        curr_bs: BalanceSheet = curr_period.balance_sheet  # type: ignore[assignment]
        curr_cf: CashFlowStatement = curr_period.cash_flow  # type: ignore[assignment]

        prior_is: IncomeStatement = prior_period.income_statement  # type: ignore[assignment]
        prior_bs: BalanceSheet = prior_period.balance_sheet  # type: ignore[assignment]
        prior_cf: CashFlowStatement = prior_period.cash_flow  # type: ignore[assignment]

        # Current year fields
        recv_t = _f(curr_bs.accounts_receivable)
        rev_t = _f(curr_is.total_revenue)
        gp_t = _f(curr_is.gross_profit)
        ca_t = _f(curr_bs.total_current_assets)
        ppe_t = _f(curr_bs.ppe_net)
        ta_t = _f(curr_bs.total_assets)
        dep_t = _f(curr_cf.depreciation_amortization) or _f(curr_is.depreciation_amortization)
        sga_t = _f(curr_is.selling_general_admin)
        ni_t = _f(curr_is.net_income)
        cfo_t = _f(curr_cf.cash_from_operations)
        cl_t = _f(curr_bs.total_current_liabilities)
        ltd_t = _f(curr_bs.long_term_debt)

        # Prior year fields
        recv_p = _f(prior_bs.accounts_receivable)
        rev_p = _f(prior_is.total_revenue)
        gp_p = _f(prior_is.gross_profit)
        ca_p = _f(prior_bs.total_current_assets)
        ppe_p = _f(prior_bs.ppe_net)
        ta_p = _f(prior_bs.total_assets)
        dep_p = _f(prior_cf.depreciation_amortization) or _f(prior_is.depreciation_amortization)
        sga_p = _f(prior_is.selling_general_admin)
        cl_p = _f(prior_bs.total_current_liabilities)
        ltd_p = _f(prior_bs.long_term_debt)

        # Lineage helpers
        def _inp_curr(name: str, value: float | None) -> dict:
            return make_input(name=name, source="financial_periods", value=value, period=period_label)

        def _inp_prior(name: str, value: float | None) -> dict:
            return make_input(name=name, source="financial_periods", value=value, period=prior_label)

        outputs: list[EngineOutput] = []

        # ------------------------------------------------------------------
        # 4. Compute the eight components
        # ------------------------------------------------------------------

        # -- DSRI: (Receivables_t/Revenue_t) / (Receivables_t-1/Revenue_t-1)
        recv_rev_t = safe_divide(recv_t, rev_t)
        recv_rev_p = safe_divide(recv_p, rev_p)
        dsri = safe_divide(recv_rev_t, recv_rev_p)
        dsri_inputs = [
            _inp_curr("accounts_receivable", recv_t),
            _inp_curr("total_revenue", rev_t),
            _inp_prior("accounts_receivable", recv_p),
            _inp_prior("total_revenue", rev_p),
        ]
        outputs.append(
            _build_output(
                security_id, entity_id, "beneish_dsri", dsri,
                period_label, period_end, dsri_inputs,
            )
        )

        # -- GMI: Gross_Margin_prior / Gross_Margin_current  (PRIOR / CURRENT)
        gm_t = safe_divide(gp_t, rev_t)
        gm_p = safe_divide(gp_p, rev_p)
        gmi = safe_divide(gm_p, gm_t)  # prior / current
        gmi_inputs = [
            _inp_curr("gross_profit", gp_t),
            _inp_curr("total_revenue", rev_t),
            _inp_prior("gross_profit", gp_p),
            _inp_prior("total_revenue", rev_p),
        ]
        outputs.append(
            _build_output(
                security_id, entity_id, "beneish_gmi", gmi,
                period_label, period_end, gmi_inputs,
            )
        )

        # -- AQI: [1-(CA_t+PPE_t)/TA_t] / [1-(CA_t-1+PPE_t-1)/TA_t-1]
        aqi = self._compute_aqi(ca_t, ppe_t, ta_t, ca_p, ppe_p, ta_p)
        aqi_inputs = [
            _inp_curr("total_current_assets", ca_t),
            _inp_curr("ppe_net", ppe_t),
            _inp_curr("total_assets", ta_t),
            _inp_prior("total_current_assets", ca_p),
            _inp_prior("ppe_net", ppe_p),
            _inp_prior("total_assets", ta_p),
        ]
        outputs.append(
            _build_output(
                security_id, entity_id, "beneish_aqi", aqi,
                period_label, period_end, aqi_inputs,
            )
        )

        # -- SGI: Revenue_t / Revenue_t-1
        sgi = safe_divide(rev_t, rev_p)
        sgi_inputs = [
            _inp_curr("total_revenue", rev_t),
            _inp_prior("total_revenue", rev_p),
        ]
        outputs.append(
            _build_output(
                security_id, entity_id, "beneish_sgi", sgi,
                period_label, period_end, sgi_inputs,
            )
        )

        # -- DEPI: Dep_Rate_prior / Dep_Rate_current
        #    where Dep_Rate = Depreciation / (Depreciation + PPE)
        dep_rate_t = safe_divide(dep_t, self._add(dep_t, ppe_t))
        dep_rate_p = safe_divide(dep_p, self._add(dep_p, ppe_p))
        depi = safe_divide(dep_rate_p, dep_rate_t)
        depi_inputs = [
            _inp_curr("depreciation_amortization", dep_t),
            _inp_curr("ppe_net", ppe_t),
            _inp_prior("depreciation_amortization", dep_p),
            _inp_prior("ppe_net", ppe_p),
        ]
        outputs.append(
            _build_output(
                security_id, entity_id, "beneish_depi", depi,
                period_label, period_end, depi_inputs,
            )
        )

        # -- SGAI: (SGA_t/Revenue_t) / (SGA_t-1/Revenue_t-1)
        sga_rev_t = safe_divide(sga_t, rev_t)
        sga_rev_p = safe_divide(sga_p, rev_p)
        sgai = safe_divide(sga_rev_t, sga_rev_p)
        sgai_inputs = [
            _inp_curr("selling_general_admin", sga_t),
            _inp_curr("total_revenue", rev_t),
            _inp_prior("selling_general_admin", sga_p),
            _inp_prior("total_revenue", rev_p),
        ]
        outputs.append(
            _build_output(
                security_id, entity_id, "beneish_sgai", sgai,
                period_label, period_end, sgai_inputs,
            )
        )

        # -- TATA: (Net Income - Operating Cash Flow) / Total Assets
        tata: float | None = None
        if ni_t is not None and cfo_t is not None and ta_t is not None and ta_t != 0:
            tata = (ni_t - cfo_t) / ta_t
        tata_inputs = [
            _inp_curr("net_income", ni_t),
            _inp_curr("cash_from_operations", cfo_t),
            _inp_curr("total_assets", ta_t),
        ]
        outputs.append(
            _build_output(
                security_id, entity_id, "beneish_tata", tata,
                period_label, period_end, tata_inputs,
            )
        )

        # -- LVGI: [(CL_t+LTD_t)/TA_t] / [(CL_t-1+LTD_t-1)/TA_t-1]
        lev_t = safe_divide(self._add(cl_t, ltd_t), ta_t)
        lev_p = safe_divide(self._add(cl_p, ltd_p), ta_p)
        lvgi = safe_divide(lev_t, lev_p)
        lvgi_inputs = [
            _inp_curr("total_current_liabilities", cl_t),
            _inp_curr("long_term_debt", ltd_t),
            _inp_curr("total_assets", ta_t),
            _inp_prior("total_current_liabilities", cl_p),
            _inp_prior("long_term_debt", ltd_p),
            _inp_prior("total_assets", ta_p),
        ]
        outputs.append(
            _build_output(
                security_id, entity_id, "beneish_lvgi", lvgi,
                period_label, period_end, lvgi_inputs,
            )
        )

        # ------------------------------------------------------------------
        # 5. Composite M-Score
        # ------------------------------------------------------------------
        components = {
            "dsri": dsri,
            "gmi": gmi,
            "aqi": aqi,
            "sgi": sgi,
            "depi": depi,
            "sgai": sgai,
            "tata": tata,
            "lvgi": lvgi,
        }
        available_count = sum(1 for v in components.values() if v is not None)

        # Components available (SCORE)
        outputs.append(
            _build_output(
                security_id, entity_id, "beneish_components_available",
                float(available_count), period_label, period_end,
                [make_input("components_available", "computed", float(available_count), period_label)],
                unit="SCORE",
            )
        )

        # Accruals quality classification based on |TATA|
        accruals_class: str | None = None
        accruals_value: float | None = None
        if tata is not None:
            abs_tata = abs(tata)
            if abs_tata < 0.05:
                accruals_class = "LOW"
            elif abs_tata < 0.10:
                accruals_class = "MODERATE"
            else:
                accruals_class = "HIGH"
            accruals_value = float(["LOW", "MODERATE", "HIGH"].index(accruals_class))
        outputs.append(
            _build_output(
                security_id, entity_id, "beneish_accruals_quality",
                accruals_value, period_label, period_end,
                [
                    _inp_curr("tata", tata),
                    make_input("classification", "computed", accruals_value, period_label,
                               accruals_class or ""),
                ],
                unit="CLASSIFICATION",
                data_quality="COMPLETE" if accruals_class is not None else "INSUFFICIENT_DATA",
            )
        )

        # Compute M-Score
        m_score: float | None = None
        m_quality = "COMPLETE"

        if available_count < 8:
            # [Bug 40 fix] Do not score missing components as neutral
            m_quality = "INSUFFICIENT_DATA"
            m_score = None
            flag_value = None
            flag_label = ""
        else:
            # All eight components present
            m_score = self._compute_m_score(components)

        m_score_inputs = [
            make_input("dsri", "computed", dsri, period_label),
            make_input("gmi", "computed", gmi, period_label),
            make_input("aqi", "computed", aqi, period_label),
            make_input("sgi", "computed", sgi, period_label),
            make_input("depi", "computed", depi, period_label),
            make_input("sgai", "computed", sgai, period_label),
            make_input("tata", "computed", tata, period_label),
            make_input("lvgi", "computed", lvgi, period_label),
        ]

        outputs.append(
            _build_output(
                security_id, entity_id, "beneish_m_score",
                m_score, period_label, period_end, m_score_inputs,
                data_quality=m_quality, unit="SCORE",
            )
        )

        # Flag
        flag_value: float | None = None
        flag_label = ""
        if m_score is not None:
            if m_score > _MANIPULATION_THRESHOLD:
                flag_value = 1.0
                flag_label = "POSSIBLE_MANIPULATOR"
            else:
                flag_value = 0.0
                flag_label = "UNLIKELY_MANIPULATOR"

        outputs.append(
            _build_output(
                security_id, entity_id, "beneish_flag",
                flag_value, period_label, period_end,
                [
                    make_input("m_score", "computed", m_score, period_label),
                    make_input("threshold", "constant", _MANIPULATION_THRESHOLD, ""),
                    make_input("classification", "computed", flag_value, period_label, flag_label),
                ],
                data_quality=m_quality, unit="CLASSIFICATION",
            )
        )

        logger.info(
            "Beneish: computed %d metrics for security %s (period %s, "
            "components=%d/8, m_score=%s, flag=%s)",
            len(outputs), security_id, period_label,
            available_count,
            f"{m_score:.4f}" if m_score is not None else "N/A",
            flag_label or "N/A",
        )
        return outputs

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _add(a: float | None, b: float | None) -> float | None:
        """Add two nullable floats. Returns None only if both are None."""
        if a is None and b is None:
            return None
        return (a or 0.0) + (b or 0.0)

    @staticmethod
    def _compute_aqi(
        ca_t: float | None,
        ppe_t: float | None,
        ta_t: float | None,
        ca_p: float | None,
        ppe_p: float | None,
        ta_p: float | None,
    ) -> float | None:
        """Asset Quality Index.

        AQI = [1 - (CA_t + PPE_t) / TA_t] / [1 - (CA_p + PPE_p) / TA_p]
        """
        if any(v is None for v in (ca_t, ppe_t, ta_t, ca_p, ppe_p, ta_p)):
            return None
        if ta_t == 0 or ta_p == 0:
            return None
        hard_t = (ca_t + ppe_t) / ta_t  # type: ignore[operator]
        hard_p = (ca_p + ppe_p) / ta_p  # type: ignore[operator]
        numerator = 1.0 - hard_t
        denominator = 1.0 - hard_p
        if abs(denominator) < 1e-7:
            return None
        return numerator / denominator

    @staticmethod
    def _compute_m_score(components: dict[str, float | None]) -> float:
        """Compute M-Score from available components.

        Missing components contribute zero (their coefficient term is
        omitted), which is the neutral assumption.  The caller must
        verify that at least ``_MIN_COMPONENTS`` are available.
        """
        coefficients = {
            "dsri": _COEFF_DSRI,
            "gmi": _COEFF_GMI,
            "aqi": _COEFF_AQI,
            "sgi": _COEFF_SGI,
            "depi": _COEFF_DEPI,
            "sgai": _COEFF_SGAI,
            "tata": _COEFF_TATA,
            "lvgi": _COEFF_LVGI,
        }
        score = _INTERCEPT
        for key, coeff in coefficients.items():
            val = components.get(key)
            if val is not None:
                score += coeff * val
        return score

    # ------------------------------------------------------------------
    # Insufficient-data fallback
    # ------------------------------------------------------------------

    @staticmethod
    def _insufficient_data_outputs(
        security_id: UUID,
        entity_id: UUID,
        period_label: str,
        period_end: Any,
    ) -> list[EngineOutput]:
        """Return placeholder outputs when prior-year data is missing."""
        metrics = [
            ("beneish_dsri", "RATIO"),
            ("beneish_gmi", "RATIO"),
            ("beneish_aqi", "RATIO"),
            ("beneish_sgi", "RATIO"),
            ("beneish_depi", "RATIO"),
            ("beneish_sgai", "RATIO"),
            ("beneish_tata", "RATIO"),
            ("beneish_lvgi", "RATIO"),
            ("beneish_m_score", "SCORE"),
            ("beneish_flag", "CLASSIFICATION"),
            ("beneish_accruals_quality", "CLASSIFICATION"),
            ("beneish_components_available", "SCORE"),
        ]
        return [
            _build_output(
                security_id, entity_id, name, None,
                period_label, period_end,
                [make_input("prior_year", "financial_periods", None, "", "MISSING")],
                data_quality="INSUFFICIENT_DATA", unit=unit,
            )
            for name, unit in metrics
        ]
