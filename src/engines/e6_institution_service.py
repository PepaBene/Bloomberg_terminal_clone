"""E6 Institution Service — query helper for institution-level endpoints.

Not a BaseEngine subclass.  Provides async methods to fetch institution
profiles, current holdings, position changes across quarters, multi-quarter
history summaries, investment style classification, and tier/type lookups.

All methods accept an ``AsyncSession`` first and return plain dicts/lists
suitable for API serialisation.
"""

from __future__ import annotations

import logging
import statistics
from datetime import date
from uuid import UUID

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.analytics import AnalyticsResult
from src.models.ownership import InstitutionalHolding, InstitutionProfile
from src.models.security import Security

logger = logging.getLogger(__name__)


def _f(val) -> float | None:
    """Convert a Decimal/numeric value to float, or None."""
    return float(val) if val is not None else None


class InstitutionService:
    """Query helper for institution-level data.

    Provides reusable async methods consumed by FastAPI endpoints and
    the broader E6 analytics pipeline.  All queries use SQLAlchemy 2.0
    ``select()`` patterns with ``AsyncSession``.
    """

    async def get_profile(
        self,
        session: AsyncSession,
        institution_id: UUID,
    ) -> dict | None:
        """Fetch institution profile by primary key.

        Returns a dict with all ``InstitutionProfile`` fields, or
        ``None`` if the institution does not exist.
        """
        stmt = select(InstitutionProfile).where(
            InstitutionProfile.institution_id == institution_id
        )
        result = await session.execute(stmt)
        profile = result.scalar_one_or_none()
        if profile is None:
            return None

        return {
            "institution_id": profile.institution_id,
            "entity_id": profile.entity_id,
            "cik": profile.cik,
            "institution_name": profile.institution_name,
            "institution_type": profile.institution_type,
            "tier": profile.tier,
            "aum": _f(profile.aum),
            "number_of_holdings": profile.number_of_holdings,
        }

    async def get_holdings(
        self,
        session: AsyncSession,
        institution_id: UUID,
        report_date: date | None = None,
    ) -> list[dict]:
        """Get current holdings for an institution.

        If *report_date* is not specified, uses the latest available
        report_date for this institution.  Joins with ``Security`` to
        include name and security_type.
        """
        # Resolve report_date if not provided
        if report_date is None:
            latest_stmt = (
                select(func.max(InstitutionalHolding.report_date))
                .where(InstitutionalHolding.institution_id == institution_id)
            )
            latest_result = await session.execute(latest_stmt)
            report_date = latest_result.scalar_one_or_none()
            if report_date is None:
                return []

        stmt = (
            select(InstitutionalHolding, Security.name, Security.security_type)
            .outerjoin(
                Security,
                InstitutionalHolding.security_id == Security.security_id,
            )
            .where(
                InstitutionalHolding.institution_id == institution_id,
                InstitutionalHolding.report_date == report_date,
            )
            .order_by(desc(InstitutionalHolding.market_value))
        )
        result = await session.execute(stmt)
        rows = result.all()

        holdings: list[dict] = []
        for holding, sec_name, sec_type in rows:
            holdings.append({
                "security_id": holding.security_id,
                "security_name": sec_name,
                "security_type": sec_type,
                "report_date": holding.report_date,
                "shares_held": _f(holding.shares_held),
                "market_value": _f(holding.market_value),
                "percent_of_portfolio": _f(holding.percent_of_portfolio),
                "percent_of_outstanding": _f(holding.percent_of_outstanding),
                "shares_change": _f(holding.shares_change),
                "is_new_position": holding.is_new_position,
                "is_sold_out": holding.is_sold_out,
                "source": holding.source,
            })

        return holdings

    async def get_changes(
        self,
        session: AsyncSession,
        institution_id: UUID,
        quarters: int = 4,
    ) -> list[dict]:
        """Get position changes across consecutive quarters.

        Compares each consecutive pair of report_dates for the
        institution. Returns a flat list of change records covering
        the requested number of quarters.
        """
        # Fetch distinct report_dates (need quarters + 1 to form pairs)
        dates_stmt = (
            select(InstitutionalHolding.report_date)
            .where(InstitutionalHolding.institution_id == institution_id)
            .distinct()
            .order_by(desc(InstitutionalHolding.report_date))
            .limit(quarters + 1)
        )
        dates_result = await session.execute(dates_stmt)
        all_dates: list[date] = [row[0] for row in dates_result.all()]

        if len(all_dates) < 2:
            return []

        changes: list[dict] = []

        for i in range(len(all_dates) - 1):
            later_date = all_dates[i]
            earlier_date = all_dates[i + 1]

            # Fetch holdings for both quarters
            later_stmt = (
                select(InstitutionalHolding, Security.name)
                .outerjoin(
                    Security,
                    InstitutionalHolding.security_id == Security.security_id,
                )
                .where(
                    InstitutionalHolding.institution_id == institution_id,
                    InstitutionalHolding.report_date == later_date,
                )
            )
            earlier_stmt = (
                select(InstitutionalHolding, Security.name)
                .outerjoin(
                    Security,
                    InstitutionalHolding.security_id == Security.security_id,
                )
                .where(
                    InstitutionalHolding.institution_id == institution_id,
                    InstitutionalHolding.report_date == earlier_date,
                )
            )

            later_result = await session.execute(later_stmt)
            earlier_result = await session.execute(earlier_stmt)

            later_map: dict[UUID, tuple] = {
                row[0].security_id: (row[0], row[1])
                for row in later_result.all()
            }
            earlier_map: dict[UUID, tuple] = {
                row[0].security_id: (row[0], row[1])
                for row in earlier_result.all()
            }

            all_sids = set(later_map.keys()) | set(earlier_map.keys())

            for sid in all_sids:
                later_holding, later_name = later_map.get(sid, (None, None))
                earlier_holding, earlier_name = earlier_map.get(sid, (None, None))
                sec_name = later_name or earlier_name

                if later_holding is not None and earlier_holding is None:
                    # New position
                    changes.append({
                        "security_id": sid,
                        "security_name": sec_name,
                        "report_date": later_date,
                        "prior_date": earlier_date,
                        "prior_shares": None,
                        "current_shares": _f(later_holding.shares_held),
                        "shares_change": _f(later_holding.shares_held),
                        "change_type": "NEW_POSITION",
                        "percent_change": None,
                        "market_value": _f(later_holding.market_value),
                    })
                elif later_holding is None and earlier_holding is not None:
                    # Closed position
                    changes.append({
                        "security_id": sid,
                        "security_name": sec_name,
                        "report_date": later_date,
                        "prior_date": earlier_date,
                        "prior_shares": _f(earlier_holding.shares_held),
                        "current_shares": 0.0,
                        "shares_change": -(_f(earlier_holding.shares_held) or 0.0),
                        "change_type": "CLOSED_POSITION",
                        "percent_change": -1.0,
                        "market_value": 0.0,
                    })
                else:
                    # Both exist — determine INCREASED / DECREASED
                    prior_shares = _f(earlier_holding.shares_held) or 0.0  # type: ignore[union-attr]
                    current_shares = _f(later_holding.shares_held) or 0.0  # type: ignore[union-attr]
                    sc = _f(later_holding.shares_change) or (current_shares - prior_shares)  # type: ignore[union-attr]
                    pct = (sc / prior_shares) if prior_shares != 0 else None

                    if sc > 0:
                        ctype = "INCREASED"
                    elif sc < 0:
                        ctype = "DECREASED"
                    else:
                        ctype = "UNCHANGED"

                    changes.append({
                        "security_id": sid,
                        "security_name": sec_name,
                        "report_date": later_date,
                        "prior_date": earlier_date,
                        "prior_shares": prior_shares,
                        "current_shares": current_shares,
                        "shares_change": sc,
                        "change_type": ctype,
                        "percent_change": pct,
                        "market_value": _f(later_holding.market_value),  # type: ignore[union-attr]
                    })

        return changes

    async def get_history(
        self,
        session: AsyncSession,
        institution_id: UUID,
        periods: int = 8,
    ) -> list[dict]:
        """Multi-quarter summary for an institution.

        Returns one dict per quarter with total_positions, total_value,
        new_positions, and closed_positions counts.
        """
        # Fetch distinct report_dates
        dates_stmt = (
            select(InstitutionalHolding.report_date)
            .where(InstitutionalHolding.institution_id == institution_id)
            .distinct()
            .order_by(desc(InstitutionalHolding.report_date))
            .limit(periods)
        )
        dates_result = await session.execute(dates_stmt)
        all_dates: list[date] = [row[0] for row in dates_result.all()]

        if not all_dates:
            return []

        history: list[dict] = []

        for rd in all_dates:
            # Aggregate counts and value for this report_date
            agg_stmt = select(
                func.count().label("total_positions"),
                func.sum(InstitutionalHolding.market_value).label("total_value"),
                func.sum(
                    func.cast(InstitutionalHolding.is_new_position, func.integer())  # type: ignore[attr-defined]
                ).label("new_positions"),
                func.sum(
                    func.cast(InstitutionalHolding.is_sold_out, func.integer())  # type: ignore[attr-defined]
                ).label("closed_positions"),
            ).where(
                InstitutionalHolding.institution_id == institution_id,
                InstitutionalHolding.report_date == rd,
            )
            agg_result = await session.execute(agg_stmt)
            row = agg_result.one_or_none()

            if row is None:
                continue

            # Use CASE expression fallback for boolean sum
            # Some DBs may not support casting bool -> int directly
            new_count_stmt = select(
                func.count()
            ).where(
                InstitutionalHolding.institution_id == institution_id,
                InstitutionalHolding.report_date == rd,
                InstitutionalHolding.is_new_position.is_(True),
            )
            new_result = await session.execute(new_count_stmt)
            new_count = new_result.scalar_one() or 0

            closed_count_stmt = select(
                func.count()
            ).where(
                InstitutionalHolding.institution_id == institution_id,
                InstitutionalHolding.report_date == rd,
                InstitutionalHolding.is_sold_out.is_(True),
            )
            closed_result = await session.execute(closed_count_stmt)
            closed_count = closed_result.scalar_one() or 0

            history.append({
                "report_date": rd,
                "total_positions": row[0] or 0,
                "total_value": _f(row[1]),
                "new_positions": new_count,
                "closed_positions": closed_count,
            })

        return history

    async def classify_style(
        self,
        session: AsyncSession,
        institution_id: UUID,
    ) -> str:
        """Classify investment style based on holdings characteristics.

        Decision tree:
        1. Fetch top 50 holdings by market_value (latest report_date)
        2. Join with AnalyticsResult to get PE_TRAILING and revenue_yoy
        3. If median P/E < 15 and median P/B < 2 -> ``"VALUE"``
        4. If median revenue_yoy > 0.15 -> ``"GROWTH"``
        5. If number_of_holdings < 30 and top-10 concentration > 0.50 -> ``"CONCENTRATED"``
        6. If number_of_holdings > 200 -> ``"DIVERSIFIED"``
        7. Default -> ``"GARP"``
        """
        # Resolve latest report_date
        latest_stmt = (
            select(func.max(InstitutionalHolding.report_date))
            .where(InstitutionalHolding.institution_id == institution_id)
        )
        latest_result = await session.execute(latest_stmt)
        latest_date = latest_result.scalar_one_or_none()
        if latest_date is None:
            return "GARP"

        # Total holdings count for this quarter
        count_stmt = select(
            func.count()
        ).where(
            InstitutionalHolding.institution_id == institution_id,
            InstitutionalHolding.report_date == latest_date,
        )
        count_result = await session.execute(count_stmt)
        total_holdings = count_result.scalar_one() or 0

        # Top 50 holdings by market_value
        top_stmt = (
            select(InstitutionalHolding)
            .where(
                InstitutionalHolding.institution_id == institution_id,
                InstitutionalHolding.report_date == latest_date,
            )
            .order_by(desc(InstitutionalHolding.market_value))
            .limit(50)
        )
        top_result = await session.execute(top_stmt)
        top_holdings = top_result.scalars().all()

        if not top_holdings:
            return "GARP"

        # Collect security_ids for analytics lookup
        security_ids = [h.security_id for h in top_holdings]

        # Fetch PE_TRAILING for each security (most recent value)
        pe_values: list[float] = []
        pb_values: list[float] = []
        rev_yoy_values: list[float] = []

        if security_ids:
            for metric_name, target_list in [
                ("pe_trailing", pe_values),
                ("pb", pb_values),
                ("revenue_yoy", rev_yoy_values),
            ]:
                # Use ROW_NUMBER window to get the latest value per security
                ranked = (
                    select(
                        AnalyticsResult.security_id,
                        AnalyticsResult.value,
                        func.row_number().over(
                            partition_by=AnalyticsResult.security_id,
                            order_by=AnalyticsResult.as_of_date.desc(),
                        ).label("rn"),
                    ).where(
                        AnalyticsResult.security_id.in_(security_ids),
                        AnalyticsResult.metric_name == metric_name,
                        AnalyticsResult.value.isnot(None),
                    ).subquery()
                )
                metric_stmt = select(ranked.c.value).where(ranked.c.rn == 1)
                metric_result = await session.execute(metric_stmt)
                for (val,) in metric_result.all():
                    target_list.append(float(val))

        # Compute medians (safely handle empty lists)
        median_pe = statistics.median(pe_values) if pe_values else None
        median_pb = statistics.median(pb_values) if pb_values else None
        median_rev_yoy = statistics.median(rev_yoy_values) if rev_yoy_values else None

        # Top-10 concentration
        total_value = sum(_f(h.market_value) or 0.0 for h in top_holdings)
        top_10_value = sum(
            _f(h.market_value) or 0.0
            for h in top_holdings[:10]
        )
        top_10_concentration = top_10_value / max(total_value, 1.0)

        # Decision tree
        if median_pe is not None and median_pb is not None:
            if median_pe < 15 and median_pb < 2:
                return "VALUE"

        if median_rev_yoy is not None and median_rev_yoy > 0.15:
            return "GROWTH"

        if total_holdings < 30 and top_10_concentration > 0.50:
            return "CONCENTRATED"

        if total_holdings > 200:
            return "DIVERSIFIED"

        return "GARP"

    async def get_by_tier(
        self,
        session: AsyncSession,
        tier: str,
    ) -> list[InstitutionProfile]:
        """Get all InstitutionProfile rows matching the specified tier."""
        stmt = select(InstitutionProfile).where(
            InstitutionProfile.tier == tier
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_type(
        self,
        session: AsyncSession,
        inst_type: str,
    ) -> list[InstitutionProfile]:
        """Get all InstitutionProfile rows matching the specified institution_type."""
        stmt = select(InstitutionProfile).where(
            InstitutionProfile.institution_type == inst_type
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())
