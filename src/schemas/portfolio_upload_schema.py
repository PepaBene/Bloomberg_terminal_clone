"""Pydantic schemas for Pillar 4 Phase 1: Portfolio upload endpoints."""

from pydantic import BaseModel
from uuid import UUID


class UploadPreviewPosition(BaseModel):
    ticker: str
    shares: float
    cost_basis_per_share: float
    matched: bool = False
    error: str | None = None


class UploadPreviewResponse(BaseModel):
    total_rows: int
    matched: int
    unmatched: int
    errors: int
    preview_positions: list[UploadPreviewPosition]


class UploadCommitResponse(BaseModel):
    portfolio_id: UUID
    positions_created: int
    status: str
