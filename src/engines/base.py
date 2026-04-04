"""Base engine framework for Pillar 2 Analytics.

Every analytics engine inherits from BaseEngine and produces EngineOutput
instances that follow the composability contract (Spec §13): every output
carries its full lineage so other engines can consume it without special
integration.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


@dataclass
class EngineOutput:
    """Standard output from any engine computation.

    Implements the composability contract from spec §13.  Every metric
    produced by any engine uses this structure so that downstream engines
    and the API layer can consume results uniformly.
    """

    security_id: UUID
    entity_id: UUID
    engine_id: str  # "E1", "E2", …
    metric_name: str  # "gross_margin", "pe_trailing", …
    metric_category: str  # matches RatioCategory enum
    value: float | str | None  # None when computation impossible
    unit: str = "RATIO"  # RATIO, PERCENT, CURRENCY, MULTIPLE, YEARS, DAYS, SCORE
    period: str = "LATEST"  # "TTM", "Q4_2025", "FY_2024"
    period_end_date: date | None = None
    as_of_date: date = field(default_factory=date.today)
    data_quality: str = "COMPLETE"  # DataQualityFlag values
    inputs: list[dict] | None = None  # [{source, field, value, as_of, filing_source}]
    calculation_version: str = "1.0"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def safe_divide(
    numerator: float | None,
    denominator: float | None,
    *,
    allow_negative_denominator: bool = True,
) -> float | None:
    """Divide two values, returning None for zero/missing denominators."""
    if numerator is None or denominator is None:
        return None
    if denominator == 0:
        return None
    if not allow_negative_denominator and denominator < 0:
        return None
    return float(numerator) / float(denominator)


def pct_change(current: float | None, prior: float | None) -> float | None:
    """Compute percentage change: (current - prior) / |prior|."""
    if current is None or prior is None:
        return None
    if prior == 0:
        return None
    return (float(current) - float(prior)) / abs(float(prior))


def cagr(end_value: float | None, start_value: float | None, years: int) -> float | None:
    """Compound annual growth rate."""
    if end_value is None or start_value is None or years <= 0:
        return None
    if start_value <= 0 or end_value <= 0:
        return None
    return (float(end_value) / float(start_value)) ** (1.0 / years) - 1.0


def make_input(
    name: str,
    source: str,
    value: float | None,
    period: str = "",
    filing_source: str = "",
) -> dict:
    """Build a lineage input dict for EngineOutput.inputs."""
    return {
        "name": name,
        "source": source,
        "value": value,
        "period": period,
        "filing_source": filing_source,
    }


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class BaseEngine(ABC):
    """Abstract base for all analytics engines."""

    engine_id: str = ""  # "E1", "E2", …
    engine_name: str = ""  # human-readable
    engine_version: str = "1.0.0"

    @abstractmethod
    async def compute(
        self,
        session: Any,
        security_id: UUID,
        **kwargs: Any,
    ) -> list[EngineOutput]:
        """Compute metrics for a single security.

        Must be implemented by every concrete engine.
        """
        ...

    async def compute_batch(
        self,
        session: Any,
        security_ids: list[UUID],
        **kwargs: Any,
    ) -> list[EngineOutput]:
        """Compute for multiple securities.

        The default implementation iterates one-by-one.  Engines that
        benefit from vectorised batch processing should override this.
        """
        results: list[EngineOutput] = []
        for sid in security_ids:
            try:
                outputs = await asyncio.wait_for(
                    self.compute(session, security_id=sid, **kwargs),
                    timeout=30.0
                )
                results.extend(outputs)
            except asyncio.TimeoutError:
                logger.warning("%s timed out after 30s for security %s", self.engine_id, sid)
            except Exception:
                logger.exception("%s failed for security %s", self.engine_id, sid)
        return results
