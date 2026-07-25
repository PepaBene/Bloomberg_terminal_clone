from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://bloomberg:bloomberg_dev@localhost:5432/bloomberg"
    DB_POOL_MIN: int = 10
    DB_POOL_MAX: int = 50

    # Sync database URL (for Alembic)
    @property
    def DATABASE_URL_SYNC(self) -> str:
        return self.DATABASE_URL.replace("+asyncpg", "")

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Elasticsearch
    ELASTICSEARCH_URL: str = "http://localhost:9200"

    # API
    API_V1_PREFIX: str = "/v1"
    DEFAULT_PAGE_SIZE: int = 100
    MAX_PAGE_SIZE: int = 1000

    # SEC EDGAR — override SEC_USER_AGENT in .env or environment variables
    SEC_USER_AGENT: str = "BloombergDataFabric contact@yourdomain.com"
    SEC_RATE_LIMIT: int = 10  # requests per second

    # OpenFIGI
    OPENFIGI_API_KEY: str = ""
    OPENFIGI_RATE_LIMIT: int = 25  # req/min without key, 250 with

    @property
    def openfigi_effective_rate_limit(self) -> int:
        return 250 if self.OPENFIGI_API_KEY else 25

    # FRED API (Macroeconomic data)
    FRED_API_KEY: str = ""
    FRED_RATE_LIMIT: int = 120  # requests per minute

    # Congressional trading (STOCK Act periodic transaction reports).
    # Free public, machine-readable aggregations of House/Senate disclosures.
    # Override to point at any compatible JSON feed; both feeds are optional.
    CONGRESS_HOUSE_FEED_URL: str = (
        "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions.json"
    )
    CONGRESS_SENATE_FEED_URL: str = (
        "https://senate-stock-watcher-data.s3-us-west-2.amazonaws.com/aggregate/all_transactions.json"
    )

    # Political / regulatory intelligence (all keyless, free public sources).
    # Legislative bills: GovInfo Congressional Bills RSS (keyless XML).
    GOVINFO_BILLS_FEED_URL: str = "https://www.govinfo.gov/rss/bills.xml"
    # Regulatory actions: Federal Register public API (keyless JSON).
    FEDERAL_REGISTER_API_URL: str = (
        "https://www.federalregister.gov/api/v1/documents.json"
    )
    # Sanctions: OFAC Specially Designated Nationals (SDN) list (keyless CSV).
    OFAC_SDN_CSV_URL: str = "https://www.treasury.gov/ofac/downloads/sdn.csv"

    # Polygon.io (EOD Prices)
    POLYGON_API_KEY: str = ""
    POLYGON_RATE_LIMIT: int = 5  # requests per MINUTE (free tier) -- see RateLimiter(per_seconds=60.0) call sites

    # Finnhub (Index constituents)
    FINNHUB_API_KEY: str = ""

    # Alpha Vantage (forward consensus estimates -- Finnhub's free tier 403s
    # on /stock/eps-estimate and /stock/price-target)
    ALPHA_VANTAGE_API_KEY: str = ""
    ALPHA_VANTAGE_RATE_LIMIT: int = 5  # requests per minute (free tier)

    # EPA Envirofacts (secondary ESG environmental-score input; free, no key)
    EPA_ENVIROFACTS_BASE_URL: str = "https://data.epa.gov/efservice"

    # EIA (US Energy Information Administration) -- free API key, same signup
    # model as FRED. Powers real commodity supply/demand stock-level data
    # (weekly petroleum/natural-gas/gasoline stocks) for
    # GET /global/commodities/{code}/supply-demand.
    EIA_API_KEY: str = ""
    EIA_RATE_LIMIT: int = 30  # requests per minute (documented EIA v2 default)

    # Agency (GSE) bonds -- FHLB Office of Finance publishes free CSV/XML
    # consolidated-obligation data with no formal API; override if the feed
    # URL changes.
    FHLB_OF_DATA_URL: str = ""
    AGENCY_BONDS_FEED_URL: str = ""
    AGENCY_BONDS_API_KEY: str = ""

    # Primary-market bond issuances -- no free structured feed exists;
    # AGENCY_BONDS-style configurable JSON feed as a fallback path.
    BOND_ISSUANCES_FEED_URL: str = ""
    BOND_ISSUANCES_API_KEY: str = ""

    # FINRA TRACE -- requires registered credentials (Academic/BTDS), not a
    # keyless public API. FINRA_TRACE_LOCAL_FILE points at a downloaded bulk
    # dissemination file when no live feed is configured.
    FINRA_TRACE_FEED_URL: str = ""
    FINRA_TRACE_API_KEY: str = ""
    FINRA_TRACE_LOCAL_FILE: str = ""

    # ESG controversies -- no free structured feed exists; GDELT (already
    # used for geopolitical events) is the best-effort free source.
    ESG_CONTROVERSY_FEED_URL: str = ""

    # AI Services (Claude narratives, Gemini embeddings)
    ANTHROPIC_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""

    # Object Storage (S3/MinIO for raw file storage)
    S3_ENDPOINT: str = ""
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_BUCKET: str = "bloomberg-raw"

    # JWT / Authentication
    # SECURITY: Override in .env or environment variables
    JWT_SECRET_KEY: str = "CHANGE-ME-IN-PRODUCTION-USE-32B+"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_MINUTES: int = 60

    # Analytics Engine (Pillar 2)
    ANALYTICS_DEFAULT_ERP: float = 0.055             # Equity risk premium (5.5%)
    ANALYTICS_BETA_LOOKBACK_DAYS: int = 756          # ~3 years of trading days
    ANALYTICS_BETA_BLUME_WEIGHT: float = 0.67        # Blume adjustment weight
    ANALYTICS_RISK_FREE_INDICATOR: str = "DGS10"     # FRED series for 10Y Treasury
    ANALYTICS_MARKET_BENCHMARK_TICKER: str = "SPY"   # Market proxy for beta calc

    # Cache TTLs (seconds)
    CACHE_TTL_REFERENCE: int = 3600       # 1 hour
    CACHE_TTL_ENTITY: int = 900           # 15 min
    CACHE_TTL_SECURITY: int = 900         # 15 min
    CACHE_TTL_MACRO: int = 1800           # 30 min
    CACHE_TTL_FUNDAMENTALS: int = 3600    # 1 hour
    CACHE_TTL_OWNERSHIP: int = 3600       # 1 hour
    CACHE_TTL_ESG: int = 7200             # 2 hours

    # Pillar 2 Analytics cache TTLs
    CACHE_TTL_ANALYTICS_RATIOS: int = 86400       # 24h (daily batch)
    CACHE_TTL_ANALYTICS_MULTIPLES: int = 14400    # 4h (price-sensitive)
    CACHE_TTL_ANALYTICS_WACC: int = 86400         # 24h
    CACHE_TTL_ANALYTICS_DUPONT: int = 86400       # 24h

    # CORS — comma-separated origins via env var ``ALLOWED_ORIGINS``.
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
    ]

    # Authentication enforcement: when True, every endpoint requires a
    # valid Bearer token; when False (default), routes accept anonymous
    # access via ``get_optional_user``.
    REQUIRE_AUTH: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


settings = Settings()
