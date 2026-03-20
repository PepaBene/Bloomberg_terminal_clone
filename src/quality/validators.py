"""Data quality validation rules per domain (Spec 13.4)."""

import logging
import math
import re
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.entity import Entity, EntityIdentifier
from src.models.reference import Country, Currency, Exchange, GICSClassification
from src.models.security import EODPrice, Security, SecurityIdentifier

logger = logging.getLogger(__name__)


@dataclass
class ValidationIssue:
    domain: str
    record_id: uuid.UUID | None
    issue_type: str
    severity: str
    field_name: str | None
    description: str


# ── Entity Validation Rules ─────────────────────────────────────────


async def validate_lei_format(session: AsyncSession) -> list[ValidationIssue]:
    """LEI must match ISO 17442 pattern: 20 alphanumeric characters."""
    issues = []
    result = await session.execute(
        select(EntityIdentifier).where(
            EntityIdentifier.identifier_type == "LEI"
        )
    )
    for ident in result.scalars():
        if not re.match(r"^[A-Z0-9]{20}$", ident.identifier_value):
            issues.append(
                ValidationIssue(
                    domain="ENTITY",
                    record_id=ident.entity_id,
                    issue_type="INVALID_VALUE",
                    severity="HIGH",
                    field_name="lei",
                    description=f"LEI '{ident.identifier_value}' does not match ISO 17442 format",
                )
            )
    return issues


async def validate_entity_has_country(session: AsyncSession) -> list[ValidationIssue]:
    """Active entities must have an incorporation country."""
    issues = []
    result = await session.execute(
        select(Entity).where(
            Entity.status == "ACTIVE",
            Entity.incorporation_country.is_(None),
        )
    )
    for entity in result.scalars():
        issues.append(
            ValidationIssue(
                domain="ENTITY",
                record_id=entity.entity_id,
                issue_type="MISSING_VALUE",
                severity="CRITICAL",
                field_name="incorporation_country",
                description=f"Active entity '{entity.legal_name}' has no country",
            )
        )
    return issues


async def validate_entity_has_identifier(session: AsyncSession) -> list[ValidationIssue]:
    """Every entity must have at least one identifier."""
    issues = []
    result = await session.execute(
        select(Entity)
        .outerjoin(EntityIdentifier)
        .where(EntityIdentifier.id.is_(None))
    )
    for entity in result.scalars():
        issues.append(
            ValidationIssue(
                domain="ENTITY",
                record_id=entity.entity_id,
                issue_type="MISSING_VALUE",
                severity="HIGH",
                field_name="identifiers",
                description=f"Entity '{entity.legal_name}' has no identifiers",
            )
        )
    return issues


async def validate_fiscal_year_end(session: AsyncSession) -> list[ValidationIssue]:
    """Fiscal year end must be valid MM-DD format."""
    issues = []
    result = await session.execute(
        select(Entity).where(Entity.fiscal_year_end.isnot(None))
    )
    for entity in result.scalars():
        fye = entity.fiscal_year_end
        if not re.match(r"^(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$", fye):
            issues.append(
                ValidationIssue(
                    domain="ENTITY",
                    record_id=entity.entity_id,
                    issue_type="FORMAT_ERROR",
                    severity="MEDIUM",
                    field_name="fiscal_year_end",
                    description=f"Invalid fiscal year end format: '{fye}' (expected MM-DD)",
                )
            )
    return issues


# ── Security Validation Rules ───────────────────────────────────────


def _luhn_checksum(isin: str) -> bool:
    """Validate ISIN check digit using Luhn algorithm on numeric encoding."""
    if len(isin) != 12:
        return False
    # Convert letters to numbers (A=10, B=11, ..., Z=35)
    digits = ""
    for ch in isin:
        if ch.isdigit():
            digits += ch
        elif ch.isalpha():
            digits += str(ord(ch.upper()) - 55)
        else:
            return False

    # Luhn algorithm
    total = 0
    for i, d in enumerate(reversed(digits)):
        n = int(d)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


