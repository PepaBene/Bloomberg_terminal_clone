"""Multi-stage entity resolution pipeline (Spec 3.5).

Resolution proceeds through three stages in order, returning as soon as a
stage produces a high-confidence match:

1. **Exact ID match** (LEI, CIK, DUNS, etc.) — confidence 1.0
2. **Exact normalised name + country** — confidence 0.98
3. **Fuzzy name match** — variable confidence

Confidence thresholds determine the outcome:

* ``>= 0.95`` — auto-match (``MATCHED``)
* ``0.70 – 0.95`` — added to the human review queue (``UNCERTAIN``)
* ``< 0.70`` — create new entity (``NEW``)
"""

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from src.resolution.matcher import (
    MatchResult,
    address_match,
    exact_id_match,
    exact_name_match,
    fuzzy_name_match,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Confidence thresholds
# ---------------------------------------------------------------------------
THRESHOLD_AUTO_MATCH: float = 0.95
THRESHOLD_REVIEW: float = 0.70


@dataclass(slots=True)
class ResolutionResult:
    """Outcome of the multi-stage resolution pipeline."""

    entity_id: uuid.UUID | None
    confidence: float
    match_method: str | None
    status: str  # MATCHED | UNCERTAIN | NEW
    details: dict | None = None


def _classify(match: MatchResult) -> ResolutionResult:
    """Map a :class:`MatchResult` to the appropriate resolution status."""
    if match.confidence >= THRESHOLD_AUTO_MATCH:
        status = "MATCHED"
    elif match.confidence >= THRESHOLD_REVIEW:
        status = "UNCERTAIN"
    else:
        status = "NEW"

    return ResolutionResult(
        entity_id=match.entity_id,
        confidence=match.confidence,
        match_method=match.match_method,
        status=status,
        details=match.details,
    )


async def resolve(
    legal_name: str,
    country: str | None = None,
    identifiers: dict[str, str] | None = None,
    address: dict | None = None,
    session: AsyncSession | None = None,
) -> ResolutionResult:
    """Run the multi-stage entity resolution pipeline.

    Parameters
    ----------
    legal_name:
        The legal name of the entity to resolve.
    country:
        Optional ISO-3166 alpha-2 country code for incorporation.
    identifiers:
        Optional dict mapping identifier type (e.g. ``"LEI"``) to its value.
    address:
        Optional address dict with keys: street, city, state, postal_code, country.
    session:
        Active SQLAlchemy async session.

    Returns
    -------
    ResolutionResult
        Contains ``entity_id``, ``confidence``, ``match_method``, and a
        ``status`` of ``MATCHED``, ``UNCERTAIN``, or ``NEW``.
    """
    if session is None:
        raise ValueError("An active database session is required for resolution.")

    logger.info("Starting resolution for '%s' (country=%s)", legal_name, country)

    # ------------------------------------------------------------------
    # Stage 1: Exact identifier match (LEI, CIK, DUNS, …)
    # ------------------------------------------------------------------
    if identifiers:
        for id_type, id_value in identifiers.items():
            if not id_value:
                continue

            match = await exact_id_match(id_type, id_value, session)
            if match is not None:
                logger.info(
                    "Stage 1 hit: %s=%s -> entity %s (confidence %.2f)",
                    id_type,
                    id_value,
                    match.entity_id,
                    match.confidence,
                )
                return _classify(match)

        logger.debug("Stage 1: no identifier match found")

    # ------------------------------------------------------------------
    # Stage 2: Exact normalised name + country
    # ------------------------------------------------------------------
    match = await exact_name_match(legal_name, country, session)
    if match is not None:
        logger.info(
            "Stage 2 hit: exact name '%s' -> entity %s (confidence %.2f)",
            legal_name,
            match.entity_id,
            match.confidence,
        )
        return _classify(match)

    logger.debug("Stage 2: no exact name match found")

    # ------------------------------------------------------------------
    # Stage 3: Fuzzy name match
    # ------------------------------------------------------------------
    # Use a lower DB-query threshold so we don't miss borderline candidates.
    # The classification step decides whether the match is truly usable.
    fuzzy_matches = await fuzzy_name_match(
        legal_name,
        country,
        session,
        threshold=THRESHOLD_REVIEW * 100,  # rapidfuzz works in 0-100 scale
    )

    if fuzzy_matches:
        best = fuzzy_matches[0]
        logger.info(
            "Stage 3 hit: fuzzy '%s' -> entity %s (%s, confidence %.4f)",
            legal_name,
            best.entity_id,
            best.legal_name,
            best.confidence,
        )
        return _classify(best)

    # ------------------------------------------------------------------
    # Stage 4: Address-based matching
    # ------------------------------------------------------------------
    if address:
        addr_matches = await address_match(
            legal_name,
            address,
            country,
            session,
            threshold=THRESHOLD_REVIEW * 100,
        )

        if addr_matches:
            best = addr_matches[0]
            logger.info(
                "Stage 4 hit: address '%s' -> entity %s (%s, confidence %.4f)",
                legal_name,
                best.entity_id,
                best.legal_name,
                best.confidence,
            )
            return _classify(best)

        logger.debug("Stage 4: no address match found")

    # ------------------------------------------------------------------
    # No match at any stage — new entity
    # ------------------------------------------------------------------
    logger.info("No match found for '%s' — flagging as NEW", legal_name)
    return ResolutionResult(
        entity_id=None,
        confidence=0.0,
        match_method=None,
        status="NEW",
        details={"legal_name": legal_name, "country": country},
    )
