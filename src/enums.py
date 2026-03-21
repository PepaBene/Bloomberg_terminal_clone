from enum import Enum


# ---------------------------------------------------------------------------
# Entity enums (Spec 3.2, 3.3, 3.4)
# ---------------------------------------------------------------------------

class EntityType(str, Enum):
    PUBLIC_COMPANY = "PUBLIC_COMPANY"
    PRIVATE_COMPANY = "PRIVATE_COMPANY"
    GOVERNMENT = "GOVERNMENT"
    GOVERNMENT_AGENCY = "GOVERNMENT_AGENCY"
    SUPRANATIONAL = "SUPRANATIONAL"
    FUND = "FUND"
    TRUST = "TRUST"
    SPV = "SPV"
    NON_PROFIT = "NON_PROFIT"
    OTHER = "OTHER"


class EntityStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    MERGED = "MERGED"
    LIQUIDATED = "LIQUIDATED"


class AccountingStandard(str, Enum):
    US_GAAP = "US_GAAP"
    IFRS = "IFRS"
    LOCAL_GAAP = "LOCAL_GAAP"


class ConsolidationType(str, Enum):
    FULL = "FULL"
    PROPORTIONAL = "PROPORTIONAL"
    EQUITY_METHOD = "EQUITY_METHOD"


class RelationshipType(str, Enum):
    PARENT_OF = "PARENT_OF"
    SUBSIDIARY_OF = "SUBSIDIARY_OF"
    JOINT_VENTURE_PARTNER = "JOINT_VENTURE_PARTNER"
    PREDECESSOR_OF = "PREDECESSOR_OF"
    SUCCESSOR_OF = "SUCCESSOR_OF"
    SPUN_OFF_FROM = "SPUN_OFF_FROM"
    SPUN_OFF_TO = "SPUN_OFF_TO"
    CONTROLS = "CONTROLS"
    CONTROLLED_BY = "CONTROLLED_BY"


class EntityIdentifierType(str, Enum):
    LEI = "LEI"
    CIK = "CIK"
    EIN = "EIN"
    ISIN_ISSUER = "ISIN_ISSUER"
    CUSIP_ISSUER = "CUSIP_ISSUER"
    SEDOL_ISSUER = "SEDOL_ISSUER"
    BLOOMBERG_ID = "BLOOMBERG_ID"
    REFINITIV_PERM_ID = "REFINITIV_PERM_ID"
    FACTSET_ENTITY_ID = "FACTSET_ENTITY_ID"
    SPGLOBAL_ID = "SPGLOBAL_ID"
    DUNS = "DUNS"


class EntityNameType(str, Enum):
    LEGAL = "LEGAL"
    SHORT = "SHORT"
    ALIAS = "ALIAS"
    PREVIOUS = "PREVIOUS"
    TRADING = "TRADING"
    DBA = "DBA"


# ---------------------------------------------------------------------------
# Security enums (Spec 4.2, 4.3, 4.4, 4.5)
# ---------------------------------------------------------------------------

class SecurityType(str, Enum):
    COMMON_STOCK = "COMMON_STOCK"
    PREFERRED_STOCK = "PREFERRED_STOCK"
    DEPOSITARY_RECEIPT = "DEPOSITARY_RECEIPT"
    REIT = "REIT"
    MLP = "MLP"
    CORPORATE_BOND = "CORPORATE_BOND"
    GOVERNMENT_BOND = "GOVERNMENT_BOND"
    MUNICIPAL_BOND = "MUNICIPAL_BOND"
    CONVERTIBLE_BOND = "CONVERTIBLE_BOND"
    ETF = "ETF"
    MUTUAL_FUND = "MUTUAL_FUND"
    INDEX = "INDEX"


class SecurityStatus(str, Enum):
    ACTIVE = "ACTIVE"
    MATURED = "MATURED"
    CALLED = "CALLED"
    CONVERTED = "CONVERTED"
    DELISTED = "DELISTED"


class AssetClass(str, Enum):
    EQUITY = "EQUITY"
    FIXED_INCOME = "FIXED_INCOME"
    FUND = "FUND"
    INDEX = "INDEX"


class SecurityIdentifierType(str, Enum):
    ISIN = "ISIN"
    CUSIP = "CUSIP"
    SEDOL = "SEDOL"
    FIGI = "FIGI"
    COMPOSITE_FIGI = "COMPOSITE_FIGI"
    SHARE_CLASS_FIGI = "SHARE_CLASS_FIGI"
    TICKER = "TICKER"
    EXCHANGE_TICKER = "EXCHANGE_TICKER"


class CouponType(str, Enum):
    FIXED = "FIXED"
    FLOATING = "FLOATING"
    ZERO = "ZERO"
    STEP_UP = "STEP_UP"


class DayCountConvention(str, Enum):
    ACT_360 = "ACT_360"
    THIRTY_360 = "30_360"
    ACT_ACT = "ACT_ACT"


class Seniority(str, Enum):
    SENIOR_SECURED = "SENIOR_SECURED"
    SENIOR_UNSECURED = "SENIOR_UNSECURED"
    SUBORDINATED = "SUBORDINATED"
    JUNIOR_SUBORDINATED = "JUNIOR_SUBORDINATED"


class Frequency(str, Enum):
    ANNUAL = "ANNUAL"
    SEMI_ANNUAL = "SEMI_ANNUAL"
    QUARTERLY = "QUARTERLY"
    MONTHLY = "MONTHLY"
    IRREGULAR = "IRREGULAR"


