"""E4 Screening & Ranking Engine.

A query engine that filters and ranks securities based on pre-computed
analytics (Pillar 2) and reference data (Pillar 1).  Unlike E1-E3 this
is NOT a BaseEngine subclass — it does not produce new metrics but
instead queries existing ones to power security discovery.

The screening pipeline:
    1. Accept a filter tree (ScreenFilterGroup) with AND/OR/NOT logic.
    2. Translate each leaf filter into a SQLAlchemy subquery that returns
       matching ``security_id`` values from the appropriate source table.
    3. Combine subqueries with set logic (intersect / union / except).
    4. Optionally constrain to a universe of security IDs.
    5. Enrich matches with security name, ticker, and requested metrics.
    6. Optionally rank matches using a multi-factor composite percentile
       scoring model.

Part of Pillar 2 analytics — consumes AnalyticsResult, Entity, Security,
OwnershipSummary, and InstitutionalFlowSignal data.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID
from datetime import date, datetime, timezone

from sqlalchemy import select, func, and_, or_, not_, desc, asc, Numeric as SANumeric
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.analytics import AnalyticsResult
from src.models.entity import Entity
from src.models.security import Security
from src.models.ownership import OwnershipSummary
from src.models.screening import SavedScreen

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ScreenFilter:
    """Single filter criterion applied to one field.

    Parameters
    ----------
    field:
        Column or metric name to filter on (e.g. ``"pe_trailing"``).
    source:
        Which table family owns the field — one of
        ``ANALYTICS_RESULT``, ``ENTITY``, ``SECURITY``, ``OWNERSHIP``.
    op:
        Comparison operator.  Supported:
        GT, LT, GTE, LTE, EQ, NEQ, BETWEEN, IN, NOT_IN, CONTAINS,
        NOT_NULL, TOP_N, BOTTOM_N, TOP_N_PCT, BOTTOM_N_PCT.
    value:
        Primary comparison value.
    value2:
        Secondary value (only used by BETWEEN).
    """

    field: str
    source: str = "ANALYTICS_RESULT"
    op: str = "GT"
    value: Any = None
    value2: Any = None


@dataclass
class ScreenFilterGroup:
    """Composite filter node using AND/OR/NOT logic.

    ``filters`` may contain both :class:`ScreenFilter` (leaf) and nested
    :class:`ScreenFilterGroup` (branch) instances for arbitrary depth.
    """

    logic: str = "AND"
    filters: list[ScreenFilter | ScreenFilterGroup] = field(default_factory=list)


@dataclass
class RankFactor:
    """Single ranking dimension in a composite score.

    Parameters
    ----------
    field:
        Metric name stored in ``AnalyticsResult.metric_name``.
    weight:
        Relative weight of this factor in the composite score.
    ascending:
        If ``True`` lower values are better (e.g. PE ratio);
        if ``False`` higher values are better (e.g. ROE).
    """

    field: str
    weight: float = 1.0
    ascending: bool = False


@dataclass
class ScreenedSecurity:
    """A single security that passed screening filters."""

    security_id: UUID
    entity_id: UUID | None = None
    ticker: str | None = None
    name: str | None = None
    rank: int | None = None
    composite_score: float | None = None
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScreenResult:
    """Complete output of a screen execution."""

    total_matches: int
    securities: list[ScreenedSecurity]
    screen_name: str | None = None
    universe: str = "ALL"
    execution_time_ms: int = 0


# ---------------------------------------------------------------------------
# Screening & ranking engine
# ---------------------------------------------------------------------------

class ScreeningEngine:
    """Screening and ranking engine for security discovery.

    Translates declarative filter definitions into efficient SQL against
    the analytics warehouse and reference tables, combines them using set
    logic, and returns enriched + optionally ranked results.
    """

    # ----- public API -------------------------------------------------------

    async def run_screen(
        self,
        session: AsyncSession,
        filters: ScreenFilterGroup,
        universe_ids: list[UUID] | None = None,
        limit: int = 100,
        include_metrics: list[str] | None = None,
        ranking: list[RankFactor] | None = None,
    ) -> ScreenResult:
        """Execute a screen with filters and optional ranking.

        Parameters
        ----------
        session:
            Async SQLAlchemy session.
        filters:
            Root filter group (may contain nested groups).
        universe_ids:
            If provided, only these security IDs are considered.
        limit:
            Maximum securities to return.
        include_metrics:
            Metric names to fetch and attach to each result row.
        ranking:
            If provided, results are ranked via multi-factor composite.

        Returns
        -------
        ScreenResult
        """
        t0 = time.monotonic()

        # 1. Build the combined security_id subquery from the filter tree.
        combined_subq = self._build_filter_group_query(filters, universe_ids)

        # 2. Execute to get the list of matching security IDs.
        matched_rows = (await session.execute(combined_subq)).all()
        matched_ids: list[UUID] = [row[0] for row in matched_rows]

        if not matched_ids:
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            return ScreenResult(
                total_matches=0,
                securities=[],
                universe="CUSTOM" if universe_ids else "ALL",
                execution_time_ms=elapsed_ms,
            )

        total_matches = len(matched_ids)

        # 3. If ranking requested, rank first then slice.
        if ranking:
            ranked = await self.run_ranking(
                session, matched_ids, ranking, limit=limit,
            )
        else:
            ranked = None

        # 4. Enrich with security metadata.
        enriched = await self._enrich_securities(
            session,
            [s.security_id for s in ranked] if ranked else matched_ids[:limit],
        )

        # 5. Merge rank info into enriched results.
        securities: list[ScreenedSecurity] = []
        if ranked:
            rank_lookup = {s.security_id: s for s in ranked}
            for sid in [s.security_id for s in ranked]:
                base = enriched.get(sid, ScreenedSecurity(security_id=sid))
                ri = rank_lookup[sid]
                base.rank = ri.rank
                base.composite_score = ri.composite_score
                securities.append(base)
        else:
            for idx, sid in enumerate(matched_ids[:limit]):
                sec = enriched.get(sid, ScreenedSecurity(security_id=sid))
                sec.rank = idx + 1
                securities.append(sec)

        # 6. Optionally attach requested metric values.
        if include_metrics and securities:
            await self._attach_metrics(
                session,
                securities,
                include_metrics,
            )

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        return ScreenResult(
            total_matches=total_matches,
            securities=securities,
            universe="CUSTOM" if universe_ids else "ALL",
            execution_time_ms=elapsed_ms,
        )

    async def run_ranking(
        self,
        session: AsyncSession,
        security_ids: list[UUID],
        factors: list[RankFactor],
        limit: int = 100,
    ) -> list[ScreenedSecurity]:
        """Rank securities by multi-factor composite percentile score.

        For each factor the value is fetched from ``AnalyticsResult``,
        converted to a 0-100 percentile, optionally inverted when
        ``ascending=True`` (lower-is-better), and weighted into a single
        composite score.

        Parameters
        ----------
        security_ids:
            Candidate security IDs to rank.
        factors:
            One or more rank factors with field, weight, and direction.
        limit:
            Number of top-ranked securities to return.

        Returns
        -------
        list[ScreenedSecurity]
            Sorted descending by composite score.
        """
        if not factors or not security_ids:
            return []

        # factor_name -> {security_id: raw_value}
        factor_values: dict[str, dict[UUID, float]] = {}

        for factor in factors:
            # Subquery: latest as_of_date per security for this metric
            latest_subq = (
                select(
                    AnalyticsResult.security_id,
                    func.max(AnalyticsResult.as_of_date).label("max_date"),
                )
                .where(
                    AnalyticsResult.metric_name == factor.field,
                    AnalyticsResult.security_id.in_(security_ids),
                    AnalyticsResult.value.is_not(None),
                )
                .group_by(AnalyticsResult.security_id)
                .subquery("latest_factor")
            )
            stmt = (
                select(
                    AnalyticsResult.security_id,
                    AnalyticsResult.value,
                )
                .join(
                    latest_subq,
                    and_(
                        AnalyticsResult.security_id == latest_subq.c.security_id,
                        AnalyticsResult.as_of_date == latest_subq.c.max_date,
                    ),
                )
                .where(
                    AnalyticsResult.metric_name == factor.field,
                    AnalyticsResult.value.is_not(None),
                )
            )
            rows = (await session.execute(stmt)).all()
            factor_values[factor.field] = {
                row.security_id: float(row.value) for row in rows
            }

        # Compute percentile ranks per factor.
        # factor_name -> {security_id: percentile 0-100}
        factor_pctiles: dict[str, dict[UUID, float]] = {}

        for factor in factors:
            values_map = factor_values.get(factor.field, {})
            if not values_map:
                factor_pctiles[factor.field] = {}
                continue

            sorted_sids = sorted(values_map.keys(), key=lambda s: values_map[s])
            n = len(sorted_sids)
            pctile_map: dict[UUID, float] = {}
            for rank_idx, sid in enumerate(sorted_sids):
                raw_pctile = (rank_idx / max(n - 1, 1)) * 100.0
                if factor.ascending:
                    # Lower is better -> invert so lower raw value = higher percentile
                    pctile_map[sid] = 100.0 - raw_pctile
                else:
                    pctile_map[sid] = raw_pctile
            factor_pctiles[factor.field] = pctile_map

        # Composite score = weighted average of percentiles.
        total_weight = sum(f.weight for f in factors)
        if total_weight == 0:
            total_weight = 1.0

        composite: dict[UUID, float] = {}
        for sid in security_ids:
            weighted_sum = 0.0
            available_weight = 0.0
            for factor in factors:
                pctile = factor_pctiles.get(factor.field, {}).get(sid)
                if pctile is not None:
                    weighted_sum += factor.weight * pctile
                    available_weight += factor.weight
            if available_weight > 0:
                composite[sid] = weighted_sum / available_weight
            # Securities with no factor data are excluded.

        # Sort descending by composite and return top N.
        sorted_sids = sorted(composite.keys(), key=lambda s: composite[s], reverse=True)
        results: list[ScreenedSecurity] = []
        for rank_pos, sid in enumerate(sorted_sids[:limit], start=1):
            results.append(
                ScreenedSecurity(
                    security_id=sid,
                    rank=rank_pos,
                    composite_score=round(composite[sid], 4),
                )
            )
        return results

    def get_field_metadata(self) -> list[dict[str, str]]:
        """Return metadata for all screenable fields.

        Each entry describes one field available in the screening UI,
        including its source table, data type, human description, and
        category grouping.
        """
        return list(_FIELD_METADATA)

    async def save_screen(
        self,
        session: AsyncSession,
        name: str,
        definition: dict[str, Any],
        description: str | None = None,
        tags: list[str] | None = None,
    ) -> SavedScreen:
        """Persist a screen definition for later replay.

        Parameters
        ----------
        name:
            Display name for the saved screen.
        definition:
            JSON-serialisable dict holding filters, ranking, etc.
        description:
            Optional human-readable explanation.
        tags:
            Categorisation tags (e.g. ``["value", "graham"]``).

        Returns
        -------
        SavedScreen
        """
        screen = SavedScreen(
            name=name,
            description=description,
            screen_type="CUSTOM",
            is_prebuilt=False,
            definition=definition,
            universe="ALL",
            tags=tags or [],
            last_run_at=datetime.now(timezone.utc),
        )
        session.add(screen)
        await session.flush()
        return screen

    async def get_saved_screens(self, session: AsyncSession) -> list[SavedScreen]:
        """List all saved screens ordered by most recently run."""
        stmt = select(SavedScreen).order_by(desc(SavedScreen.last_run_at))
        result = await session.execute(stmt)
        return list(result.scalars().all())

    # ----- internal: filter compilation -------------------------------------

    def _build_filter_group_query(
        self,
        group: ScreenFilterGroup,
        universe_ids: list[UUID] | None = None,
    ):
        """Recursively translate a ScreenFilterGroup into a combined subquery.

        Returns a SQLAlchemy ``Select`` yielding distinct ``security_id``
        values that satisfy the group's logic.
        """
        subqueries = []
        for item in group.filters:
            if isinstance(item, ScreenFilterGroup):
                subqueries.append(self._build_filter_group_query(item, universe_ids))
            elif isinstance(item, ScreenFilter):
                subqueries.append(self._build_single_filter(item, universe_ids))
            else:
                # Accept raw dicts (e.g. from deserialized JSON).
                filt = self._dict_to_filter(item)
                if isinstance(filt, ScreenFilterGroup):
                    subqueries.append(self._build_filter_group_query(filt, universe_ids))
                else:
                    subqueries.append(self._build_single_filter(filt, universe_ids))

        if not subqueries:
            # Empty group — return nothing.
            stmt = select(Security.security_id).where(False)  # type: ignore[arg-type]
            return stmt

        if len(subqueries) == 1 and group.logic != "NOT":
            return subqueries[0]

        if group.logic == "AND":
            combined = subqueries[0].intersect(*subqueries[1:])
        elif group.logic == "OR":
            combined = subqueries[0].union(*subqueries[1:])
        elif group.logic == "NOT":
            # NOT: start from the full universe and subtract matched IDs.
            # Use NOT IN subquery for broader database compatibility.
            matched_subq = subqueries[0]
            if len(subqueries) > 1:
                matched_subq = subqueries[0].union(*subqueries[1:])
            matched_subq = matched_subq.scalar_subquery()

            if universe_ids:
                combined = select(Security.security_id).where(
                    Security.security_id.in_(universe_ids),
                    Security.security_id.notin_(matched_subq),
                )
            else:
                combined = select(Security.security_id).where(
                    Security.security_id.notin_(matched_subq),
                )
        else:
            logger.warning("Unknown logic %r — defaulting to AND", group.logic)
            combined = subqueries[0].intersect_all(*subqueries[1:])

        return combined

    def _build_single_filter(
        self,
        filt: ScreenFilter,
        universe_ids: list[UUID] | None = None,
    ):
        """Translate one leaf ScreenFilter into a Select[security_id]."""
        source = filt.source.upper()

        if source == "ANALYTICS_RESULT":
            stmt = self._filter_analytics(filt)
        elif source == "ENTITY":
            stmt = self._filter_entity(filt)
        elif source == "SECURITY":
            stmt = self._filter_security(filt)
        elif source == "OWNERSHIP":
            stmt = self._filter_ownership(filt)
        else:
            logger.warning("Unknown filter source %r — returning empty set", source)
            return select(Security.security_id).where(False)  # type: ignore[arg-type]

        # Apply universe constraint if provided.
        if universe_ids:
            # The first column in every stmt is security_id.
            stmt = stmt.where(
                self._security_id_col(source).in_(universe_ids)
            )

        return stmt.distinct()

    # -- source-specific builders --

    def _filter_analytics(self, filt: ScreenFilter):
        """Build subquery against ``analytics_results`` table."""
        stmt = select(AnalyticsResult.security_id).where(
            AnalyticsResult.metric_name == filt.field,
        )
        stmt = self._apply_numeric_op(stmt, AnalyticsResult.value, filt)
        return stmt

    def _filter_entity(self, filt: ScreenFilter):
        """Build subquery joining securities -> entities."""
        stmt = select(Security.security_id).join(
            Entity, Security.issuer_entity_id == Entity.entity_id,
        )
        col = getattr(Entity, filt.field, None)
        if col is None:
            logger.warning("Entity has no column %r", filt.field)
            return stmt.where(False)  # type: ignore[arg-type]
        stmt = self._apply_generic_op(stmt, col, filt)
        return stmt

    def _filter_security(self, filt: ScreenFilter):
        """Build subquery against ``securities`` table."""
        stmt = select(Security.security_id)
        col = getattr(Security, filt.field, None)
        if col is None:
            logger.warning("Security has no column %r", filt.field)
            return stmt.where(False)  # type: ignore[arg-type]
        stmt = self._apply_generic_op(stmt, col, filt)
        return stmt

    def _filter_ownership(self, filt: ScreenFilter):
        """Build subquery against ``ownership_summaries`` (latest per security)."""
        # Subquery: latest report_date per security.
        latest_date_subq = (
            select(
                OwnershipSummary.security_id,
                func.max(OwnershipSummary.report_date).label("max_date"),
            )
            .group_by(OwnershipSummary.security_id)
            .subquery("latest_ownership")
        )

        stmt = (
            select(OwnershipSummary.security_id)
            .join(
                latest_date_subq,
                and_(
                    OwnershipSummary.security_id == latest_date_subq.c.security_id,
                    OwnershipSummary.report_date == latest_date_subq.c.max_date,
                ),
            )
        )
        col = getattr(OwnershipSummary, filt.field, None)
        if col is None:
            logger.warning("OwnershipSummary has no column %r", filt.field)
            return stmt.where(False)  # type: ignore[arg-type]
        stmt = self._apply_generic_op(stmt, col, filt)
        return stmt

    # -- operator helpers --

    def _apply_numeric_op(self, stmt, col, filt: ScreenFilter):
        """Apply operator to a numeric column (AnalyticsResult.value)."""
        op = filt.op.upper()
        v = filt.value
        v2 = filt.value2

        if op == "GT":
            stmt = stmt.where(col > v)
        elif op == "LT":
            stmt = stmt.where(col < v)
        elif op == "GTE":
            stmt = stmt.where(col >= v)
        elif op == "LTE":
            stmt = stmt.where(col <= v)
        elif op == "EQ":
            stmt = stmt.where(col == v)
        elif op == "NEQ":
            stmt = stmt.where(col != v)
        elif op == "BETWEEN":
            stmt = stmt.where(col.between(v, v2))
        elif op == "IN":
            stmt = stmt.where(col.in_(v if isinstance(v, (list, tuple)) else [v]))
        elif op == "NOT_IN":
            stmt = stmt.where(col.notin_(v if isinstance(v, (list, tuple)) else [v]))
        elif op == "NOT_NULL":
            stmt = stmt.where(col.is_not(None))
        elif op == "TOP_N":
            stmt = stmt.where(col.is_not(None)).order_by(desc(col)).limit(int(v))
        elif op == "BOTTOM_N":
            stmt = stmt.where(col.is_not(None)).order_by(asc(col)).limit(int(v))
        elif op == "TOP_N_PCT":
            # Select securities whose value is >= the (100 - N)th percentile.
            pct_threshold = 1.0 - (float(v) / 100.0)
            cutoff_subq = select(
                func.percentile_cont(pct_threshold)
                .within_group(col)
                .label("cutoff")
            ).where(col.is_not(None)).scalar_subquery()
            stmt = stmt.where(col >= cutoff_subq)
        elif op == "BOTTOM_N_PCT":
            pct_threshold = float(v) / 100.0
            cutoff_subq = select(
                func.percentile_cont(pct_threshold)
                .within_group(col)
                .label("cutoff")
            ).where(col.is_not(None)).scalar_subquery()
            stmt = stmt.where(col <= cutoff_subq)
        else:
            logger.warning("Unknown numeric op %r — no filter applied", op)

        return stmt

    def _apply_generic_op(self, stmt, col, filt: ScreenFilter):
        """Apply operator to any column (entity/security/ownership fields)."""
        op = filt.op.upper()
        v = filt.value
        v2 = filt.value2

        if op == "GT":
            stmt = stmt.where(col > v)
        elif op == "LT":
            stmt = stmt.where(col < v)
        elif op == "GTE":
            stmt = stmt.where(col >= v)
        elif op == "LTE":
            stmt = stmt.where(col <= v)
        elif op == "EQ":
            stmt = stmt.where(col == v)
        elif op == "NEQ":
            stmt = stmt.where(col != v)
        elif op == "BETWEEN":
            stmt = stmt.where(col.between(v, v2))
        elif op == "IN":
            stmt = stmt.where(col.in_(v if isinstance(v, (list, tuple)) else [v]))
        elif op == "NOT_IN":
            stmt = stmt.where(col.notin_(v if isinstance(v, (list, tuple)) else [v]))
        elif op == "CONTAINS":
            stmt = stmt.where(col.ilike(f"%{v}%"))
        elif op == "NOT_NULL":
            stmt = stmt.where(col.is_not(None))
        else:
            logger.warning("Unknown generic op %r — no filter applied", op)

        return stmt

    @staticmethod
    def _security_id_col(source: str):
        """Return the ``security_id`` mapped column for the given source."""
        if source == "ANALYTICS_RESULT":
            return AnalyticsResult.security_id
        if source == "OWNERSHIP":
            return OwnershipSummary.security_id
        # ENTITY and SECURITY both query via Security table.
        return Security.security_id

    # ----- internal: enrichment ---------------------------------------------

    async def _enrich_securities(
        self,
        session: AsyncSession,
        security_ids: list[UUID],
    ) -> dict[UUID, ScreenedSecurity]:
        """Load security name, short_name, and issuer_entity_id for IDs."""
        if not security_ids:
            return {}

        stmt = (
            select(
                Security.security_id,
                Security.name,
                Security.short_name,
                Security.issuer_entity_id,
            )
            .where(Security.security_id.in_(security_ids))
        )
        rows = (await session.execute(stmt)).all()

        result: dict[UUID, ScreenedSecurity] = {}
        for row in rows:
            result[row.security_id] = ScreenedSecurity(
                security_id=row.security_id,
                entity_id=row.issuer_entity_id,
                ticker=row.short_name,
                name=row.name,
            )
        return result

    async def _attach_metrics(
        self,
        session: AsyncSession,
        securities: list[ScreenedSecurity],
        metric_names: list[str],
    ) -> None:
        """Fetch latest metric values and attach to each ScreenedSecurity."""
        sids = [s.security_id for s in securities]
        if not sids or not metric_names:
            return

        # Fetch the most recent value per (security_id, metric_name).
        latest_metric_subq = (
            select(
                AnalyticsResult.security_id,
                AnalyticsResult.metric_name,
                func.max(AnalyticsResult.as_of_date).label("max_date"),
            )
            .where(
                AnalyticsResult.security_id.in_(sids),
                AnalyticsResult.metric_name.in_(metric_names),
            )
            .group_by(AnalyticsResult.security_id, AnalyticsResult.metric_name)
            .subquery("latest_metric")
        )
        stmt = (
            select(
                AnalyticsResult.security_id,
                AnalyticsResult.metric_name,
                AnalyticsResult.value,
            )
            .join(
                latest_metric_subq,
                and_(
                    AnalyticsResult.security_id == latest_metric_subq.c.security_id,
                    AnalyticsResult.metric_name == latest_metric_subq.c.metric_name,
                    AnalyticsResult.as_of_date == latest_metric_subq.c.max_date,
                ),
            )
        )
        rows = (await session.execute(stmt)).all()

        # Index by security_id.
        metrics_by_sid: dict[UUID, dict[str, float | None]] = {}
        for row in rows:
            metrics_by_sid.setdefault(row.security_id, {})[row.metric_name] = (
                float(row.value) if row.value is not None else None
            )

        for sec in securities:
            sec.metrics = metrics_by_sid.get(sec.security_id, {})

    # ----- internal: dict deserialization -----------------------------------

    @staticmethod
    def _dict_to_filter(data: Any) -> ScreenFilter | ScreenFilterGroup:
        """Convert a raw dict (e.g. from JSON) into the correct dataclass."""
        if isinstance(data, (ScreenFilter, ScreenFilterGroup)):
            return data
        if not isinstance(data, dict):
            raise ValueError(f"Cannot convert {type(data)} to a filter")

        # Presence of "logic" key => group.
        if "logic" in data:
            group = ScreenFilterGroup(logic=data.get("logic", "AND"))
            for child in data.get("filters", []):
                group.filters.append(ScreeningEngine._dict_to_filter(child))
            return group

        return ScreenFilter(
            field=data["field"],
            source=data.get("source", "ANALYTICS_RESULT"),
            op=data.get("op", "GT"),
            value=data.get("value"),
            value2=data.get("value2"),
        )

    # ----- public convenience: deserialize & run ----------------------------

    async def run_screen_from_dict(
        self,
        session: AsyncSession,
        definition: dict[str, Any],
        universe_ids: list[UUID] | None = None,
        limit: int = 100,
    ) -> ScreenResult:
        """Convenience wrapper that accepts a raw dict definition.

        The dict should have ``"filters"`` (a filter group dict) and
        optionally ``"ranking"`` (list of rank-factor dicts).
        """
        filters_raw = definition.get("filters", {})
        root = self._dict_to_filter(filters_raw)
        if isinstance(root, ScreenFilter):
            root = ScreenFilterGroup(logic="AND", filters=[root])

        ranking_raw = definition.get("ranking")
        ranking: list[RankFactor] | None = None
        if ranking_raw:
            ranking = [
                RankFactor(
                    field=r["field"],
                    weight=r.get("weight", 1.0),
                    ascending=r.get("ascending", False),
                )
                for r in ranking_raw
            ]

        include_metrics = definition.get("include_metrics")

        return await self.run_screen(
            session,
            filters=root,
            universe_ids=universe_ids,
            limit=limit,
            include_metrics=include_metrics,
            ranking=ranking,
        )


# ---------------------------------------------------------------------------
# Field metadata catalogue
# ---------------------------------------------------------------------------

_FIELD_METADATA: list[dict[str, str]] = [
    # --- E1 Profitability ratios ---
    {"field_name": "gross_margin", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "Gross profit / Revenue", "category": "profitability", "unit": "RATIO"},
    {"field_name": "operating_margin", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "Operating income / Revenue", "category": "profitability", "unit": "RATIO"},
    {"field_name": "net_margin", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "Net income / Revenue", "category": "profitability", "unit": "RATIO"},
    {"field_name": "ebitda_margin", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "EBITDA / Revenue", "category": "profitability", "unit": "RATIO"},
    {"field_name": "roe", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "Return on equity (Net income / Avg equity)", "category": "profitability", "unit": "RATIO"},
    {"field_name": "roa", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "Return on assets (Net income / Avg assets)", "category": "profitability", "unit": "RATIO"},
    {"field_name": "roic", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "Return on invested capital (NOPAT / Invested capital)", "category": "profitability", "unit": "RATIO"},
    {"field_name": "roce", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "Return on capital employed (EBIT / Capital employed)", "category": "profitability", "unit": "RATIO"},

    # --- E1 Leverage ratios ---
    {"field_name": "debt_to_equity", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "Total debt / Total equity", "category": "leverage", "unit": "RATIO"},
    {"field_name": "debt_to_assets", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "Total debt / Total assets", "category": "leverage", "unit": "RATIO"},
    {"field_name": "net_debt_to_ebitda", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "Net debt / EBITDA", "category": "leverage", "unit": "MULTIPLE"},
    {"field_name": "interest_coverage", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "EBIT / Interest expense", "category": "leverage", "unit": "MULTIPLE"},
    {"field_name": "current_ratio", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "Current assets / Current liabilities", "category": "leverage", "unit": "RATIO"},
    {"field_name": "quick_ratio", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "(Current assets - Inventory) / Current liabilities", "category": "leverage", "unit": "RATIO"},
    {"field_name": "equity_multiplier", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "Total assets / Total equity", "category": "leverage", "unit": "MULTIPLE"},

    # --- E1 Efficiency ratios ---
    {"field_name": "asset_turnover", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "Revenue / Avg total assets", "category": "efficiency", "unit": "RATIO"},
    {"field_name": "inventory_turnover", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "COGS / Avg inventory", "category": "efficiency", "unit": "RATIO"},
    {"field_name": "receivables_turnover", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "Revenue / Avg receivables", "category": "efficiency", "unit": "RATIO"},
    {"field_name": "days_sales_outstanding", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "365 / Receivables turnover", "category": "efficiency", "unit": "DAYS"},
    {"field_name": "days_inventory_outstanding", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "365 / Inventory turnover", "category": "efficiency", "unit": "DAYS"},
    {"field_name": "cash_conversion_cycle", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "DIO + DSO - DPO", "category": "efficiency", "unit": "DAYS"},

    # --- E1 Growth ratios ---
    {"field_name": "revenue_yoy", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "Year-over-year revenue growth", "category": "growth", "unit": "RATIO"},
    {"field_name": "revenue_3y_cagr", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "3-year revenue CAGR", "category": "growth", "unit": "RATIO"},
    {"field_name": "ebitda_yoy", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "Year-over-year EBITDA growth", "category": "growth", "unit": "RATIO"},
    {"field_name": "eps_yoy", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "Year-over-year EPS growth", "category": "growth", "unit": "RATIO"},
    {"field_name": "dividend_growth_1y", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "1-year dividend growth", "category": "growth", "unit": "RATIO"},
    {"field_name": "dividend_growth_3y", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "3-year dividend growth CAGR", "category": "growth", "unit": "RATIO"},
    {"field_name": "dividend_growth_5y", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "5-year dividend growth CAGR", "category": "growth", "unit": "RATIO"},

    # --- E1 Per-share metrics ---
    {"field_name": "eps_basic", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "Basic earnings per share", "category": "per_share", "unit": "CURRENCY"},
    {"field_name": "eps_diluted", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "Diluted earnings per share", "category": "per_share", "unit": "CURRENCY"},
    {"field_name": "book_value_per_share", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "Book value per share", "category": "per_share", "unit": "CURRENCY"},
    {"field_name": "tangible_book_per_share", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "Tangible book value per share", "category": "per_share", "unit": "CURRENCY"},
    {"field_name": "ncav_per_share", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "Net current asset value per share", "category": "per_share", "unit": "CURRENCY"},

    # --- E1 Cash flow metrics ---
    {"field_name": "fcf_margin", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "Free cash flow / Revenue", "category": "cash_flow", "unit": "RATIO"},
    {"field_name": "fcf_yield", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "Free cash flow / Market cap", "category": "cash_flow", "unit": "RATIO"},
    {"field_name": "fcf_per_share", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "Free cash flow per share", "category": "cash_flow", "unit": "CURRENCY"},
    {"field_name": "operating_cash_flow_ratio", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "Operating cash flow / Current liabilities", "category": "cash_flow", "unit": "RATIO"},
    {"field_name": "cash_flow_to_debt", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "Operating cash flow / Total debt", "category": "cash_flow", "unit": "RATIO"},

    # --- E1 Capital allocation & dividend ---
    {"field_name": "dividend_yield", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "Annual dividend per share / Price", "category": "dividend", "unit": "RATIO"},
    {"field_name": "payout_ratio", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "Dividends / Net income", "category": "dividend", "unit": "RATIO"},
    {"field_name": "fcf_payout_ratio", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "Dividends / Free cash flow", "category": "dividend", "unit": "RATIO"},
    {"field_name": "consecutive_dividend_years", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "Consecutive years of dividend payments", "category": "dividend", "unit": "COUNT"},
    {"field_name": "shareholder_yield", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "Dividend yield + net buyback yield", "category": "capital_allocation", "unit": "RATIO"},
    {"field_name": "capex_to_revenue", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "Capital expenditures / Revenue", "category": "capital_allocation", "unit": "RATIO"},

    # --- E2 Valuation multiples ---
    {"field_name": "pe_trailing", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "Price / Trailing-12-month EPS", "category": "valuation", "unit": "MULTIPLE"},
    {"field_name": "pe_forward", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "Price / Forward EPS estimate", "category": "valuation", "unit": "MULTIPLE"},
    {"field_name": "pb", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "Price / Book value per share", "category": "valuation", "unit": "MULTIPLE"},
    {"field_name": "ps", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "Price / Sales per share", "category": "valuation", "unit": "MULTIPLE"},
    {"field_name": "ev_ebitda", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "Enterprise value / EBITDA", "category": "valuation", "unit": "MULTIPLE"},
    {"field_name": "ev_revenue", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "Enterprise value / Revenue", "category": "valuation", "unit": "MULTIPLE"},
    {"field_name": "ev_fcf", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "Enterprise value / Free cash flow", "category": "valuation", "unit": "MULTIPLE"},
    {"field_name": "peg_ratio", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "PE ratio / EPS growth rate", "category": "valuation", "unit": "MULTIPLE"},
    {"field_name": "earnings_yield", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "EBIT / Enterprise value (inverse of EV/EBIT)", "category": "valuation", "unit": "RATIO"},

    # --- E3 Quality & safety scores ---
    {"field_name": "piotroski_f_score", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "Piotroski F-Score (0-9)", "category": "quality_score", "unit": "SCORE"},
    {"field_name": "altman_z_score", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "Altman Z-Score", "category": "quality_score", "unit": "SCORE"},
    {"field_name": "altman_zone", "source": "ANALYTICS_RESULT", "data_type": "categorical", "description": "Altman Z classification: SAFE / GREY / DISTRESS", "category": "quality_score", "unit": ""},
    {"field_name": "beneish_m_score", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "Beneish M-Score (earnings manipulation probability)", "category": "quality_score", "unit": "SCORE"},

    # --- E3 Composite scores ---
    {"field_name": "earnings_quality_score", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "Composite earnings quality (0-100)", "category": "composite_score", "unit": "SCORE"},
    {"field_name": "financial_strength_score", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "Composite financial strength (0-100)", "category": "composite_score", "unit": "SCORE"},

    # --- Entity fields ---
    {"field_name": "gics_sector", "source": "ENTITY", "data_type": "categorical", "description": "GICS sector code (2-digit)", "category": "classification", "unit": ""},
    {"field_name": "gics_industry_group", "source": "ENTITY", "data_type": "categorical", "description": "GICS industry group code (4-digit)", "category": "classification", "unit": ""},
    {"field_name": "gics_industry", "source": "ENTITY", "data_type": "categorical", "description": "GICS industry code (6-digit)", "category": "classification", "unit": ""},
    {"field_name": "gics_sub_industry", "source": "ENTITY", "data_type": "categorical", "description": "GICS sub-industry code (8-digit)", "category": "classification", "unit": ""},
    {"field_name": "incorporation_country", "source": "ENTITY", "data_type": "categorical", "description": "ISO 3166-1 alpha-2 country of incorporation", "category": "classification", "unit": ""},
    {"field_name": "domicile_country", "source": "ENTITY", "data_type": "categorical", "description": "ISO 3166-1 alpha-2 country of domicile", "category": "classification", "unit": ""},
    {"field_name": "entity_type", "source": "ENTITY", "data_type": "categorical", "description": "Entity type (CORPORATION, FUND, etc.)", "category": "classification", "unit": ""},
    {"field_name": "status", "source": "ENTITY", "data_type": "categorical", "description": "Entity status (ACTIVE, INACTIVE, etc.)", "category": "classification", "unit": ""},

    # --- Security fields ---
    {"field_name": "security_type", "source": "SECURITY", "data_type": "categorical", "description": "Security type (COMMON_STOCK, PREFERRED, etc.)", "category": "security_info", "unit": ""},
    {"field_name": "asset_class", "source": "SECURITY", "data_type": "categorical", "description": "Asset class (EQUITY, FIXED_INCOME, etc.)", "category": "security_info", "unit": ""},
    {"field_name": "primary_exchange_mic", "source": "SECURITY", "data_type": "categorical", "description": "Primary exchange MIC code", "category": "security_info", "unit": ""},
    {"field_name": "primary_currency", "source": "SECURITY", "data_type": "categorical", "description": "Primary trading currency (ISO 4217)", "category": "security_info", "unit": ""},

    # --- Ownership fields ---
    {"field_name": "institutional_percent", "source": "OWNERSHIP", "data_type": "numeric", "description": "Institutional ownership as % of outstanding", "category": "ownership", "unit": "PERCENT"},
    {"field_name": "insider_percent", "source": "OWNERSHIP", "data_type": "numeric", "description": "Insider ownership as % of outstanding", "category": "ownership", "unit": "PERCENT"},
    {"field_name": "top_10_concentration", "source": "OWNERSHIP", "data_type": "numeric", "description": "Top 10 holders as % of outstanding", "category": "ownership", "unit": "PERCENT"},
    {"field_name": "institutional_holders_count", "source": "OWNERSHIP", "data_type": "numeric", "description": "Number of institutional holders", "category": "ownership", "unit": "COUNT"},

    # --- E6 Flow fields ---
    {"field_name": "inst_breadth_score", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "Institutional breadth score (-1 to +1)", "category": "flow", "unit": "SCORE"},
    {"field_name": "inst_smart_money_flow", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "Smart-money (whale-tier) flow signal (-1 to +1)", "category": "flow", "unit": "SCORE"},
    {"field_name": "inst_squeeze_potential", "source": "ANALYTICS_RESULT", "data_type": "categorical", "description": "Short-squeeze potential: HIGH / MODERATE / LOW", "category": "flow", "unit": ""},
    {"field_name": "inst_conviction_score", "source": "ANALYTICS_RESULT", "data_type": "numeric", "description": "Institutional conviction score", "category": "flow", "unit": "SCORE"},
    {"field_name": "inst_flow_trend_3q", "source": "ANALYTICS_RESULT", "data_type": "categorical", "description": "3-quarter flow trend: ACCUMULATION / DISTRIBUTION / NEUTRAL", "category": "flow", "unit": ""},
]
