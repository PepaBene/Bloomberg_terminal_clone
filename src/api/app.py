"""FastAPI application factory for Bloomberg Data Fabric API."""

import logging
import subprocess
import sys
import time
import uuid

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text

from src.api.auth.dependencies import get_current_user
from src.api.middleware import RequestContextMiddleware
from src.api.middleware.audit import AuditLogMiddleware
from src.api.utils.field_selection import FieldSelectionMiddleware
from src.config import settings
from src.database import get_session_factory
from src.models.analytics import AnalyticsResult
from src.schemas.common import ErrorDetail, ErrorResponse, ResponseMeta

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Bloomberg Data Fabric API starting up")

    # --- Validate dependencies on startup ---
    # Check database connectivity
    try:
        async with get_session_factory()() as session:
            await session.execute(text("SELECT 1"))
        logger.info("Database connection: OK")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")

    # Check required environment / config
    try:
        if not settings.DATABASE_URL:
            logger.error("DATABASE_URL not configured")
    except Exception as e:
        logger.error(f"Failed to load settings: {e}")

    # [Bug 73 fix] Auto-seed on startup if DB is empty
    try:
        async with get_session_factory()() as session:
            count = await session.scalar(select(func.count()).select_from(AnalyticsResult))
            if count == 0:
                logger.info("AnalyticsResult is empty. Triggering auto-seed batch run in background...")
                subprocess.Popen([sys.executable, "scripts/run_analytics_batch.py", "--engine", "all"])
    except Exception as e:
        logger.warning("Auto-seed failed to start: %s", e)

    yield
    logger.info("Bloomberg Data Fabric API shutting down")


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""

    # Global auth dependency only when REQUIRE_AUTH is on. With it always
    # on, every endpoint returns 401 to anonymous callers — that breaks
    # the test suite and the open-by-default development workflow. Routes
    # that need user identity should depend on ``get_optional_user``
    # individually instead.
    #
    # [Bug 74] Flipping REQUIRE_AUTH's default to True was considered, since
    # a real auth flow does exist (/auth/token issues JWTs, get_current_user
    # validates them — see src/api/routers/auth.py). It was NOT flipped:
    # ~88 tests under tests/test_api/ exercise the API via the `client`
    # fixture (tests/test_api/conftest.py) with no Bearer token, and that
    # fixture calls create_app() directly with no REQUIRE_AUTH override, so
    # a flipped default would turn every one of those into a 401 regression.
    # Fixing that properly means adding a test-only override in
    # tests/conftest.py / tests/test_api/conftest.py, which is out of scope
    # for this change. Until that's done, make the gap loud instead of silent.
    if not settings.REQUIRE_AUTH:
        logger.warning(
            "REQUIRE_AUTH is False — API is running without authentication "
            "enforcement. Do not use this configuration in production."
        )
    global_deps = [Depends(get_current_user)] if settings.REQUIRE_AUTH else []
    app = FastAPI(
        title="Bloomberg Data Fabric API",
        version="1.0.0",
        description="Unified financial data platform providing reference, entity, and security data.",
        lifespan=lifespan,
        dependencies=global_deps,
    )

    # ------------------------------------------------------------------
    # Middleware (Starlette executes middleware in reverse registration
    # order, so the last-registered middleware runs first on request.)
    # ------------------------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, restrict to actual frontend origins
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(AuditLogMiddleware)
    app.add_middleware(FieldSelectionMiddleware)

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------
    # Auth is wired in via:
    #   - /auth/token  (login endpoint)
    #   - /auth/me     (current user info)
    #   - get_optional_user dependency in src/api/deps.py (for gradual rollout)
    #   - get_current_user dependency on write endpoints (approve/reject)
    #
    # To enforce auth globally add:
    #   from fastapi import Depends
    #   from src.api.auth.dependencies import get_current_user
    #   app = FastAPI(..., dependencies=[Depends(get_current_user)])
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Router registration order
    # ------------------------------------------------------------------
    # IMPORTANT: Registration order matters for path resolution. FastAPI
    # matches routes in the order they are registered, so more-specific
    # paths must come BEFORE parameterized catch-all paths:
    #
    #   1. Auth router (no prefix -- handles /auth/*)
    #   2. Pillar 1 core routers (/v1)
    #      - security_finder BEFORE securities (avoids /securities/find
    #        being captured by /securities/{security_id})
    #   3. Pillar 2 analytics routers (carry their own /v2 prefix)
    #   4. Pillar 1 & 2 supplement routers (/v1)
    #   5. Pillar 2 FI supplement routers (carry their own prefix)
    #   6. Pillar 3 research & intelligence routers (/v3, /v4)
    #      - alerts_expansion BEFORE alerts (avoids /alerts/quality-scores
    #        being captured by /alerts/{entity_id})
    #   7. Pillar 4 portfolio routers (/v4)
    #      - portfolio_risk BEFORE portfolio_performance BEFORE
    #        portfolio_watchlists BEFORE portfolios (avoids sub-paths
    #        being captured by /portfolios/{portfolio_id})
    #   8. Health check and exception handlers (last)
    # ------------------------------------------------------------------
    # A-003: router-import failures were previously only visible in logs.
    # Collected here and surfaced on /health so an operator doesn't need
    # active log monitoring to notice a router silently failed to load.
    router_import_failures: list[str] = []

    # A-008: registration-order constraints (see the block comment above)
    # were previously enforced only by code comments. Each critical
    # include_router call below records its position here; _assert_
    # registration_order (called just before create_app() returns) turns a
    # future reordering mistake into a startup failure instead of a silent
    # routing bug.
    order_marks: dict[str, int] = {}

    from src.api.routers.auth import router as auth_router
    app.include_router(auth_router)

    from src.api.routers.reference import router as reference_router
    app.include_router(reference_router, prefix="/v1")

    from src.api.routers.entities import router as entities_router
    app.include_router(entities_router, prefix="/v1")

    # NOTE: Security Finder must be registered BEFORE Securities to avoid
    # /securities/find being captured by /securities/{security_id}
    from src.api.routers.security_finder import router as security_finder_router
    order_marks["security_finder"] = len(app.routes)
    app.include_router(security_finder_router, prefix="/v1")

    from src.api.routers.securities import router as securities_router
    order_marks["securities"] = len(app.routes)
    app.include_router(securities_router, prefix="/v1")

    from src.api.routers.resolution import router as resolution_router
    app.include_router(resolution_router, prefix="/v1")

    from src.api.routers.macro import router as macro_router
    app.include_router(macro_router, prefix="/v1")

    from src.api.routers.fundamentals import router as fundamentals_router
    app.include_router(fundamentals_router, prefix="/v1")

    from src.api.routers.ownership import router as ownership_router
    app.include_router(ownership_router, prefix="/v1")

    from src.api.routers.esg import router as esg_router
    app.include_router(esg_router, prefix="/v1")

    from src.api.routers.corporate_actions import router as corporate_actions_router
    app.include_router(corporate_actions_router, prefix="/v1")

    from src.api.routers.relationships import router as relationships_router
    app.include_router(relationships_router, prefix="/v1")

    # ------------------------------------------------------------------
    # Pillar 2: Analytics Engines
    # ------------------------------------------------------------------
    from src.api.routers.analytics import router as analytics_router
    app.include_router(analytics_router)

    from src.api.routers.screening import router as screening_router
    app.include_router(screening_router)

    from src.api.routers.flows import router as flows_router
    app.include_router(flows_router)

    from src.api.routers.risk import router as risk_router
    app.include_router(risk_router)

    from src.api.routers.quant import router as quant_router
    app.include_router(quant_router, prefix="/v2/analytics/quant")
    # P4-A-004: also serve the same endpoints under /v4/quant — no
    # existing frontend QUANT entry to align to (endpoints.ts has none),
    # so keep the legacy /v2 mount for existing callers and add the /v4
    # mount other Pillar-4 routers use.
    app.include_router(quant_router, prefix="/v4/quant")

    from src.api.routers.scenario import router as scenario_router
    app.include_router(scenario_router)

    # Pillar 1 Supplement routers
    from src.api.routers.capital_structure import router as capital_structure_router
    app.include_router(capital_structure_router, prefix="/v1")

    from src.api.routers.debt_maturity import router as debt_maturity_router
    app.include_router(debt_maturity_router, prefix="/v1")

    from src.api.routers.credit_rating import router as credit_rating_router
    app.include_router(credit_rating_router, prefix="/v1")

    from src.api.routers.calendar import router as calendar_router
    app.include_router(calendar_router, prefix="/v1")

    # Pillar 1 Supplement – Part 2: Macro extensions
    from src.api.routers.yield_curve import router as yield_curve_router
    app.include_router(yield_curve_router, prefix="/v1")

    from src.api.routers.fed_meeting import router as fed_meeting_router
    app.include_router(fed_meeting_router, prefix="/v1")

    from src.api.routers.money_market import router as money_market_router
    app.include_router(money_market_router, prefix="/v1")

    # Pillar 1 Supplement – Part 3: Deals / IPO / Earnings
    from src.api.routers.ma_deals import router as ma_deals_router
    app.include_router(ma_deals_router, prefix="/v1")

    from src.api.routers.ipo import router as ipo_router
    app.include_router(ipo_router, prefix="/v1")

    from src.api.routers.earnings_intelligence import router as earnings_router
    app.include_router(earnings_router, prefix="/v1")

    # Pillar 1 Supplement – Part 4: Fund Holdings / Executives
    from src.api.routers.fund_holdings import router as fund_holdings_router
    app.include_router(fund_holdings_router, prefix="/v1")

    from src.api.routers.executives import router as executives_router
    app.include_router(executives_router, prefix="/v1")

    from src.api.routers.technical_studies import router as technical_studies_router
    app.include_router(technical_studies_router, prefix="/v1")

    from src.api.routers.custom_classifications import router as custom_classifications_router
    app.include_router(custom_classifications_router, prefix="/v1")

    from src.api.routers.esg_temperature import router as esg_temperature_router
    app.include_router(esg_temperature_router, prefix="/v1")

    # Pillar 2 Supplement – Part 1: Yield Curve Analytics
    from src.api.routers.yield_curve_analytics import router as yield_curve_analytics_router
    app.include_router(yield_curve_analytics_router, prefix="/v1")

    # Pillar 2 Supplement – Part 5: Events Calendar, Market Movers
    from src.api.routers.events_calendar_engine import router as events_calendar_engine_router
    app.include_router(events_calendar_engine_router, prefix="/v1")

    from src.api.routers.market_movers import router as market_movers_router
    app.include_router(market_movers_router, prefix="/v1")

    # Pillar 2 Supplement – Part 4: Custom Index + Portfolio Upload
    from src.api.routers.custom_index import router as custom_index_router
    app.include_router(custom_index_router, prefix="/v1")

    from src.api.routers.portfolio_upload import router as portfolio_upload_router
    app.include_router(portfolio_upload_router, prefix="/v1")

    # Pillar 2 Supplement – Part 3: Backtesting
    from src.api.routers.backtesting import router as backtesting_router
    app.include_router(backtesting_router, prefix="/v1")

    from src.api.routers.backtesting import strategies_router as backtest_strategies_router
    app.include_router(backtest_strategies_router)

    # Pillar 2 Frontend Bugs 93-95: Benchmarks (standard indices + custom)
    from src.api.routers.benchmarks import router as benchmarks_router
    app.include_router(benchmarks_router, prefix="/v1")

    # Pillar 2 Supplement – Part 2: Default Risk Scoring
    from src.api.routers.default_risk import router as default_risk_router
    app.include_router(default_risk_router, prefix="/v1")

    # Pillar 2 Supplement – Part 6: Custom Data + Technical Backtest
    from src.api.routers.custom_data import router as custom_data_router
    app.include_router(custom_data_router, prefix="/v1")

    from src.api.routers.technical_backtest import router as technical_backtest_router
    app.include_router(technical_backtest_router, prefix="/v1")

    # Pillar 2 Supplement – Part 7: AI Company Intelligence + Primers
    from src.api.routers.company_intelligence import router as company_intelligence_router
    app.include_router(company_intelligence_router, prefix="/v1")

    from src.api.routers.company_primer import router as company_primer_router
    app.include_router(company_primer_router, prefix="/v1")

    # Pillar 2 Supplement – Part 8: Sentiment Analysis
    from src.api.routers.sentiment import router as sentiment_router
    app.include_router(sentiment_router, prefix="/v1")

    # D11 FI Supplement – Part 2: Treasuries
    from src.api.routers.fi_treasuries import router as fi_treasuries_router
    app.include_router(fi_treasuries_router, prefix="/v1")

    # D11 FI Supplement – Part 3: Fixed Income Yield Curve
    from src.api.routers.fi_yield_curve import router as fi_yield_curve_router
    app.include_router(fi_yield_curve_router, prefix="/v1")

    # D11 FI Supplement – Part 4: Corporate Bonds + TRACE
    from src.api.routers.fi_bonds import router as fi_bonds_router
    app.include_router(fi_bonds_router, prefix="/v1")

    # D11 FI Supplement – Part 5: Credit Rating Analytics
    from src.api.routers.fi_ratings import router as fi_ratings_router
    app.include_router(fi_ratings_router, prefix="/v1")

    # D11 FI Supplement – Part 6: Credit Spreads
    from src.api.routers.fi_spreads import router as fi_spreads_router
    app.include_router(fi_spreads_router, prefix="/v1")

    # D11 FI Supplement – Part 7: Bond Issuances
    from src.api.routers.fi_issuances import router as fi_issuances_router
    app.include_router(fi_issuances_router, prefix="/v1")

    # D11 FI Supplement – Part 8: Agency Bonds
    from src.api.routers.fi_agency_bonds import router as fi_agency_bonds_router
    app.include_router(fi_agency_bonds_router, prefix="/v1")

    # Pillar 2 FI Supplement – Part 1: Bond Analytics
    from src.api.routers.fi_bond_analytics import router as fi_bond_analytics_router
    app.include_router(fi_bond_analytics_router)

    # Pillar 2 FI Supplement – Part 2: Duration Analytics
    from src.api.routers.fi_duration import router as fi_duration_router
    app.include_router(fi_duration_router)

    # Pillar 2 FI Supplement – Part 3: Spread Analytics
    from src.api.routers.fi_spread_analytics import router as fi_spread_analytics_router
    app.include_router(fi_spread_analytics_router)

    # Pillar 2 FI Supplement – Part 4: Credit Quality Analytics
    from src.api.routers.fi_credit_quality import router as fi_credit_quality_router
    app.include_router(fi_credit_quality_router)

    # Pillar 2 FI Supplement – Part 5: FI Risk Analytics
    from src.api.routers.fi_risk import router as fi_risk_router
    app.include_router(fi_risk_router)

    # Pillar 2 FI Supplement – Part 6: FI Screening & Scenarios
    from src.api.routers.fi_screening import router as fi_screening_router
    app.include_router(fi_screening_router)

    # Pillar 2 FI Supplement – Part 7: Issuer FI Profile + Cross-Asset Signals
    from src.api.routers.fi_issuer_profile import router as fi_issuer_profile_router
    app.include_router(fi_issuer_profile_router)

    from src.api.routers.fi_cross_asset import router as fi_cross_asset_router
    app.include_router(fi_cross_asset_router)

    # ------------------------------------------------------------------
    # Pillar 3: Research & Intelligence
    # Each import is wrapped in try/except for graceful degradation --
    # if a module fails to load the rest of the API still starts.
    # ------------------------------------------------------------------
    try:
        from src.api.routers.filing_intelligence import router as filing_intel_router
        app.include_router(filing_intel_router, prefix="/v3")
    except Exception as e:
        logger.warning(f"Failed to import router filing_intelligence: {e}")
        router_import_failures.append("filing_intelligence")

    try:
        from src.api.routers.governance_intelligence import router as governance_intel_router
        app.include_router(governance_intel_router, prefix="/v3")
    except Exception as e:
        logger.warning(f"Failed to import router governance_intelligence: {e}")
        router_import_failures.append("governance_intelligence")

    try:
        from src.api.routers.news import router as news_router
        app.include_router(news_router, prefix="/v3")
    except Exception as e:
        logger.warning(f"Failed to import router news: {e}")
        router_import_failures.append("news")

    # NOTE: Alerts Expansion must be registered BEFORE Alerts to avoid
    # /alerts/quality-scores being captured by /alerts/{entity_id}
    try:
        from src.api.routers.alerts_expansion import router as alerts_exp_router
        order_marks["alerts_expansion"] = len(app.routes)
        app.include_router(alerts_exp_router, prefix="/v3")
    except Exception as e:
        logger.warning(f"Failed to import router alerts_expansion: {e}")
        router_import_failures.append("alerts_expansion")

    try:
        from src.api.routers.alerts import router as alerts_router
        order_marks["alerts"] = len(app.routes)
        app.include_router(alerts_router, prefix="/v3")
    except Exception as e:
        logger.warning(f"Failed to import router alerts: {e}")
        router_import_failures.append("alerts")

    # Pillar 3 Phase 2: Earnings, Sentiment, Economic Calendar, Company Intel
    try:
        from src.api.routers.earnings_p2 import router as earnings_p2_router
        app.include_router(earnings_p2_router, prefix="/v3")
    except Exception as e:
        logger.warning(f"Failed to import router earnings_p2: {e}")
        router_import_failures.append("earnings_p2")

    try:
        from src.api.routers.sentiment_p2 import router as sentiment_p2_router
        app.include_router(sentiment_p2_router, prefix="/v3")
    except Exception as e:
        logger.warning(f"Failed to import router sentiment_p2: {e}")
        router_import_failures.append("sentiment_p2")

    try:
        from src.api.routers.economic_calendar import router as economic_calendar_router
        app.include_router(economic_calendar_router, prefix="/v3")
    except Exception as e:
        logger.warning(f"Failed to import router economic_calendar: {e}")
        router_import_failures.append("economic_calendar")

    try:
        from src.api.routers.company_intel_p2 import router as company_intel_p2_router
        app.include_router(company_intel_p2_router, prefix="/v3")
    except Exception as e:
        logger.warning(f"Failed to import router company_intel_p2: {e}")
        router_import_failures.append("company_intel_p2")

    # Pillar 3 Phase 3A: Industry & Competitive Intelligence
    try:
        from src.api.routers.industry import router as industry_router
        app.include_router(industry_router, prefix="/v3")
    except Exception as e:
        logger.warning(f"Failed to import router industry: {e}")
        router_import_failures.append("industry")

    try:
        from src.api.routers.competitive import router as competitive_router
        app.include_router(competitive_router, prefix="/v3")
    except Exception as e:
        logger.warning(f"Failed to import router competitive: {e}")
        router_import_failures.append("competitive")

    # Pillar 3 Phase 3B: Global Intelligence
    try:
        from src.api.routers.global_intelligence import router as global_intel_router
        app.include_router(global_intel_router, prefix="/v3")
    except Exception as e:
        logger.warning(f"Failed to import router global_intelligence: {e}")
        router_import_failures.append("global_intelligence")

    # Pillar 3 Phase 3C: FI Intelligence
    try:
        from src.api.routers.fi_intelligence import router as fi_intel_router
        app.include_router(fi_intel_router, prefix="/v3")
    except Exception as e:
        logger.warning(f"Failed to import router fi_intelligence: {e}")
        router_import_failures.append("fi_intelligence")

    # Pillar 3 Phase 4A: AI Research Layer
    try:
        from src.api.routers.research_primers import router as research_primers_router
        app.include_router(research_primers_router, prefix="/v4")
    except Exception as e:
        logger.warning(f"Failed to import router research_primers: {e}")
        router_import_failures.append("research_primers")

    try:
        from src.api.routers.research_briefings import router as research_briefings_router
        app.include_router(research_briefings_router, prefix="/v4")
    except Exception as e:
        logger.warning(f"Failed to import router research_briefings: {e}")
        router_import_failures.append("research_briefings")

    try:
        from src.api.routers.research_anomalies import router as research_anomalies_router
        app.include_router(research_anomalies_router, prefix="/v4")
    except Exception as e:
        logger.warning(f"Failed to import router research_anomalies: {e}")
        router_import_failures.append("research_anomalies")

    # Pillar 3 Phase 4B: Semantic Search, Investment Thesis, Analyst Q&A
    try:
        from src.api.routers.research_search import router as research_search_router
        app.include_router(research_search_router, prefix="/v4")
    except Exception as e:
        logger.warning(f"Failed to import router research_search: {e}")
        router_import_failures.append("research_search")

    try:
        from src.api.routers.research_thesis import router as research_thesis_router
        app.include_router(research_thesis_router, prefix="/v4")
    except Exception as e:
        logger.warning(f"Failed to import router research_thesis: {e}")
        router_import_failures.append("research_thesis")

    try:
        from src.api.routers.research_qa import router as research_qa_router
        app.include_router(research_qa_router, prefix="/v4")
    except Exception as e:
        logger.warning(f"Failed to import router research_qa: {e}")
        router_import_failures.append("research_qa")

    # Pillar 3 Phase 4C: Macro Themes, Scenarios, Intelligent Alerts, Earnings Intelligence
    try:
        from src.api.routers.research_themes import router as research_themes_router
        app.include_router(research_themes_router, prefix="/v4")
    except Exception as e:
        logger.warning(f"Failed to import router research_themes: {e}")
        router_import_failures.append("research_themes")

    try:
        from src.api.routers.research_alerts_p4 import router as research_alerts_p4_router
        app.include_router(research_alerts_p4_router, prefix="/v4")
    except Exception as e:
        logger.warning(f"Failed to import router research_alerts_p4: {e}")
        router_import_failures.append("research_alerts_p4")

    # AI Layer 1 — Interpreter (AI_THREE_LAYER_REBUILD_PLAN.md Phase 1)
    try:
        from src.api.routers.interpret import router as interpret_router
        app.include_router(interpret_router, prefix="/v5")
    except Exception as e:
        logger.warning(f"Failed to import router interpret: {e}")
        router_import_failures.append("interpret")

    # AI Layer 2 — News analysis (AI_THREE_LAYER_REBUILD_PLAN.md Phase 2 §4.4)
    try:
        from src.api.routers.news_analysis import router as news_analysis_router
        app.include_router(news_analysis_router, prefix="/v5")
    except Exception as e:
        logger.warning(f"Failed to import router news_analysis: {e}")
        router_import_failures.append("news_analysis")

    # AI Layer 2 — on-demand Deep Research (AI_THREE_LAYER_REBUILD_PLAN.md Phase 2 §4.6)
    try:
        from src.api.routers.research_deep import router as research_deep_router
        app.include_router(research_deep_router, prefix="/v5")
    except Exception as e:
        logger.warning(f"Failed to import router research_deep: {e}")
        router_import_failures.append("research_deep")

    # AI Layer 3 — Financial Adviser: portfolio advisor tools (AI_THREE_LAYER_REBUILD_PLAN.md Phase 3 §5.1)
    try:
        from src.api.routers.portfolio_advisor import router as portfolio_advisor_router
        app.include_router(portfolio_advisor_router, prefix="/v5")
    except Exception as e:
        logger.warning(f"Failed to import router portfolio_advisor: {e}")
        router_import_failures.append("portfolio_advisor")

    # AI Layer 3 — Financial Adviser: chat (AI_THREE_LAYER_REBUILD_PLAN.md Phase 3 §5.3)
    try:
        from src.api.routers.adviser_chat import router as adviser_chat_router
        app.include_router(adviser_chat_router, prefix="/v5")
    except Exception as e:
        logger.warning(f"Failed to import router adviser_chat: {e}")
        router_import_failures.append("adviser_chat")

    # ------------------------------------------------------------------
    # Pillar 4 Phase 3: Risk Management
    # NOTE: Risk router must be registered BEFORE Performance and Portfolios
    # to avoid /portfolios/risk/scenarios being captured by /portfolios/{portfolio_id}
    # ------------------------------------------------------------------
    from src.api.routers.portfolio_risk import router as portfolio_risk_router
    order_marks["portfolio_risk"] = len(app.routes)
    app.include_router(portfolio_risk_router, prefix="/v4")

    # ------------------------------------------------------------------
    # Pillar 4 Phase 2: Performance & Attribution
    # NOTE: Performance router must be registered BEFORE Portfolios to avoid
    # /portfolios/performance/compare being captured by /portfolios/{portfolio_id}
    # ------------------------------------------------------------------
    from src.api.routers.portfolio_performance import router as perf_router
    order_marks["portfolio_performance"] = len(app.routes)
    app.include_router(perf_router, prefix="/v4")

    # ------------------------------------------------------------------
    # Pillar 4 Phase 1: Portfolio Foundation
    # NOTE: Watchlists router must be registered BEFORE Portfolios to avoid
    # /portfolios/watchlists being captured by /portfolios/{portfolio_id}
    # ------------------------------------------------------------------
    from src.api.routers.portfolio_watchlists import router as portfolio_watchlists_router
    order_marks["portfolio_watchlists"] = len(app.routes)
    app.include_router(portfolio_watchlists_router, prefix="/v4")

    from src.api.routers.portfolios import router as portfolios_router
    order_marks["portfolios"] = len(app.routes)
    app.include_router(portfolios_router, prefix="/v4")

    # ------------------------------------------------------------------
    # Pillar 4 Phase 4: Research Notes
    # ------------------------------------------------------------------
    from src.api.routers.research_notes import router as research_notes_router
    app.include_router(research_notes_router, prefix="/v4")

    # ------------------------------------------------------------------
    # Financial Analysis Suite: Smart-Money tracking, Auto Model Builder,
    # and Complex Financial Structure analysis (free-data, EDGAR/STOCK Act).
    # ------------------------------------------------------------------
    from src.api.routers.smart_money import router as smart_money_router
    app.include_router(smart_money_router, prefix="/v1")

    from src.api.routers.auto_model import router as auto_model_router
    app.include_router(auto_model_router, prefix="/v1")

    from src.api.routers.complex_structure import router as complex_structure_router
    app.include_router(complex_structure_router, prefix="/v1")

    # A-008: fail startup loudly if a documented ordering constraint was
    # violated, instead of relying solely on the block comment above to
    # keep future router additions in the right order.
    _ordering_constraints = [
        ("security_finder", "securities"),
        ("alerts_expansion", "alerts"),
        ("portfolio_risk", "portfolio_performance"),
        ("portfolio_performance", "portfolio_watchlists"),
        ("portfolio_watchlists", "portfolios"),
    ]
    for before, after in _ordering_constraints:
        if before not in order_marks or after not in order_marks:
            continue  # router failed to import — already tracked as a failure above
        if order_marks[before] >= order_marks[after]:
            raise RuntimeError(
                f"Router registration order violated: '{before}' must be "
                f"registered before '{after}' (see block comment above "
                f"router registration) to avoid its specific paths being "
                f"captured by the other router's catch-all path."
            )

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------
    @app.get("/health", tags=["health"], response_model=None)
    async def health_check():
        # ``dict | JSONResponse`` is not a valid Pydantic field, so the
        # router can't auto-generate a response model. Disable schema
        # generation here (response_model=None) and let the function
        # return either a plain dict or a JSONResponse on failure.
        try:
            async with get_session_factory()() as session:
                await session.execute(text("SELECT 1"))
            status: dict = {"status": "ok", "database": "connected"}
            # A-003: surface router-import failures here so they're
            # discoverable without active log monitoring.
            if router_import_failures:
                status["status"] = "degraded"
                status["router_import_failures"] = list(router_import_failures)
            return status
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return JSONResponse(
                status_code=503,
                content={"status": "degraded", "database": str(e)},
            )

    # ------------------------------------------------------------------
    # Global exception handlers
    # ------------------------------------------------------------------
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        start_time = getattr(request.state, "start_time", time.perf_counter())
        processing_time = int((time.perf_counter() - start_time) * 1000)

        logger.warning("ValueError on %s %s: %s", request.method, request.url.path, exc)

        error_response = ErrorResponse(
            errors=[
                ErrorDetail(
                    code="VALIDATION_ERROR",
                    message=str(exc),
                ),
            ],
            meta=ResponseMeta(
                request_id=request_id,
                processing_time_ms=processing_time,
            ),
        )
        return JSONResponse(
            status_code=422,
            content=error_response.model_dump(mode="json"),
        )

    # A-006: RuntimeError is what the AI/embedding clients raise for
    # "not configured" (missing ANTHROPIC_API_KEY/GOOGLE_API_KEY) — a
    # distinct, expected condition, not an unexpected server bug. Without
    # this it fell through to the generic 500 handler below and looked
    # identical to a real crash.
    @app.exception_handler(RuntimeError)
    async def runtime_error_handler(request: Request, exc: RuntimeError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        start_time = getattr(request.state, "start_time", time.perf_counter())
        processing_time = int((time.perf_counter() - start_time) * 1000)

        logger.warning("RuntimeError on %s %s: %s", request.method, request.url.path, exc)

        error_response = ErrorResponse(
            errors=[
                ErrorDetail(
                    code="SERVICE_UNAVAILABLE",
                    message=str(exc),
                ),
            ],
            meta=ResponseMeta(
                request_id=request_id,
                processing_time_ms=processing_time,
            ),
        )
        return JSONResponse(
            status_code=503,
            content=error_response.model_dump(mode="json"),
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        start_time = getattr(request.state, "start_time", time.perf_counter())
        processing_time = int((time.perf_counter() - start_time) * 1000)

        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)

        error_response = ErrorResponse(
            errors=[
                ErrorDetail(
                    code="INTERNAL_SERVER_ERROR",
                    message="An unexpected error occurred.",
                ),
            ],
            meta=ResponseMeta(
                request_id=request_id,
                processing_time_ms=processing_time,
            ),
        )
        return JSONResponse(
            status_code=500,
            content=error_response.model_dump(mode="json"),
        )

    return app


app = create_app()
