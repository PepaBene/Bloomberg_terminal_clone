"""SQLAlchemy models for Bloomberg Data Fabric."""

from src.models.base import Base, TimestampMixin
from src.models.entity import (
    Entity,
    EntityHistory,
    EntityIdentifier,
    EntityName,
    EntityRelationship,
    ResolutionQueue,
)
from src.models.governance import (
    DataCatalogEntry,
    DataRevision,
    LineageRecord,
    SourceConnector,
)
from src.models.macro import (
    CentralBankPolicy,
    MacroIndicator,
    MacroValue,
)
from src.models.fundamentals import (
    BalanceSheet,
    CashFlowStatement,
    Filing,
    FinancialPeriod,
    IncomeStatement,
    KPIDefinition,
    KPIValue,
    SegmentData,
)
from src.models.esg import (
    ESGControversy,
    ESGMetric,
    ESGScore,
)
from src.models.estimates import (
    CompanyGuidance,
    ConsensusEstimate,
    EstimateSurprise,
)
from src.models.ownership import (
    BeneficialOwnershipFiling,
    InsiderHolding,
    InstitutionalHolding,
    InstitutionProfile,
    OwnershipSummary,
    ShortInterest,
)
from src.models.corporate_actions import (
    CorporateAction,
    DividendAction,
    MergerAcquisitionAction,
    SplitAction,
)
from src.models.relationships import (
    BusinessRelationship,
    RelationshipHistory,
)
from src.models.auth import APIAuditLog, User
from src.models.quality import DataQualityIssue, DataQualityScore
from src.models.reference import (
    Country,
    Currency,
    Exchange,
    GICSClassification,
    NAICSCode,
    SICCode,
    SICToGICSMapping,
    TradingCalendar,
    TradingDay,
)
from src.models.security import (
    CallPutSchedule,
    CreditRating,
    EODPrice,
    EquityDetails,
    FixedIncomeDetails,
    Security,
    SecurityIdentifier,
)

__all__ = [
    "Base",
    "TimestampMixin",
    # Reference (D8)
    "Country",
    "Currency",
    "Exchange",
    "GICSClassification",
    "SICCode",
    "NAICSCode",
    "SICToGICSMapping",
    "TradingCalendar",
    "TradingDay",
    # Entity (D1)
    "Entity",
    "EntityIdentifier",
    "EntityName",
    "EntityRelationship",
    "EntityHistory",
    "ResolutionQueue",
    # Security (D2)
    "Security",
    "SecurityIdentifier",
    "EquityDetails",
    "FixedIncomeDetails",
    "CreditRating",
    "CallPutSchedule",
    "EODPrice",
    # Quality
    "DataQualityScore",
    "DataQualityIssue",
    # Governance
    "DataRevision",
    "LineageRecord",
    "DataCatalogEntry",
    "SourceConnector",
    # Macro (D7)
    "MacroIndicator",
    "MacroValue",
    "CentralBankPolicy",
    # Fundamentals (D3)
    "Filing",
    "FinancialPeriod",
    "IncomeStatement",
    "BalanceSheet",
    "CashFlowStatement",
    "SegmentData",
    "KPIDefinition",
    "KPIValue",
    # Estimates (D4)
    "ConsensusEstimate",
    "EstimateSurprise",
    "CompanyGuidance",
    # ESG (D9)
    "ESGScore",
    "ESGMetric",
    "ESGControversy",
    # Ownership (D6)
    "InstitutionProfile",
    "InstitutionalHolding",
    "InsiderHolding",
    "OwnershipSummary",
    "ShortInterest",
    "BeneficialOwnershipFiling",
    # Corporate Actions (D5)
    "CorporateAction",
    "DividendAction",
    "SplitAction",
    "MergerAcquisitionAction",
    # Business Relationships (D10)
    "BusinessRelationship",
    "RelationshipHistory",
    # Auth
    "User",
    "APIAuditLog",
]