async def validate_isin_check_digit(session: AsyncSession) -> list[ValidationIssue]:
    """ISIN must pass Luhn check digit validation."""
    issues = []
    result = await session.execute(
        select(SecurityIdentifier).where(
            SecurityIdentifier.identifier_type == "ISIN"
        )
    )
    for ident in result.scalars():
        if not _luhn_checksum(ident.identifier_value):
            issues.append(
                ValidationIssue(
                    domain="SECURITY",
                    record_id=ident.security_id,
                    issue_type="INVALID_VALUE",
                    severity="HIGH",
                    field_name="isin",
                    description=f"ISIN '{ident.identifier_value}' fails check digit validation",
                )
            )
    return issues


async def validate_security_has_issuer(session: AsyncSession) -> list[ValidationIssue]:
    """Every security should have an issuer entity."""
    issues = []
    result = await session.execute(
        select(Security).where(Security.issuer_entity_id.is_(None))
    )
    for sec in result.scalars():
        issues.append(
            ValidationIssue(
                domain="SECURITY",
                record_id=sec.security_id,
                issue_type="REFERENTIAL_INTEGRITY",
                severity="HIGH",
                field_name="issuer_entity_id",
                description=f"Security '{sec.name}' has no issuer entity",
            )
        )
    return issues


async def validate_eod_price_ranges(session: AsyncSession) -> list[ValidationIssue]:
    """EOD prices: close > 0, high >= low, close within high/low range."""
    issues = []

    # Negative/zero close
    result = await session.execute(
        select(EODPrice).where(EODPrice.close <= 0)
    )
    for price in result.scalars():
        issues.append(
            ValidationIssue(
                domain="SECURITY",
                record_id=price.security_id,
                issue_type="INVALID_VALUE",
                severity="CRITICAL",
                field_name="close",
                description=f"Non-positive close price on {price.price_date}",
            )
        )

    # High < Low
    result = await session.execute(
        select(EODPrice).where(
            EODPrice.high.isnot(None),
            EODPrice.low.isnot(None),
            EODPrice.high < EODPrice.low,
        )
    )
    for price in result.scalars():
        issues.append(
            ValidationIssue(
                domain="SECURITY",
                record_id=price.security_id,
                issue_type="INVALID_VALUE",
                severity="CRITICAL",
                field_name="high",
                description=f"High < Low on {price.price_date}",
            )
        )

    return issues


# ── Reference Validation Rules ──────────────────────────────────────


async def validate_country_codes(session: AsyncSession) -> list[ValidationIssue]:
    """Country alpha2 codes must be 2 uppercase letters."""
    issues = []
    result = await session.execute(select(Country))
    for country in result.scalars():
        if not re.match(r"^[A-Z]{2}$", country.country_code_alpha2):
            issues.append(
                ValidationIssue(
                    domain="REFERENCE",
                    record_id=None,
                    issue_type="FORMAT_ERROR",
                    severity="CRITICAL",
                    field_name="country_code_alpha2",
                    description=f"Invalid alpha2 code: '{country.country_code_alpha2}'",
                )
            )
    return issues


async def validate_currency_codes(session: AsyncSession) -> list[ValidationIssue]:
    """Currency codes must be 3 uppercase letters."""
    issues = []
    result = await session.execute(select(Currency))
    for currency in result.scalars():
        if not re.match(r"^[A-Z]{3}$", currency.currency_code):
            issues.append(
                ValidationIssue(
                    domain="REFERENCE",
                    record_id=None,
                    issue_type="FORMAT_ERROR",
                    severity="CRITICAL",
                    field_name="currency_code",
                    description=f"Invalid currency code: '{currency.currency_code}'",
                )
            )
    return issues


# ── Macro Validation Rules ─────────────────────────────────────────


