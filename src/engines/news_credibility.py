"""Layer 2 (AI_THREE_LAYER_REBUILD_PLAN.md §4.2): corroboration clustering
+ credibility scoring. Pure computation — no database access.

Clustering reuses ``news_dedup``'s URL / title-Jaccard / simhash tiers, but
as a "does this candidate corroborate an existing article" query rather
than ``deduplicate()``'s "drop duplicates from a list". Layer 2 wants
every article kept — each is a distinct piece of coverage worth crediting
to its own source — just grouped so ``corroboration_count`` reflects how
many independent sources reported the same event.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.engines.news_dedup import _jaccard_words, hamming_distance, simhash

# §4.2's tier enum: WIRE|TIER1|TIER2|BLOG|SOCIAL|PR. PR wires are
# self-reported (not independent corroboration) but not unreliable either —
# weighted between TIER1 and TIER2.
TIER_WEIGHTS: dict[str, float] = {
    "WIRE": 1.00,
    "TIER1": 0.85,
    "PR": 0.70,
    "TIER2": 0.55,
    "BLOG": 0.35,
    "SOCIAL": 0.20,
}
DEFAULT_TIER_WEIGHT = 0.40  # unrated/unknown source

# Looser than news_dedup.deduplicate's 0.8 title threshold: corroboration
# only needs "same event," not "near-identical headline."
TITLE_JACCARD_THRESHOLD = 0.6
CONTENT_HAMMING_THRESHOLD = 3

# Corroboration boost: +8% per independent corroborating source beyond the
# first, capped at +40% total. Multiple trusted wires reporting the same
# event is real signal, but shouldn't let a dozen aggregators of one PR
# blast outweigh a single WIRE-tier exclusive.
CORROBORATION_STEP = 0.08
CORROBORATION_CAP = 0.40

# Tiers "needs corroboration" applies to when nothing else has confirmed
# the story yet.
_LOW_TRUST_TIERS = frozenset({"TIER2", "BLOG", "SOCIAL", ""})


def source_trust_weight(tier: str | None) -> float:
    return TIER_WEIGHTS.get((tier or "").upper(), DEFAULT_TIER_WEIGHT)


@dataclass(frozen=True)
class ClusterCandidate:
    """Minimal article shape clustering needs — decoupled from the ORM
    model so this stays pure/testable without a DB session."""

    id: str
    source_url: str
    title: str
    body_text: str | None = None


def find_cluster_match(
    candidate: ClusterCandidate, existing: list[ClusterCandidate]
) -> ClusterCandidate | None:
    """First article in ``existing`` that ``candidate`` corroborates, else
    ``None``. Same three tiers ``news_dedup.deduplicate`` uses (URL exact →
    title Jaccard → simhash content), returning the match instead of
    dropping the candidate.
    """
    cand_url = (candidate.source_url or "").strip().lower()
    cand_title = candidate.title or ""
    cand_text = candidate.body_text or cand_title
    cand_hash = simhash(cand_text) if cand_text.strip() else None

    for ex in existing:
        if cand_url and cand_url == (ex.source_url or "").strip().lower():
            return ex
        if _jaccard_words(cand_title, ex.title or "") >= TITLE_JACCARD_THRESHOLD:
            return ex
        if cand_hash is not None:
            ex_text = ex.body_text or ex.title or ""
            if ex_text.strip() and hamming_distance(cand_hash, simhash(ex_text)) <= CONTENT_HAMMING_THRESHOLD:
                return ex
    return None


def compute_credibility_score(*, tier: str | None, corroboration_count: int) -> float:
    """Source tier weight × corroboration boost, clipped to [0, 1]."""
    base = source_trust_weight(tier)
    extra = max(0, corroboration_count - 1)
    boost = min(CORROBORATION_STEP * extra, CORROBORATION_CAP)
    return round(min(base * (1.0 + boost), 1.0), 4)


def classify_non_consensus(*, tier: str | None, corroboration_count: int) -> bool:
    """Flag as "needs corroboration": a lower-trust tier that no other
    source has independently confirmed yet."""
    return (tier or "").upper() in _LOW_TRUST_TIERS and corroboration_count <= 1
