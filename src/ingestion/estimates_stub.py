"""Estimates ingestion stub — requires paid vendor API (Spec 15.3).

This connector is a placeholder for consensus estimates, earnings surprises,
and company guidance data. Full implementation requires a paid vendor key
(Intrinio + Zacks, estimated $20-30K/year).

Once a vendor API key is configured, implement the extract/transform/load
methods to pull:
- ConsensusEstimate records (EPS, Revenue, EBITDA)
- EstimateSurprise records (actual vs. consensus)
- CompanyGuidance records (management guidance)

Models: src/models/estimates.py
"""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.ingestion.base import BaseConnector

logger = logging.getLogger(__name__)

_VENDOR_MSG = (
    "EstimatesStubConnector requires a paid vendor API key "
    "(Intrinio + Zacks, ~$20-30K/year). Configure ESTIMATES_VENDOR_API_KEY "
    "in .env and replace this stub with a full implementation."
)


class EstimatesStubConnector(BaseConnector):
    """Schema-only stub for consensus estimates ingestion.

    All methods raise NotImplementedError until a paid vendor API key
    (Intrinio + Zacks) is configured and the connector is implemented.
    """

    name = "Estimates Stub"
    connector_type = "BATCH_API"
    data_domain = "ESTIMATES"

    def __init__(self) -> None:
        logger.warning(
            "[%s] This connector is a stub — vendor API key required. "
            "See estimates_stub.py docstring for details.",
            self.name,
        )

    async def extract(self) -> list[dict[str, Any]]:
        """Pull consensus estimates from vendor API.

        Not yet implemented — requires paid vendor key.
        Target models: ConsensusEstimate, EstimateSurprise, CompanyGuidance.
        """
        raise NotImplementedError(_VENDOR_MSG)

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Validate raw estimate records against expected schema."""
        raise NotImplementedError(_VENDOR_MSG)

    async def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Transform vendor-specific format into internal estimate models."""
        raise NotImplementedError(_VENDOR_MSG)

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        """Write ConsensusEstimate / EstimateSurprise / CompanyGuidance records.

        Target tables:
        - consensus_estimates
        - estimate_surprises
        - company_guidance
        """
        raise NotImplementedError(_VENDOR_MSG)
