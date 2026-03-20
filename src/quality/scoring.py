"""Data quality scoring engine (Spec 13.3)."""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.entity import Entity, EntityIdentifier
from src.models.quality import DataQualityIssue, DataQualityScore
from src.models.security import Security, SecurityIdentifier
from src.quality.validators import ALL_VALIDATORS, ValidationIssue, run_all_validators

logger = logging.getLogger(__name__)


async def calculate_completeness(domain: str, session: AsyncSession) -> float:
    """Calculate completeness score: ratio of filled required fields."""
    if domain == "ENTITY":
        total = await session.execute(select(func.count(Entity.entity_id)))
        total_count = total.scalar_one()
        if total_count == 0:
            return 100.0

        # Check key fields: country, at least one identifier, fiscal_year_end
        with_country = await session.execute(
            select(func.count(Entity.entity_id)).where(
                Entity.incorporation_country.isnot(None)
            )
        )
        country_count = with_country.scalar_one()

        with_fye = await session.execute(
            select(func.count(Entity.entity_id)).where(
                Entity.fiscal_year_end.isnot(None)
            )
        )
        fye_count = with_fye.scalar_one()

        # Average completeness across key fields
        return round(
            ((country_count + fye_count) / (2 * total_count)) * 100, 2
        )

    elif domain == "SECURITY":
        total = await session.execute(select(func.count(Security.security_id)))
        total_count = total.scalar_one()
        if total_count == 0:
            return 100.0

        with_issuer = await session.execute(
            select(func.count(Security.security_id)).where(
                Security.issuer_entity_id.isnot(None)
            )
        )
        issuer_count = with_issuer.scalar_one()

        with_exchange = await session.execute(
            select(func.count(Security.security_id)).where(
                Security.primary_exchange_mic.isnot(None)
            )
        )
        exchange_count = with_exchange.scalar_one()

        return round(
            ((issuer_count + exchange_count) / (2 * total_count)) * 100, 2
        )

    return 100.0


async def calculate_accuracy(
    issues: list[ValidationIssue], domain: str, session: AsyncSession
) -> float:
    """Calculate accuracy score based on validation pass rate."""
    if domain == "ENTITY":
        total = await session.execute(select(func.count(Entity.entity_id)))
    elif domain == "SECURITY":
        total = await session.execute(select(func.count(Security.security_id)))
    else:
        return 100.0

    total_count = total.scalar_one()
    if total_count == 0:
        return 100.0

    domain_issues = [i for i in issues if i.domain == domain]
    error_count = len(domain_issues)

    # Accuracy = (total - errors) / total * 100
    return round(max(0, (total_count - error_count) / total_count * 100), 2)


async def run_quality_check(
    session: AsyncSession, domain: str | None = None
) -> list[DataQualityScore]:
    """Run all validators, calculate scores, and persist results."""
    logger.info(f"Running quality check for domain: {domain or 'ALL'}")

    # Run validators
    issues = await run_all_validators(session, domain)

    # Group issues by domain
    domains = {domain} if domain else set(ALL_VALIDATORS.keys())
    scores = []

    for d in domains:
        domain_issues = [i for i in issues if i.domain == d]
        critical_count = sum(1 for i in domain_issues if i.severity == "CRITICAL")

        completeness = await calculate_completeness(d, session)
        accuracy = await calculate_accuracy(issues, d, session)

        # Overall score: weighted average
        overall = round(completeness * 0.4 + accuracy * 0.6, 2)

        score = DataQualityScore(
            score_id=uuid.uuid4(),
            domain=d,
            overall_score=overall,
            completeness_score=completeness,
            accuracy_score=accuracy,
            issues_count=len(domain_issues),
            critical_issues=critical_count,
        )
        session.add(score)
        scores.append(score)

        # Persist individual issues
        for issue in domain_issues:
            session.add(
                DataQualityIssue(
                    issue_id=uuid.uuid4(),
                    domain=issue.domain,
                    record_id=issue.record_id,
                    issue_type=issue.issue_type,
                    severity=issue.severity,
                    field_name=issue.field_name,
                    issue_description=issue.description,
                )
            )

        logger.info(
            f"  {d}: overall={overall}, completeness={completeness}, "
            f"accuracy={accuracy}, issues={len(domain_issues)}, "
            f"critical={critical_count}"
        )

    await session.flush()
    return scores
