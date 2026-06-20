"""Pydantic schemas for the Automatic Model Builder endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ModelBuildRequest(BaseModel):
    scope: str = Field(..., description="ECONOMIC / MARKET / INDUSTRY / CORPORATE / COMPANY")
    subject: str | None = Field(None, description="Name of the modeled subject")
    data: dict = Field(default_factory=dict, description="Input metrics for the chosen scope")


class ModelSectionResponse(BaseModel):
    title: str
    metrics: dict = {}
    assessment: str = ""


class AnalyticalModelResponse(BaseModel):
    scope: str
    subject: str | None = None
    as_of: str | None = None
    sections: list[ModelSectionResponse] = []
    drivers: list[str] = []
    assumptions: list[str] = []
    scores: dict = {}
    composite_score: float = 0.0
    rating: str = "NEUTRAL"
    summary: str = ""
