"""Portfolio Upload API endpoints (Pillar 2 Supplement – Part 4)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.models.portfolio_upload import PortfolioUpload
from src.schemas.portfolio_upload import ParsedHoldingRow, UploadResultResponse

router = APIRouter(tags=["Portfolio Upload"])


@router.post(
    "/analytics/portfolio/upload",
    response_model=UploadResultResponse,
    status_code=201,
)
async def upload_portfolio(
    session: AsyncSession = Depends(get_session),
    file_name: str = Query("portfolio.csv", description="Uploaded file name"),
    file_format: str = Query("CSV", description="CSV or EXCEL"),
):
    """Upload a portfolio file for security matching.

    In production this would accept a file upload; here we create
    the upload record. Actual file parsing would happen asynchronously.
    """
    upload = PortfolioUpload(
        upload_id=uuid.uuid4(),
        file_name=file_name,
        file_format=file_format.upper(),
        status="PENDING",
        total_rows=0,
        matched_rows=0,
        unmatched_rows=0,
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
    if row.parsed_holdings and isinstance(row.parsed_holdings, list):
        for h in row.parsed_holdings:
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