# ---------------------------------------------------------------------------
# Reference enums (Spec 10.3, 10.4)
# ---------------------------------------------------------------------------

class MarketType(str, Enum):
    STOCK = "STOCK"
    BOND = "BOND"
    COMMODITY = "COMMODITY"
    DERIVATIVES = "DERIVATIVES"


class ExchangeStatus(str, Enum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    MERGED = "MERGED"


class DevelopmentStatus(str, Enum):
    DEVELOPED = "DEVELOPED"
    EMERGING = "EMERGING"
    FRONTIER = "FRONTIER"


# ---------------------------------------------------------------------------
# Data quality enums (Spec 13)
# ---------------------------------------------------------------------------

class DataDomain(str, Enum):
    ENTITY = "ENTITY"
    SECURITY = "SECURITY"
    REFERENCE = "REFERENCE"
    FUNDAMENTALS = "FUNDAMENTALS"
    ESTIMATES = "ESTIMATES"
    CORPORATE_ACTIONS = "CORPORATE_ACTIONS"
    OWNERSHIP = "OWNERSHIP"
    MACRO = "MACRO"
    ESG = "ESG"
    RELATIONSHIPS = "RELATIONSHIPS"


class IssueSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class IssueType(str, Enum):
    MISSING_VALUE = "MISSING_VALUE"
    INVALID_VALUE = "INVALID_VALUE"
    DUPLICATE = "DUPLICATE"
    REFERENTIAL_INTEGRITY = "REFERENTIAL_INTEGRITY"
    FORMAT_ERROR = "FORMAT_ERROR"
    BUSINESS_RULE_VIOLATION = "BUSINESS_RULE_VIOLATION"


# ---------------------------------------------------------------------------
# Governance enums (Spec 14, 15, 18)
# ---------------------------------------------------------------------------

class RevisionType(str, Enum):
    INITIAL = "INITIAL"
    AMENDMENT = "AMENDMENT"
    RESTATEMENT = "RESTATEMENT"
    CORRECTION = "CORRECTION"


class ConnectorType(str, Enum):
    BATCH_API = "BATCH_API"
    BATCH_FILE = "BATCH_FILE"
    SCHEDULED_PULL = "SCHEDULED_PULL"


class ValidationStatus(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class DataSensitivity(str, Enum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"


class ResolutionStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CREATED_NEW = "CREATED_NEW"


# ---------------------------------------------------------------------------
# Macroeconomic enums (Spec 9.2, 9.3)
# ---------------------------------------------------------------------------

class MacroCategory(str, Enum):
    PRICES = "PRICES"
    LABOR = "LABOR"
    GDP = "GDP"
    RATES = "RATES"
    HOUSING = "HOUSING"
    CONSUMER = "CONSUMER"
    MANUFACTURING = "MANUFACTURING"
    TRADE = "TRADE"
    MONEY_SUPPLY = "MONEY_SUPPLY"
    FISCAL = "FISCAL"
    OTHER = "OTHER"


class MacroFrequency(str, Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    SEMI_ANNUAL = "SEMI_ANNUAL"
    ANNUAL = "ANNUAL"


class SeasonalAdjustment(str, Enum):
    SA = "SA"
    NSA = "NSA"
    SAAR = "SAAR"


class MacroTransformation(str, Enum):
    LEVEL = "LEVEL"
    YOY = "YOY"
    MOM = "MOM"
    QOQ = "QOQ"
    ANNUALIZED = "ANNUALIZED"
    INDEX = "INDEX"


class RateDirection(str, Enum):
    HIKE = "HIKE"
    CUT = "CUT"
    HOLD = "HOLD"


class GuidanceTone(str, Enum):
    HAWKISH = "HAWKISH"
    NEUTRAL = "NEUTRAL"
    DOVISH = "DOVISH"
    MIXED = "MIXED"


class CentralBank(str, Enum):
    FED = "FED"
    ECB = "ECB"
    BOJ = "BOJ"
    BOE = "BOE"
    PBOC = "PBOC"
    RBA = "RBA"
    BOC = "BOC"
    SNB = "SNB"
    RBNZ = "RBNZ"
    RBI = "RBI"


# ---------------------------------------------------------------------------
# Fundamentals enums (Spec 5.2, 5.3)
# ---------------------------------------------------------------------------

class FilingType(str, Enum):
    TEN_K = "10-K"
    TEN_Q = "10-Q"
    EIGHT_K = "8-K"
    TWENTY_F = "20-F"
    SIX_K = "6-K"
    TEN_K_A = "10-K/A"
    TEN_Q_A = "10-Q/A"
    DEF_14A = "DEF_14A"
    S_1 = "S-1"
    ANNUAL_REPORT = "ANNUAL_REPORT"


class PeriodType(str, Enum):
    ANNUAL = "ANNUAL"
    QUARTERLY = "QUARTERLY"
    SEMI_ANNUAL = "SEMI_ANNUAL"
    TTM = "TTM"
    YTD = "YTD"
    LTM = "LTM"


class ProcessingStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"
    REPROCESSING = "REPROCESSING"


class DataVersion(str, Enum):
    AS_REPORTED = "AS_REPORTED"
    STANDARDIZED = "STANDARDIZED"
    ADJUSTED = "ADJUSTED"


class AuditOpinion(str, Enum):
    UNQUALIFIED = "UNQUALIFIED"
    QUALIFIED = "QUALIFIED"
    ADVERSE = "ADVERSE"
    DISCLAIMER = "DISCLAIMER"
    GOING_CONCERN = "GOING_CONCERN"


class SegmentType(str, Enum):
    BUSINESS = "BUSINESS"
    GEOGRAPHIC = "GEOGRAPHIC"
    PRODUCT = "PRODUCT"


# ---------------------------------------------------------------------------
# Corporate Actions enums (Spec 7.2, 7.3)
# ---------------------------------------------------------------------------

class CorporateActionType(str, Enum):
    CASH_DIVIDEND = "CASH_DIVIDEND"
    STOCK_DIVIDEND = "STOCK_DIVIDEND"
    STOCK_SPLIT = "STOCK_SPLIT"
    REVERSE_SPLIT = "REVERSE_SPLIT"
    MERGER = "MERGER"
    ACQUISITION = "ACQUISITION"
    TENDER_OFFER = "TENDER_OFFER"
    SPIN_OFF = "SPIN_OFF"
    RIGHTS_ISSUE = "RIGHTS_ISSUE"
    SHARE_BUYBACK = "SHARE_BUYBACK"
    NAME_CHANGE = "NAME_CHANGE"
    DELISTING = "DELISTING"
    RELISTING = "RELISTING"
    SPECIAL_DISTRIBUTION = "SPECIAL_DISTRIBUTION"


class DividendType(str, Enum):
    REGULAR = "REGULAR"
    SPECIAL = "SPECIAL"
    LIQUIDATING = "LIQUIDATING"
    RETURN_OF_CAPITAL = "RETURN_OF_CAPITAL"


class ActionStatus(str, Enum):
    ANNOUNCED = "ANNOUNCED"
    CONFIRMED = "CONFIRMED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    WITHDRAWN = "WITHDRAWN"


class ConsiderationType(str, Enum):
    ALL_CASH = "ALL_CASH"
    ALL_STOCK = "ALL_STOCK"
    MIXED = "MIXED"


class MAType(str, Enum):
    MERGER = "MERGER"
    ACQUISITION = "ACQUISITION"
    TENDER = "TENDER"
    GOING_PRIVATE = "GOING_PRIVATE"
    REVERSE_MERGER = "REVERSE_MERGER"


# ---------------------------------------------------------------------------
# Estimates enums (Spec 6.2, 6.3)
# ---------------------------------------------------------------------------

class EstimateMetric(str, Enum):
    EPS = "EPS"
    EPS_GAAP = "EPS_GAAP"
    REVENUE = "REVENUE"
    EBITDA = "EBITDA"
    EBIT = "EBIT"
    NET_INCOME = "NET_INCOME"
    FCF = "FCF"
    DPS = "DPS"
    BV = "BV"
    CAPEX = "CAPEX"
    GROSS_MARGIN = "GROSS_MARGIN"
    OPERATING_MARGIN = "OPERATING_MARGIN"
    NAV = "NAV"


class Recommendation(str, Enum):
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    OVERWEIGHT = "OVERWEIGHT"
    HOLD = "HOLD"
    UNDERWEIGHT = "UNDERWEIGHT"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"


class GuidanceType(str, Enum):
    POINT = "POINT"
    RANGE = "RANGE"
    QUALITATIVE = "QUALITATIVE"


class EstimateRevisionDirection(str, Enum):
    RAISED = "RAISED"
    LOWERED = "LOWERED"
    NARROWED = "NARROWED"
    WIDENED = "WIDENED"
    MAINTAINED = "MAINTAINED"
    WITHDRAWN = "WITHDRAWN"


# ---------------------------------------------------------------------------
# Ownership enums (Spec 8.2, 8.3)
# ---------------------------------------------------------------------------

class InstitutionType(str, Enum):
    PASSIVE_INDEX = "PASSIVE_INDEX"
    ACTIVE_MUTUAL_FUND = "ACTIVE_MUTUAL_FUND"
    HEDGE_FUND = "HEDGE_FUND"
    PENSION_FUND = "PENSION_FUND"
    SOVEREIGN_WEALTH = "SOVEREIGN_WEALTH"
    INSURANCE_COMPANY = "INSURANCE_COMPANY"
    BANK_ASSET_MANAGER = "BANK_ASSET_MANAGER"
    FAMILY_OFFICE = "FAMILY_OFFICE"
    ENDOWMENT = "ENDOWMENT"
    VENTURE_CAPITAL = "VENTURE_CAPITAL"
    PRIVATE_EQUITY = "PRIVATE_EQUITY"
    OTHER = "OTHER"


class InstitutionTier(str, Enum):
    WHALE = "WHALE"
    MAJOR = "MAJOR"
    NOTABLE = "NOTABLE"
    SMALL = "SMALL"


class InsiderTransactionType(str, Enum):
    PURCHASE = "PURCHASE"
    SALE = "SALE"
    GRANT = "GRANT"
    EXERCISE = "EXERCISE"
    GIFT = "GIFT"
    CONVERSION = "CONVERSION"
    DISPOSITION = "DISPOSITION"


class OwnershipNature(str, Enum):
    DIRECT = "DIRECT"
    INDIRECT = "INDIRECT"


# ---------------------------------------------------------------------------
# ESG enums (Spec 11.2, 11.3)
# ---------------------------------------------------------------------------

class ESGProvider(str, Enum):
    MSCI = "MSCI"
    SUSTAINALYTICS = "SUSTAINALYTICS"
    REFINITIV = "REFINITIV"
    ISS = "ISS"
    SP_GLOBAL = "SP_GLOBAL"
    BLOOMBERG = "BLOOMBERG"
    CDP = "CDP"
    INTERNAL = "INTERNAL"


class ESGCategory(str, Enum):
    ENVIRONMENTAL = "ENVIRONMENTAL"
    SOCIAL = "SOCIAL"
    GOVERNANCE = "GOVERNANCE"


class ControversyLevel(str, Enum):
    SEVERE = "SEVERE"
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"
    NONE = "NONE"


class ControversyStatus(str, Enum):
    ONGOING = "ONGOING"
    RESOLVED = "RESOLVED"
    ESCALATING = "ESCALATING"


# ---------------------------------------------------------------------------
# Business Relationships enums (Spec 12.2, 12.3)
# ---------------------------------------------------------------------------

class BusinessRelationshipType(str, Enum):
    MAJOR_CUSTOMER = "MAJOR_CUSTOMER"
    SIGNIFICANT_CUSTOMER = "SIGNIFICANT_CUSTOMER"
    KNOWN_CUSTOMER = "KNOWN_CUSTOMER"
    CRITICAL_SUPPLIER = "CRITICAL_SUPPLIER"
    MAJOR_SUPPLIER = "MAJOR_SUPPLIER"
    KNOWN_SUPPLIER = "KNOWN_SUPPLIER"
    DISTRIBUTOR = "DISTRIBUTOR"
    DIRECT_COMPETITOR = "DIRECT_COMPETITOR"
    INDIRECT_COMPETITOR = "INDIRECT_COMPETITOR"
    JOINT_VENTURE = "JOINT_VENTURE"
    STRATEGIC_ALLIANCE = "STRATEGIC_ALLIANCE"
    LICENSING_PARTNER = "LICENSING_PARTNER"


class RelationshipDirection(str, Enum):
    OUTBOUND = "OUTBOUND"
    INBOUND = "INBOUND"
    BIDIRECTIONAL = "BIDIRECTIONAL"


class ExtractionMethod(str, Enum):
    MANUAL = "MANUAL"
    NLP_EXTRACTED = "NLP_EXTRACTED"
    VENDOR = "VENDOR"
    SEC_FILING = "SEC_FILING"
    PUBLIC_ANNOUNCEMENT = "PUBLIC_ANNOUNCEMENT"


# ---------------------------------------------------------------------------
# Analytics Engine enums (Pillar 2 Spec §1-§4)
# ---------------------------------------------------------------------------

class RatioCategory(str, Enum):
    PROFITABILITY = "PROFITABILITY"
    LEVERAGE = "LEVERAGE"
    EFFICIENCY = "EFFICIENCY"
    GROWTH = "GROWTH"
    VALUATION = "VALUATION"
    PER_SHARE = "PER_SHARE"
    LIQUIDITY = "LIQUIDITY"
    CASH_FLOW = "CASH_FLOW"
    CAPITAL_ALLOCATION = "CAPITAL_ALLOCATION"
    DIVIDEND = "DIVIDEND"
    DUPONT = "DUPONT"
    INDUSTRY_KPI = "INDUSTRY_KPI"


class TrendDirection(str, Enum):
    IMPROVING = "IMPROVING"
    DETERIORATING = "DETERIORATING"
    STABLE = "STABLE"


class TrendConsistency(str, Enum):
    HIGHLY_CONSISTENT = "HIGHLY_CONSISTENT"
    MODERATE = "MODERATE"
    VOLATILE = "VOLATILE"


class DataQualityFlag(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    ESTIMATED = "ESTIMATED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class ValuationMultiple(str, Enum):
    PE_TRAILING = "PE_TRAILING"
    PE_FORWARD = "PE_FORWARD"
    EV_EBITDA = "EV_EBITDA"
    EV_EBIT = "EV_EBIT"
    EV_SALES = "EV_SALES"
    EV_FCF = "EV_FCF"
    PB = "PB"
    P_TBV = "P_TBV"
    PEG = "PEG"
    PS = "PS"
    DIVIDEND_YIELD = "DIVIDEND_YIELD"


class WACCComponent(str, Enum):
    RISK_FREE_RATE = "RISK_FREE_RATE"
    EQUITY_RISK_PREMIUM = "EQUITY_RISK_PREMIUM"
    BETA = "BETA"
    SIZE_PREMIUM = "SIZE_PREMIUM"
    COUNTRY_PREMIUM = "COUNTRY_PREMIUM"
    COST_OF_DEBT = "COST_OF_DEBT"
    TAX_RATE = "TAX_RATE"


class DuPontModel(str, Enum):
    THREE_FACTOR = "THREE_FACTOR"
    FIVE_FACTOR = "FIVE_FACTOR"


class TTMMethod(str, Enum):
    SUM_4Q = "SUM_4Q"
    LATEST_ANNUAL = "LATEST_ANNUAL"
    ANNUALIZED = "ANNUALIZED"


class DCFMethod(str, Enum):
    FCFF = "FCFF"
    FCFE = "FCFE"


class TerminalValueMethod(str, Enum):
    GORDON_GROWTH = "GORDON_GROWTH"
    EXIT_MULTIPLE = "EXIT_MULTIPLE"


class CompositeScoreType(str, Enum):
    EARNINGS_QUALITY = "EARNINGS_QUALITY"
    FINANCIAL_STRENGTH = "FINANCIAL_STRENGTH"
    DIVIDEND_SAFETY = "DIVIDEND_SAFETY"
    VALUE_TRAP = "VALUE_TRAP"
    CAPITAL_ALLOCATION = "CAPITAL_ALLOCATION"


class DividendSafetyZone(str, Enum):
    SAFE = "SAFE"
    BORDERLINE = "BORDERLINE"
    AT_RISK = "AT_RISK"
    DANGEROUS = "DANGEROUS"


class ValueTrapRisk(str, Enum):
    LOW_RISK = "LOW_RISK"
    MODERATE_RISK = "MODERATE_RISK"
    HIGH_RISK = "HIGH_RISK"
    VALUE_TRAP_WARNING = "VALUE_TRAP_WARNING"


# ---------------------------------------------------------------------------
# Risk Analytics enums (Pillar 2 Spec §7)
# ---------------------------------------------------------------------------

class VaRMethod(str, Enum):
    HISTORICAL = "HISTORICAL"
    PARAMETRIC = "PARAMETRIC"
    MONTE_CARLO = "MONTE_CARLO"


class VaRConfidence(str, Enum):
    P95 = "95"
    P99 = "99"


class StressScenarioType(str, Enum):
    HISTORICAL = "HISTORICAL"
    HYPOTHETICAL = "HYPOTHETICAL"


class RiskFactor(str, Enum):
    VALUE = "VALUE"
    SIZE = "SIZE"
    MOMENTUM = "MOMENTUM"
    QUALITY = "QUALITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"
    GROWTH = "GROWTH"
    DIVIDEND_YIELD = "DIVIDEND_YIELD"


# ---------------------------------------------------------------------------
# Quantitative Analytics enums (Pillar 2 Spec §9)
# ---------------------------------------------------------------------------

class RegressionMethod(str, Enum):
    OLS = "OLS"
    ROBUST_HUBER = "ROBUST_HUBER"
    THEIL_SEN = "THEIL_SEN"


class CorrelationMethod(str, Enum):
    PEARSON = "PEARSON"
    SPEARMAN = "SPEARMAN"
    KENDALL = "KENDALL"


class StationarityTest(str, Enum):
    ADF = "ADF"
    KPSS = "KPSS"


class ScenarioType(str, Enum):
    SENSITIVITY_2D = "SENSITIVITY_2D"
    SENSITIVITY_3D = "SENSITIVITY_3D"
    TORNADO = "TORNADO"
    SHOCK = "SHOCK"
    BREAKEVEN = "BREAKEVEN"


class SensitivityVariable(str, Enum):
    REVENUE_GROWTH = "revenue_growth"
    EBIT_MARGIN = "ebit_margin"
    DISCOUNT_RATE = "discount_rate"
    TERMINAL_GROWTH = "terminal_growth"
    TAX_RATE = "tax_rate"
    CAPEX_TO_REVENUE = "capex_to_revenue"
    DNA_TO_REVENUE = "dna_to_revenue"
    WC_TO_REVENUE = "wc_to_revenue"


# ---------------------------------------------------------------------------
# Pillar 1 Supplement — Capital Structure enums
# ---------------------------------------------------------------------------

class InstrumentType(str, Enum):
    """Debt instrument classification (CAST)."""
    SENIOR_SECURED_NOTES = "SENIOR_SECURED_NOTES"
    SENIOR_UNSECURED_NOTES = "SENIOR_UNSECURED_NOTES"
    SUBORDINATED_NOTES = "SUBORDINATED_NOTES"
    CONVERTIBLE_NOTES = "CONVERTIBLE_NOTES"
    REVOLVING_CREDIT_FACILITY = "REVOLVING_CREDIT_FACILITY"
    TERM_LOAN_A = "TERM_LOAN_A"
    TERM_LOAN_B = "TERM_LOAN_B"
    CAPITAL_LEASE_OBLIGATION = "CAPITAL_LEASE_OBLIGATION"
    FINANCE_LEASE = "FINANCE_LEASE"
    COMMERCIAL_PAPER = "COMMERCIAL_PAPER"
    PREFERRED_STOCK = "PREFERRED_STOCK"
    OTHER = "OTHER"


class CouponType(str, Enum):
    """Coupon payment type for debt instruments."""
    FIXED = "FIXED"
    FLOATING = "FLOATING"
    ZERO = "ZERO"


class SeniorityType(str, Enum):
    """Debt seniority/priority ranking."""
    SUPER_SENIOR = "SUPER_SENIOR"
    SENIOR_SECURED = "SENIOR_SECURED"
    SENIOR_UNSECURED = "SENIOR_UNSECURED"
    SENIOR_SUBORDINATED = "SENIOR_SUBORDINATED"
    SUBORDINATED = "SUBORDINATED"
    JUNIOR_SUBORDINATED = "JUNIOR_SUBORDINATED"


# ---------------------------------------------------------------------------
# Pillar 1 Supplement — Credit Rating enums
# ---------------------------------------------------------------------------

class RatingAgency(str, Enum):
    """Credit rating agencies."""
    SP = "SP"
    MOODYS = "MOODYS"
    FITCH = "FITCH"


class RatingType(str, Enum):
    """Type of credit rating."""
    LONG_TERM = "LONG_TERM"
    SHORT_TERM = "SHORT_TERM"
    OUTLOOK = "OUTLOOK"


class RatingDirection(str, Enum):
    """Direction of a rating change."""
    UPGRADE = "UPGRADE"
    DOWNGRADE = "DOWNGRADE"
    AFFIRM = "AFFIRM"
    INITIATED = "INITIATED"
    WITHDRAWN = "WITHDRAWN"


class RatingOutlook(str, Enum):
    """Rating outlook assessment."""
    POSITIVE = "POSITIVE"
    STABLE = "STABLE"
    NEGATIVE = "NEGATIVE"
    DEVELOPING = "DEVELOPING"


# ---------------------------------------------------------------------------
# Pillar 1 Supplement — Calendar enums
# ---------------------------------------------------------------------------

class CalendarEventType(str, Enum):
    """Corporate actions calendar event types."""
    DIVIDEND_EX_DATE = "DIVIDEND_EX_DATE"
    DIVIDEND_RECORD_DATE = "DIVIDEND_RECORD_DATE"
    DIVIDEND_PAYMENT_DATE = "DIVIDEND_PAYMENT_DATE"
    STOCK_SPLIT = "STOCK_SPLIT"
    REVERSE_SPLIT = "REVERSE_SPLIT"
    MERGER_VOTE = "MERGER_VOTE"
    MERGER_CLOSE = "MERGER_CLOSE"
    SPINOFF_RECORD = "SPINOFF_RECORD"
    SPINOFF_DISTRIBUTION = "SPINOFF_DISTRIBUTION"
    TENDER_OFFER_EXPIRATION = "TENDER_OFFER_EXPIRATION"
    RIGHTS_ISSUE_EXPIRATION = "RIGHTS_ISSUE_EXPIRATION"
    EARNINGS_ANNOUNCEMENT = "EARNINGS_ANNOUNCEMENT"
    SHAREHOLDER_MEETING = "SHAREHOLDER_MEETING"
    ANALYST_DAY = "ANALYST_DAY"


# ---------------------------------------------------------------------------
# Pillar 1 Supplement – Part 2: Yield Curve / Central Bank / Money Market
# ---------------------------------------------------------------------------


class CurveType(str, Enum):
    """Type of yield curve."""
    TREASURY_NOMINAL = "TREASURY_NOMINAL"
    TREASURY_REAL = "TREASURY_REAL"
    SWAP = "SWAP"
    TIPS = "TIPS"


class MeetingType(str, Enum):
    """Type of central bank meeting."""
    SCHEDULED = "SCHEDULED"
    UNSCHEDULED = "UNSCHEDULED"


class RateDecision(str, Enum):
    """Central bank rate decision."""
    HIKE = "HIKE"
    CUT = "CUT"
    HOLD = "HOLD"


class MoneyMarketRateType(str, Enum):
    """Money market rate identifier."""
    SOFR = "SOFR"
    FED_FUNDS_EFFECTIVE = "FED_FUNDS_EFFECTIVE"
    FED_FUNDS_TARGET = "FED_FUNDS_TARGET"
    TBILL_3M = "TBILL_3M"
    TBILL_6M = "TBILL_6M"
    TBILL_1Y = "TBILL_1Y"
    COMMERCIAL_PAPER_FIN = "COMMERCIAL_PAPER_FIN"
    COMMERCIAL_PAPER_NONFIN = "COMMERCIAL_PAPER_NONFIN"
    PRIME = "PRIME"


# ---------------------------------------------------------------------------
# Pillar 1 Supplement – Part 3: M&A / IPO / Earnings Intelligence
# ---------------------------------------------------------------------------


class DealType(str, Enum):
    """M&A deal type."""
    ACQUISITION = "ACQUISITION"
    MERGER_OF_EQUALS = "MERGER_OF_EQUALS"
    LEVERAGED_BUYOUT = "LEVERAGED_BUYOUT"
    MANAGEMENT_BUYOUT = "MANAGEMENT_BUYOUT"
    SPINOFF = "SPINOFF"
    DIVESTITURE = "DIVESTITURE"
    TENDER_OFFER = "TENDER_OFFER"
    GOING_PRIVATE = "GOING_PRIVATE"
    ASSET_PURCHASE = "ASSET_PURCHASE"


class DealStatus(str, Enum):
    """M&A deal status."""
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    TERMINATED = "TERMINATED"
    WITHDRAWN = "WITHDRAWN"


class PaymentType(str, Enum):
    """M&A payment type."""
    CASH = "CASH"
    STOCK = "STOCK"
    MIXED = "MIXED"


class IPOStatus(str, Enum):
    """IPO lifecycle status."""
    FILED = "FILED"
    AMENDED = "AMENDED"
    PRICED = "PRICED"
    TRADING = "TRADING"
    WITHDRAWN = "WITHDRAWN"


class GuidanceType(str, Enum):
    """Corporate guidance type."""
    INITIAL = "INITIAL"
    RAISED = "RAISED"
    LOWERED = "LOWERED"
    MAINTAINED = "MAINTAINED"
    WITHDRAWN = "WITHDRAWN"


class GuidanceVsConsensus(str, Enum):
    """Guidance vs. consensus comparison."""
    ABOVE = "ABOVE"
    INLINE = "INLINE"
    BELOW = "BELOW"


# ---------------------------------------------------------------------------
# Pillar 1 Supplement – Part 4: Fund Holdings / Executives
# ---------------------------------------------------------------------------


class FundType(str, Enum):
    """Investment fund type."""
    ETF = "ETF"
    MUTUAL_FUND = "MUTUAL_FUND"
    CLOSED_END = "CLOSED_END"
    INTERVAL = "INTERVAL"


class FundAssetType(str, Enum):
    """Asset type within fund holdings."""
    EQUITY = "EQUITY"
    DEBT = "DEBT"
    DERIVATIVE = "DERIVATIVE"
    CASH = "CASH"
    OTHER = "OTHER"


class IssuerCategory(str, Enum):
    """Issuer category for fund holdings."""
    CORPORATE = "CORPORATE"
    GOVERNMENT = "GOVERNMENT"
    AGENCY = "AGENCY"
    MUNICIPAL = "MUNICIPAL"


class RoleType(str, Enum):
    """Executive/director role type."""
    EXECUTIVE = "EXECUTIVE"
    DIRECTOR = "DIRECTOR"
    BOTH = "BOTH"


# ---------------------------------------------------------------------------
# Part 5 — Technical Studies, Custom Classifications, ESG Temperature
# ---------------------------------------------------------------------------

class TechnicalIndicator(str, Enum):
    """Technical analysis indicator names."""
    RSI = "RSI"
    MACD = "MACD"
    MACD_SIGNAL = "MACD_SIGNAL"
    MACD_HISTOGRAM = "MACD_HISTOGRAM"
    BOLLINGER_UPPER = "BOLLINGER_UPPER"
    BOLLINGER_MIDDLE = "BOLLINGER_MIDDLE"
    BOLLINGER_LOWER = "BOLLINGER_LOWER"
    SMA_50 = "SMA_50"
    SMA_200 = "SMA_200"
    EMA_20 = "EMA_20"
    VWAP = "VWAP"
    STOCHASTIC_K = "STOCHASTIC_K"
    STOCHASTIC_D = "STOCHASTIC_D"
    ATR = "ATR"
    OBV = "OBV"


class IndicatorCategory(str, Enum):
    """Category grouping for technical indicators."""
    MOMENTUM = "MOMENTUM"
    TREND = "TREND"
    VOLATILITY = "VOLATILITY"
    VOLUME = "VOLUME"


class ClassificationVisibility(str, Enum):
    """Visibility scope for custom classifications."""
    PRIVATE = "PRIVATE"
    SHARED = "SHARED"


class TemperatureAlignment(str, Enum):
    """Paris Agreement temperature alignment buckets."""
    BELOW_1_5C = "BELOW_1_5C"
    BETWEEN_1_5_AND_2C = "BETWEEN_1_5_AND_2C"
    BETWEEN_2_AND_3C = "BETWEEN_2_AND_3C"
    ABOVE_3C = "ABOVE_3C"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


# ---------------------------------------------------------------------------
# Pillar 2 Supplement — Yield Curve Analytics (Part 1)
# ---------------------------------------------------------------------------

class InterpolationMethod(str, Enum):
    """Yield curve interpolation method."""
    LINEAR = "LINEAR"
    CUBIC_SPLINE = "CUBIC_SPLINE"
    NELSON_SIEGEL = "NELSON_SIEGEL"


class CurveShiftType(str, Enum):
    """Yield curve scenario shift type."""
    PARALLEL = "PARALLEL"
    STEEPENER = "STEEPENER"
    FLATTENER = "FLATTENER"
    CUSTOM = "CUSTOM"


class CurveAnalyticType(str, Enum):
    """Yield curve analytic metric type."""
    SPREAD_2S10S = "SPREAD_2S10S"
    SPREAD_3M10Y = "SPREAD_3M10Y"
    STEEPNESS = "STEEPNESS"
    CURVATURE = "CURVATURE"
    BREAKEVEN_INFLATION = "BREAKEVEN_INFLATION"


# ---------------------------------------------------------------------------
# Pillar 2 Supplement — Default Risk Scoring (Part 2)
# ---------------------------------------------------------------------------

class CreditScoreZone(str, Enum):
    """Credit risk zone classification."""
    INVESTMENT_GRADE = "INVESTMENT_GRADE"
    CROSSOVER = "CROSSOVER"
    HIGH_YIELD = "HIGH_YIELD"
    DISTRESSED = "DISTRESSED"


class ImpliedRating(str, Enum):
    """Credit rating mapped from composite score."""
    AAA = "AAA"
    AA_PLUS = "AA+"
    AA = "AA"
    AA_MINUS = "AA-"
    A_PLUS = "A+"
    A = "A"
    A_MINUS = "A-"
    BBB_PLUS = "BBB+"
    BBB = "BBB"
    BBB_MINUS = "BBB-"
    BB_PLUS = "BB+"
    BB = "BB"
    BB_MINUS = "BB-"
    B_PLUS = "B+"
    B = "B"
    B_MINUS = "B-"
    CCC = "CCC"
    CC = "CC"
    C = "C"
    D = "D"


class DefaultRiskModel(str, Enum):
    """Default risk model type."""
    ALTMAN_Z = "ALTMAN_Z"
    MERTON_DD = "MERTON_DD"
    COMPOSITE = "COMPOSITE"


# ---------------------------------------------------------------------------
# Pillar 2 Supplement — Equity Strategy Backtester (Part 3)
# ---------------------------------------------------------------------------

class BacktestStatus(str, Enum):
    """Backtest run status."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class WeightingMethod(str, Enum):
    """Portfolio weighting method."""
    EQUAL = "EQUAL"
    MARKET_CAP = "MARKET_CAP"
    SCORE_BASED = "SCORE_BASED"
    CUSTOM = "CUSTOM"


class RebalanceFrequency(str, Enum):
    """Portfolio rebalance frequency."""
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    SEMI_ANNUAL = "SEMI_ANNUAL"
    ANNUAL = "ANNUAL"


class BenchmarkType(str, Enum):
    """Benchmark for backtest comparison."""
    SP500 = "SP500"
    RUSSELL_1000 = "RUSSELL_1000"
    RUSSELL_2000 = "RUSSELL_2000"
    EQUAL_WEIGHT_UNIVERSE = "EQUAL_WEIGHT_UNIVERSE"
    CUSTOM = "CUSTOM"


# ---------------------------------------------------------------------------
# Pillar 2 Supplement — Custom Index + Portfolio Upload (Part 4)
# ---------------------------------------------------------------------------

class IndexStatus(str, Enum):
    """Custom index status."""
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    ARCHIVED = "ARCHIVED"


class UploadFormat(str, Enum):
    """Portfolio upload file format."""
    CSV = "CSV"
    EXCEL = "EXCEL"


class UploadStatus(str, Enum):
    """Portfolio upload processing status."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"


class UploadMappingStatus(str, Enum):
    """Individual holding mapping status."""
    MATCHED = "MATCHED"
    AMBIGUOUS = "AMBIGUOUS"
    NOT_FOUND = "NOT_FOUND"


# ---------------------------------------------------------------------------
# Pillar 2 Supplement — Security Finder, Events Calendar, Market Movers (Part 5)
# ---------------------------------------------------------------------------

class SecurityFinderSort(str, Enum):
    """Sort order for security finder."""
    RELEVANCE = "RELEVANCE"
    MARKET_CAP = "MARKET_CAP"
    NAME = "NAME"
    TICKER = "TICKER"


class MoverCategory(str, Enum):
    """Market mover category."""
    TOP_GAINERS = "TOP_GAINERS"
    TOP_LOSERS = "TOP_LOSERS"
    MOST_ACTIVE = "MOST_ACTIVE"
    FIFTY_TWO_WEEK_HIGH = "52_WEEK_HIGH"
    FIFTY_TWO_WEEK_LOW = "52_WEEK_LOW"


class EventSourceType(str, Enum):
    """Unified event source type."""
    CALENDAR_EVENT = "CALENDAR_EVENT"
    EARNINGS_ANNOUNCEMENT = "EARNINGS_ANNOUNCEMENT"
    FED_MEETING = "FED_MEETING"
    CORPORATE_ACTION = "CORPORATE_ACTION"
    IPO_EVENT = "IPO_EVENT"


# ---------------------------------------------------------------------------
# Pillar 2 Supplement — Custom Data Environment, Technical Backtester (Part 6)
# ---------------------------------------------------------------------------

class CustomFieldType(str, Enum):
    """Data type for custom computed fields."""
    NUMERIC = "NUMERIC"
    BOOLEAN = "BOOLEAN"
    STRING = "STRING"


class CustomFieldScope(str, Enum):
    """Visibility scope for custom fields."""
    PRIVATE = "PRIVATE"
    SHARED = "SHARED"


class TechnicalSignalType(str, Enum):
    """Technical trading signal types."""
    CROSSOVER_ABOVE = "CROSSOVER_ABOVE"
    CROSSOVER_BELOW = "CROSSOVER_BELOW"
    THRESHOLD_ABOVE = "THRESHOLD_ABOVE"
    THRESHOLD_BELOW = "THRESHOLD_BELOW"
    BAND_BREAKOUT = "BAND_BREAKOUT"
    BAND_BREAKDOWN = "BAND_BREAKDOWN"


# ---------------------------------------------------------------------------
# Pillar 2 Supplement — AI Company Intelligence, Company Primers (Part 7)
# ---------------------------------------------------------------------------

class BriefingType(str, Enum):
    """Type of company intelligence briefing."""
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    EVENT_DRIVEN = "EVENT_DRIVEN"


class BriefingStatus(str, Enum):
    """Status of a briefing generation."""
    PENDING = "PENDING"
    GENERATING = "GENERATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    STALE = "STALE"


class SignalSeverity(str, Enum):
    """Severity level for key signals."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


# ---------------------------------------------------------------------------
# Pillar 2 Supplement — Sentiment Analysis (Part 8)
# ---------------------------------------------------------------------------

class SentimentLabel(str, Enum):
    """Sentiment classification label."""
    POSITIVE = "POSITIVE"
    NEUTRAL = "NEUTRAL"
    NEGATIVE = "NEGATIVE"


class SentimentSource(str, Enum):
    """Source type for sentiment analysis."""
    NEWS_ARTICLE = "NEWS_ARTICLE"
    EARNINGS_CALL = "EARNINGS_CALL"
    PRESS_RELEASE = "PRESS_RELEASE"
    SEC_FILING = "SEC_FILING"


class SentimentTimeframe(str, Enum):
    """Timeframe for sentiment aggregation."""
    ROLLING_7D = "ROLLING_7D"
    ROLLING_30D = "ROLLING_30D"
    ROLLING_90D = "ROLLING_90D"
