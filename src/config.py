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

    # Polygon.io (EOD Prices)
    POLYGON_API_KEY: str = ""
    POLYGON_RATE_LIMIT: int = 5  # requests per second (free tier)

    # Estimates vendor (paid — schema-only until configured)
    ESTIMATES_VENDOR: str = ""
    ESTIMATES_API_KEY: str = ""

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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


settings = Settings()
