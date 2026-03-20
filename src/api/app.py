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
