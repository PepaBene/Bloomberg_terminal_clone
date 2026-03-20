"""Entity matching engine using fuzzy and phonetic matching (Spec 3.5).

Provides three levels of matching, each with a fixed confidence band:

* **Exact ID match** — confidence 1.0
* **Exact normalised-name + country** — confidence 0.98
* **Fuzzy name match** (token_sort_ratio / partial_ratio) — variable
"""

import logging
import uuid
from dataclasses import dataclass, field

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.entity import Entity, EntityIdentifier
from src.resolution.normalizer import normalize_name, phonetic_key, strip_suffixes

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class MatchResult:
    """A single candidate match returned by the matching engine."""

    entity_id: uuid.UUID
    confidence: float
    match_method: str
    legal_name: str = ""
    details: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Stage 1: Exact identifier lookup
# ---------------------------------------------------------------------------

async def exact_id_match(
    identifier_type: str,
    identifier_value: str,
    session: AsyncSession,
) -> MatchResult | None:
    """Look up an entity by an exact external identifier (LEI, CIK, DUNS, etc.).

    Returns a :class:`MatchResult` with confidence **1.0** if found, else ``None``.
    """
    if not identifier_type or not identifier_value:
        return None

    stmt = (
        select(EntityIdentifier)
        .where(
            EntityIdentifier.identifier_type == identifier_type.upper(),
            EntityIdentifier.identifier_value == identifier_value.strip(),
        )
        .limit(1)
    )

    result = await session.execute(stmt)
    row = result.scalar_one_or_none()

    if row is None:
        return None

    # Fetch the parent entity's legal name for the result
    entity_stmt = select(Entity.legal_name).where(Entity.entity_id == row.entity_id)
    entity_result = await session.execute(entity_stmt)
    legal_name = entity_result.scalar_one_or_none() or ""

    logger.info(
        "Exact ID match: %s=%s -> entity %s",
        identifier_type,
        identifier_value,
        row.entity_id,
    )

    return MatchResult(
        entity_id=row.entity_id,
        confidence=1.0,
        match_method=f"exact_id:{identifier_type}",
        legal_name=legal_name,
        details={"identifier_type": identifier_type, "identifier_value": identifier_value},
    )


# ---------------------------------------------------------------------------
# Stage 2: Exact normalised name + country
# ---------------------------------------------------------------------------

async def exact_name_match(
    name: str,
    country: str | None,
    session: AsyncSession,
) -> MatchResult | None:
    """Exact normalized name (+ optional country) match — confidence **0.98**.

    The supplied *name* is normalised and suffix-stripped before comparison.
    """
    if not name:
        return None

    norm = strip_suffixes(normalize_name(name))
    if not norm:
        return None

    # Load candidates — pre-filter by normalized name substring to avoid loading all entities
    stmt = select(Entity).where(Entity.legal_name.ilike(f"%{norm}%"))
    if country:
        stmt = stmt.where(Entity.incorporation_country == country.upper())

    result = await session.execute(stmt)
    entities: list[Entity] = list(result.scalars().all())

    for entity in entities:
        candidate_norm = strip_suffixes(normalize_name(entity.legal_name))
        if candidate_norm == norm:
            logger.info(
                "Exact name match: '%s' -> entity %s (%s)",
                name,
                entity.entity_id,
                entity.legal_name,
            )
            return MatchResult(
                entity_id=entity.entity_id,
                confidence=0.98,
                match_method="exact_name",
                legal_name=entity.legal_name,
                details={"normalized": norm, "country": country},
            )

    return None


# ---------------------------------------------------------------------------
# Stage 3: Fuzzy name matching (rapidfuzz)
# ---------------------------------------------------------------------------

