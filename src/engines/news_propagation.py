"""Pillar 3 Phase 2 -- Part 5: News Propagation Engine.

Computes how a news event affecting one entity propagates to related
entities through supply-chain, customer, competitive, sector, geographic,
and macro-economic relationships.

All functions are pure computation -- no database access.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class PropagationTarget:
    """An entity affected by a propagated news event."""
    target_entity_id: str
    propagation_type: str  # SUPPLY_CHAIN, CUSTOMER, COMPETITIVE, SECTOR, GEOGRAPHIC, MACRO
    hop_number: int  # 1 or 2
    relevance_score: float
    severity: str  # CRITICAL / HIGH / MEDIUM / LOW
    event_summary: str
    relationship_type: str | None = None


@dataclass
class PropagationResult:
    """Complete propagation analysis for a single event."""
    source_entity_id: str
    event_category: str
    targets: list
    total_affected: int


# ---------------------------------------------------------------------------
# Propagation configuration
# ---------------------------------------------------------------------------

PROPAGATION_CONFIG: dict[str, dict] = {
    "SUPPLY_CHAIN": {
        "events": {
            "bankruptcy": "CRITICAL",
            "disruption": "HIGH",
            "price_increase": "MEDIUM",
            "strike": "MEDIUM",
        },
        "hop1_decay": 0.3,
        "hop2_decay": 0.1,
    },
    "CUSTOMER": {
        "events": {
            "revenue_decline": "MEDIUM",
            "bankruptcy": "HIGH",
            "contract_cancel": "HIGH",
            "ma": "MEDIUM",
        },
        "hop1_decay": 0.3,
        "hop2_decay": 0.1,
    },
    "COMPETITIVE": {
        "events": {
            "contract_win": "MEDIUM",
            "price_war": "HIGH",
            "bankruptcy": "HIGH",
            "product_launch": "MEDIUM",
        },
        "hop1_decay": 0.3,
        "hop2_decay": 0.1,
    },
    "SECTOR": {
        "events": {
            "commodity_price": "MEDIUM",
            "regulation": "HIGH",
            "industry_trend": "MEDIUM",
        },
        "hop1_decay": 0.15,
    },
    "GEOGRAPHIC": {
        "events": {
            "country_crisis": "HIGH",
            "sanctions": "CRITICAL",
            "natural_disaster": "HIGH",
        },
        "hop1_decay": 0.15,
    },
    "MACRO": {
        "events": {
            "rate_decision": "HIGH",
            "employment": "MEDIUM",
            "inflation": "MEDIUM",
        },
        "hop1_decay": 0.15,
    },
}


# Keyword map for event classification from article content
_EVENT_KEYWORDS: dict[str, list[str]] = {
    "bankruptcy": ["bankruptcy", "chapter 11", "insolvency", "liquidation", "default"],
    "disruption": ["supply disruption", "shortage", "supply chain disruption", "factory closure"],
    "price_increase": ["price increase", "price hike", "cost increase", "raw material cost"],
    "strike": ["strike", "labor dispute", "work stoppage", "walkout"],
    "revenue_decline": ["revenue decline", "revenue miss", "revenue drop", "sales decline"],
    "contract_cancel": ["contract cancel", "contract termination", "lost contract"],
    "ma": ["acquisition", "merger", "takeover", "buyout"],
    "contract_win": ["contract win", "contract award", "new contract", "awarded"],
    "price_war": ["price war", "pricing pressure", "price competition"],
    "product_launch": ["product launch", "new product", "unveil", "release"],
    "commodity_price": ["commodity price", "oil price", "raw material"],
    "regulation": ["regulation", "regulatory", "compliance", "new rule", "legislation"],
    "industry_trend": ["industry trend", "sector trend", "market shift"],
    "country_crisis": ["political crisis", "civil unrest", "coup", "war"],
    "sanctions": ["sanctions", "embargo", "trade ban", "blacklist"],
    "natural_disaster": ["earthquake", "hurricane", "flood", "tsunami", "wildfire"],
    "rate_decision": ["rate decision", "interest rate", "fed funds", "rate hike", "rate cut", "fomc"],
    "employment": ["employment", "jobs report", "non-farm payroll", "unemployment", "nfp"],
    "inflation": ["inflation", "cpi", "consumer price", "deflation"],
}

# Map event_category -> which propagation type it belongs to
_EVENT_TO_TYPE: dict[str, str] = {}
for _ptype, _cfg in PROPAGATION_CONFIG.items():
    for _evt in _cfg["events"]:
        _EVENT_TO_TYPE[_evt] = _ptype


# ---------------------------------------------------------------------------
# 1. Classify event for propagation
# ---------------------------------------------------------------------------

def classify_event_for_propagation(article_data: dict) -> tuple[str, str] | None:
    """Classify an article's event category and propagation type.

    Parameters
    ----------
    article_data : dict
        Keys: title (str), topics (list[str], optional),
        materiality (str, optional), text (str, optional).

    Returns
    -------
    (event_category, propagation_type) or None if not propagatable.
    """
    title = (article_data.get("title") or "").lower()
    text = (article_data.get("text") or "").lower()
    topics = [t.lower() for t in (article_data.get("topics") or [])]
    combined = title + " " + text + " " + " ".join(topics)

    best_event: str | None = None
    best_score = 0

    for event_category, keywords in _EVENT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in combined)
        if score > best_score:
            best_score = score
            best_event = event_category

    if best_event is None or best_score == 0:
        return None

    propagation_type = _EVENT_TO_TYPE.get(best_event)
    if propagation_type is None:
        return None

    return (best_event, propagation_type)


# ---------------------------------------------------------------------------
# 2. Compute propagation targets
# ---------------------------------------------------------------------------

def compute_propagation_targets(
    source_entity_id: str,
    event_category: str,
    propagation_type: str,
    relationships: list[dict],
    max_hops: int = 2,
) -> list[PropagationTarget]:
    """Compute entities affected by event propagation.

    Parameters
    ----------
    source_entity_id : str
        Entity where the event originated.
    event_category : str
        The classified event (e.g. 'bankruptcy', 'disruption').
    propagation_type : str
        The propagation channel (e.g. 'SUPPLY_CHAIN', 'CUSTOMER').
    relationships : list[dict]
        Each: {source_id, target_id, relationship_type, revenue_pct (optional),
               second_degree_targets (optional, list of dict)}.
    max_hops : int
        Maximum propagation hops (1 or 2).

    Returns
    -------
    list[PropagationTarget] — deduplicated by target_entity_id.
    """
    config = PROPAGATION_CONFIG.get(propagation_type)
    if config is None:
        return []

    events = config.get("events", {})
    severity = events.get(event_category, "LOW")
    hop1_decay = config.get("hop1_decay", 0.3)
    hop2_decay = config.get("hop2_decay", 0.1)

    seen: set[str] = {source_entity_id}
    targets: list[PropagationTarget] = []

    # Hop 1: direct relationships
    hop1_entities: list[dict] = []
    for rel in relationships:
        src = rel.get("source_id", "")
        tgt = rel.get("target_id", "")
        rel_type = rel.get("relationship_type", "")

        # Match if this relationship connects from the source entity
        # and the relationship type matches the propagation type
        if src == source_entity_id and tgt not in seen:
            revenue_pct = rel.get("revenue_pct", 1.0)
            relevance = hop1_decay * revenue_pct

            targets.append(PropagationTarget(
                target_entity_id=tgt,
                propagation_type=propagation_type,
                hop_number=1,
                relevance_score=round(relevance, 4),
                severity=severity,
                event_summary=f"{event_category} at {source_entity_id}",
                relationship_type=rel_type,
            ))
            seen.add(tgt)
            hop1_entities.append(rel)

    # Hop 2: second-degree relationships
    if max_hops >= 2 and hop2_decay:
        for rel in hop1_entities:
            second_degree = rel.get("second_degree_targets", [])
            for sd in second_degree:
                sd_id = sd.get("target_id", "")
                if sd_id and sd_id not in seen:
                    targets.append(PropagationTarget(
                        target_entity_id=sd_id,
                        propagation_type=propagation_type,
                        hop_number=2,
                        relevance_score=round(hop2_decay, 4),
                        severity=_downgrade_severity(severity),
                        event_summary=f"{event_category} at {source_entity_id} (2nd degree)",
                        relationship_type=sd.get("relationship_type"),
                    ))
                    seen.add(sd_id)

    return targets


def _downgrade_severity(severity: str) -> str:
    """Downgrade severity by one level for hop-2 propagation."""
    mapping = {
        "CRITICAL": "HIGH",
        "HIGH": "MEDIUM",
        "MEDIUM": "LOW",
        "LOW": "LOW",
    }
    return mapping.get(severity, "LOW")


# ---------------------------------------------------------------------------
# 3. Sector propagation
# ---------------------------------------------------------------------------

def apply_sector_propagation(
    event_category: str,
    gics_sector: str,
    sector_entities: list[dict],
) -> list[PropagationTarget]:
    """Propagate an event across an entire GICS sector.

    Parameters
    ----------
    event_category : str
        The event type (must be in SECTOR config events).
    gics_sector : str
        GICS sector name (e.g. 'Industrials').
    sector_entities : list[dict]
        Each: {entity_id, entity_name (optional)}.

    Returns
    -------
    list[PropagationTarget] for sector peers.
    """
    config = PROPAGATION_CONFIG.get("SECTOR", {})
    events = config.get("events", {})
    severity = events.get(event_category, "LOW")
    decay = config.get("hop1_decay", 0.15)

    targets: list[PropagationTarget] = []
    for ent in sector_entities:
        eid = ent.get("entity_id", "")
        if not eid:
            continue
        targets.append(PropagationTarget(
            target_entity_id=eid,
            propagation_type="SECTOR",
            hop_number=1,
            relevance_score=round(decay, 4),
            severity=severity,
            event_summary=f"{event_category} affecting {gics_sector} sector",
            relationship_type=f"SECTOR:{gics_sector}",
        ))

    return targets


# ---------------------------------------------------------------------------
# 4. Macro propagation
# ---------------------------------------------------------------------------

def apply_macro_propagation(
    event_category: str,
    sensitive_sectors: list[str],
    sector_entities: dict[str, list[dict]],
) -> list[PropagationTarget]:
    """Propagate a macro-economic event to sensitive sectors.

    Parameters
    ----------
    event_category : str
        Macro event type (rate_decision, employment, inflation).
    sensitive_sectors : list[str]
        GICS sectors sensitive to this event.
    sector_entities : dict[str, list[dict]]
        {sector_name: [{entity_id, ...}]}.

    Returns
    -------
    list[PropagationTarget] for all entities in sensitive sectors.
    """
    config = PROPAGATION_CONFIG.get("MACRO", {})
    events = config.get("events", {})
    severity = events.get(event_category, "LOW")
    decay = config.get("hop1_decay", 0.15)

    targets: list[PropagationTarget] = []
    seen: set[str] = set()

    for sector in sensitive_sectors:
        entities = sector_entities.get(sector, [])
        for ent in entities:
            eid = ent.get("entity_id", "")
            if not eid or eid in seen:
                continue
            seen.add(eid)
            targets.append(PropagationTarget(
                target_entity_id=eid,
                propagation_type="MACRO",
                hop_number=1,
                relevance_score=round(decay, 4),
                severity=severity,
                event_summary=f"Macro event: {event_category} (sector: {sector})",
                relationship_type=f"MACRO:{sector}",
            ))

    return targets


# ---------------------------------------------------------------------------
# 5. Filter by user preferences
# ---------------------------------------------------------------------------

def filter_by_preferences(
    targets: list[PropagationTarget],
    user_preferences: dict[str, bool],
) -> list[PropagationTarget]:
    """Filter propagation targets by user notification preferences.

    Parameters
    ----------
    targets : list[PropagationTarget]
        All computed targets.
    user_preferences : dict[str, bool]
        {propagation_type: enabled}. Types not in dict default to True.

    Returns
    -------
    Filtered list of PropagationTarget.
    """
    if not user_preferences:
        return targets

    return [
        t for t in targets
        if user_preferences.get(t.propagation_type, True)
    ]


# ---------------------------------------------------------------------------
# 6. Orchestrator
# ---------------------------------------------------------------------------

def propagate_event(
    source_entity_id: str,
    article_data: dict,
    relationships: list[dict],
    sector_entities: dict[str, list[dict]],
    user_preferences: dict[str, bool] | None = None,
) -> PropagationResult | None:
    """Full event propagation pipeline.

    Parameters
    ----------
    source_entity_id : str
        Entity where the event originated.
    article_data : dict
        Article data for classification.
    relationships : list[dict]
        Relationship data for entity-to-entity propagation.
    sector_entities : dict[str, list[dict]]
        {sector: [{entity_id, ...}]} for sector/macro propagation.
    user_preferences : dict[str, bool] | None
        Optional notification preferences.

    Returns
    -------
    PropagationResult or None if event is not propagatable.
    """
    classification = classify_event_for_propagation(article_data)
    if classification is None:
        return None

    event_category, propagation_type = classification

    all_targets: list[PropagationTarget] = []

    # Entity-to-entity propagation
    direct_targets = compute_propagation_targets(
        source_entity_id=source_entity_id,
        event_category=event_category,
        propagation_type=propagation_type,
        relationships=relationships,
    )
    all_targets.extend(direct_targets)

    # Sector propagation for sector-level events
    if propagation_type == "SECTOR":
        for sector_name, entities in sector_entities.items():
            sector_targets = apply_sector_propagation(
                event_category=event_category,
                gics_sector=sector_name,
                sector_entities=entities,
            )
            # Avoid duplicates
            existing_ids = {t.target_entity_id for t in all_targets}
            existing_ids.add(source_entity_id)
            for st in sector_targets:
                if st.target_entity_id not in existing_ids:
                    all_targets.append(st)
                    existing_ids.add(st.target_entity_id)

    # Macro propagation for macro events
    if propagation_type == "MACRO":
        # Determine sensitive sectors from event category
        sensitive_sectors: list[str] = []
        if event_category == "rate_decision":
            sensitive_sectors = ["Financials", "Real Estate", "Utilities"]
        elif event_category == "employment":
            sensitive_sectors = ["Consumer Discretionary", "Financials"]
        elif event_category == "inflation":
            sensitive_sectors = ["Real Estate", "Utilities", "Consumer Discretionary"]

        if sensitive_sectors:
            macro_targets = apply_macro_propagation(
                event_category=event_category,
                sensitive_sectors=sensitive_sectors,
                sector_entities=sector_entities,
            )
            existing_ids = {t.target_entity_id for t in all_targets}
            existing_ids.add(source_entity_id)
            for mt in macro_targets:
                if mt.target_entity_id not in existing_ids:
                    all_targets.append(mt)
                    existing_ids.add(mt.target_entity_id)

    # Apply user preference filtering
    if user_preferences:
        all_targets = filter_by_preferences(all_targets, user_preferences)

    return PropagationResult(
        source_entity_id=source_entity_id,
        event_category=event_category,
        targets=all_targets,
        total_affected=len(all_targets),
    )
