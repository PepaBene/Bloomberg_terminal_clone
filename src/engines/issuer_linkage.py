"""D11 FI Supplement P9: Issuer linkage analytics."""

FINANCING_SUBSIDIARY_PATTERNS = [
    "Capital", "Funding", "Finance", "Treasury", "Issuer",
]


def detect_financing_subsidiary(name: str) -> bool:
    """Detect if entity name suggests a financing subsidiary."""
    if not name:
        return False
    name_upper = name.upper()
    for pattern in FINANCING_SUBSIDIARY_PATTERNS:
        if pattern.upper() in name_upper:
            return True
    return False


def resolve_issuer_to_parent(
    issuer_name: str,
    parent_candidates: list[dict],
) -> dict | None:
    """Find the best parent match for a financing subsidiary.
    Each candidate dict has 'entity_id', 'legal_name'.
    Returns the best matching candidate or None."""
    if not issuer_name or not parent_candidates:
        return None
    # Simple heuristic: find candidate whose name is a substring of issuer name
    # or issuer name starts with candidate name
    issuer_lower = issuer_name.lower()
    best = None
    best_score = 0
    for candidate in parent_candidates:
        cand_name = candidate.get("legal_name", "").lower()
        if not cand_name:
            continue
        # Score: length of matching prefix
        score = 0
        for i, (a, b) in enumerate(zip(issuer_lower, cand_name)):
            if a == b:
                score = i + 1
            else:
                break
        if cand_name in issuer_lower:
            score = max(score, len(cand_name))
        if score > best_score:
            best_score = score
            best = candidate
    return best if best_score > 3 else None


def build_issuer_bond_hierarchy(
    parent_entity: dict,
    subsidiaries: list[dict],
    bonds_by_entity: dict[str, list[dict]],
) -> dict:
    """Build a tree structure: parent -> subsidiaries -> bonds.
    Returns: {entity_id, legal_name, bonds: [...], subsidiaries: [{entity_id, legal_name, bonds: [...]}]}."""
    parent_id = str(parent_entity.get("entity_id", ""))
    result = {
        "entity_id": parent_id,
        "legal_name": parent_entity.get("legal_name", ""),
        "bonds": bonds_by_entity.get(parent_id, []),
        "subsidiaries": [],
    }
    for sub in subsidiaries:
        sub_id = str(sub.get("entity_id", ""))
        result["subsidiaries"].append({
            "entity_id": sub_id,
            "legal_name": sub.get("legal_name", ""),
            "bonds": bonds_by_entity.get(sub_id, []),
        })
    return result
