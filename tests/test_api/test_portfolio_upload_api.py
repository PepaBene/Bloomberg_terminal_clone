"""API tests for portfolio upload endpoints (Pillar 2 Supplement – Part 4)."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.portfolio_upload import PortfolioUpload


@pytest.mark.asyncio
async def test_upload_portfolio(client: AsyncClient):
    csv_content = "ticker,shares\nAAPL,100\nMSFT,50\n"
    resp = await client.post(
        "/v1/analytics/portfolio/upload",
        files={"file": ("my_portfolio.csv", csv_content, "text/csv")},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["file_name"] == "my_portfolio.csv"
    assert data["file_format"] == "CSV"
    assert data["status"] == "COMPLETED"
    assert data["total_rows"] == 2


@pytest.mark.asyncio
async def test_upload_portfolio_excel_pending(client: AsyncClient):
    resp = await client.post(
        "/v1/analytics/portfolio/upload",
        files={"file": ("my_portfolio.xlsx", b"binary-xlsx-bytes", "application/vnd.ms-excel")},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["file_format"] == "EXCEL"
    assert data["status"] == "PENDING"


@pytest.mark.asyncio
async def test_get_upload_status(client: AsyncClient, session: AsyncSession):
    uid = uuid.uuid4()
    upload = PortfolioUpload(
        upload_id=uid,
        file_name="test.csv",
        file_format="CSV",
        status="COMPLETED",
        total_rows=10,
        matched_rows=8,
        unmatched_rows=2,
    )
    session.add(upload)
    await session.commit()

    resp = await client.get(f"/v1/analytics/portfolio/upload/{uid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["upload_id"] == str(uid)
    assert data["status"] == "COMPLETED"
    assert data["total_rows"] == 10
    assert data["matched_rows"] == 8


@pytest.mark.asyncio
async def test_get_upload_status_404(client: AsyncClient):
    resp = await client.get(f"/v1/analytics/portfolio/upload/{uuid.uuid4()}")
    assert resp.status_code == 404
