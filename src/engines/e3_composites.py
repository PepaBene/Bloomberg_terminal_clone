"""E3 Composite Quality Scores Engine.

Computes four composite quality/safety scores by combining pre-computed
metrics from the AnalyticsResult table:

1. **Earnings Quality** (0-100)  — accruals, cash flow quality, Beneish
   M-Score, and revenue growth consistency.

2. **Financial Strength** (0-100) — interest coverage, net-debt/EBITDA,
   current ratio, FCF-to-debt, and Altman Z-Score.

3. **Dividend Safety** (point-based) — payout ratio, FCF payout ratio,
   leverage, and Piotroski F-Score.

4. **Value Trap Risk** (point-based) — detects cheap-but-deteriorating
   patterns across valuation and fundamental metrics.

Part of Pillar 2 analytics (engine family E3 — Quality).  Consumes
pre-computed E1 ratios and E3 scores stored in ``analytics_results``
and persists composite scores to the ``composite_scores`` table.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.engines.base import BaseEngine, EngineOutput, make_input
from src.models.analytics import AnalyticsResult, CompositeScore
from src.models.security import Security

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALL_SCORE_TYPES = frozenset({
    "earnings_quality",
    "financial_strength",
    "dividend_safety",
    "value_trap_risk",
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _f(val: Any) -> float | None:
    """Convert a Decimal/numeric value to float, or None."""
    return float(val) if val is not None else None


def _build_output(
    security_id: UUID,
    entity_id: UUID,
    metric_name: str,
    value: float | None,
    inputs: list[dict],
    *,
    data_quality: str = "COMPLETE",
    unit: str = "SCORE",
) -> EngineOutput:
    """Convenience factory for a Composite-Score EngineOutput."""
    return EngineOutput(
        security_id=security_id,
        entity_id=entity_id,
        engine_id="E3",
        metric_name=metric_name,
        metric_category="QUALITY",
        value=value,
        unit=unit,
        period="LATEST",
        period_end_date=None,
        data_quality=data_quality,
        inputs=inputs,
    )


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class CompositeScoreEngine(BaseEngine):
    """Composite Quality Scores engine (E3).

    Reads pre-computed E1 ratios and E3 scores from ``analytics_results``
    and combines them into four composite scores:

    - **earnings_quality** (0-100): accruals ratio, OCF-to-NI, Beneish
      M-Score, revenue growth consistency.
    - **financial_strength** (0-100): interest coverage, net-debt/EBITDA,
      current ratio, FCF-to-debt, Altman Z-Score.
    - **dividend_safety** (points): payout ratio, FCF payout ratio,
      debt/EBITDA, Piotroski F-Score.
    - **value_trap_risk** (points): cheap-but-deteriorating signals.

    Each composite is persisted to the ``composite_scores`` table and
    emitted as a list of ``EngineOutput`` metrics.
    """

    engine_id = "E3"
    engine_name = "Composite Scores"
    engine_version = "1.0.0"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def compute(
        self,
        session: AsyncSession,
        security_id: UUID,
        *,
        score_types: set[str] | None = None,
        **kwargs: Any,
    ) -> list[EngineOutput]:
        """Compute composite scores for *security_id*.

        Parameters
        ----------
        session:
            Async SQLAlchemy session.
        security_id:
            Target security UUID.
        score_types:
            Subset of score types to compute.  ``None`` computes all four.

        Returns
        -------
        list[EngineOutput]
            One or more outputs per composite score (numeric value,
            classification, and per-component breakdowns).
        """
        requested = score_types or ALL_SCORE_TYPES

        # 1. Resolve security -> entity
        sec_result = await session.execute(
            select(Security).where(Security.security_id == security_id)
        )
        security = sec_result.scalar_one_or_none()
        if security is None or security.issuer_entity_id is None:
            logger.warning(
                "Composites: security %s not found or has no issuer", security_id
            )
            return []
        entity_id: UUID = security.issuer_entity_id

        # 2. Pre-fetch all latest metrics for this security once
        metrics = await self._fetch_latest_metrics(session, security_id)

        outputs: list[EngineOutput] = []

        # 3. Dispatch to individual score builders
        if "earnings_quality" in requested:
            outputs.extend(
                await self._earnings_quality(
                    session, security_id, entity_id, metrics
                )
            )
        if "financial_strength" in requested:
            outputs.extend(
                await self._financial_strength(
                    session, security_id, entity_id, metrics
                )
            )
        if "dividend_safety" in requested:
            outputs.extend(
                await self._dividend_safety(
                    session, security_id, entity_id, metrics
                )
            )
        if "value_trap_risk" in requested:
            outputs.extend(
                await self._value_trap_risk(
                    session, security_id, entity_id, metrics
                )
            )

        logger.info(
            "Composites: computed %d outputs for security %s",
            len(outputs), security_id,
        )
        return outputs

    # ------------------------------------------------------------------
    # Metric fetcher
    # ------------------------------------------------------------------

    async def _fetch_latest_metrics(
        self,
        session: AsyncSession,
        security_id: UUID,
    ) -> dict[str, float | None]:
        """Return ``{metric_name: value}`` for all latest analytics results.

        Uses a subquery to find the max as_of_date per metric_name, then
        joins back to get the corresponding value.  This avoids
        ``DISTINCT ON`` which is PostgreSQL-only.
        """
        latest_date = (
            select(
                AnalyticsResult.metric_name,
                func.max(AnalyticsResult.as_of_date).label("max_date"),
            )
            .where(AnalyticsResult.security_id == security_id)
            .group_by(AnalyticsResult.metric_name)
            .subquery()
        )
        stmt = (
            select(
                AnalyticsResult.metric_name,
                AnalyticsResult.value,
            )
            .join(
                latest_date,
                (AnalyticsResult.metric_name == latest_date.c.metric_name)
                & (AnalyticsResult.as_of_date == latest_date.c.max_date),
            )
            .where(AnalyticsResult.security_id == security_id)
        )
        rows = (await session.execute(stmt)).all()
        return {name: _f(val) for name, val in rows}

    async def _fetch_metric_history(
        self,
        session: AsyncSession,
        security_id: UUID,
        metric_name: str,
        limit: int = 5,
    ) -> list[float | None]:
        """Return up to *limit* most recent values for *metric_name* (newest first)."""
        stmt = (
            select(AnalyticsResult.value)
            .where(
                AnalyticsResult.security_id == security_id,
                AnalyticsResult.metric_name == metric_name,
            )
            .order_by(AnalyticsResult.as_of_date.desc())
            .limit(limit)
        )
        rows = (await session.execute(stmt)).scalars().all()
        return [_f(v) for v in rows]

    # ------------------------------------------------------------------
    # Persistence helper
    # ------------------------------------------------------------------

    async def _persist_composite(
        self,
        session: AsyncSession,
        security_id: UUID,
        entity_id: UUID,
        score_type: str,
        score_value: float | None,
        classification: str | None,
        components: dict,
        data_quality: str,
    ) -> None:
        """Upsert a row into the ``composite_scores`` table."""
        try:
            stmt = select(CompositeScore).where(
                CompositeScore.security_id == security_id,
                CompositeScore.score_type == score_type,
                CompositeScore.calculation_date == date.today()
            )
            existing = (await session.execute(stmt)).scalar_one_or_none()

            if existing:
                existing.score_value = score_value
                existing.classification = classification
                existing.components = components
                existing.data_quality = data_quality
            else:
                record = CompositeScore(
                    security_id=security_id,
                    entity_id=entity_id,
                    calculation_date=date.today(),
                    score_type=score_type,
                    score_value=score_value,
                    classification=classification,
                    components=components,
                    data_quality=data_quality,
                )
                session.add(record)
        except Exception:
            logger.error(
                "Composites: failed to persist %s for security %s — "
                "DB write skipped (schema mismatch or constraint violation)",
                score_type, security_id, exc_info=True,
            )

    # ------------------------------------------------------------------
    # Score 1: Earnings Quality (0-100)
    # ------------------------------------------------------------------

    async def _earnings_quality(
        self,
        session: AsyncSession,
        security_id: UUID,
        entity_id: UUID,
        metrics: dict[str, float | None],
    ) -> list[EngineOutput]:
        outputs: list[EngineOutput] = []
        components: dict[str, Any] = {}
        missing_count = 0
        total_components = 4

        # --- Component 1: Accruals ratio (weight 30%) ---
        accruals = metrics.get("accruals_ratio")
        if accruals is not None:
            abs_accruals = abs(accruals)
            if abs_accruals < 0.05:
                accruals_score = 100.0
            elif abs_accruals <= 0.10:
                accruals_score = 70.0
            elif abs_accruals <= 0.20:
                accruals_score = 40.0
            else:
                accruals_score = 10.0
        else:
            accruals_score = 0.0
            missing_count += 1

        components["accruals_ratio"] = {
            "raw": accruals, "score": accruals_score, "weight": 0.30,
        }
        outputs.append(_build_output(
            security_id, entity_id,
            "eq_accruals_component", accruals_score,
            [make_input("accruals_ratio", "analytics_results", accruals)],
            data_quality="COMPLETE" if accruals is not None else "PARTIAL",
        ))

        # --- Component 2: Cash flow quality (weight 30%) ---
        ocf_ni = metrics.get("ocf_to_net_income")
        if ocf_ni is not None:
            if ocf_ni > 1.2:
                cfq_score = 100.0
            elif ocf_ni >= 1.0:
                cfq_score = 80.0
            elif ocf_ni >= 0.8:
                cfq_score = 50.0
            else:
                cfq_score = 20.0
        else:
            cfq_score = 0.0
            missing_count += 1

        components["ocf_to_net_income"] = {
            "raw": ocf_ni, "score": cfq_score, "weight": 0.30,
        }
        outputs.append(_build_output(
            security_id, entity_id,
            "eq_cashflow_quality_component", cfq_score,
            [make_input("ocf_to_net_income", "analytics_results", ocf_ni)],
            data_quality="COMPLETE" if ocf_ni is not None else "PARTIAL",
        ))

        # --- Component 3: Beneish M-Score (weight 20%) ---
        beneish = metrics.get("beneish_m_score")
        if beneish is not None:
            if beneish < -2.5:
                beneish_score = 100.0
            elif beneish <= -1.78:
                beneish_score = 60.0
            else:
                beneish_score = 20.0
        else:
            beneish_score = 0.0
            missing_count += 1

        components["beneish_m_score"] = {
            "raw": beneish, "score": beneish_score, "weight": 0.20,
        }
        outputs.append(_build_output(
            security_id, entity_id,
            "eq_beneish_component", beneish_score,
            [make_input("beneish_m_score", "analytics_results", beneish)],
            data_quality="COMPLETE" if beneish is not None else "PARTIAL",
        ))

        # --- Component 4: Revenue growth consistency (weight 20%) ---
        rev_history = await self._fetch_metric_history(
            session, security_id, "revenue_yoy", limit=5,
        )
        # [Bug 43 fix] Change from strict consecutive to a count out of 5
        positive_years = sum(1 for val in rev_history if val is not None and val > 0)

        if len(rev_history) == 0:
            rev_score = 0.0
            missing_count += 1
        elif positive_years >= 5:
            rev_score = 100.0
        elif positive_years >= 3:
            rev_score = 70.0
        else:
            rev_score = 30.0

        components["revenue_growth_consistency"] = {
            "positive_years_out_of_5": positive_years,
            "score": rev_score,
            "weight": 0.20,
        }
        outputs.append(_build_output(
            security_id, entity_id,
            "eq_revenue_consistency_component", rev_score,
            [make_input(
                "revenue_yoy_history", "analytics_results",
                positive_years,
            )],
            data_quality="COMPLETE" if len(rev_history) > 0 else "PARTIAL",
        ))

        # --- Weighted composite ---
        if missing_count > total_components // 2:
            data_quality = "INSUFFICIENT_DATA"
            composite = None
            classification = "INSUFFICIENT_DATA"
        else:
            data_quality = "PARTIAL" if missing_count > 0 else "COMPLETE"
            wt_acc = 0.30 if accruals is not None else 0.0
            wt_cfq = 0.30 if ocf_ni is not None else 0.0
            wt_ben = 0.20 if beneish is not None else 0.0
            wt_rev = 0.20 if len(rev_history) > 0 else 0.0
            used_wt = wt_acc + wt_cfq + wt_ben + wt_rev
            
            raw_score = (
                accruals_score * wt_acc
                + cfq_score * wt_cfq
                + beneish_score * wt_ben
                + rev_score * wt_rev
            )
            # [Bug 42 fix] Scale by used weight instead of assuming missing = 0
            composite = raw_score / used_wt if used_wt > 0 else 0.0
            
            if composite >= 80:
                classification = "HIGH"
            elif composite >= 60:
                classification = "MODERATE"
            elif composite >= 40:
                classification = "LOW"
            else:
                classification = "POOR"

        components["composite"] = composite
        components["classification"] = classification

        outputs.append(_build_output(
            security_id, entity_id,
            "earnings_quality_score", composite,
            [
                make_input("accruals_component", "derived", accruals_score),
                make_input("cfq_component", "derived", cfq_score),
                make_input("beneish_component", "derived", beneish_score),
                make_input("revenue_component", "derived", rev_score),
            ],
            data_quality=data_quality,
        ))

        outputs.append(_build_output(
            security_id, entity_id,
            "earnings_quality_classification", None,
            [make_input("earnings_quality_score", "derived", composite)],
            data_quality=data_quality,
            unit="CLASSIFICATION",
        ))
        outputs[-1].inputs.append(  # type: ignore[union-attr]
            make_input(
                name="classification", source="derived",
                value=None, period=classification,
            )
        )

        await self._persist_composite(
            session, security_id, entity_id,
            "earnings_quality", composite, classification,
            components, data_quality,
        )

        return outputs

    # ------------------------------------------------------------------
    # Score 2: Financial Strength (0-100)
    # ------------------------------------------------------------------

    async def _financial_strength(
        self,
        session: AsyncSession,
        security_id: UUID,
        entity_id: UUID,
        metrics: dict[str, float | None],
    ) -> list[EngineOutput]:
        outputs: list[EngineOutput] = []
        components: dict[str, Any] = {}
        missing_count = 0
        total_components = 5

        # --- Component 1: Interest coverage (weight 25%) ---
        int_cov = metrics.get("interest_coverage")
        if int_cov is not None:
            if int_cov > 8:
                ic_score = 100.0
            elif int_cov >= 4:
                ic_score = 75.0
            elif int_cov >= 2:
                ic_score = 50.0
            elif int_cov >= 1:
                ic_score = 25.0
            else:
                ic_score = 0.0
        else:
            ic_score = 0.0
            missing_count += 1

        components["interest_coverage"] = {
            "raw": int_cov, "score": ic_score, "weight": 0.25,
        }
        outputs.append(_build_output(
            security_id, entity_id,
            "fs_interest_coverage_component", ic_score,
            [make_input("interest_coverage", "analytics_results", int_cov)],
            data_quality="COMPLETE" if int_cov is not None else "PARTIAL",
        ))

        # --- Component 2: Net debt to EBITDA (weight 25%) ---
        nd_ebitda = metrics.get("net_debt_to_ebitda")
        if nd_ebitda is not None:
            if nd_ebitda < 1:
                nde_score = 100.0
            elif nd_ebitda <= 2:
                nde_score = 80.0
            elif nd_ebitda <= 3:
                nde_score = 60.0
            elif nd_ebitda <= 5:
                nde_score = 30.0
            else:
                nde_score = 10.0
        else:
            nde_score = 0.0
            missing_count += 1

        components["net_debt_to_ebitda"] = {
            "raw": nd_ebitda, "score": nde_score, "weight": 0.25,
        }
        outputs.append(_build_output(
            security_id, entity_id,
            "fs_net_debt_ebitda_component", nde_score,
            [make_input("net_debt_to_ebitda", "analytics_results", nd_ebitda)],
            data_quality="COMPLETE" if nd_ebitda is not None else "PARTIAL",
        ))

        # --- Component 3: Current ratio (weight 15%) ---
        cr = metrics.get("current_ratio")
        if cr is not None:
            if 1.5 <= cr <= 3.0:
                cr_score = 100.0
            elif cr > 3.0:
                cr_score = 70.0  # too high = idle assets
            elif cr >= 1.0:
                cr_score = 60.0
            else:
                cr_score = 20.0
        else:
            cr_score = 0.0
            missing_count += 1

        components["current_ratio"] = {
            "raw": cr, "score": cr_score, "weight": 0.15,
        }
        outputs.append(_build_output(
            security_id, entity_id,
            "fs_current_ratio_component", cr_score,
            [make_input("current_ratio", "analytics_results", cr)],
            data_quality="COMPLETE" if cr is not None else "PARTIAL",
        ))

        # --- Component 4: FCF to debt (weight 20%) ---
        fcf = metrics.get("free_cash_flow")
        total_debt = metrics.get("total_debt")
        if fcf is not None and total_debt is not None and total_debt != 0:
            fcf_to_debt = fcf / total_debt
        else:
            fcf_to_debt = None

        if fcf_to_debt is not None:
            if fcf_to_debt > 0.3:
                ftd_score = 100.0
            elif fcf_to_debt >= 0.15:
                ftd_score = 70.0
            elif fcf_to_debt >= 0.05:
                ftd_score = 40.0
            else:
                ftd_score = 10.0
        else:
            ftd_score = 0.0
            missing_count += 1

        components["fcf_to_debt"] = {
            "raw": fcf_to_debt, "score": ftd_score, "weight": 0.20,
        }
        outputs.append(_build_output(
            security_id, entity_id,
            "fs_fcf_to_debt_component", ftd_score,
            [
                make_input("free_cash_flow", "analytics_results", fcf),
                make_input("total_debt", "analytics_results", total_debt),
            ],
            data_quality="COMPLETE" if fcf_to_debt is not None else "PARTIAL",
        ))

        # --- Component 5: Altman Z-Score (weight 15%) ---
        altman = metrics.get("altman_z_score")
        if altman is not None:
            if altman > 3.0:
                az_score = 100.0
            elif altman >= 2.0:
                az_score = 70.0
            elif altman >= 1.0:
                az_score = 40.0
            else:
                az_score = 10.0
        else:
            az_score = 0.0
            missing_count += 1

        components["altman_z_score"] = {
            "raw": altman, "score": az_score, "weight": 0.15,
        }
        outputs.append(_build_output(
            security_id, entity_id,
            "fs_altman_z_component", az_score,
            [make_input("altman_z_score", "analytics_results", altman)],
            data_quality="COMPLETE" if altman is not None else "PARTIAL",
        ))

        # --- Weighted composite ---
        if missing_count > total_components // 2:
            data_quality = "INSUFFICIENT_DATA"
            composite = None
            classification = "INSUFFICIENT_DATA"
        else:
            data_quality = "PARTIAL" if missing_count > 0 else "COMPLETE"
            wt_ic = 0.25 if int_cov is not None else 0.0
            wt_nd = 0.25 if nd_ebitda is not None else 0.0
            wt_cr = 0.15 if cr is not None else 0.0
            wt_fcf = 0.20 if fcf_to_debt is not None else 0.0
            wt_az = 0.15 if altman is not None else 0.0
            used_wt = wt_ic + wt_nd + wt_cr + wt_fcf + wt_az
            
            raw_score = (
                ic_score * wt_ic
                + nde_score * wt_nd
                + cr_score * wt_cr
                + ftd_score * wt_fcf
                + az_score * wt_az
            )
            # [Bug 42 fix] Scale by used weight instead of assuming missing = 0
            composite = raw_score / used_wt if used_wt > 0 else 0.0
            
            if composite >= 80:
                classification = "STRONG"
            elif composite >= 60:
                classification = "MODERATE"
            elif composite >= 40:
                classification = "WEAK"
            else:
                classification = "DISTRESSED"

        components["composite"] = composite
        components["classification"] = classification

        outputs.append(_build_output(
            security_id, entity_id,
            "financial_strength_score", composite,
            [
                make_input("ic_component", "derived", ic_score),
                make_input("nde_component", "derived", nde_score),
                make_input("cr_component", "derived", cr_score),
                make_input("ftd_component", "derived", ftd_score),
                make_input("az_component", "derived", az_score),
            ],
            data_quality=data_quality,
        ))

        outputs.append(_build_output(
            security_id, entity_id,
            "financial_strength_classification", None,
            [make_input("financial_strength_score", "derived", composite)],
            data_quality=data_quality,
            unit="CLASSIFICATION",
        ))
        outputs[-1].inputs.append(  # type: ignore[union-attr]
            make_input(
                name="classification", source="derived",
                value=None, period=classification,
            )
        )

        await self._persist_composite(
            session, security_id, entity_id,
            "financial_strength", composite, classification,
            components, data_quality,
        )

        # [Bug 44 fix] Check if we should compute the credit-aware supplement
        o_score = metrics.get("ohlson_o_score")
        m_dd = metrics.get("merton_dd")
        c_mom = metrics.get("credit_momentum")

        if any(v is not None for v in (o_score, m_dd, c_mom)):
            credit_aware = compute_credit_aware_financial_strength(
                composite, o_score, m_dd, c_mom
            )
            cr_score = credit_aware["score"]
            cr_class = credit_aware["classification"]
            if cr_score is not None:
                outputs.append(_build_output(
                    security_id, entity_id,
                    "credit_aware_financial_strength_score", cr_score,
                    [
                        make_input("base_financial_strength", "derived", composite),
                        make_input("ohlson_o_score", "analytics_results", o_score),
                        make_input("merton_dd", "analytics_results", m_dd),
                        make_input("credit_momentum", "analytics_results", c_mom),
                    ],
                    data_quality=credit_aware.get("data_quality", "PARTIAL"),
                ))
            if cr_class is not None:
                outputs.append(_build_output(
                    security_id, entity_id,
                    "credit_aware_financial_strength_classification", None,
                    [make_input("credit_aware_financial_strength_score", "derived", cr_score)],
                    data_quality=credit_aware.get("data_quality", "PARTIAL"),
                    unit="CLASSIFICATION",
                ))
                outputs[-1].inputs.append(  # type: ignore[union-attr]
                    make_input(
                        name="classification", source="derived",
                        value=None, period=cr_class,
                    )
                )

        return outputs

    # ------------------------------------------------------------------
    # Score 3: Dividend Safety (point-based)
    # ------------------------------------------------------------------

    async def _dividend_safety(
        self,
        session: AsyncSession,
        security_id: UUID,
        entity_id: UUID,
        metrics: dict[str, float | None],
    ) -> list[EngineOutput]:
        outputs: list[EngineOutput] = []
        components: dict[str, Any] = {}
        missing_count = 0
        total_components = 4

        # --- Component 1: Payout ratio (earnings) ---
        payout = metrics.get("payout_ratio")
        if payout is not None:
            if payout < 0.50:
                pr_pts = 2
            elif payout <= 0.75:
                pr_pts = 1
            elif payout <= 1.0:
                pr_pts = 0
            else:
                pr_pts = -1
        else:
            pr_pts = 0
            missing_count += 1

        components["payout_ratio"] = {"raw": payout, "points": pr_pts}
        outputs.append(_build_output(
            security_id, entity_id,
            "ds_payout_ratio_component", float(pr_pts),
            [make_input("payout_ratio", "analytics_results", payout)],
            data_quality="COMPLETE" if payout is not None else "PARTIAL",
            unit="SCORE",
        ))

        # --- Component 2: FCF payout ratio ---
        fcf_payout = metrics.get("fcf_payout_ratio")
        if fcf_payout is not None:
            if fcf_payout < 0.60:
                fcfp_pts = 2
            elif fcf_payout <= 0.80:
                fcfp_pts = 1
            elif fcf_payout <= 1.0:
                fcfp_pts = 0
            else:
                fcfp_pts = -1
        else:
            fcfp_pts = 0
            missing_count += 1

        components["fcf_payout_ratio"] = {"raw": fcf_payout, "points": fcfp_pts}
        outputs.append(_build_output(
            security_id, entity_id,
            "ds_fcf_payout_component", float(fcfp_pts),
            [make_input("fcf_payout_ratio", "analytics_results", fcf_payout)],
            data_quality="COMPLETE" if fcf_payout is not None else "PARTIAL",
            unit="SCORE",
        ))

        # --- Component 3: Debt to EBITDA ---
        nd_ebitda = metrics.get("net_debt_to_ebitda")
        if nd_ebitda is not None:
            if nd_ebitda < 2:
                de_pts = 1
            elif nd_ebitda <= 4:
                de_pts = 0
            else:
                de_pts = -1
        else:
            de_pts = 0
            missing_count += 1

        components["debt_to_ebitda"] = {"raw": nd_ebitda, "points": de_pts}
        outputs.append(_build_output(
            security_id, entity_id,
            "ds_debt_ebitda_component", float(de_pts),
            [make_input("net_debt_to_ebitda", "analytics_results", nd_ebitda)],
            data_quality="COMPLETE" if nd_ebitda is not None else "PARTIAL",
            unit="SCORE",
        ))

        # --- Component 4: Piotroski F-Score ---
        piotroski = metrics.get("piotroski_f_score")
        if piotroski is not None:
            if piotroski >= 7:
                pf_pts = 1
            elif piotroski >= 4:
                pf_pts = 0
            else:
                pf_pts = -1
        else:
            pf_pts = 0
            missing_count += 1

        components["piotroski_f_score"] = {"raw": piotroski, "points": pf_pts}
        outputs.append(_build_output(
            security_id, entity_id,
            "ds_piotroski_component", float(pf_pts),
            [make_input("piotroski_f_score", "analytics_results", piotroski)],
            data_quality="COMPLETE" if piotroski is not None else "PARTIAL",
            unit="SCORE",
        ))

        # --- Total points and classification ---
        raw_pts = pr_pts + fcfp_pts + de_pts + pf_pts

        if missing_count > total_components // 2:
            data_quality = "INSUFFICIENT_DATA"
            classification = "INSUFFICIENT_DATA"
            total_pts = 0.0
        else:
            data_quality = "PARTIAL" if missing_count > 0 else "COMPLETE"
            # [Bug 42 fix] Prorate points up to fully available set
            available = total_components - missing_count
            total_pts = raw_pts * (total_components / available) if available > 0 else 0.0
            
            if total_pts >= 5:
                classification = "SAFE"
            elif total_pts >= 3:
                classification = "BORDERLINE"
            elif total_pts >= 1:
                classification = "AT_RISK"
            else:
                classification = "DANGEROUS"

        components["total_points"] = total_pts
        components["classification"] = classification

        outputs.append(_build_output(
            security_id, entity_id,
            "dividend_safety_score", float(total_pts),
            [
                make_input("payout_ratio_pts", "derived", float(pr_pts)),
                make_input("fcf_payout_pts", "derived", float(fcfp_pts)),
                make_input("debt_ebitda_pts", "derived", float(de_pts)),
                make_input("piotroski_pts", "derived", float(pf_pts)),
            ],
            data_quality=data_quality,
        ))

        outputs.append(_build_output(
            security_id, entity_id,
            "dividend_safety_classification", None,
            [make_input("dividend_safety_score", "derived", float(total_pts))],
            data_quality=data_quality,
            unit="CLASSIFICATION",
        ))
        outputs[-1].inputs.append(  # type: ignore[union-attr]
            make_input(
                name="classification", source="derived",
                value=None, period=classification,
            )
        )

        await self._persist_composite(
            session, security_id, entity_id,
            "dividend_safety", float(total_pts), classification,
            components, data_quality,
        )

        return outputs

    # ------------------------------------------------------------------
    # Score 4: Value Trap Risk (point-based)
    # ------------------------------------------------------------------

    async def _value_trap_risk(
        self,
        session: AsyncSession,
        security_id: UUID,
        entity_id: UUID,
        metrics: dict[str, float | None],
    ) -> list[EngineOutput]:
        outputs: list[EngineOutput] = []
        components: dict[str, Any] = {}
        trap_pts = 0
        checks_performed = 0
        total_checks = 5

        # --- Check 1: Low P/E + declining margins ---
        pe = metrics.get("pe_trailing")
        gm_yoy = metrics.get("gross_margin_yoy")
        om_yoy = metrics.get("operating_margin_yoy")
        c1_triggered = False

        if pe is not None and (gm_yoy is not None or om_yoy is not None):
            checks_performed += 1
            margin_declining = (
                (gm_yoy is not None and gm_yoy < 0)
                or (om_yoy is not None and om_yoy < 0)
            )
            if pe < 12 and margin_declining:
                trap_pts += 2
                c1_triggered = True
        else:
            # Not enough data for this check — do not penalise
            pass

        components["low_pe_declining_margins"] = {
            "pe_trailing": pe,
            "gross_margin_yoy": gm_yoy,
            "operating_margin_yoy": om_yoy,
            "triggered": c1_triggered,
            "points": 2 if c1_triggered else 0,
        }
        outputs.append(_build_output(
            security_id, entity_id,
            "vt_pe_margin_check", 2.0 if c1_triggered else 0.0,
            [
                make_input("pe_trailing", "analytics_results", pe),
                make_input("gross_margin_yoy", "analytics_results", gm_yoy),
                make_input("operating_margin_yoy", "analytics_results", om_yoy),
            ],
            data_quality="COMPLETE" if pe is not None else "PARTIAL",
        ))

        # --- Check 2: Low P/B + declining ROE ---
        pb = metrics.get("pb")
        roe_yoy = metrics.get("roe_yoy")
        c2_triggered = False

        if pb is not None and roe_yoy is not None:
            checks_performed += 1
            if pb < 1.0 and roe_yoy < 0:
                trap_pts += 2
                c2_triggered = True
        else:
            pass

        components["low_pb_declining_roe"] = {
            "pb": pb, "roe_yoy": roe_yoy,
            "triggered": c2_triggered,
            "points": 2 if c2_triggered else 0,
        }
        outputs.append(_build_output(
            security_id, entity_id,
            "vt_pb_roe_check", 2.0 if c2_triggered else 0.0,
            [
                make_input("pb", "analytics_results", pb),
                make_input("roe_yoy", "analytics_results", roe_yoy),
            ],
            data_quality="COMPLETE" if (pb is not None and roe_yoy is not None) else "PARTIAL",
        ))

        # --- Check 3: High yield + rising payout ---
        div_yield = metrics.get("dividend_yield")
        payout = metrics.get("payout_ratio")
        c3_triggered = False

        if div_yield is not None and payout is not None:
            checks_performed += 1
            if div_yield > 0.04 and payout > 0.80:
                trap_pts += 2
                c3_triggered = True
        else:
            pass

        components["high_yield_rising_payout"] = {
            "dividend_yield": div_yield, "payout_ratio": payout,
            "triggered": c3_triggered,
            "points": 2 if c3_triggered else 0,
        }
        outputs.append(_build_output(
            security_id, entity_id,
            "vt_yield_payout_check", 2.0 if c3_triggered else 0.0,
            [
                make_input("dividend_yield", "analytics_results", div_yield),
                make_input("payout_ratio", "analytics_results", payout),
            ],
            data_quality="COMPLETE" if (div_yield is not None and payout is not None) else "PARTIAL",
        ))

        # --- Check 4: Cheap EV/EBITDA + negative FCF trend ---
        ev_ebitda = metrics.get("ev_ebitda")
        fcf_yoy = metrics.get("free_cash_flow_yoy")
        c4_triggered = False

        if ev_ebitda is not None and fcf_yoy is not None:
            checks_performed += 1
            if ev_ebitda < 6 and fcf_yoy < -0.10:
                trap_pts += 2
                c4_triggered = True
        else:
            pass

        components["cheap_ev_negative_fcf"] = {
            "ev_ebitda": ev_ebitda, "free_cash_flow_yoy": fcf_yoy,
            "triggered": c4_triggered,
            "points": 2 if c4_triggered else 0,
        }
        outputs.append(_build_output(
            security_id, entity_id,
            "vt_ev_fcf_check", 2.0 if c4_triggered else 0.0,
            [
                make_input("ev_ebitda", "analytics_results", ev_ebitda),
                make_input("free_cash_flow_yoy", "analytics_results", fcf_yoy),
            ],
            data_quality="COMPLETE" if (ev_ebitda is not None and fcf_yoy is not None) else "PARTIAL",
        ))

        # --- Check 5: Piotroski < 4 ---
        piotroski = metrics.get("piotroski_f_score")
        c5_triggered = False

        if piotroski is not None:
            checks_performed += 1
            if piotroski < 4:
                trap_pts += 1
                c5_triggered = True
        else:
            pass

        components["weak_piotroski"] = {
            "piotroski_f_score": piotroski,
            "triggered": c5_triggered,
            "points": 1 if c5_triggered else 0,
        }
        outputs.append(_build_output(
            security_id, entity_id,
            "vt_piotroski_check", 1.0 if c5_triggered else 0.0,
            [make_input("piotroski_f_score", "analytics_results", piotroski)],
            data_quality="COMPLETE" if piotroski is not None else "PARTIAL",
        ))

        # --- Total trap points and classification ---
        if checks_performed < total_checks // 2:
            data_quality = "INSUFFICIENT_DATA"
            classification = "INSUFFICIENT_DATA"
            trap_pts = 0.0
        else:
            data_quality = (
                "PARTIAL" if checks_performed < total_checks else "COMPLETE"
            )
            # [Bug 42 fix] Prorate trap points by checks performed
            trap_pts = float(trap_pts) * (total_checks / checks_performed) if checks_performed > 0 else 0.0
            
            if trap_pts <= 1:
                classification = "LOW_RISK"
            elif trap_pts <= 3:
                classification = "MODERATE_RISK"
            elif trap_pts <= 5:
                classification = "HIGH_RISK"
            else:
                classification = "VALUE_TRAP_WARNING"

        components["total_trap_points"] = trap_pts
        components["checks_performed"] = checks_performed
        components["classification"] = classification

        outputs.append(_build_output(
            security_id, entity_id,
            "value_trap_risk_score", float(trap_pts),
            [
                make_input("pe_margin_pts", "derived", components["low_pe_declining_margins"]["points"]),
                make_input("pb_roe_pts", "derived", components["low_pb_declining_roe"]["points"]),
                make_input("yield_payout_pts", "derived", components["high_yield_rising_payout"]["points"]),
                make_input("ev_fcf_pts", "derived", components["cheap_ev_negative_fcf"]["points"]),
                make_input("piotroski_pts", "derived", components["weak_piotroski"]["points"]),
            ],
            data_quality=data_quality,
        ))

        outputs.append(_build_output(
            security_id, entity_id,
            "value_trap_risk_classification", None,
            [make_input("value_trap_risk_score", "derived", float(trap_pts))],
            data_quality=data_quality,
            unit="CLASSIFICATION",
        ))
        outputs[-1].inputs.append(  # type: ignore[union-attr]
            make_input(
                name="classification", source="derived",
                value=None, period=classification,
            )
        )

        await self._persist_composite(
            session, security_id, entity_id,
            "value_trap_risk", float(trap_pts), classification,
            components, data_quality,
        )

        return outputs


# ---------------------------------------------------------------------------
# Standalone: Credit-Aware Financial Strength (FI Supplement)
# ---------------------------------------------------------------------------

def _map_o_score(o_score: float) -> float:
    """Map Ohlson O-Score to a 0-100 component score (inverse: lower O = healthier)."""
    if o_score < -1.0:
        return 90.0
    elif o_score <= 0.0:
        return 70.0
    elif o_score <= 0.5:
        return 50.0
    elif o_score <= 1.0:
        return 30.0
    else:
        return 10.0


def _map_merton_dd(dd: float) -> float:
    """Map Merton distance-to-default to a 0-100 component score."""
    if dd > 4.0:
        return 95.0
    elif dd >= 3.0:
        return 80.0
    elif dd >= 2.0:
        return 60.0
    elif dd >= 1.0:
        return 35.0
    else:
        return 10.0


def _map_credit_momentum(momentum: float) -> float:
    """Map credit momentum score [-1, +1] linearly to [10, 90]."""
    # Clamp to valid range first
    clamped = max(-1.0, min(1.0, momentum))
    # Linear: -1 → 10, +1 → 90
    return 10.0 + (clamped + 1.0) * 40.0


def compute_credit_aware_financial_strength(
    financial_strength_score: float | None,
    ohlson_o_score: float | None,
    merton_dd: float | None,
    credit_momentum_score: float | None,
) -> dict:
    """Compute a credit-aware financial strength composite score.

    Combines the existing financial strength score with FI-specific credit
    risk metrics (Ohlson O-Score, Merton distance-to-default, and credit
    momentum) into a single 0-100 composite.

    Parameters
    ----------
    financial_strength_score:
        Existing financial strength score (0-100 scale).
    ohlson_o_score:
        Ohlson O-Score (lower = healthier).
    merton_dd:
        Merton distance-to-default (higher = safer).
    credit_momentum_score:
        Credit momentum score in [-1, +1] (positive = improving).

    Returns
    -------
    dict
        Composite result with score, classification, components, and data_quality.
    """
    # Base weights
    base_weights = {
        "financial_strength": 0.40,
        "ohlson_o_score": 0.25,
        "merton_dd": 0.20,
        "credit_momentum": 0.15,
    }

    # Map raw inputs to component scores
    raw_values = {
        "financial_strength": financial_strength_score,
        "ohlson_o_score": ohlson_o_score,
        "merton_dd": merton_dd,
        "credit_momentum": credit_momentum_score,
    }

    mapped_scores: dict[str, float | None] = {}

    if financial_strength_score is not None:
        mapped_scores["financial_strength"] = financial_strength_score
    else:
        mapped_scores["financial_strength"] = None

    if ohlson_o_score is not None:
        mapped_scores["ohlson_o_score"] = _map_o_score(ohlson_o_score)
    else:
        mapped_scores["ohlson_o_score"] = None

    if merton_dd is not None:
        mapped_scores["merton_dd"] = _map_merton_dd(merton_dd)
    else:
        mapped_scores["merton_dd"] = None

    if credit_momentum_score is not None:
        mapped_scores["credit_momentum"] = _map_credit_momentum(credit_momentum_score)
    else:
        mapped_scores["credit_momentum"] = None

    # Determine which components are available
    available = {k for k, v in mapped_scores.items() if v is not None}
    n_available = len(available)

    # Data quality
    if n_available == 4:
        data_quality = "COMPLETE"
    elif n_available >= 1:
        data_quality = "PARTIAL"
    else:
        data_quality = "INSUFFICIENT"

    # Compute normalized weights and composite score
    if n_available == 0:
        composite_score = None
        classification = None
        # All weights stay at base (no normalization needed since score is None)
        normalized_weights = dict(base_weights)
    else:
        # Sum of base weights for available components
        total_available_weight = sum(base_weights[k] for k in available)
        # Normalize weights so they sum to 1.0
        normalized_weights = {}
        for k in base_weights:
            if k in available:
                normalized_weights[k] = base_weights[k] / total_available_weight
            else:
                normalized_weights[k] = 0.0

        # Weighted sum
        composite_score = sum(
            mapped_scores[k] * normalized_weights[k]  # type: ignore[operator]
            for k in available
        )

        # Clamp to [0, 100]
        composite_score = max(0.0, min(100.0, composite_score))

        # Classification
        if composite_score > 75.0:
            classification = "STRONG"
        elif composite_score >= 50.0:
            classification = "ADEQUATE"
        elif composite_score >= 25.0:
            classification = "WEAK"
        else:
            classification = "DISTRESSED"

    # Build components dict
    components = {}
    for key in base_weights:
        components[key] = {
            "raw": raw_values[key],
            "score": mapped_scores[key],
            "weight": normalized_weights[key],
        }

    return {
        "score": composite_score,
        "classification": classification,
        "components": components,
        "data_quality": data_quality,
    }
