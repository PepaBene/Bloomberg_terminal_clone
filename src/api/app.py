"""FastAPI application factory for Bloomberg Data Fabric API."""

import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.api.middleware import RequestContextMiddleware
from src.api.utils.field_selection import FieldSelectionMiddleware
from src.schemas.common import ErrorDetail, ErrorResponse, ResponseMeta

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""

    app = FastAPI(
        title="Bloomberg Data Fabric API",
        version="1.0.0",
        description="Unified financial data platform providing reference, entity, and security data.",
    )

    # ------------------------------------------------------------------
    # Middleware (Starlette executes middleware in reverse registration
    # order, so the last-registered middleware runs first on request.)
    # ------------------------------------------------------------------
    app.add_middleware(RequestContextMiddleware)
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
        from src.api.routers.estimates import router as estimates_router

        app.include_router(estimates_router, prefix="/v1")
    except ImportError:
        logger.warning("Estimates router not available; skipping.")

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