async def validate_macro_value_range(session: AsyncSession) -> list[ValidationIssue]:
    """Macro values should be within reasonable bounds per category."""
    from src.models.macro import MacroIndicator, MacroValue

    issues = []
    # Check for NULL or zero values that should be non-zero
    result = await session.execute(
        select(MacroValue, MacroIndicator.category, MacroIndicator.indicator_code)
        .join(MacroIndicator, MacroValue.indicator_id == MacroIndicator.indicator_id)
        .where(MacroValue.value.is_(None))
    )
    for row in result.all():
        issues.append(
            ValidationIssue(
                domain="MACRO",
                record_id=row[0].indicator_id,
                issue_type="MISSING_VALUE",
                severity="HIGH",
                field_name="value",
                description=f"Null value for {row[2]} on {row[0].observation_date}",
            )
        )

    # Check percentage-type indicators (rates) for extreme values
    result = await session.execute(
        select(MacroValue, MacroIndicator.indicator_code)
        .join(MacroIndicator, MacroValue.indicator_id == MacroIndicator.indicator_id)
        .where(
            MacroIndicator.category == "RATES",
            (MacroValue.value < -50) | (MacroValue.value > 100),
        )
    )
    for row in result.all():
        issues.append(
            ValidationIssue(
                domain="MACRO",
                record_id=row[0].indicator_id,
                issue_type="INVALID_VALUE",
                severity="CRITICAL",
                field_name="value",
                description=f"Rate indicator {row[1]} has extreme value {row[0].value} on {row[0].observation_date}",
            )
        )

    return issues


async def validate_macro_indicator_has_values(session: AsyncSession) -> list[ValidationIssue]:
    """Active indicators must have at least one value."""
    from src.models.macro import MacroIndicator, MacroValue

    issues = []
    result = await session.execute(
        select(MacroIndicator)
        .outerjoin(MacroValue)
        .where(
            MacroIndicator.is_active.is_(True),
            MacroValue.indicator_id.is_(None),
        )
    )
    for indicator in result.scalars():
        issues.append(
            ValidationIssue(
                domain="MACRO",
                record_id=indicator.indicator_id,
                issue_type="MISSING_VALUE",
                severity="MEDIUM",
                field_name="values",
                description=f"Active indicator '{indicator.indicator_code}' has no values",
            )
        )
    return issues


async def validate_macro_chronological_order(session: AsyncSession) -> list[ValidationIssue]:
    """Vintage dates must be >= observation dates."""
    from src.models.macro import MacroIndicator, MacroValue

    issues = []
    result = await session.execute(
        select(MacroValue, MacroIndicator.indicator_code)
        .join(MacroIndicator, MacroValue.indicator_id == MacroIndicator.indicator_id)
        .where(MacroValue.vintage_date < MacroValue.observation_date)
    )
    for row in result.all():
        issues.append(
            ValidationIssue(
                domain="MACRO",
                record_id=row[0].indicator_id,
                issue_type="BUSINESS_RULE_VIOLATION",
                severity="HIGH",
                field_name="vintage_date",
                description=f"Vintage date {row[0].vintage_date} is before observation date {row[0].observation_date} for {row[1]}",
            )
        )
    return issues


# ── Corporate Actions Validation Rules (D5) ────────────────────────


async def validate_split_factor(session: AsyncSession) -> list[ValidationIssue]:
    """Split factor must equal split_ratio_to / split_ratio_from."""
    from src.models.corporate_actions import SplitAction

    issues = []
    result = await session.execute(
        select(SplitAction).where(
            SplitAction.split_factor.isnot(None),
            SplitAction.split_ratio_from > 0,
        )
    )
    for split in result.scalars():
        expected = float(split.split_ratio_to) / float(split.split_ratio_from)
        if abs(float(split.split_factor) - expected) > 0.0001:
            issues.append(
                ValidationIssue(
                    domain="CORPORATE_ACTIONS",
                    record_id=split.action_id,
                    issue_type="BUSINESS_RULE_VIOLATION",
                    severity="HIGH",
                    field_name="split_factor",
                    description=(
                        f"Split factor {split.split_factor} does not match "
                        f"ratio {split.split_ratio_to}/{split.split_ratio_from} = {expected:.6f}"
                    ),
                )
            )
    return issues


