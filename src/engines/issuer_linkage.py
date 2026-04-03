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
    min_confidence: float = 0.5,
) -> dict | None:
    """Find the best parent match for a financing subsidiary.

    Each candidate dict has 'entity_id', 'legal_name'.
    Returns the best matching candidate or None.

    Parameters
    ----------
    issuer_name : Name of the issuer entity (e.g. "Apple Inc. Capital LLC").
    parent_candidates : List of potential parent entities.
    min_confidence : Minimum confidence score (0.0–1.0) to accept a match.
        Default 0.5 means at least 50% of the shorter name must match.
    """
    if not issuer_name or not parent_candidates:
        return None

    issuer_lower = issuer_name.lower()
    best = None
    best_score = 0.0

    for candidate in parent_candidates:
        cand_name = candidate.get("legal_name", "").lower()
        if not cand_name:
            continue

        # Score: length of matching prefix
        prefix_score = 0
        for i, (a, b) in enumerate(zip(issuer_lower, cand_name)):
            if a == b:
                prefix_score = i + 1
            else:
                break

        # Substring containment bonus
        if cand_name in issuer_lower:
            prefix_score = max(prefix_score, len(cand_name))

        # Normalize to 0.0–1.0 based on shorter name length
        shorter_len = min(len(issuer_lower), len(cand_name))
        confidence = prefix_score / shorter_len if shorter_len > 0 else 0.0

        if confidence > best_score:
            best_score = confidence
            best = candidate

    return best if best_score >= min_confidence else None


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
