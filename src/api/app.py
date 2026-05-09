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
        allow_origins=settings.ALLOWED_ORIGINS,
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
    from src.api.routers.auth import router as auth_router
    app.include_router(auth_router)

    from src.api.routers.reference import router as reference_router
    app.include_router(reference_router, prefix="/v1")

    from src.api.routers.entities import router as entities_router
    app.include_router(entities_router, prefix="/v1")

    # NOTE: Security Finder must be registered BEFORE Securities to avoid
    # /securities/find being captured by /securities/{security_id}
    from src.api.routers.security_finder import router as security_finder_router
    app.include_router(security_finder_router, prefix="/v1")

    from src.api.routers.securities import router as securities_router
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
    app.include_router(quant_router)

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
    # ------------------------------------------------------------------
    from src.api.routers.filing_intelligence import router as filing_intel_router
    app.include_router(filing_intel_router, prefix="/v3")

    from src.api.routers.governance_intelligence import router as governance_intel_router
    app.include_router(governance_intel_router, prefix="/v3")

    from src.api.routers.news import router as news_router
    app.include_router(news_router, prefix="/v3")

    # NOTE: Alerts Expansion must be registered BEFORE Alerts to avoid
    # /alerts/quality-scores being captured by /alerts/{entity_id}
    from src.api.routers.alerts_expansion import router as alerts_exp_router
    app.include_router(alerts_exp_router, prefix="/v3")

    from src.api.routers.alerts import router as alerts_router
    app.include_router(alerts_router, prefix="/v3")

    # Pillar 3 Phase 2: Earnings, Sentiment, Economic Calendar, Company Intel
    from src.api.routers.earnings_p2 import router as earnings_p2_router
    app.include_router(earnings_p2_router, prefix="/v3")

    from src.api.routers.sentiment_p2 import router as sentiment_p2_router
    app.include_router(sentiment_p2_router, prefix="/v3")

    from src.api.routers.economic_calendar import router as economic_calendar_router
    app.include_router(economic_calendar_router, prefix="/v3")

    from src.api.routers.company_intel_p2 import router as company_intel_p2_router
    app.include_router(company_intel_p2_router, prefix="/v3")

    # Pillar 3 Phase 3A: Industry & Competitive Intelligence
    from src.api.routers.industry import router as industry_router
    app.include_router(industry_router, prefix="/v3")

    from src.api.routers.competitive import router as competitive_router
    app.include_router(competitive_router, prefix="/v3")

    # Pillar 3 Phase 3B: Global Intelligence
    from src.api.routers.global_intelligence import router as global_intel_router
    app.include_router(global_intel_router, prefix="/v3")

    # Pillar 3 Phase 3C: FI Intelligence
    from src.api.routers.fi_intelligence import router as fi_intel_router
    app.include_router(fi_intel_router, prefix="/v3")

    # Pillar 3 Phase 4A: AI Research Layer
    from src.api.routers.research_primers import router as research_primers_router
    app.include_router(research_primers_router, prefix="/v4")

    from src.api.routers.research_briefings import router as research_briefings_router
    app.include_router(research_briefings_router, prefix="/v4")

    from src.api.routers.research_anomalies import router as research_anomalies_router
    app.include_router(research_anomalies_router, prefix="/v4")

    # Pillar 3 Phase 4B: Semantic Search, Investment Thesis, Analyst Q&A
    from src.api.routers.research_search import router as research_search_router
    app.include_router(research_search_router, prefix="/v4")

    from src.api.routers.research_thesis import router as research_thesis_router
    app.include_router(research_thesis_router, prefix="/v4")

    from src.api.routers.research_qa import router as research_qa_router
    app.include_router(research_qa_router, prefix="/v4")

    # Pillar 3 Phase 4C: Macro Themes, Scenarios, Intelligent Alerts, Earnings Intelligence
    from src.api.routers.research_themes import router as research_themes_router
    app.include_router(research_themes_router, prefix="/v4")

    from src.api.routers.research_alerts_p4 import router as research_alerts_p4_router
    app.include_router(research_alerts_p4_router, prefix="/v4")

    # ------------------------------------------------------------------
    # Pillar 4 Phase 3: Risk Management
    # NOTE: Risk router must be registered BEFORE Performance and Portfolios
    # to avoid /portfolios/risk/scenarios being captured by /portfolios/{portfolio_id}
    # ------------------------------------------------------------------
    from src.api.routers.portfolio_risk import router as portfolio_risk_router
    app.include_router(portfolio_risk_router, prefix="/v4")

    # ------------------------------------------------------------------
    # Pillar 4 Phase 2: Performance & Attribution
    # NOTE: Performance router must be registered BEFORE Portfolios to avoid
    # /portfolios/performance/compare being captured by /portfolios/{portfolio_id}
    # ------------------------------------------------------------------
    from src.api.routers.portfolio_performance import router as perf_router
    app.include_router(perf_router, prefix="/v4")

    # ------------------------------------------------------------------
    # Pillar 4 Phase 1: Portfolio Foundation
    # NOTE: Watchlists router must be registered BEFORE Portfolios to avoid
    # /portfolios/watchlists being captured by /portfolios/{portfolio_id}
    # ------------------------------------------------------------------
    from src.api.routers.portfolio_watchlists import router as portfolio_watchlists_router
    app.include_router(portfolio_watchlists_router, prefix="/v4")

    from src.api.routers.portfolios import router as portfolios_router
    app.include_router(portfolios_router, prefix="/v4")

    # ------------------------------------------------------------------
    # Pillar 4 Phase 4: Research Notes
    # ------------------------------------------------------------------
    from src.api.routers.research_notes import router as research_notes_router
    app.include_router(research_notes_router, prefix="/v4")

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
            return {"status": "ok"}
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return JSONResponse(status_code=503, content={"status": "error", "detail": "Database connection failed"})

    # ------------------------------------------------------------------
    # Global exception handler
    # ------------------------------------------------------------------
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
