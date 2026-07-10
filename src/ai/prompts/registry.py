"""Versioned prompt registry.

Prompts live as YAML under ``src/ai/prompts/vN/<id>.yaml``. Old versions are
kept so prompt changes are auditable and A/B-testable, and so telemetry can pin
``(prompt_id, prompt_version)``. Load with::

    from src.ai.prompts import load_prompt
    p = load_prompt("analyst_qa")             # latest version
    p = load_prompt("analyst_qa", version=1)  # pinned
    system, user = p.system, p.render(question=q, context=ctx)
"""
from __future__ import annotations

import functools
from dataclasses import dataclass
from pathlib import Path

import yaml

_PROMPTS_DIR = Path(__file__).parent


@dataclass(frozen=True)
class Prompt:
    id: str
    version: int
    feature: str
    system: str
    max_tokens: int = 2048
    temperature: float = 0.3
    cache: bool = True
    tier: str | None = None
    user_template: str | None = None

    def render(self, **kwargs) -> str:
        """Fill the user template. Raises if the prompt has no user_template."""
        if self.user_template is None:
            raise ValueError(f"prompt '{self.id}' has no user_template")
        return self.user_template.format(**kwargs)


def _available_versions(prompt_id: str) -> list[int]:
    out: list[int] = []
    for path in _PROMPTS_DIR.glob(f"v*/{prompt_id}.yaml"):
        name = path.parent.name
        if name.startswith("v") and name[1:].isdigit():
            out.append(int(name[1:]))
    return sorted(out)


@functools.lru_cache(maxsize=None)
def load_prompt(prompt_id: str, version: int | None = None) -> Prompt:
    versions = _available_versions(prompt_id)
    if not versions:
        raise KeyError(f"no prompt found for id '{prompt_id}'")
    v = version if version is not None else versions[-1]
    if v not in versions:
        raise KeyError(f"prompt '{prompt_id}' has no version {v} (have {versions})")
    path = _PROMPTS_DIR / f"v{v}" / f"{prompt_id}.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if "system" not in data:
        raise ValueError(f"prompt '{prompt_id}' v{v} missing required 'system' field")
    return Prompt(
        id=data.get("id", prompt_id),
        version=int(data.get("version", v)),
        feature=data.get("feature", prompt_id),
        system=data["system"],
        max_tokens=int(data.get("max_tokens", 2048)),
        temperature=float(data.get("temperature", 0.3)),
        cache=bool(data.get("cache", True)),
        tier=data.get("tier"),
        user_template=data.get("user_template"),
    )


def list_prompts() -> dict[str, list[int]]:
    """Map of prompt_id → sorted available versions."""
    ids: dict[str, list[int]] = {}
    for path in _PROMPTS_DIR.glob("v*/*.yaml"):
        ver = path.parent.name
        if ver.startswith("v") and ver[1:].isdigit():
            ids.setdefault(path.stem, []).append(int(ver[1:]))
    return {k: sorted(v) for k, v in ids.items()}
