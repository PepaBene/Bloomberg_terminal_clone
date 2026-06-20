"""Pydantic schemas for the Complex Financial Structure analyzer."""

from __future__ import annotations

from pydantic import BaseModel, Field


class StructureAnalysisRequest(BaseModel):
    subject: str | None = None
    subsidiaries: list[dict] = Field(default_factory=list)
    share_classes: list[dict] = Field(default_factory=list)
    off_balance_sheet: dict = Field(default_factory=dict)
    total_assets: float | None = None
    debt_tranches: list[dict] = Field(default_factory=list)


class StructureReportResponse(BaseModel):
    subject: str | None = None
    subsidiary_tree: dict = {}
    share_classes: dict = {}
    off_balance_sheet: dict = {}
    debt_waterfall: dict = {}
    complexity_score: float = 0.0
    complexity_rating: str = "SIMPLE"
    flags: list[str] = []
