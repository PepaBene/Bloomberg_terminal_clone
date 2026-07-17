"""Portfolio Upload API endpoints (Pillar 2 Supplement – Part 4)."""

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_optional_user, get_session
from src.engines.portfolio_parser import match_holdings_to_securities, parse_csv
from src.models.portfolio_upload import PortfolioUpload
from src.models.security import SecurityIdentifier
from src.schemas.portfolio_upload import ParsedHoldingRow, UploadResultResponse

router = APIRouter(tags=["Portfolio Upload"])

# P4-M-019: mirrors the anonymous-fallback identity pattern used by
# src/api/routers/portfolios.py (ANONYMOUS_USER/_resolve_user) so uploads
# get a real owner even when no Bearer token is present.
ANONYMOUS_USER = "default_user"


def _resolve_user(user: str | None) -> str:
    return user or ANONYMOUS_USER


@router.post(
    "/analytics/portfolio/upload",
    response_model=UploadResultResponse,
    status_code=201,
)
async def upload_portfolio(
    file: UploadFile = File(..., description="Portfolio holdings file (CSV or Excel)"),
    file_format: str | None = Form(None, description="CSV or EXCEL; inferred from filename if omitted"),
    session: AsyncSession = Depends(get_session),
    user: str | None = Depends(get_optional_user),
):
    """Upload a portfolio file for security matching.

    CSV files are parsed and matched against known securities synchronously.
    Excel files are recorded as PENDING — no Excel parser exists yet, so
    they're accepted but not silently marked complete with fabricated
    matched/unmatched counts.
    """
    user_id = _resolve_user(user)
    raw = await file.read()
    fmt = (
        file_format
        or ("EXCEL" if (file.filename or "").lower().endswith((".xlsx", ".xls")) else "CSV")
    ).upper()

    if fmt == "CSV":
        content = raw.decode("utf-8", errors="replace")
        holdings = parse_csv(content)

        known_tickers: dict[str, str] = {}
        if holdings:
            id_rows = (
                await session.execute(
                    select(SecurityIdentifier.identifier_value, SecurityIdentifier.security_id)
                    .where(SecurityIdentifier.identifier_type == "TICKER")
                )
            ).all()
            known_tickers = {row[0].upper(): str(row[1]) for row in id_rows}

        match_results = match_holdings_to_securities(holdings, known_tickers=known_tickers)
        by_row = {h.row_number: h for h in holdings}
        matched_rows = sum(1 for m in match_results if m.status == "MATCHED")
        unmatched_rows = len(match_results) - matched_rows
        parsed_holdings = [
            {
                "row_number": m.row_number,
                "identifier": m.identifier,
                "name": m.name,
                "quantity": by_row[m.row_number].quantity if m.row_number in by_row else None,
                "weight": by_row[m.row_number].weight if m.row_number in by_row else None,
                "mapping_status": m.status,
                "matched_security_id": m.matched_security_id,
            }
            for m in match_results
        ]
        status = "COMPLETED"
        total_rows = len(holdings)
    else:
        parsed_holdings = None
        status = "PENDING"
        total_rows = 0
        matched_rows = 0
        unmatched_rows = 0

    upload = PortfolioUpload(
        upload_id=uuid.uuid4(),
        file_name=file.filename or "portfolio.csv",
        file_format=fmt,
        status=status,
        total_rows=total_rows,
        matched_rows=matched_rows,
        unmatched_rows=unmatched_rows,
        parsed_holdings=parsed_holdings,
        # P4-M-019: the only construction site previously left both
        # ownership fields unset.
        user_id=user_id,
        created_by=user_id,
    )
    session.add(upload)
    await session.commit()

    return UploadResultResponse(
        upload_id=upload.upload_id,
        file_name=upload.file_name,
        file_format=upload.file_format,
        status=upload.status,
        total_rows=upload.total_rows,
        matched_rows=upload.matched_rows,
        unmatched_rows=upload.unmatched_rows,
    )


@router.get(
    "/analytics/portfolio/upload/{upload_id}",
    response_model=UploadResultResponse,
)
async def get_upload_status(
    upload_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get the status of a portfolio upload."""
    result = await session.execute(
        select(PortfolioUpload).where(PortfolioUpload.upload_id == upload_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Upload not found")

    holdings = []
    if row.parsed_holdings is not None:
        if not isinstance(row.parsed_holdings, list):
            raise HTTPException(
                status_code=422,
                detail="Stored parsed_holdings has an unexpected shape (expected a list of rows)",
            )
        for h in row.parsed_holdings:
            if not isinstance(h, dict):
                raise HTTPException(
                    status_code=422,
                    detail="Stored parsed_holdings contains a row that is not an object",
                )
            holdings.append(ParsedHoldingRow(**h))

    return UploadResultResponse(
        upload_id=row.upload_id,
        file_name=row.file_name,
        file_format=row.file_format,
        status=row.status,
        total_rows=row.total_rows,
        matched_rows=row.matched_rows,
        unmatched_rows=row.unmatched_rows,
        holdings=holdings,
    )