async def validate_dividend_positive(session: AsyncSession) -> list[ValidationIssue]:
    """Gross amount must be positive for cash dividends."""
    from src.models.corporate_actions import DividendAction

    issues = []
    result = await session.execute(
        select(DividendAction).where(
            DividendAction.dividend_type.in_(["CASH", "REGULAR", "SPECIAL"]),
            DividendAction.gross_amount.isnot(None),
            DividendAction.gross_amount <= 0,
        )
    )
    for div in result.scalars():
        issues.append(
            ValidationIssue(
                domain="CORPORATE_ACTIONS",
                record_id=div.action_id,
                issue_type="INVALID_VALUE",
                severity="CRITICAL",
                field_name="gross_amount",
                description=f"Cash dividend has non-positive gross amount: {div.gross_amount}",
            )
        )
    return issues


async def validate_ex_date_order(session: AsyncSession) -> list[ValidationIssue]:
    """Announcement date <= ex_date <= payment_date."""
    from src.models.corporate_actions import CorporateAction

    issues = []
    # Check announcement_date > ex_date
    result = await session.execute(
        select(CorporateAction).where(
            CorporateAction.announcement_date.isnot(None),
            CorporateAction.ex_date.isnot(None),
            CorporateAction.announcement_date > CorporateAction.ex_date,
        )
    )
    for ca in result.scalars():
        issues.append(
            ValidationIssue(
                domain="CORPORATE_ACTIONS",
                record_id=ca.action_id,
                issue_type="BUSINESS_RULE_VIOLATION",
                severity="HIGH",
                field_name="announcement_date",
                description=(
                    f"Announcement date {ca.announcement_date} is after "
                    f"ex-date {ca.ex_date}"
                ),
            )
        )

    # Check ex_date > payment_date
    result = await session.execute(
        select(CorporateAction).where(
            CorporateAction.ex_date.isnot(None),
            CorporateAction.payment_date.isnot(None),
            CorporateAction.ex_date > CorporateAction.payment_date,
        )
    )
    for ca in result.scalars():
        issues.append(
            ValidationIssue(
                domain="CORPORATE_ACTIONS",
                record_id=ca.action_id,
                issue_type="BUSINESS_RULE_VIOLATION",
                severity="HIGH",
                field_name="ex_date",
                description=(
                    f"Ex-date {ca.ex_date} is after payment date {ca.payment_date}"
                ),
            )
        )
    return issues


# ── Ownership Validation Rules (D6) ────────────────────────────────


async def validate_holding_percent_range(session: AsyncSession) -> list[ValidationIssue]:
    """Percent of outstanding must be between 0 and 100."""
    from src.models.ownership import InstitutionalHolding

    issues = []
    result = await session.execute(
        select(InstitutionalHolding).where(
            InstitutionalHolding.percent_of_outstanding.isnot(None),
            (InstitutionalHolding.percent_of_outstanding < 0)
            | (InstitutionalHolding.percent_of_outstanding > 100),
        )
    )
    for holding in result.all():
        issues.append(
            ValidationIssue(
                domain="OWNERSHIP",
                record_id=holding.security_id,
                issue_type="INVALID_VALUE",
                severity="HIGH",
                field_name="percent_of_outstanding",
                description=(
                    f"Institutional holding percent of outstanding "
                    f"{holding.percent_of_outstanding} is outside 0-100 range"
                ),
            )
        )
    return issues


