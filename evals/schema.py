"""Golden example schema + loader for the eval harness.

Each YAML file under ``evals/golden/<category>/`` is one example: fixed
inputs, deterministic pass/fail checks (``must_include``/``must_not_include``/
``max_tokens``), optional ``expected_citations``, and a free-text ``notes``
rubric the LLM judge reads alongside its grading criteria.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

GOLDEN_DIR = Path(__file__).parent / "golden"


class GoldenExample(BaseModel):
    id: str
    category: str
    type: str = "factual"  # factual | comparative | scenario (category-dependent)
    inputs: dict[str, Any]
    must_include: list[str] = Field(default_factory=list)
    must_not_include: list[str] = Field(default_factory=list)
    max_tokens: int | None = None
    expected_citations: list[str] = Field(default_factory=list)
    notes: str = ""


def load_golden_examples(category: str) -> list[GoldenExample]:
    """Load every example YAML under ``evals/golden/<category>/``, sorted by id.

    Returns ``[]`` for an unknown/empty category rather than raising -- a
    category with no examples yet (most of them, until Phase 2's per-feature
    migrations each add 3-5) is a normal, not exceptional, state.
    """
    category_dir = GOLDEN_DIR / category
    if not category_dir.is_dir():
        return []
    examples = [
        GoldenExample.model_validate(yaml.safe_load(path.read_text()))
        for path in sorted(category_dir.glob("*.yaml"))
    ]
    return sorted(examples, key=lambda e: e.id)


def list_categories() -> list[str]:
    if not GOLDEN_DIR.is_dir():
        return []
    return sorted(p.name for p in GOLDEN_DIR.iterdir() if p.is_dir())
