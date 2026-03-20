"""Pydantic schemas for D8 Reference & Classification Data endpoints."""

from datetime import date, time

from pydantic import BaseModel


# --- Country ---
class CountryResponse(BaseModel):
    country_code_alpha2: str
    country_code_alpha3: str
    country_code_numeric: str | None = None
    name: str
    official_name: str | None = None
    capital: str | None = None
    continent: str | None = None
    region: str | None = None
    subregion: str | None = None
    currency_code: str | None = None
    languages: dict | None = None
    development_status: str | None = None
    income_group: str | None = None
    primary_exchange_mic: str | None = None
    is_active: bool

    model_config = {"from_attributes": True}


# --- Currency ---
class CurrencyResponse(BaseModel):
    currency_code: str
    name: str
    numeric_code: str | None = None
    minor_unit: int | None = None
    is_active: bool

    model_config = {"from_attributes": True}


# --- Exchange ---
class ExchangeResponse(BaseModel):
    mic: str
    operating_mic: str | None = None
    name: str
    acronym: str | None = None
    country: str | None = None
    city: str | None = None
    timezone: str | None = None
    market_type: str | None = None
    asset_class: str | None = None
    status: str | None = None
    trading_hours: dict | None = None

    model_config = {"from_attributes": True}


# --- GICS ---
class GICSResponse(BaseModel):
    sub_industry_code: str
    sector_code: str
    sector_name: str
    industry_group_code: str
    industry_group_name: str
    industry_code: str
    industry_name: str
    sub_industry_name: str
    sector_description: str | None = None
    sub_industry_description: str | None = None
    effective_date: date | None = None
    version: str | None = None

    model_config = {"from_attributes": True}


class GICSSectorResponse(BaseModel):
    sector_code: str
    sector_name: str
    sector_description: str | None = None

    model_config = {"from_attributes": True}


# --- SIC ---
class SICResponse(BaseModel):
    sic_code: str
    description: str | None = None
    division: str | None = None
    major_group: str | None = None

    model_config = {"from_attributes": True}


# --- NAICS ---
class NAICSResponse(BaseModel):
    naics_code: str
    description: str | None = None
    sector_code: str | None = None

    model_config = {"from_attributes": True}


# --- Trading Calendar ---
class TradingDayResponse(BaseModel):
    date: date
    is_trading_day: bool
    is_half_day: bool
    open_time: time | None = None
    close_time: time | None = None
    holiday_name: str | None = None
    notes: str | None = None

    model_config = {"from_attributes": True}


class IsTradingDayResponse(BaseModel):
    date: date
    calendar_code: str
    is_trading_day: bool
    is_half_day: bool = False
    holiday_name: str | None = None
