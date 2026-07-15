"""Complex Financial Structure analysis API endpoints.

Analyzes corporate org/subsidiary trees, multi-class voting structures,
off-balance-sheet/VIE exposure, and debt subordination waterfalls. The
generic ``/analyze`` endpoint accepts a caller-supplied payload; the
``/entity/{id}`` endpoint enriches it with the platform's stored data:

* Subsidiary org tree — real, from ``Subsidiary`` rows (SEC EX-21 ingestion,
  src/ingestion/edgar_exhibit21.py), when the entity has any on file.
* Debt tranches — real, from the entity's latest ``CapitalStructure``.
* Share classes — partially real: distinct ``EquityDetails.share_class``
  values found on the entity's equity securities, with real
  ``shares_outstanding`` where available. ``votes_per_share`` and
  ``economic_rights`` are NOT sourced from any feed currently ingested by
  this platform (no free source for per-class voting-rights multipliers is
  wired up) and default to 1 / 1.0 — i.e. one-share-one-vote, pari passu —
  which understates any real dual-class control wedge. Only surfaced when
  2+ distinct classes are found, so single-class issuers don't get a
  fabricated share-classes section.
* Off-balance-sheet/VIE exposure — still caller-supplied only (no stored
  source yet); empty unless the caller passes it via the generic endpoint.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.engines.complex_structure import analyze_complex_structure
from src.models.capital_structure import CapitalStructure, DebtTranche
from src.models.entity import Entity
from src.models.security import EquityDetails, Security
from src.models.subsidiary import Subsidiary
from src.schemas.complex_structure import (
    StructureAnalysisRequest,
    StructureReportResponse,
)

router = APIRouter(prefix="/complex-structure", tags=["Complex Structure"])


async def _fetch_latest_subsidiaries(session: AsyncSession, entity_id: uuid.UUID) -> list[dict]:
    """Subsidiaries for an entity from its most recent EX-21 ingestion batch.

    Subsidiary rows accumulate across ingestion runs (one snapshot per
    ``as_of_date``); only the single most recent ``as_of_date`` is used so
    that older snapshots don't get double-counted alongside the current one.
    """
    max_as_of = (
        await session.execute(
            select(func.max(Subsidiary.as_of_date)).where(
                Subsidiary.parent_entity_id == entity_id
            )
        )
    ).scalar_one_or_none()
    if max_as_of is None:
        return []

    rows = (
        await session.execute(
            select(Subsidiary).where(
                Subsidiary.parent_entity_id == entity_id,
                Subsidiary.as_of_date == max_as_of,
            )
        )
    ).scalars().all()

    return [
        {
            "name": r.name,
            "jurisdiction": r.jurisdiction,
            "ownership_pct": float(r.ownership_pct) if r.ownership_pct is not None else None,
            "is_vie": bool(r.is_vie),
        }
        for r in rows
    ]


async def _fetch_share_classes(session: AsyncSession, entity_id: uuid.UUID) -> list[dict]:
    """Distinct disclosed share classes for an entity's equity securities.

    Joins Security -> EquityDetails for the real ``shares_outstanding``
    figure. ``votes_per_share`` / ``economic_rights`` have no ingested
    source yet and are left at their pari-passu defaults (see module
    docstring) rather than fabricated.
    """
    rows = (
        await session.execute(
            select(EquityDetails)
            .join(Security, Security.security_id == EquityDetails.security_id)
            .where(
                Security.issuer_entity_id == entity_id,
                Security.asset_class == "EQUITY",
            )
        )
    ).scalars().all()

    classes: dict[str, dict] = {}
    for eq in rows:
        cls_name = (eq.share_class or "").strip()
        if not cls_name:
            # No disclosed share-class label -- don't invent a class.
            continue
        shares = float(eq.shares_outstanding) if eq.shares_outstanding is not None else None
        existing = classes.get(cls_name)
        if existing is None or (existing["shares_outstanding"] is None and shares is not None):
            classes[cls_name] = {
                "class_name": cls_name,
                "shares_outstanding": shares,
                # No ingested source for actual per-class voting multipliers
                # or dividend/economic-rights ratios -- known limitation,
                # see module docstring. Defaults assume one-share-one-vote,
                # pari passu economics until a real source is wired up.
                "votes_per_share": 1,
                "economic_rights": 1.0,
            }

    return list(classes.values())


@router.post("/analyze", response_model=StructureReportResponse)
async def analyze_structure(request: StructureAnalysisRequest):
    """Analyze a complex financial structure from a caller-supplied payload."""
    report = analyze_complex_structure(request.model_dump(exclude={"subject"}), request.subject)
    return asdict(report)


@router.get("/entity/{entity_id}", response_model=StructureReportResponse)
async def analyze_entity_structure(
    entity_id: uuid.UUID, session: AsyncSession = Depends(get_session)
):
    """Analyze structure for an entity, enriched with stored platform data.

    Debt tranches come from the latest capital structure; the subsidiary
    org tree comes from the most recent EX-21 ingestion batch on file; share
    classes come from distinct disclosed ``EquityDetails.share_class``
    values on the entity's equity securities (2+ required to surface a
    share-class section). Off-balance-sheet inputs have no stored source yet
    and stay empty here — see module docstring for what's real vs. default.
    """
    entity = (
        await session.execute(select(Entity).where(Entity.entity_id == entity_id))
    ).scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    cap = (
        await session.execute(
            select(CapitalStructure)
            .where(CapitalStructure.entity_id == entity_id)
            .order_by(CapitalStructure.as_of_date.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    debt_tranches: list[dict] = []
    if cap is not None:
        tranches = (
            await session.execute(
                select(DebtTranche).where(
                    DebtTranche.capital_structure_id == cap.capital_structure_id
                )
            )
        ).scalars().all()
        for t in tranches:
            debt_tranches.append(
                {
                    "instrument_name": t.instrument_name,
                    "principal_amount": float(t.principal_amount)
                    if t.principal_amount is not None
                    else 0.0,
                    "seniority_rank": t.seniority_rank,
                    # Real values are "SENIOR_SECURED" / "SENIOR_UNSECURED" /
                    # "SUBORDINATED" / "JUNIOR_SUBORDINATED" on seniority_type
                    # (src/enums.py) — instrument_type never starts with
                    # "SECURED", so this was always 0.0/False for every entity.
                    "is_secured": (t.seniority_type or "").upper() == "SENIOR_SECURED",
                }
            )

    subject = getattr(entity, "legal_name", None) or str(entity_id)

    payload: dict = {"debt_tranches": debt_tranches}

    subsidiaries = await _fetch_latest_subsidiaries(session, entity_id)
    if subsidiaries:
        payload["subsidiaries"] = subsidiaries

    share_classes = await _fetch_share_classes(session, entity_id)
    if len(share_classes) >= 2:
        # analyze_share_classes() on a single-entry list still returns a
        # populated (if trivial) report rather than the "no data" default,
        # which would misrepresent a single-class issuer as having a
        # share-class analysis on file. Only surface it for genuine
        # multi-class structures.
        payload["share_classes"] = share_classes

    report = analyze_complex_structure(payload, subject)
    return asdict(report)