async def fuzzy_name_match(
    name: str,
    country: str | None,
    session: AsyncSession,
    threshold: float = 85.0,
) -> list[MatchResult]:
    """Fuzzy name match using rapidfuzz scoring.

    Loads all entities for the given *country* (or all entities when country is
    ``None``), then scores each candidate using a composite of:

    * ``token_sort_ratio`` — good for reordered tokens ("Apple Inc" vs "Inc Apple")
    * ``partial_ratio`` — good for substring matches ("JP Morgan" vs "JPMorgan Chase")

    The final score is ``max(token_sort, partial)``, normalised to ``[0, 1]``.

    Only candidates whose composite score meets *threshold* (default 85) are
    returned, sorted by descending confidence.  Phonetic-key overlap is used as
    a tiebreaker bonus (+2 points) to favour phonetically similar names.
    """
    if not name:
        return []

    norm = strip_suffixes(normalize_name(name))
    if not norm:
        return []

    input_phonetic = phonetic_key(norm)

    # Load candidate pool — limit result set to prevent loading the entire table
    stmt = select(Entity)
    if country:
        stmt = stmt.where(Entity.incorporation_country == country.upper())
    stmt = stmt.limit(5000)

    result = await session.execute(stmt)
    candidates: list[Entity] = list(result.scalars().all())

    if not candidates:
        logger.debug("Fuzzy match: no candidate entities for country=%s", country)
        return []

    matches: list[MatchResult] = []

    for entity in candidates:
        candidate_norm = strip_suffixes(normalize_name(entity.legal_name))
        if not candidate_norm:
            continue

        # Core fuzzy scores (0-100 range)
        token_sort_score = fuzz.token_sort_ratio(norm, candidate_norm)
        partial_score = fuzz.partial_ratio(norm, candidate_norm)
        base_score = max(token_sort_score, partial_score)

        # Phonetic bonus: if primary or alternate key overlaps, add a small bonus
        candidate_phonetic = phonetic_key(candidate_norm)
        phonetic_bonus = 0.0
        if input_phonetic[0] and candidate_phonetic[0]:
            if input_phonetic[0] == candidate_phonetic[0]:
                phonetic_bonus = 2.0
            elif input_phonetic[0] == candidate_phonetic[1] or input_phonetic[1] == candidate_phonetic[0]:
                phonetic_bonus = 1.0

        composite = min(base_score + phonetic_bonus, 100.0)

        if composite >= threshold:
            # Normalise to [0, 1] confidence
            confidence = round(composite / 100.0, 4)
            matches.append(
                MatchResult(
                    entity_id=entity.entity_id,
                    confidence=confidence,
                    match_method="fuzzy_name",
                    legal_name=entity.legal_name,
                    details={
                        "input_normalized": norm,
                        "candidate_normalized": candidate_norm,
                        "token_sort_ratio": round(token_sort_score, 2),
                        "partial_ratio": round(partial_score, 2),
                        "phonetic_bonus": phonetic_bonus,
                        "composite_score": round(composite, 2),
                    },
                )
            )

    # Sort by confidence descending, then by legal_name as tiebreaker
    matches.sort(key=lambda m: (-m.confidence, m.legal_name))

    logger.info(
        "Fuzzy match for '%s' (country=%s): %d candidates above threshold %.1f",
        name,
        country,
        len(matches),
        threshold,
    )

    return matches


# ---------------------------------------------------------------------------
# Stage 4: Address-based matching
# ---------------------------------------------------------------------------

async def address_match(
    name: str,
    address: dict | None,
    country: str | None,
    session: AsyncSession,
    threshold: float = 70.0,
) -> list[MatchResult]:
    """Address-based matching to supplement fuzzy name matching.

    Loads entities matching the country, then scores each candidate using a
    composite of:
    * Name similarity (token_sort_ratio) — weighted 60%
    * Address similarity (token_sort_ratio on normalized address) — weighted 40%

    Only candidates above *threshold* are returned.
    """
    from src.resolution.normalizer import normalize_address, normalize_name, strip_suffixes

    if not name or not address:
        return []

    norm_name = strip_suffixes(normalize_name(name))
    norm_addr = normalize_address(address)
    if not norm_name or not norm_addr:
        return []

    # Build a flat address string for comparison
    input_addr_str = " ".join(
        str(v) for v in [
            norm_addr.get("street", ""),
            norm_addr.get("city", ""),
            norm_addr.get("state", ""),
            norm_addr.get("postal_code", ""),
        ]
        if v
    ).strip()

    if not input_addr_str:
        return []

    # Load candidates with addresses
    stmt = select(Entity).where(Entity.domicile_address.isnot(None))
    if country:
        stmt = stmt.where(Entity.incorporation_country == country.upper())

    result = await session.execute(stmt)
    candidates: list[Entity] = list(result.scalars().all())

    if not candidates:
        return []

    matches: list[MatchResult] = []

    for entity in candidates:
        candidate_norm = strip_suffixes(normalize_name(entity.legal_name))
        if not candidate_norm:
            continue

        # Name score
        name_score = fuzz.token_sort_ratio(norm_name, candidate_norm)

        # Address score
        cand_addr = normalize_address(entity.domicile_address)
        if not cand_addr:
            continue

        cand_addr_str = " ".join(
            str(v) for v in [
                cand_addr.get("street", ""),
                cand_addr.get("city", ""),
                cand_addr.get("state", ""),
                cand_addr.get("postal_code", ""),
            ]
            if v
        ).strip()

        if not cand_addr_str:
            continue

        addr_score = fuzz.token_sort_ratio(input_addr_str, cand_addr_str)

        # Composite: 60% name + 40% address
        composite = name_score * 0.6 + addr_score * 0.4

        if composite >= threshold:
            confidence = round(composite / 100.0, 4)
            matches.append(
                MatchResult(
                    entity_id=entity.entity_id,
                    confidence=confidence,
                    match_method="address_match",
                    legal_name=entity.legal_name,
                    details={
                        "name_score": round(name_score, 2),
                        "address_score": round(addr_score, 2),
                        "composite": round(composite, 2),
                    },
                )
            )

    matches.sort(key=lambda m: (-m.confidence, m.legal_name))

    logger.info(
        "Address match for '%s' (country=%s): %d candidates above threshold %.1f",
        name,
        country,
        len(matches),
        threshold,
    )

    return matches