async def validate_insider_transaction_sign(session: AsyncSession) -> list[ValidationIssue]:
    """Purchases must have positive shares_transacted, sales must be negative."""
    from src.models.ownership import InsiderHolding

    issues = []
    # Purchases with negative shares
    result = await session.execute(
        select(InsiderHolding).where(
            InsiderHolding.transaction_type == "PURCHASE",
            InsiderHolding.shares_transacted.isnot(None),
            InsiderHolding.shares_transacted < 0,
        )
    )
    for txn in result.scalars():
        issues.append(
            ValidationIssue(
                domain="OWNERSHIP",
                record_id=txn.transaction_id,
                issue_type="BUSINESS_RULE_VIOLATION",
                severity="HIGH",
                field_name="shares_transacted",
                description=(
                    f"Purchase transaction has negative shares: {txn.shares_transacted}"
                ),
            )
        )

    # Sales with positive shares
    result = await session.execute(
        select(InsiderHolding).where(
            InsiderHolding.transaction_type == "SALE",
            InsiderHolding.shares_transacted.isnot(None),
            InsiderHolding.shares_transacted > 0,
        )
    )
    for txn in result.scalars():
        issues.append(
            ValidationIssue(
                domain="OWNERSHIP",
                record_id=txn.transaction_id,
                issue_type="BUSINESS_RULE_VIOLATION",
                severity="HIGH",
                field_name="shares_transacted",
                description=(
                    f"Sale transaction has positive shares: {txn.shares_transacted}"
                ),
            )
        )
    return issues


async def validate_short_interest_consistency(session: AsyncSession) -> list[ValidationIssue]:
    """Short percent of outstanding must not exceed 100."""
    from src.models.ownership import ShortInterest

    issues = []
    result = await session.execute(
        select(ShortInterest).where(
            ShortInterest.short_percent_outstanding.isnot(None),
            ShortInterest.short_percent_outstanding > 100,
        )
    )
    for si in result.scalars():
        issues.append(
            ValidationIssue(
                domain="OWNERSHIP",
                record_id=si.security_id,
                issue_type="INVALID_VALUE",
                severity="CRITICAL",
                field_name="short_percent_outstanding",
                description=(
                    f"Short percent of outstanding {si.short_percent_outstanding} "
                    f"exceeds 100 on {si.settlement_date}"
                ),
            )
        )
    return issues


# ── Fundamentals Validation Rules (D3) ─────────────────────────────


async def validate_balance_sheet_balances(session: AsyncSession) -> list[ValidationIssue]:
    """Total assets must approximately equal total liabilities and equity."""
    from src.models.fundamentals import BalanceSheet

    issues = []
    result = await session.execute(
        select(BalanceSheet).where(
            BalanceSheet.total_assets.isnot(None),
            BalanceSheet.total_liabilities_and_equity.isnot(None),
        )
    )
    for bs in result.scalars():
        assets = float(bs.total_assets)
        tle = float(bs.total_liabilities_and_equity)
        if assets == 0 and tle == 0:
            continue
        denominator = max(abs(assets), abs(tle), 1.0)
        pct_diff = abs(assets - tle) / denominator
        if pct_diff > 0.01:  # 1% tolerance
            issues.append(
                ValidationIssue(
                    domain="FUNDAMENTALS",
                    record_id=bs.period_id,
                    issue_type="BUSINESS_RULE_VIOLATION",
                    severity="CRITICAL",
                    field_name="total_assets",
                    description=(
                        f"Balance sheet imbalance: total_assets={assets} vs "
                        f"total_liabilities_and_equity={tle} (diff {pct_diff:.2%})"
                    ),
                )
            )
    return issues


async def validate_revenue_positive(session: AsyncSession) -> list[ValidationIssue]:
    """Total revenue should be non-negative."""
    from src.models.fundamentals import IncomeStatement

    issues = []
    result = await session.execute(
        select(IncomeStatement).where(
            IncomeStatement.total_revenue.isnot(None),
            IncomeStatement.total_revenue < 0,
        )
    )
    for inc in result.scalars():
        issues.append(
            ValidationIssue(
                domain="FUNDAMENTALS",
                record_id=inc.period_id,
                issue_type="INVALID_VALUE",
                severity="HIGH",
                field_name="total_revenue",
                description=f"Negative total revenue: {inc.total_revenue}",
            )
        )
    return issues


