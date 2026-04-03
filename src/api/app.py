"""FastAPI application factory for Bloomberg Data Fabric API."""

import logging
import time
import uuid

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.middleware import RequestContextMiddleware
from src.api.middleware.audit import AuditLogMiddleware
from src.api.utils.field_selection import FieldSelectionMiddleware
from src.schemas.common import ErrorDetail, ErrorResponse, ResponseMeta

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Bloomberg Data Fabric API starting up")
    yield
    logger.info("Bloomberg Data Fabric API shutting down")


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""

    app = FastAPI(
        title="Bloomberg Data Fabric API",
        version="1.0.0",
        description="Unified financial data platform providing reference, entity, and security data.",
        lifespan=lifespan,
    )

    # ------------------------------------------------------------------
    # Middleware (Starlette executes middleware in reverse registration
    # order, so the last-registered middleware runs first on request.)
    # ------------------------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
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
    # Routers — imported defensively so the app can start even when
    # individual router modules have not been created yet.
    # ------------------------------------------------------------------
    try:
        from src.api.routers.auth import router as auth_router

        app.include_router(auth_router)
    except ImportError:
        logger.warning("Auth router not available; skipping.")

    try:
        from src.api.routers.reference import router as reference_router

        app.include_router(reference_router, prefix="/v1")
    except ImportError:
        logger.warning("Reference router not available; skipping.")

    try:
        from src.api.routers.entities import router as entities_router

        app.include_router(entities_router, prefix="/v1")
    except ImportError:
        logger.warning("Entities router not available; skipping.")

    # NOTE: Security Finder must be registered BEFORE Securities to avoid
    # /securities/find being captured by /securities/{security_id}
    try:
        from src.api.routers.security_finder import router as security_finder_router

        app.include_router(security_finder_router, prefix="/v1")
    except ImportError:
        logger.warning("Security Finder router not available; skipping.")

    try:
        from src.api.routers.securities import router as securities_router

        app.include_router(securities_router, prefix="/v1")
    except ImportError:
        logger.warning("Securities router not available; skipping.")

    try:
        from src.api.routers.resolution import router as resolution_router

        app.include_router(resolution_router, prefix="/v1")
    except ImportError:
        logger.warning("Resolution router not available; skipping.")

    try:
        from src.api.routers.macro import router as macro_router

        app.include_router(macro_router, prefix="/v1")
    except ImportError:
        logger.warning("Macro router not available; skipping.")

    try:
        from src.api.routers.fundamentals import router as fundamentals_router

        app.include_router(fundamentals_router, prefix="/v1")
    except ImportError:
        logger.warning("Fundamentals router not available; skipping.")

    try:
        from src.api.routers.ownership import router as ownership_router

        app.include_router(ownership_router, prefix="/v1")
    except ImportError:
        logger.warning("Ownership router not available; skipping.")

    try:
        from src.api.routers.esg import router as esg_router

        app.include_router(esg_router, prefix="/v1")
    except ImportError:
        logger.warning("ESG router not available; skipping.")

    try:
        from src.api.routers.corporate_actions import router as corporate_actions_router

        app.include_router(corporate_actions_router, prefix="/v1")
    except ImportError:
        logger.warning("Corporate Actions router not available; skipping.")

    try:
        from src.api.routers.relationships import router as relationships_router

        app.include_router(relationships_router, prefix="/v1")
    except ImportError:
        logger.warning("Relationships router not available; skipping.")

    # ------------------------------------------------------------------
    # Pillar 2: Analytics Engines
    # ------------------------------------------------------------------
    try:
        from src.api.routers.analytics import router as analytics_router

        app.include_router(analytics_router)
    except ImportError:
        logger.warning("Analytics router not available; skipping.")

    try:
        from src.api.routers.screening import router as screening_router

        app.include_router(screening_router)
    except ImportError:
        logger.warning("Screening router not available; skipping.")

    try:
        from src.api.routers.flows import router as flows_router

        app.include_router(flows_router)
    except ImportError:
        logger.warning("Flows router not available; skipping.")

    try:
        from src.api.routers.risk import router as risk_router

        app.include_router(risk_router)
    except ImportError:
        logger.warning("Risk router not available; skipping.")

    try:
        from src.api.routers.quant import router as quant_router

        app.include_router(quant_router)
    except ImportError:
        logger.warning("Quant router not available; skipping.")

    try:
        from src.api.routers.scenario import router as scenario_router

        app.include_router(scenario_router)
    except ImportError:
        logger.warning("Scenario router not available; skipping.")

    # Pillar 1 Supplement routers
    try:
        from src.api.routers.capital_structure import router as capital_structure_router

        app.include_router(capital_structure_router, prefix="/v1")
    except ImportError:
        logger.warning("Capital Structure router not available; skipping.")

    try:
        from src.api.routers.debt_maturity import router as debt_maturity_router

        app.include_router(debt_maturity_router, prefix="/v1")
    except ImportError:
        logger.warning("Debt Maturity router not available; skipping.")

    try:
        from src.api.routers.credit_rating import router as credit_rating_router

        app.include_router(credit_rating_router, prefix="/v1")
    except ImportError:
        logger.warning("Credit Rating router not available; skipping.")

    try:
        from src.api.routers.calendar import router as calendar_router

        app.include_router(calendar_router, prefix="/v1")
    except ImportError:
        logger.warning("Calendar router not available; skipping.")

    # Pillar 1 Supplement – Part 2: Macro extensions
    try:
        from src.api.routers.yield_curve import router as yield_curve_router

        app.include_router(yield_curve_router, prefix="/v1")
    except ImportError:
        logger.warning("Yield Curve router not available; skipping.")

    try:
        from src.api.routers.fed_meeting import router as fed_meeting_router

        app.include_router(fed_meeting_router, prefix="/v1")
    except ImportError:
        logger.warning("Fed Meeting router not available; skipping.")

    try:
        from src.api.routers.money_market import router as money_market_router

        app.include_router(money_market_router, prefix="/v1")
    except ImportError:
        logger.warning("Money Market router not available; skipping.")

    # Pillar 1 Supplement – Part 3: Deals / IPO / Earnings
    try:
        from src.api.routers.ma_deals import router as ma_deals_router

        app.include_router(ma_deals_router, prefix="/v1")
    except ImportError:
        logger.warning("M&A Deals router not available; skipping.")

    try:
        from src.api.routers.ipo import router as ipo_router

        app.include_router(ipo_router, prefix="/v1")
    except ImportError:
        logger.warning("IPO router not available; skipping.")

    try:
        from src.api.routers.earnings_intelligence import router as earnings_router

        app.include_router(earnings_router, prefix="/v1")
    except ImportError:
        logger.warning("Earnings Intelligence router not available; skipping.")

    # Pillar 1 Supplement – Part 4: Fund Holdings / Executives
    try:
        from src.api.routers.fund_holdings import router as fund_holdings_router

        app.include_router(fund_holdings_router, prefix="/v1")
    except ImportError:
        logger.warning("Fund Holdings router not available; skipping.")

    try:
        from src.api.routers.executives import router as executives_router

        app.include_router(executives_router, prefix="/v1")
    except ImportError:
        logger.warning("Executives router not available; skipping.")

    try:
        from src.api.routers.technical_studies import router as technical_studies_router

        app.include_router(technical_studies_router, prefix="/v1")
    except ImportError:
        logger.warning("Technical Studies router not available; skipping.")

    try:
        from src.api.routers.custom_classifications import router as custom_classifications_router

        app.include_router(custom_classifications_router, prefix="/v1")
    except ImportError:
        logger.warning("Custom Classifications router not available; skipping.")

    try:
        from src.api.routers.esg_temperature import router as esg_temperature_router

        app.include_router(esg_temperature_router, prefix="/v1")
    except ImportError:
        logger.warning("ESG Temperature router not available; skipping.")

    # Pillar 2 Supplement – Part 1: Yield Curve Analytics
    try:
        from src.api.routers.yield_curve_analytics import router as yield_curve_analytics_router

        app.include_router(yield_curve_analytics_router, prefix="/v1")
    except ImportError:
        logger.warning("Yield Curve Analytics router not available; skipping.")

    # Pillar 2 Supplement – Part 5: Events Calendar, Market Movers
    try:
        from src.api.routers.events_calendar_engine import router as events_calendar_engine_router

        app.include_router(events_calendar_engine_router, prefix="/v1")
    except ImportError:
        logger.warning("Events Calendar Engine router not available; skipping.")

    try:
        from src.api.routers.market_movers import router as market_movers_router

        app.include_router(market_movers_router, prefix="/v1")
    except ImportError:
        logger.warning("Market Movers router not available; skipping.")

    # Pillar 2 Supplement – Part 4: Custom Index + Portfolio Upload
    try:
        from src.api.routers.custom_index import router as custom_index_router

        app.include_router(custom_index_router, prefix="/v1")
    except ImportError:
        logger.warning("Custom Index router not available; skipping.")

    try:
        from src.api.routers.portfolio_upload import router as portfolio_upload_router

        app.include_router(portfolio_upload_router, prefix="/v1")
    except ImportError:
        logger.warning("Portfolio Upload router not available; skipping.")

    # Pillar 2 Supplement – Part 3: Backtesting
    try:
        from src.api.routers.backtesting import router as backtesting_router

        app.include_router(backtesting_router, prefix="/v1")
    except ImportError:
        logger.warning("Backtesting router not available; skipping.")

    # Pillar 2 Supplement – Part 2: Default Risk Scoring
    try:
        from src.api.routers.default_risk import router as default_risk_router

        app.include_router(default_risk_router, prefix="/v1")
    except ImportError:
        logger.warning("Default Risk router not available; skipping.")

    # Pillar 2 Supplement – Part 6: Custom Data + Technical Backtest
    try:
        from src.api.routers.custom_data import router as custom_data_router

        app.include_router(custom_data_router, prefix="/v1")
    except ImportError:
        logger.warning("Custom Data router not available; skipping.")

    try:
        from src.api.routers.technical_backtest import router as technical_backtest_router

        app.include_router(technical_backtest_router, prefix="/v1")
    except ImportError:
        logger.warning("Technical Backtest router not available; skipping.")

    # Pillar 2 Supplement – Part 7: AI Company Intelligence + Primers
    try:
        from src.api.routers.company_intelligence import router as company_intelligence_router

        app.include_router(company_intelligence_router, prefix="/v1")
    except ImportError:
        logger.warning("Company Intelligence router not available; skipping.")

    try:
        from src.api.routers.company_primer import router as company_primer_router

        app.include_router(company_primer_router, prefix="/v1")
    except ImportError:
        logger.warning("Company Primer router not available; skipping.")

    # Pillar 2 Supplement – Part 8: Sentiment Analysis
    try:
        from src.api.routers.sentiment import router as sentiment_router

        app.include_router(sentiment_router, prefix="/v1")
    except ImportError:
        logger.warning("Sentiment Analysis router not available; skipping.")

    # D11 FI Supplement – Part 2: Treasuries
    try:
        from src.api.routers.fi_treasuries import router as fi_treasuries_router

        app.include_router(fi_treasuries_router, prefix="/v1")
    except ImportError:
        logger.warning("FI Treasuries router not available; skipping.")

    # D11 FI Supplement – Part 3: Fixed Income Yield Curve
    try:
        from src.api.routers.fi_yield_curve import router as fi_yield_curve_router

        app.include_router(fi_yield_curve_router, prefix="/v1")
    except ImportError:
        logger.warning("FI Yield Curve router not available; skipping.")

    # D11 FI Supplement – Part 4: Corporate Bonds + TRACE
    try:
        from src.api.routers.fi_bonds import router as fi_bonds_router

        app.include_router(fi_bonds_router, prefix="/v1")
    except ImportError:
        logger.warning("FI Bonds router not available; skipping.")

    # D11 FI Supplement – Part 5: Credit Rating Analytics
    try:
        from src.api.routers.fi_ratings import router as fi_ratings_router

        app.include_router(fi_ratings_router, prefix="/v1")
    except ImportError:
        logger.warning("FI Ratings router not available; skipping.")

    # D11 FI Supplement – Part 6: Credit Spreads
    try:
        from src.api.routers.fi_spreads import router as fi_spreads_router

        app.include_router(fi_spreads_router, prefix="/v1")
    except ImportError:
        logger.warning("FI Spreads router not available; skipping.")

    # D11 FI Supplement – Part 7: Bond Issuances
    try:
        from src.api.routers.fi_issuances import router as fi_issuances_router

        app.include_router(fi_issuances_router, prefix="/v1")
    except ImportError:
        logger.warning("FI Issuances router not available; skipping.")

    # D11 FI Supplement – Part 8: Agency Bonds
    try:
        from src.api.routers.fi_agency_bonds import router as fi_agency_bonds_router

        app.include_router(fi_agency_bonds_router, prefix="/v1")
    except ImportError:
        logger.warning("FI Agency Bonds router not available; skipping.")

    # Pillar 2 FI Supplement – Part 1: Bond Analytics
    try:
        from src.api.routers.fi_bond_analytics import router as fi_bond_analytics_router

        app.include_router(fi_bond_analytics_router)
    except ImportError:
        logger.warning("FI Bond Analytics router not available; skipping.")

    # Pillar 2 FI Supplement – Part 2: Duration Analytics
    try:
        from src.api.routers.fi_duration import router as fi_duration_router

        app.include_router(fi_duration_router)
    except ImportError:
        logger.warning("FI Duration Analytics router not available; skipping.")

    # Pillar 2 FI Supplement – Part 3: Spread Analytics
    try:
        from src.api.routers.fi_spread_analytics import router as fi_spread_analytics_router

        app.include_router(fi_spread_analytics_router)
    except ImportError:
        logger.warning("FI Spread Analytics router not available; skipping.")

    # Pillar 2 FI Supplement – Part 4: Credit Quality Analytics
    try:
        from src.api.routers.fi_credit_quality import router as fi_credit_quality_router

        app.include_router(fi_credit_quality_router)
    except ImportError:
        logger.warning("FI Credit Quality router not available; skipping.")

    # Pillar 2 FI Supplement – Part 5: FI Risk Analytics
    try:
        from src.api.routers.fi_risk import router as fi_risk_router

        app.include_router(fi_risk_router)
    except ImportError:
        logger.warning("FI Risk Analytics router not available; skipping.")

    # Pillar 2 FI Supplement – Part 6: FI Screening & Scenarios
    try:
        from src.api.routers.fi_screening import router as fi_screening_router

        app.include_router(fi_screening_router)
    except ImportError:
        logger.warning("FI Screening & Scenarios router not available; skipping.")

    # Pillar 2 FI Supplement – Part 7: Issuer FI Profile + Cross-Asset Signals
    try:
        from src.api.routers.fi_issuer_profile import router as fi_issuer_profile_router

        app.include_router(fi_issuer_profile_router)
    except ImportError:
        logger.warning("FI Issuer Profile router not available; skipping.")

    try:
        from src.api.routers.fi_cross_asset import router as fi_cross_asset_router

        app.include_router(fi_cross_asset_router)
    except ImportError:
        logger.warning("FI Cross-Asset Signals router not available; skipping.")

    # ------------------------------------------------------------------
    # Pillar 3: Research & Intelligence
    # ------------------------------------------------------------------
    try:
        from src.api.routers.filing_intelligence import router as filing_intel_router

        app.include_router(filing_intel_router, prefix="/v3")
    except ImportError:
        logger.warning("Filing intelligence router not available; skipping.")

    try:
        from src.api.routers.governance_intelligence import router as governance_intel_router

        app.include_router(governance_intel_router, prefix="/v3")
    except ImportError:
        logger.warning("Governance intelligence router not available; skipping.")

    try:
        from src.api.routers.news import router as news_router

        app.include_router(news_router, prefix="/v3")
    except ImportError:
        logger.warning("News router not available; skipping.")

    # NOTE: Alerts Expansion must be registered BEFORE Alerts to avoid
    # /alerts/quality-scores being captured by /alerts/{entity_id}
    try:
        from src.api.routers.alerts_expansion import router as alerts_exp_router

        app.include_router(alerts_exp_router, prefix="/v3")
    except ImportError:
        logger.warning("Alerts expansion router not available; skipping.")

    try:
        from src.api.routers.alerts import router as alerts_router

        app.include_router(alerts_router, prefix="/v3")
    except ImportError:
        logger.warning("Alerts router not available; skipping.")

    # Pillar 3 Phase 2: Earnings, Sentiment, Economic Calendar, Company Intel
    try:
        from src.api.routers.earnings_p2 import router as earnings_p2_router

        app.include_router(earnings_p2_router, prefix="/v3")
    except ImportError:
        logger.warning("Earnings P2 router not available; skipping.")

    try:
        from src.api.routers.sentiment_p2 import router as sentiment_p2_router

        app.include_router(sentiment_p2_router, prefix="/v3")
    except ImportError:
        logger.warning("Sentiment P2 router not available; skipping.")

    try:
        from src.api.routers.economic_calendar import router as economic_calendar_router

        app.include_router(economic_calendar_router, prefix="/v3")
    except ImportError:
        logger.warning("Economic Calendar router not available; skipping.")

    try:
        from src.api.routers.company_intel_p2 import router as company_intel_p2_router

        app.include_router(company_intel_p2_router, prefix="/v3")
    except ImportError:
        logger.warning("Company Intelligence P2 router not available; skipping.")

    # Pillar 3 Phase 3A: Industry & Competitive Intelligence
    try:
        from src.api.routers.industry import router as industry_router

        app.include_router(industry_router, prefix="/v3")
    except ImportError:
        logger.warning("Industry router not available; skipping.")

    try:
        from src.api.routers.competitive import router as competitive_router

        app.include_router(competitive_router, prefix="/v3")
    except ImportError:
        logger.warning("Competitive router not available; skipping.")

    # Pillar 3 Phase 3B: Global Intelligence
    try:
        from src.api.routers.global_intelligence import router as global_intel_router

        app.include_router(global_intel_router, prefix="/v3")
    except ImportError:
        logger.warning("Global intelligence router not available; skipping.")

    # Pillar 3 Phase 3C: FI Intelligence
    try:
        from src.api.routers.fi_intelligence import router as fi_intel_router

        app.include_router(fi_intel_router, prefix="/v3")
    except ImportError:
        logger.warning("FI intelligence router not available; skipping.")

    # Pillar 3 Phase 4A: AI Research Layer
    try:
        from src.api.routers.research_primers import router as research_primers_router

        app.include_router(research_primers_router, prefix="/v4")
    except ImportError:
        logger.warning("Research primers router not available; skipping.")

    try:
        from src.api.routers.research_briefings import router as research_briefings_router

        app.include_router(research_briefings_router, prefix="/v4")
    except ImportError:
        logger.warning("Research briefings router not available; skipping.")

    try:
        from src.api.routers.research_anomalies import router as research_anomalies_router

        app.include_router(research_anomalies_router, prefix="/v4")
    except ImportError:
        logger.warning("Research anomalies router not available; skipping.")

    # Pillar 3 Phase 4B: Semantic Search, Investment Thesis, Analyst Q&A
    try:
        from src.api.routers.research_search import router as research_search_router

        app.include_router(research_search_router, prefix="/v4")
    except ImportError:
        logger.warning("Research search router not available; skipping.")

    try:
        from src.api.routers.research_thesis import router as research_thesis_router

        app.include_router(research_thesis_router, prefix="/v4")
    except ImportError:
        logger.warning("Research thesis router not available; skipping.")

    try:
        from src.api.routers.research_qa import router as research_qa_router

        app.include_router(research_qa_router, prefix="/v4")
    except ImportError:
        logger.warning("Research Q&A router not available; skipping.")

    # Pillar 3 Phase 4C: Macro Themes, Scenarios, Intelligent Alerts, Earnings Intelligence
    try:
        from src.api.routers.research_themes import router as research_themes_router

        app.include_router(research_themes_router, prefix="/v4")
    except ImportError:
        logger.warning("Research themes router not available; skipping.")

    try:
        from src.api.routers.research_alerts_p4 import router as research_alerts_p4_router

        app.include_router(research_alerts_p4_router, prefix="/v4")
    except ImportError:
        logger.warning("Research alerts P4 router not available; skipping.")

    # ------------------------------------------------------------------
    # Pillar 4 Phase 3: Risk Management
    # NOTE: Risk router must be registered BEFORE Performance and Portfolios
    # to avoid /portfolios/risk/scenarios being captured by /portfolios/{portfolio_id}
    # ------------------------------------------------------------------
    try:
        from src.api.routers.portfolio_risk import router as portfolio_risk_router

        app.include_router(portfolio_risk_router, prefix="/v4")
    except ImportError:
        logger.warning("Portfolio risk router not available; skipping.")

    # ------------------------------------------------------------------
    # Pillar 4 Phase 2: Performance & Attribution
    # NOTE: Performance router must be registered BEFORE Portfolios to avoid
    # /portfolios/performance/compare being captured by /portfolios/{portfolio_id}
    # ------------------------------------------------------------------
    try:
        from src.api.routers.portfolio_performance import router as perf_router

        app.include_router(perf_router, prefix="/v4")
    except ImportError:
        logger.warning("Portfolio performance router not available; skipping.")

    # ------------------------------------------------------------------
    # Pillar 4 Phase 1: Portfolio Foundation
    # NOTE: Watchlists router must be registered BEFORE Portfolios to avoid
    # /portfolios/watchlists being captured by /portfolios/{portfolio_id}
    # ------------------------------------------------------------------
    try:
        from src.api.routers.portfolio_watchlists import router as portfolio_watchlists_router

        app.include_router(portfolio_watchlists_router, prefix="/v4")
    except ImportError:
        logger.warning("Portfolio watchlists router not available; skipping.")

    try:
        from src.api.routers.portfolios import router as portfolios_router

        app.include_router(portfolios_router, prefix="/v4")
    except ImportError:
        logger.warning("Portfolios router not available; skipping.")

    # ------------------------------------------------------------------
    # Pillar 4 Phase 4: Research Notes
    # ------------------------------------------------------------------
    try:
        from src.api.routers.research_notes import router as research_notes_router

        app.include_router(research_notes_router, prefix="/v4")
    except ImportError:
        logger.warning("Research notes router not available; skipping.")

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------
    @app.get("/health", tags=["health"])
    async def health_check() -> dict:
        return {"status": "ok"}

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
