"""Central data-access layer for the Bloomberg Terminal GUI.

``DataService`` wraps every database query the GUI needs, dispatches each
one to the :class:`AsyncWorker` background loop, and delivers results back
to the GUI thread via Qt signals.  All ORM objects are converted to plain
``dict`` instances before crossing the thread boundary so that SQLAlchemy
lazy-load proxies are never touched outside the session scope.

This module creates its **own** async engine and session factory rather
than reusing the FastAPI one, because the GUI runs in a separate process
with its own event loop.

Typical wiring in the main window::

    self.async_worker = AsyncWorker()
    self.async_worker.start()
    self.async_worker.wait_ready()

    self.data_service = DataService(self.async_worker)
    self.data_service.initialize()

    self.data_service.search_results.connect(self._on_search_results)
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from PySide6.QtCore import QObject, Signal
from sqlalchemy import select, or_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from src.config import settings
from src.gui.core.async_bridge import AsyncWorker
from src.models import (
    # Entity domain
    Entity,
    EntityIdentifier,
    EntityRelationship,
    # Security domain
    Security,
    SecurityIdentifier,
    EquityDetails,
    FixedIncomeDetails,
    EODPrice,
    # Fundamentals
    FinancialPeriod,
    IncomeStatement,
    BalanceSheet,
    CashFlowStatement,
    # Macro
    MacroIndicator,
    MacroValue,
    # Ownership
    InstitutionalHolding,
    InstitutionProfile,
    InsiderHolding,
    OwnershipSummary,
    ShortInterest,
    # ESG
    ESGScore,
    ESGMetric,
    ESGControversy,
    # Corporate Actions
    CorporateAction,
    # Business Relationships
    BusinessRelationship,
)

# Pillar 2 engine imports (deferred to avoid hard dep if engines not ready)
try:
    from src.engines.e1_ratios import RatioEngine
    from src.engines.e1_dupont import DuPontEngine
    from src.engines.e2_dcf import DCFEngine
    from src.engines.e2_wacc import WACCEngine
    from src.engines.e3_piotroski import PiotroskiEngine
    from src.engines.e3_altman import AltmanEngine
    from src.engines.e3_beneish import BeneishEngine
    from src.engines.e5_risk import RiskEngine
    from src.engines.e7_quant import QuantEngine
    from src.engines.e8_scenario import ScenarioEngine
    from src.engines.e8_prebuilt_scenarios import list_prebuilt_scenarios
    _ENGINES_AVAILABLE = True
except ImportError:
    _ENGINES_AVAILABLE = False

logger = logging.getLogger(__name__)

# ======================================================================
# ORM -> dict helpers
# ======================================================================


def _to_float(value: Any) -> float | None:
    """Coerce a Decimal/number to float for the GUI thread; None passes through."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _orm_to_dict(obj: Any) -> dict[str, Any]:
    """Convert a SQLAlchemy mapped instance to a plain dict.

    Handles common column types that are not JSON-serialisable by default:
    - ``uuid.UUID``  -> ``str``
    - ``datetime`` / ``date`` -> ISO-8601 string
    - ``Decimal`` -> ``float``

    Only iterates over ``__table__.columns`` (not relationships) so the
    result is safe to use from any thread.
    """
    result: dict[str, Any] = {}
    for col in obj.__table__.columns:
        val = getattr(obj, col.name, None)
        if isinstance(val, uuid.UUID):
            val = str(val)
        elif isinstance(val, (datetime, date)):
            val = val.isoformat()
        elif isinstance(val, Decimal):
            val = float(val)
        result[col.name] = val
    return result


def _orm_list(rows: list[Any]) -> list[dict[str, Any]]:
    """Convert a list of ORM instances to a list of dicts."""
    return [_orm_to_dict(r) for r in rows]


# ======================================================================
# DataService
# ======================================================================