async def validate_eps_consistency(session: AsyncSession) -> list[ValidationIssue]:
    """Basic EPS should approximately equal net_income_to_common / basic_shares_outstanding."""
    from src.models.fundamentals import IncomeStatement

    issues = []
    result = await session.execute(
        select(IncomeStatement).where(
            IncomeStatement.basic_eps.isnot(None),
            IncomeStatement.net_income_to_common.isnot(None),
            IncomeStatement.basic_shares_outstanding.isnot(None),
            IncomeStatement.basic_shares_outstanding > 0,
        )
    )
    for inc in result.scalars():
        expected_eps = float(inc.net_income_to_common) / float(inc.basic_shares_outstanding)
        actual_eps = float(inc.basic_eps)
        if abs(expected_eps) < 0.001:
            continue
        pct_diff = abs(actual_eps - expected_eps) / max(abs(expected_eps), 0.001)
        if pct_diff > 0.05:  # 5% tolerance
            issues.append(
                ValidationIssue(
                    domain="FUNDAMENTALS",
                    record_id=inc.period_id,
                    issue_type="BUSINESS_RULE_VIOLATION",
                    severity="MEDIUM",
                    field_name="basic_eps",
                    description=(
                        f"EPS inconsistency: reported={actual_eps:.4f} vs "
                        f"calculated={expected_eps:.4f} (diff {pct_diff:.2%})"
                    ),
                )
            )
    return issues


# ── ESG Validation Rules (D9) ──────────────────────────────────────


async def validate_esg_score_range(session: AsyncSession) -> list[ValidationIssue]:
    """ESG scores must be between 0 and 100."""
    from src.models.esg import ESGScore

    issues = []
    score_fields = [
        ("esg_score", ESGScore.esg_score),
        ("environmental_score", ESGScore.environmental_score),
        ("social_score", ESGScore.social_score),
        ("governance_score", ESGScore.governance_score),
    ]
    for field_name, column in score_fields:
        result = await session.execute(
            select(ESGScore).where(
                column.isnot(None),
                (column < 0) | (column > 100),
            )
        )
        for score in result.scalars():
            issues.append(
                ValidationIssue(
                    domain="ESG",
                    record_id=score.score_id,
                    issue_type="INVALID_VALUE",
                    severity="HIGH",
                    field_name=field_name,
                    description=(
                        f"ESG {field_name} value {getattr(score, field_name)} "
                        f"is outside 0-100 range for entity on {score.as_of_date}"
                    ),
                )
            )
    return issues


async def validate_controversy_dates(session: AsyncSession) -> list[ValidationIssue]:
    """Controversy start_date must be before resolution_date."""
    from src.models.esg import ESGControversy

    issues = []
    result = await session.execute(
        select(ESGControversy).where(
            ESGControversy.start_date.isnot(None),
            ESGControversy.resolution_date.isnot(None),
            ESGControversy.start_date > ESGControversy.resolution_date,
        )
    )
    for controversy in result.scalars():
        issues.append(
            ValidationIssue(
                domain="ESG",
                record_id=controversy.controversy_id,
                issue_type="BUSINESS_RULE_VIOLATION",
                severity="HIGH",
                field_name="start_date",
                description=(
                    f"Controversy start date {controversy.start_date} is after "
                    f"resolution date {controversy.resolution_date}"
                ),
            )
        )
    return issues


# ── Relationships Validation Rules (D10) ───────────────────────────


async def validate_relationship_no_self_reference(session: AsyncSession) -> list[ValidationIssue]:
    """Source entity must not equal target entity."""
    from src.models.relationships import BusinessRelationship

    issues = []
    result = await session.execute(
        select(BusinessRelationship).where(
            BusinessRelationship.source_entity_id == BusinessRelationship.target_entity_id
        )
    )
    for rel in result.scalars():
        issues.append(
            ValidationIssue(
                domain="RELATIONSHIPS",
                record_id=rel.relationship_id,
                issue_type="BUSINESS_RULE_VIOLATION",
                severity="CRITICAL",
                field_name="source_entity_id",
                description=(
                    f"Self-referencing relationship: source and target are both "
                    f"{rel.source_entity_id}"
                ),
            )
        )
    return issues


