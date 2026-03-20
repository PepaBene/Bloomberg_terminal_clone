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