class DataService(QObject):
    """Provides query methods for every data domain.

    Each public method dispatches an async database query to the
    ``AsyncWorker`` and, on completion, emits the corresponding signal
    with the results (already converted to plain dicts).

    If a query fails, the ``error`` signal is emitted with a human-
    readable message instead.
    """

    # ------------------------------------------------------------------
    # Signals -- one per result type
    # ------------------------------------------------------------------

    #: List of entity dicts matching a search.
    entities_loaded = Signal(list)

    #: Single entity dict with full detail.
    entity_loaded = Signal(dict)

    #: List of security dicts matching a search.
    securities_loaded = Signal(list)

    #: Single security dict with full detail.
    security_loaded = Signal(dict)

    #: Combined search results: list of dicts with a ``result_type`` field.
    search_results = Signal(list)

    #: List of EODPrice dicts for a security.
    prices_loaded = Signal(list)

    #: Fundamentals payload:
    #: ``{"periods": [...], "income": [...], "balance": [...], "cashflow": [...]}``
    fundamentals_loaded = Signal(dict)

    #: List of MacroIndicator dicts.
    macro_indicators_loaded = Signal(list)

    #: List of MacroValue dicts for one indicator.
    macro_values_loaded = Signal(list)

    #: Ownership payload:
    #: ``{"summary": {...}, "institutional": [...], "insider": [...], "short_interest": [...]}``
    ownership_loaded = Signal(dict)

    #: ESG payload:
    #: ``{"scores": [...], "metrics": [...], "controversies": [...]}``
    esg_loaded = Signal(dict)

    #: List of CorporateAction dicts.
    corporate_actions_loaded = Signal(list)

    #: List of BusinessRelationship dicts.
    relationships_loaded = Signal(list)

    #: Pillar 2 analytics signals
    ratios_loaded = Signal(dict)
    dupont_loaded = Signal(dict)
    dcf_loaded = Signal(dict)
    wacc_loaded = Signal(dict)
    scores_loaded = Signal(dict)
    risk_loaded = Signal(dict)
    quant_loaded = Signal(dict)
    scenario_loaded = Signal(dict)

    #: Financial Analysis Suite signals
    notable_investors_loaded = Signal(list)
    congress_trades_loaded = Signal(list)
    auto_model_loaded = Signal(dict)
    complex_structure_loaded = Signal(dict)

    #: Fixed-income / portfolio signals
    debt_maturity_loaded = Signal(dict)
    credit_ratings_loaded = Signal(dict)
    issuance_loaded = Signal(list)
    portfolios_loaded = Signal(list)

    #: Emitted on any query error with a human-readable message.
    error = Signal(str)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def __init__(self, async_worker: AsyncWorker, parent: QObject | None = None):
        super().__init__(parent)
        self._worker = async_worker
        self._engine = None
        self._session_factory: async_sessionmaker | None = None

    def initialize(self) -> None:
        """Create the async engine and session factory.

        Must be called after the ``AsyncWorker`` has started (its loop
        must be running).  The engine is created lazily on the background
        loop so the asyncpg connection pool is tied to the correct loop.
        """
        future = self._worker.submit(self._init_engine())
        # Block briefly -- this is a one-time startup cost.
        future.result(timeout=10)
        logger.info("DataService: engine and session factory initialised.")

    async def _init_engine(self) -> None:
        """(Runs on the async-worker loop.)  Build the engine."""
        self._engine = create_async_engine(
            settings.DATABASE_URL,
            pool_size=5,
            max_overflow=5,
            pool_pre_ping=True,
            echo=False,
        )
        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def shutdown(self) -> None:
        """Dispose of the engine connection pool."""
        if self._engine is not None:
            await self._engine.dispose()
            logger.info("DataService: engine disposed.")

    # ------------------------------------------------------------------
    # Internal dispatch helper
    # ------------------------------------------------------------------

    def _dispatch(self, coro, signal: Signal) -> None:
        """Submit *coro* to the worker; on success emit *signal* with its
        return value, on failure emit ``self.error``.
        """
        future = self._worker.submit(coro)

        def _on_done(f):
            try:
                result = f.result()
                signal.emit(result)
            except Exception as exc:
                msg = f"{type(exc).__name__}: {exc}"
                logger.exception("DataService query failed: %s", msg)
                self.error.emit(msg)

        future.add_done_callback(_on_done)

    # ------------------------------------------------------------------
    # Search (unified)
    # ------------------------------------------------------------------

    def search(self, query: str) -> None:
        """Search entities and securities by name / ticker / identifier.

        Emits ``search_results`` with a combined list where each dict has
        an extra ``_result_type`` key (``"entity"`` or ``"security"``).
        """
        self._dispatch(self._search(query), self.search_results)

    async def _search(self, query: str) -> list[dict]:
        pattern = f"%{query}%"
        results: list[dict] = []

        async with self._session_factory() as session:
            # --- Search entities by legal_name / short_name ---
            stmt = (
                select(Entity)
                .where(
                    or_(
                        Entity.legal_name.ilike(pattern),
                        Entity.short_name.ilike(pattern),
                    )
                )
                .order_by(Entity.legal_name)
                .limit(50)
            )
            rows = (await session.execute(stmt)).scalars().all()
            for e in rows:
                d = _orm_to_dict(e)
                d["_result_type"] = "entity"
                results.append(d)

            # --- Search securities by name / short_name ---
            stmt = (
                select(Security)
                .where(
                    or_(
                        Security.name.ilike(pattern),
                        Security.short_name.ilike(pattern),
                    )
                )
                .order_by(Security.name)
                .limit(50)
            )
            rows = (await session.execute(stmt)).scalars().all()
            for s in rows:
                d = _orm_to_dict(s)
                d["_result_type"] = "security"
                results.append(d)

            # --- Search security identifiers (ticker, ISIN, CUSIP, etc.) ---
            stmt = (
                select(SecurityIdentifier)
                .where(SecurityIdentifier.identifier_value.ilike(pattern))
                .limit(20)
            )
            id_rows = (await session.execute(stmt)).scalars().all()
            seen_ids = {r.get("security_id") for r in results if r.get("_result_type") == "security"}
            if id_rows:
                sec_ids = [r.security_id for r in id_rows if str(r.security_id) not in seen_ids]
                if sec_ids:
                    stmt2 = select(Security).where(Security.security_id.in_(sec_ids))
                    extra = (await session.execute(stmt2)).scalars().all()
                    for s in extra:
                        d = _orm_to_dict(s)
                        d["_result_type"] = "security"
                        results.append(d)

            # --- Search entity identifiers (LEI, CIK, etc.) ---
            stmt = (
                select(EntityIdentifier)
                .where(EntityIdentifier.identifier_value.ilike(pattern))
                .limit(20)
            )
            eid_rows = (await session.execute(stmt)).scalars().all()
            seen_eids = {r.get("entity_id") for r in results if r.get("_result_type") == "entity"}
            if eid_rows:
                ent_ids = [r.entity_id for r in eid_rows if str(r.entity_id) not in seen_eids]
                if ent_ids:
                    stmt2 = select(Entity).where(Entity.entity_id.in_(ent_ids))
                    extra = (await session.execute(stmt2)).scalars().all()
                    for e in extra:
                        d = _orm_to_dict(e)
                        d["_result_type"] = "entity"
                        results.append(d)

        return results

    # ------------------------------------------------------------------
    # Entity
    # ------------------------------------------------------------------

    def load_entities(self, limit: int = 100) -> None:
        """Load a page of entities.  Emits ``entities_loaded``."""
        self._dispatch(self._load_entities(limit), self.entities_loaded)

    async def _load_entities(self, limit: int) -> list[dict]:
        async with self._session_factory() as session:
            stmt = select(Entity).order_by(Entity.legal_name).limit(limit)
            rows = (await session.execute(stmt)).scalars().all()
            return _orm_list(rows)

    def load_entity(self, entity_id: str) -> None:
        """Load a single entity with identifiers.  Emits ``entity_loaded``."""
        self._dispatch(self._load_entity(entity_id), self.entity_loaded)

    async def _load_entity(self, entity_id: str) -> dict:
        uid = uuid.UUID(entity_id)
        async with self._session_factory() as session:
            stmt = (
                select(Entity)
                .options(selectinload(Entity.identifiers), selectinload(Entity.names))
                .where(Entity.entity_id == uid)
            )
            entity = (await session.execute(stmt)).scalar_one_or_none()
            if entity is None:
                return {}
            result = _orm_to_dict(entity)
            result["identifiers"] = _orm_list(entity.identifiers)
            result["names"] = _orm_list(entity.names)
            return result

    # ------------------------------------------------------------------
    # Security
    # ------------------------------------------------------------------

    def load_securities(self, entity_id: str | None = None, limit: int = 100) -> None:
        """Load securities, optionally filtered by issuer entity.
        Emits ``securities_loaded``.
        """
        self._dispatch(self._load_securities(entity_id, limit), self.securities_loaded)

    async def _load_securities(self, entity_id: str | None, limit: int) -> list[dict]:
        async with self._session_factory() as session:
            stmt = select(Security).order_by(Security.name).limit(limit)
            if entity_id:
                stmt = stmt.where(Security.issuer_entity_id == uuid.UUID(entity_id))
            rows = (await session.execute(stmt)).scalars().all()
            return _orm_list(rows)

    def load_security(self, security_id: str) -> None:
        """Load a single security with identifiers and sub-details.
        Emits ``security_loaded``.
        """
        self._dispatch(self._load_security(security_id), self.security_loaded)

    async def _load_security(self, security_id: str) -> dict:
        uid = uuid.UUID(security_id)
        async with self._session_factory() as session:
            stmt = (
                select(Security)
                .options(
                    selectinload(Security.identifiers),
                    selectinload(Security.equity_details),
                    selectinload(Security.fixed_income_details),
                    selectinload(Security.credit_ratings),
                )
                .where(Security.security_id == uid)
            )
            sec = (await session.execute(stmt)).scalar_one_or_none()
            if sec is None:
                return {}
            result = _orm_to_dict(sec)
            result["identifiers"] = _orm_list(sec.identifiers)
            if sec.equity_details:
                result["equity_details"] = _orm_to_dict(sec.equity_details)
            if sec.fixed_income_details:
                result["fixed_income_details"] = _orm_to_dict(sec.fixed_income_details)
            result["credit_ratings"] = _orm_list(sec.credit_ratings) if sec.credit_ratings else []
            return result

    # ------------------------------------------------------------------
    # Prices
    # ------------------------------------------------------------------

    def load_prices(self, security_id: str, days: int = 365) -> None:
        """Load EOD prices for the last *days*.  Emits ``prices_loaded``."""
        self._dispatch(self._load_prices(security_id, days), self.prices_loaded)

    async def _load_prices(self, security_id: str, days: int) -> list[dict]:
        uid = uuid.UUID(security_id)
        cutoff = date.today()
        # Use Python timedelta for the cutoff.
        from datetime import timedelta
        start = cutoff - timedelta(days=days)

        async with self._session_factory() as session:
            stmt = (
                select(EODPrice)
                .where(EODPrice.security_id == uid, EODPrice.price_date >= start)
                .order_by(EODPrice.price_date)
            )
            rows = (await session.execute(stmt)).scalars().all()
            return _orm_list(rows)

    # ------------------------------------------------------------------
    # Fundamentals
    # ------------------------------------------------------------------

    def load_fundamentals(self, entity_id: str) -> None:
        """Load financial statements.  Emits ``fundamentals_loaded``."""
        self._dispatch(self._load_fundamentals(entity_id), self.fundamentals_loaded)

    async def _load_fundamentals(self, entity_id: str) -> dict:
        uid = uuid.UUID(entity_id)
        async with self._session_factory() as session:
            stmt = (
                select(FinancialPeriod)
                .options(
                    selectinload(FinancialPeriod.income_statement),
                    selectinload(FinancialPeriod.balance_sheet),
                    selectinload(FinancialPeriod.cash_flow),
                )
                .where(FinancialPeriod.entity_id == uid)
                .order_by(desc(FinancialPeriod.period_end_date))
                .limit(40)  # ~10 years of quarters
            )
            periods = (await session.execute(stmt)).scalars().all()

            result: dict[str, list] = {
                "periods": [],
                "income": [],
                "balance": [],
                "cashflow": [],
            }
            for p in periods:
                result["periods"].append(_orm_to_dict(p))
                if p.income_statement:
                    d = _orm_to_dict(p.income_statement)
                    d["period_end_date"] = p.period_end_date.isoformat()
                    d["fiscal_year"] = p.fiscal_year
                    d["fiscal_quarter"] = p.fiscal_quarter
                    result["income"].append(d)
                if p.balance_sheet:
                    d = _orm_to_dict(p.balance_sheet)
                    d["period_end_date"] = p.period_end_date.isoformat()
                    d["fiscal_year"] = p.fiscal_year
                    d["fiscal_quarter"] = p.fiscal_quarter
                    result["balance"].append(d)
                if p.cash_flow:
                    d = _orm_to_dict(p.cash_flow)
                    d["period_end_date"] = p.period_end_date.isoformat()
                    d["fiscal_year"] = p.fiscal_year
                    d["fiscal_quarter"] = p.fiscal_quarter
                    result["cashflow"].append(d)

            return result

    # ------------------------------------------------------------------
    # Macro indicators
    # ------------------------------------------------------------------

    def load_macro_indicators(self, category: str | None = None) -> None:
        """Load macro indicator definitions.  Emits ``macro_indicators_loaded``."""
        self._dispatch(self._load_macro_indicators(category), self.macro_indicators_loaded)

    async def _load_macro_indicators(self, category: str | None) -> list[dict]:
        async with self._session_factory() as session:
            stmt = (
                select(MacroIndicator)
                .where(MacroIndicator.is_active.is_(True))
                .order_by(MacroIndicator.category, MacroIndicator.name)
            )
            if category:
                stmt = stmt.where(MacroIndicator.category == category)
            rows = (await session.execute(stmt)).scalars().all()
            return _orm_list(rows)

    def load_macro_values(self, indicator_id: str, limit: int = 500) -> None:
        """Load time-series values for one macro indicator.
        Emits ``macro_values_loaded``.
        """
        self._dispatch(self._load_macro_values(indicator_id, limit), self.macro_values_loaded)

    async def _load_macro_values(self, indicator_id: str, limit: int) -> list[dict]:
        uid = uuid.UUID(indicator_id)
        async with self._session_factory() as session:
            stmt = (
                select(MacroValue)
                .where(MacroValue.indicator_id == uid)
                .order_by(desc(MacroValue.observation_date))
                .limit(limit)
            )
            rows = (await session.execute(stmt)).scalars().all()
            # Return in chronological order for charting.
            return _orm_list(list(reversed(rows)))

    # ------------------------------------------------------------------
    # Ownership
    # ------------------------------------------------------------------

    def load_ownership(self, security_id: str) -> None:
        """Load ownership data bundle.  Emits ``ownership_loaded``."""
        self._dispatch(self._load_ownership(security_id), self.ownership_loaded)

    async def _load_ownership(self, security_id: str) -> dict:
        uid = uuid.UUID(security_id)
        async with self._session_factory() as session:
            # Ownership summary (most recent)
            stmt = (
                select(OwnershipSummary)
                .where(OwnershipSummary.security_id == uid)
                .order_by(desc(OwnershipSummary.report_date))
                .limit(1)
            )
            summary_row = (await session.execute(stmt)).scalar_one_or_none()

            # Top institutional holders (most recent report date)
            stmt = (
                select(InstitutionalHolding)
                .where(InstitutionalHolding.security_id == uid)
                .order_by(
                    desc(InstitutionalHolding.report_date),
                    desc(InstitutionalHolding.market_value),
                )
                .limit(50)
            )
            inst_rows = (await session.execute(stmt)).scalars().all()

            # Enrich with institution names
            inst_list = []
            if inst_rows:
                inst_ids = list({r.institution_id for r in inst_rows})
                name_stmt = (
                    select(InstitutionProfile)
                    .where(InstitutionProfile.institution_id.in_(inst_ids))
                )
                profiles = (await session.execute(name_stmt)).scalars().all()
                profile_map = {str(p.institution_id): p.institution_name for p in profiles}
                for h in inst_rows:
                    d = _orm_to_dict(h)
                    d["institution_name"] = profile_map.get(str(h.institution_id), "Unknown")
                    inst_list.append(d)

            # Insider transactions (recent)
            stmt = (
                select(InsiderHolding)
                .where(InsiderHolding.security_id == uid)
                .order_by(desc(InsiderHolding.transaction_date))
                .limit(50)
            )
            insider_rows = (await session.execute(stmt)).scalars().all()

            # Short interest (recent)
            stmt = (
                select(ShortInterest)
                .where(ShortInterest.security_id == uid)
                .order_by(desc(ShortInterest.settlement_date))
                .limit(20)
            )
            short_rows = (await session.execute(stmt)).scalars().all()

            return {
                "summary": _orm_to_dict(summary_row) if summary_row else {},
                "institutional": inst_list,
                "insider": _orm_list(insider_rows),
                "short_interest": _orm_list(short_rows),
            }

    # ------------------------------------------------------------------
    # ESG
    # ------------------------------------------------------------------

    def load_esg(self, entity_id: str) -> None:
        """Load ESG scores, metrics, controversies.  Emits ``esg_loaded``."""
        self._dispatch(self._load_esg(entity_id), self.esg_loaded)

    async def _load_esg(self, entity_id: str) -> dict:
        uid = uuid.UUID(entity_id)
        async with self._session_factory() as session:
            # Scores
            stmt = (
                select(ESGScore)
                .where(ESGScore.entity_id == uid)
                .order_by(desc(ESGScore.as_of_date))
                .limit(20)
            )
            score_rows = (await session.execute(stmt)).scalars().all()

            # Metrics
            stmt = (
                select(ESGMetric)
                .where(ESGMetric.entity_id == uid)
                .order_by(desc(ESGMetric.period_end_date))
                .limit(100)
            )
            metric_rows = (await session.execute(stmt)).scalars().all()

            # Controversies
            stmt = (
                select(ESGControversy)
                .where(ESGControversy.entity_id == uid)
                .order_by(desc(ESGControversy.start_date))
                .limit(30)
            )
            controversy_rows = (await session.execute(stmt)).scalars().all()

            return {
                "scores": _orm_list(score_rows),
                "metrics": _orm_list(metric_rows),
                "controversies": _orm_list(controversy_rows),
            }

    # ------------------------------------------------------------------
    # Corporate Actions
    # ------------------------------------------------------------------

    def load_corporate_actions(self, security_id: str) -> None:
        """Load corporate actions.  Emits ``corporate_actions_loaded``."""
        self._dispatch(
            self._load_corporate_actions(security_id),
            self.corporate_actions_loaded,
        )

    async def _load_corporate_actions(self, security_id: str) -> list[dict]:
        uid = uuid.UUID(security_id)
        async with self._session_factory() as session:
            stmt = (
                select(CorporateAction)
                .options(
                    selectinload(CorporateAction.dividend_action),
                    selectinload(CorporateAction.split_action),
                    selectinload(CorporateAction.ma_action),
                )
                .where(CorporateAction.security_id == uid)
                .order_by(desc(CorporateAction.ex_date))
                .limit(100)
            )
            rows = (await session.execute(stmt)).scalars().all()

            results = []
            for ca in rows:
                d = _orm_to_dict(ca)
                if ca.dividend_action:
                    d["dividend"] = _orm_to_dict(ca.dividend_action)
                if ca.split_action:
                    d["split"] = _orm_to_dict(ca.split_action)
                if ca.ma_action:
                    d["merger_acquisition"] = _orm_to_dict(ca.ma_action)
                results.append(d)
            return results

    # ------------------------------------------------------------------
    # Business Relationships
    # ------------------------------------------------------------------

    def load_relationships(self, entity_id: str) -> None:
        """Load supply-chain / business relationships.
        Emits ``relationships_loaded``.
        """
        self._dispatch(self._load_relationships(entity_id), self.relationships_loaded)

    async def _load_relationships(self, entity_id: str) -> list[dict]:
        uid = uuid.UUID(entity_id)
        async with self._session_factory() as session:
            # Relationships where entity is source OR target
            stmt = (
                select(BusinessRelationship)
                .where(
                    or_(
                        BusinessRelationship.source_entity_id == uid,
                        BusinessRelationship.target_entity_id == uid,
                    )
                )
                .order_by(desc(BusinessRelationship.effective_date))
                .limit(100)
            )
            rows = (await session.execute(stmt)).scalars().all()

            # Collect entity IDs to fetch names
            entity_ids: set[uuid.UUID] = set()
            for r in rows:
                entity_ids.add(r.source_entity_id)
                entity_ids.add(r.target_entity_id)

            # Fetch entity names
            name_map: dict[str, str] = {}
            if entity_ids:
                name_stmt = (
                    select(Entity.entity_id, Entity.legal_name, Entity.short_name)
                    .where(Entity.entity_id.in_(list(entity_ids)))
                )
                name_rows = (await session.execute(name_stmt)).all()
                for eid, legal, short in name_rows:
                    name_map[str(eid)] = short or legal

            results = []
            for r in rows:
                d = _orm_to_dict(r)
                d["source_entity_name"] = name_map.get(str(r.source_entity_id), "Unknown")
                d["target_entity_name"] = name_map.get(str(r.target_entity_id), "Unknown")
                results.append(d)

            return results

    # ------------------------------------------------------------------
    # Pillar 2: Financial Ratios (E1)
    # ------------------------------------------------------------------

    def run_ratios(self, entity_id: str) -> None:
        """Compute financial ratios via E1 RatioEngine.  Emits ``ratios_loaded``."""
        if not _ENGINES_AVAILABLE:
            self.error.emit("Analytics engines not available")
            return
        self._dispatch(self._run_ratios(entity_id), self.ratios_loaded)

    async def _run_ratios(self, entity_id: str) -> dict:
        uid = uuid.UUID(entity_id)
        engine = RatioEngine()
        async with self._session_factory() as session:
            result = await engine.compute(session, entity_id=uid)
        return result or {}

    # ------------------------------------------------------------------
    # Pillar 2: DuPont Analysis (E1)
    # ------------------------------------------------------------------

    def run_dupont(self, entity_id: str) -> None:
        """Compute DuPont decomposition via E1 DuPontEngine.  Emits ``dupont_loaded``."""
        if not _ENGINES_AVAILABLE:
            self.error.emit("Analytics engines not available")
            return
        self._dispatch(self._run_dupont(entity_id), self.dupont_loaded)

    async def _run_dupont(self, entity_id: str) -> dict:
        uid = uuid.UUID(entity_id)
        engine = DuPontEngine()
        async with self._session_factory() as session:
            result = await engine.compute(session, entity_id=uid)
        return result or {}

    # ------------------------------------------------------------------
    # Pillar 2: DCF Valuation (E2)
    # ------------------------------------------------------------------

    def run_dcf(self, security_id: str) -> None:
        """Compute DCF valuation via E2 DCFEngine.  Emits ``dcf_loaded``."""
        if not _ENGINES_AVAILABLE:
            self.error.emit("Analytics engines not available")
            return
        self._dispatch(self._run_dcf(security_id), self.dcf_loaded)

    async def _run_dcf(self, security_id: str) -> dict:
        uid = uuid.UUID(security_id)
        engine = DCFEngine()
        async with self._session_factory() as session:
            result = await engine.compute(session, security_id=uid)
        return result or {}

    # ------------------------------------------------------------------
    # Pillar 2: WACC (E2)
    # ------------------------------------------------------------------

    def run_wacc(self, security_id: str) -> None:
        """Compute WACC via E2 WACCEngine.  Emits ``wacc_loaded``."""
        if not _ENGINES_AVAILABLE:
            self.error.emit("Analytics engines not available")
            return
        self._dispatch(self._run_wacc(security_id), self.wacc_loaded)

    async def _run_wacc(self, security_id: str) -> dict:
        uid = uuid.UUID(security_id)
        engine = WACCEngine()
        async with self._session_factory() as session:
            result = await engine.compute(session, security_id=uid)
        return result or {}

    # ------------------------------------------------------------------
    # Pillar 2: Scoring Models (E3)
    # ------------------------------------------------------------------

    def run_scores(self, entity_id: str) -> None:
        """Compute Piotroski/Altman/Beneish.  Emits ``scores_loaded``."""
        if not _ENGINES_AVAILABLE:
            self.error.emit("Analytics engines not available")
            return
        self._dispatch(self._run_scores(entity_id), self.scores_loaded)

    async def _run_scores(self, entity_id: str) -> dict:
        uid = uuid.UUID(entity_id)
        results: dict = {}
        async with self._session_factory() as session:
            try:
                piotroski = PiotroskiEngine()
                r = await piotroski.compute(session, entity_id=uid)
                results["piotroski"] = r or {}
            except Exception:
                results["piotroski"] = {}
            try:
                altman = AltmanEngine()
                r = await altman.compute(session, entity_id=uid)
                results["altman"] = r or {}
            except Exception:
                results["altman"] = {}
            try:
                beneish = BeneishEngine()
                r = await beneish.compute(session, entity_id=uid)
                results["beneish"] = r or {}
            except Exception:
                results["beneish"] = {}
        return results

    # ------------------------------------------------------------------
    # Pillar 2: Risk Analytics (E5)
    # ------------------------------------------------------------------

    def run_risk(self, security_id: str) -> None:
        """Compute risk analytics via E5 RiskEngine.  Emits ``risk_loaded``."""
        if not _ENGINES_AVAILABLE:
            self.error.emit("Analytics engines not available")
            return
        self._dispatch(self._run_risk(security_id), self.risk_loaded)

    async def _run_risk(self, security_id: str) -> dict:
        uid = uuid.UUID(security_id)
        engine = RiskEngine()
        async with self._session_factory() as session:
            result = await engine.compute(session, security_id=uid)
        return result or {}

    # ------------------------------------------------------------------
    # Pillar 2: Quant Analytics (E7)
    # ------------------------------------------------------------------

    def run_quant(self, security_id: str) -> None:
        """Compute quant analytics via E7 QuantEngine.  Emits ``quant_loaded``."""
        if not _ENGINES_AVAILABLE:
            self.error.emit("Analytics engines not available")
            return
        self._dispatch(self._run_quant(security_id), self.quant_loaded)

    async def _run_quant(self, security_id: str) -> dict:
        uid = uuid.UUID(security_id)
        engine = QuantEngine()
        async with self._session_factory() as session:
            result = await engine.compute(session, security_id=uid)
        return result or {}

    # ------------------------------------------------------------------
    # Pillar 2: Scenario & Sensitivity (E8)
    # ------------------------------------------------------------------

    def run_scenario(self, security_id: str, scenario_type: str = "sensitivity_2d",
                     **kwargs) -> None:
        """Run scenario analysis via E8 ScenarioEngine.  Emits ``scenario_loaded``."""
        if not _ENGINES_AVAILABLE:
            self.error.emit("Analytics engines not available")
            return
        self._dispatch(
            self._run_scenario(security_id, scenario_type, **kwargs),
            self.scenario_loaded,
        )

    async def _run_scenario(self, security_id: str, scenario_type: str,
                            **kwargs) -> dict:
        uid = uuid.UUID(security_id)
        engine = ScenarioEngine()
        async with self._session_factory() as session:
            if scenario_type == "sensitivity_2d":
                result = await engine.run_sensitivity_2d(
                    session, uid,
                    row_variable=kwargs.get("row_variable", "discount_rate"),
                    col_variable=kwargs.get("col_variable", "terminal_growth"),
                    steps=kwargs.get("steps", 7),
                )
            elif scenario_type == "tornado":
                result = await engine.run_tornado(
                    session, uid,
                    variables=kwargs.get("variables"),
                    swing_pct=kwargs.get("swing_pct", 0.20),
                )
            elif scenario_type == "shock":
                result = await engine.run_shock(
                    session, uid,
                    shock_vector=kwargs.get("shock_vector", {}),
                )
            elif scenario_type == "breakeven":
                result = await engine.run_breakeven(
                    session, uid,
                    variable=kwargs.get("variable", "discount_rate"),
                    target_price=kwargs.get("target_price", 0),
                )
            else:
                result = None
        return result or {}

    def get_prebuilt_scenarios(self) -> list[dict]:
        """Return pre-built scenario definitions (sync, no DB needed)."""
        if not _ENGINES_AVAILABLE:
            return []
        return list_prebuilt_scenarios()

    # ==================================================================
    # Financial Analysis Suite: Smart Money / Auto Model / Structure
    # (These engines are pure-Python and always available.)
    # ==================================================================

    def load_notable_investors(self) -> None:
        """Load the curated notable-investor registry. Emits ``notable_investors_loaded``."""
        self._dispatch(self._load_notable_investors(), self.notable_investors_loaded)

    async def _load_notable_investors(self) -> list[dict]:
        from src.engines.smart_money import load_notable_investors
        return load_notable_investors()

    def load_congress_trades(self, politician: str | None = None, limit: int = 200) -> None:
        """Load congressional STOCK Act trades. Emits ``congress_trades_loaded``."""
        self._dispatch(self._load_congress_trades(politician, limit), self.congress_trades_loaded)

    async def _load_congress_trades(self, politician: str | None, limit: int) -> list[dict]:
        from src.engines.smart_money import classify_political_trade
        from src.models.congressional_trades import CongressionalTrade

        async with self._session_factory() as session:
            query = select(CongressionalTrade)
            if politician:
                query = query.where(CongressionalTrade.politician_name.ilike(f"%{politician}%"))
            query = query.order_by(desc(CongressionalTrade.transaction_date)).limit(limit)
            rows = (await session.execute(query)).scalars().all()

        out: list[dict] = []
        for t in rows:
            low = float(t.amount_range_low) if t.amount_range_low is not None else None
            high = float(t.amount_range_high) if t.amount_range_high is not None else None
            flags = classify_political_trade(
                {
                    "transaction_type": t.transaction_type,
                    "transaction_date": t.transaction_date,
                    "disclosure_date": t.disclosure_date,
                    "amount_range_low": low,
                    "amount_range_high": high,
                },
                committees=t.committees or [],
            )
            out.append(
                {
                    "politician_name": t.politician_name,
                    "ticker": t.ticker,
                    "transaction_type": t.transaction_type,
                    "transaction_date": t.transaction_date.isoformat() if t.transaction_date else None,
                    "amount_range_low": low,
                    "amount_range_high": high,
                    "size_bucket": flags["size_bucket"],
                    "is_late_disclosure": flags["is_late_disclosure"],
                }
            )
        return out

    def run_auto_model(self, entity_id: str) -> None:
        """Auto-build a COMPANY model from fundamentals. Emits ``auto_model_loaded``."""
        self._dispatch(self._run_auto_model(entity_id), self.auto_model_loaded)

    async def _run_auto_model(self, entity_id: str) -> dict:
        from src.engines.auto_model_builder import build_model

        uid = uuid.UUID(entity_id)
        data: dict = {}
        subject = str(entity_id)
        async with self._session_factory() as session:
            entity = (
                await session.execute(select(Entity).where(Entity.entity_id == uid))
            ).scalar_one_or_none()
            if entity is not None:
                subject = getattr(entity, "legal_name", None) or subject

            periods = (
                await session.execute(
                    select(FinancialPeriod)
                    .where(FinancialPeriod.entity_id == uid)
                    .order_by(desc(FinancialPeriod.period_end_date))
                    .limit(2)
                )
            ).scalars().all()
            statements = []
            for period in periods:
                stmt = (
                    await session.execute(
                        select(IncomeStatement).where(IncomeStatement.period_id == period.period_id)
                    )
                ).scalar_one_or_none()
                if stmt:
                    statements.append(stmt)

        if statements:
            latest = statements[0]
            rev = float(latest.total_revenue) if latest.total_revenue is not None else None
            op = float(latest.operating_income) if latest.operating_income is not None else None
            if rev and op is not None:
                data["ebitda_margin"] = round(op / rev * 100, 2)
            if len(statements) > 1 and statements[1].total_revenue and rev:
                prev_rev = float(statements[1].total_revenue)
                if prev_rev:
                    data["revenue_growth"] = round((rev - prev_rev) / prev_rev * 100, 2)

        return build_model("COMPANY", data, subject).to_dict()

    def run_complex_structure(self, entity_id: str) -> None:
        """Analyze complex structure from stored capital structure. Emits ``complex_structure_loaded``."""
        self._dispatch(self._run_complex_structure(entity_id), self.complex_structure_loaded)

    async def _run_complex_structure(self, entity_id: str) -> dict:
        from dataclasses import asdict

        from src.engines.complex_structure import analyze_complex_structure
        from src.models.capital_structure import CapitalStructure, DebtTranche

        uid = uuid.UUID(entity_id)
        subject = str(entity_id)
        debt_tranches: list[dict] = []
        async with self._session_factory() as session:
            entity = (
                await session.execute(select(Entity).where(Entity.entity_id == uid))
            ).scalar_one_or_none()
            if entity is not None:
                subject = getattr(entity, "legal_name", None) or subject

            cap = (
                await session.execute(
                    select(CapitalStructure)
                    .where(CapitalStructure.entity_id == uid)
                    .order_by(desc(CapitalStructure.as_of_date))
                    .limit(1)
                )
            ).scalar_one_or_none()
            if cap is not None:
                tranches = (
                    await session.execute(
                        select(DebtTranche).where(
                            DebtTranche.capital_structure_id == cap.capital_structure_id
                        )
                    )
                ).scalars().all()
                for t in tranches:
                    debt_tranches.append(
                        {
                            "instrument_name": t.instrument_name,
                            "principal_amount": float(t.principal_amount)
                            if t.principal_amount is not None
                            else 0.0,
                            "seniority_rank": t.seniority_rank,
                            "is_secured": (t.instrument_type or "").upper().startswith("SECURED")
                            if t.instrument_type
                            else False,
                        }
                    )

        report = analyze_complex_structure({"debt_tranches": debt_tranches}, subject)
        return asdict(report)

    # ------------------------------------------------------------------
    # Debt maturity (DDIS)
    # ------------------------------------------------------------------

    def run_debt_maturity(self, entity_id: str) -> None:
        """Load the latest debt maturity profile. Emits ``debt_maturity_loaded``."""
        self._dispatch(self._run_debt_maturity(entity_id), self.debt_maturity_loaded)

    async def _run_debt_maturity(self, entity_id: str) -> dict:
        from src.models.debt_maturity import DebtMaturityProfile, MaturityBucket

        uid = uuid.UUID(entity_id)
        async with self._session_factory() as session:
            subject = await self._entity_name(session, uid)
            profile = (
                await session.execute(
                    select(DebtMaturityProfile)
                    .where(DebtMaturityProfile.entity_id == uid)
                    .order_by(desc(DebtMaturityProfile.as_of_date))
                    .limit(1)
                )
            ).scalar_one_or_none()
            if profile is None:
                return {"subject": subject, "profile": {}, "buckets": []}
            buckets = (
                await session.execute(
                    select(MaturityBucket)
                    .where(MaturityBucket.profile_id == profile.profile_id)
                    .order_by(MaturityBucket.year)
                )
            ).scalars().all()

        return {
            "subject": subject,
            "profile": {
                "weighted_avg_maturity_years": _to_float(profile.weighted_avg_maturity_years),
                "weighted_avg_coupon": _to_float(profile.weighted_avg_coupon),
                "debt_maturing_1yr": _to_float(profile.debt_maturing_1yr),
                "pct_debt_maturing_1yr": _to_float(profile.pct_debt_maturing_1yr),
                "pct_debt_maturing_3yr": _to_float(profile.pct_debt_maturing_3yr),
                "cash_to_1yr_maturities": _to_float(profile.cash_to_1yr_maturities),
                "maturity_wall_alert": bool(profile.maturity_wall_alert),
                "near_term_stress": bool(profile.near_term_stress),
            },
            "buckets": [
                {"year": b.year, "total_amount": _to_float(b.total_amount), "breakdown": b.breakdown or {}}
                for b in buckets
            ],
        }

    # ------------------------------------------------------------------
    # Credit ratings (CRPR)
    # ------------------------------------------------------------------

    def run_credit_ratings(self, entity_id: str) -> None:
        """Load current ratings + rating actions. Emits ``credit_ratings_loaded``."""
        self._dispatch(self._run_credit_ratings(entity_id), self.credit_ratings_loaded)

    async def _run_credit_ratings(self, entity_id: str) -> dict:
        from src.models.credit_rating import CreditRatingEvent, CurrentCreditRating

        uid = uuid.UUID(entity_id)
        async with self._session_factory() as session:
            subject = await self._entity_name(session, uid)
            current = (
                await session.execute(
                    select(CurrentCreditRating).where(CurrentCreditRating.entity_id == uid)
                )
            ).scalars().all()
            events = (
                await session.execute(
                    select(CreditRatingEvent)
                    .where(CreditRatingEvent.entity_id == uid)
                    .order_by(desc(CreditRatingEvent.event_date))
                    .limit(50)
                )
            ).scalars().all()

        return {
            "subject": subject,
            "current": [
                {
                    "agency": c.agency,
                    "current_rating": c.current_rating,
                    "outlook": c.outlook,
                    "watch_status": c.watch_status,
                    "is_investment_grade": c.is_investment_grade,
                    "last_action_date": c.last_action_date.isoformat() if c.last_action_date else None,
                }
                for c in current
            ],
            "events": [
                {
                    "event_date": e.event_date.isoformat() if e.event_date else None,
                    "agency": e.agency,
                    "old_rating": e.old_rating,
                    "new_rating": e.new_rating,
                    "direction": e.direction,
                    "notches_changed": e.notches_changed,
                }
                for e in events
            ],
        }

    # ------------------------------------------------------------------
    # New issuance (ISSD)
    # ------------------------------------------------------------------

    def run_issuance(self, entity_id: str | None = None, limit: int = 100) -> None:
        """Load primary-market issuance. Emits ``issuance_loaded``."""
        self._dispatch(self._run_issuance(entity_id, limit), self.issuance_loaded)

    async def _run_issuance(self, entity_id: str | None, limit: int) -> list[dict]:
        from src.models.bond_issuance import BondIssuance

        async with self._session_factory() as session:
            query = select(BondIssuance)
            if entity_id:
                query = query.where(BondIssuance.issuer_entity_id == uuid.UUID(entity_id))
            query = query.order_by(desc(BondIssuance.pricing_date)).limit(limit)
            rows = (await session.execute(query)).scalars().all()

        return [
            {
                "pricing_date": d.pricing_date.isoformat() if d.pricing_date else None,
                "coupon_rate": _to_float(d.coupon_rate),
                "maturity_date": d.maturity_date.isoformat() if d.maturity_date else None,
                "issued_size_mm": _to_float(d.issued_size_mm),
                "final_spread_bps": d.final_spread_bps,
                "issue_yield": _to_float(d.issue_yield),
                "seniority": d.seniority,
            }
            for d in rows
        ]

    # ------------------------------------------------------------------
    # Portfolios (PORT)
    # ------------------------------------------------------------------

    def load_portfolios(self, limit: int = 200) -> None:
        """Load managed portfolios. Emits ``portfolios_loaded``."""
        self._dispatch(self._load_portfolios(limit), self.portfolios_loaded)

    async def _load_portfolios(self, limit: int) -> list[dict]:
        from src.models.portfolio import Portfolio

        async with self._session_factory() as session:
            rows = (
                await session.execute(
                    select(Portfolio)
                    .where(Portfolio.deleted_at.is_(None))
                    .order_by(Portfolio.portfolio_name)
                    .limit(limit)
                )
            ).scalars().all()

        return [
            {
                "portfolio_name": p.portfolio_name,
                "portfolio_type": p.portfolio_type,
                "inception_date": p.inception_date.isoformat() if p.inception_date else None,
                "base_currency": p.base_currency,
                "initial_cash": _to_float(p.initial_cash),
                "current_cash": _to_float(p.current_cash),
                "status": p.status,
            }
            for p in rows
        ]

    async def _entity_name(self, session: AsyncSession, entity_id: uuid.UUID) -> str:
        entity = (
            await session.execute(select(Entity).where(Entity.entity_id == entity_id))
        ).scalar_one_or_none()
        if entity is not None:
            return getattr(entity, "legal_name", None) or str(entity_id)
        return str(entity_id)