async def validate_relationship_revenue_percent(session: AsyncSession) -> list[ValidationIssue]:
    """Revenue percentage must be between 0 and 1."""
    from src.models.relationships import BusinessRelationship

    issues = []
    result = await session.execute(
        select(BusinessRelationship).where(
            BusinessRelationship.revenue_percentage.isnot(None),
            (BusinessRelationship.revenue_percentage < 0)
            | (BusinessRelationship.revenue_percentage > 1),
        )
    )
    for rel in result.scalars():
        issues.append(
            ValidationIssue(
                domain="RELATIONSHIPS",
                record_id=rel.relationship_id,
                issue_type="INVALID_VALUE",
                severity="HIGH",
                field_name="revenue_percentage",
                description=(
                    f"Revenue percentage {rel.revenue_percentage} is outside 0-1 range"
                ),
            )
        )
    return issues


async def validate_relationship_confidence(session: AsyncSession) -> list[ValidationIssue]:
    """Confidence score must be between 0 and 1."""
    from src.models.relationships import BusinessRelationship

    issues = []
    result = await session.execute(
        select(BusinessRelationship).where(
            BusinessRelationship.confidence_score.isnot(None),
            (BusinessRelationship.confidence_score < 0)
            | (BusinessRelationship.confidence_score > 1),
        )
    )
    for rel in result.scalars():
        issues.append(
            ValidationIssue(
                domain="RELATIONSHIPS",
                record_id=rel.relationship_id,
                issue_type="INVALID_VALUE",
                severity="HIGH",
                field_name="confidence_score",
                description=(
                    f"Confidence score {rel.confidence_score} is outside 0-1 range"
                ),
            )
        )
    return issues


# ── Run All Validators ──────────────────────────────────────────────

ALL_VALIDATORS = {
    "ENTITY": [
        validate_lei_format,
        validate_entity_has_country,
        validate_entity_has_identifier,
        validate_fiscal_year_end,
    ],
    "SECURITY": [
        validate_isin_check_digit,
        validate_security_has_issuer,
        validate_eod_price_ranges,
    ],
    "REFERENCE": [
        validate_country_codes,
        validate_currency_codes,
    ],
    "MACRO": [
        validate_macro_value_range,
        validate_macro_indicator_has_values,
        validate_macro_chronological_order,
    ],
    "CORPORATE_ACTIONS": [
        validate_split_factor,
        validate_dividend_positive,
        validate_ex_date_order,
    ],
    "OWNERSHIP": [
        validate_holding_percent_range,
        validate_insider_transaction_sign,
        validate_short_interest_consistency,
    ],
    "FUNDAMENTALS": [
        validate_balance_sheet_balances,
        validate_revenue_positive,
        validate_eps_consistency,
    ],
    "ESG": [
        validate_esg_score_range,
        validate_controversy_dates,
    ],
    "RELATIONSHIPS": [
        validate_relationship_no_self_reference,
        validate_relationship_revenue_percent,
        validate_relationship_confidence,
    ],
}


async def run_all_validators(
    session: AsyncSession, domain: str | None = None
) -> list[ValidationIssue]:
    """Run all validation rules, optionally filtered by domain."""
    all_issues: list[ValidationIssue] = []

    domains = [domain] if domain else list(ALL_VALIDATORS.keys())
    for d in domains:
        validators = ALL_VALIDATORS.get(d, [])
        for validator_fn in validators:
            try:
                issues = await validator_fn(session)
                all_issues.extend(issues)
                logger.info(f"  {validator_fn.__name__}: {len(issues)} issues")
            except Exception as e:
                logger.error(f"  {validator_fn.__name__} failed: {e}")

    return all_issues
