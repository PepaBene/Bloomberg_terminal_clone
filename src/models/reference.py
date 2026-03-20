"""Domain 8: Reference & Classification Data models (Spec Section 10)."""

import uuid
from datetime import date, time

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, Text, Time
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class Country(Base):
    """ISO 3166 country reference (Spec 10.3)."""

    __tablename__ = "countries"

    country_code_alpha2: Mapped[str] = mapped_column(String(2), primary_key=True)
    country_code_alpha3: Mapped[str] = mapped_column(String(3), unique=True, nullable=False)
    country_code_numeric: Mapped[str | None] = mapped_column(String(3))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    official_name: Mapped[str | None] = mapped_column(String(200))
    capital: Mapped[str | None] = mapped_column(String(100))
    continent: Mapped[str | None] = mapped_column(String(20))
    region: Mapped[str | None] = mapped_column(String(50))
    subregion: Mapped[str | None] = mapped_column(String(80))
    currency_code: Mapped[str | None] = mapped_column(String(3), ForeignKey("currencies.currency_code"))
    languages: Mapped[dict | None] = mapped_column(JSONB)
    development_status: Mapped[str | None] = mapped_column(String(20))
    income_group: Mapped[str | None] = mapped_column(String(50))
    primary_exchange_mic: Mapped[str | None] = mapped_column(String(4))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Currency(Base):
    """ISO 4217 currency reference."""

    __tablename__ = "currencies"

    currency_code: Mapped[str] = mapped_column(String(3), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    numeric_code: Mapped[str | None] = mapped_column(String(3))
    minor_unit: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Exchange(Base):
    """ISO 10383 exchange/market reference (Spec 10.4)."""

    __tablename__ = "exchanges"

    mic: Mapped[str] = mapped_column(String(4), primary_key=True)
    operating_mic: Mapped[str | None] = mapped_column(String(4))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    acronym: Mapped[str | None] = mapped_column(String(20))
    country: Mapped[str | None] = mapped_column(String(2), ForeignKey("countries.country_code_alpha2"))
    city: Mapped[str | None] = mapped_column(String(100))
    timezone: Mapped[str | None] = mapped_column(String(50))
    market_type: Mapped[str | None] = mapped_column(String(20))
    asset_class: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str | None] = mapped_column(String(20))
    trading_hours: Mapped[dict | None] = mapped_column(JSONB)


class GICSClassification(Base):
    """GICS industry classification hierarchy (Spec 10.5)."""

    __tablename__ = "gics_classifications"

    sub_industry_code: Mapped[str] = mapped_column(String(8), primary_key=True)
    sector_code: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    sector_name: Mapped[str] = mapped_column(String(100), nullable=False)
    industry_group_code: Mapped[str] = mapped_column(String(4), nullable=False, index=True)
    industry_group_name: Mapped[str] = mapped_column(String(100), nullable=False)
    industry_code: Mapped[str] = mapped_column(String(6), nullable=False, index=True)
    industry_name: Mapped[str] = mapped_column(String(100), nullable=False)
    sub_industry_name: Mapped[str] = mapped_column(String(100), nullable=False)
    sector_description: Mapped[str | None] = mapped_column(Text)
    sub_industry_description: Mapped[str | None] = mapped_column(Text)
    effective_date: Mapped[date | None] = mapped_column(Date)
    version: Mapped[str | None] = mapped_column(String(10))


class SICCode(Base):
    """US Standard Industrial Classification codes."""

    __tablename__ = "sic_codes"

    sic_code: Mapped[str] = mapped_column(String(4), primary_key=True)
    description: Mapped[str | None] = mapped_column(String(200))
    division: Mapped[str | None] = mapped_column(String(1))
    major_group: Mapped[str | None] = mapped_column(String(2))


class NAICSCode(Base):
    """US North American Industry Classification System codes."""

    __tablename__ = "naics_codes"

    naics_code: Mapped[str] = mapped_column(String(6), primary_key=True)
    description: Mapped[str | None] = mapped_column(String(200))
    sector_code: Mapped[str | None] = mapped_column(String(2))


class SICToGICSMapping(Base):
    """Cross-walk mapping from SIC to GICS classifications."""

    __tablename__ = "sic_to_gics_mapping"

    sic_code: Mapped[str] = mapped_column(
        String(4), ForeignKey("sic_codes.sic_code"), primary_key=True
    )
    gics_sub_industry_code: Mapped[str | None] = mapped_column(
        String(8), ForeignKey("gics_classifications.sub_industry_code")
    )


class TradingCalendar(Base):
    """Exchange/country trading calendar definition (Spec 10.6)."""

    __tablename__ = "trading_calendars"

    calendar_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    calendar_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(100))
    exchange_mic: Mapped[str | None] = mapped_column(String(4), ForeignKey("exchanges.mic"))
    country: Mapped[str | None] = mapped_column(String(2), ForeignKey("countries.country_code_alpha2"))


class TradingDay(Base):
    """Individual trading day records (Spec 10.6)."""

    __tablename__ = "trading_days"

    calendar_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trading_calendars.calendar_id"), primary_key=True
    )
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    is_trading_day: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_half_day: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    open_time: Mapped[time | None] = mapped_column(Time)
    close_time: Mapped[time | None] = mapped_column(Time)
    holiday_name: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(String(200))
