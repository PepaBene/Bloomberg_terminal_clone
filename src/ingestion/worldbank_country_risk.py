"""World Bank connector: non-US global macro + composite country risk scores.

Source: World Bank Indicators API (https://api.worldbank.org/v2) — KEYLESS, no
auth, free. This is the non-FRED source the DATA_WIRING_AUDIT §6 flagged as
missing for non-US global macro and for country-risk profiles/scores.

It writes THREE tables:

* ``global_macro_indicators`` — one row per country+indicator (latest available
  observation). Matches exactly the schema written by
  ``global_intelligence.py::_ensure_us_macro_indicators`` (which populates the
  US rows from FRED); this adds the non-US countries. ``source='WORLD_BANK'``.
* ``country_profiles`` — light reference rows (code/name/region/G20) so the
  risk-ranking endpoint can show country names.
* ``country_risk_scores`` — a deterministic composite ECONOMIC risk score
  derived from the macro indicators (formula documented in
  ``_compute_country_risk``). Political / sanctions dimensions have no free
  keyless source, so they are left NULL honestly and the composite equals the
  economic score.

World Bank indicators pulled (per country, annual):
    NY.GDP.MKTP.KD.ZG  GDP growth (annual %)              -> GDP_GROWTH
    FP.CPI.TOTL.ZG     Inflation, consumer prices (%)     -> CPI
    SL.UEM.TOTL.ZS     Unemployment, total (% labor force)-> UNEMPLOYMENT
    GC.DOD.TOTL.GD.ZS  Central govt debt (% of GDP)       -> GOVT_DEBT_GDP
    BN.CAB.XOKA.GD.ZS  Current account balance (% of GDP) -> CURRENT_ACCOUNT_GDP
"""

import logging
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ingestion.base import BaseConnector
from src.ingestion.rate_limiter import RateLimiter
from src.models.country_risk import CountryProfile, CountryRiskScore
from src.models.global_macro import GlobalMacroIndicator

logger = logging.getLogger(__name__)

WB_BASE_URL = "https://api.worldbank.org/v2"

# indicator code -> (internal indicator_type, human label)
WB_INDICATORS: dict[str, tuple[str, str]] = {
    "NY.GDP.MKTP.KD.ZG": ("GDP_GROWTH", "GDP growth (annual %)"),
    "FP.CPI.TOTL.ZG": ("CPI", "Inflation, consumer prices (annual %)"),
    "SL.UEM.TOTL.ZS": ("UNEMPLOYMENT", "Unemployment, total (% of labor force)"),
    "GC.DOD.TOTL.GD.ZS": ("GOVT_DEBT_GDP", "Central government debt (% of GDP)"),
    "BN.CAB.XOKA.GD.ZS": ("CURRENT_ACCOUNT_GDP", "Current account balance (% of GDP)"),
}

# ISO2 (used in the WB URL path) -> (country_name fallback, region, is_g20)
# The canonical ISO3 code + name come from the API response; region/G20 are
# static reference facts.
COUNTRIES: dict[str, tuple[str, str, bool]] = {
    "US": ("United States", "North America", True),
    "CN": ("China", "Asia", True),
    "JP": ("Japan", "Asia", True),
    "DE": ("Germany", "Europe", True),
    "GB": ("United Kingdom", "Europe", True),
    "IN": ("India", "Asia", True),
    "FR": ("France", "Europe", True),
    "IT": ("Italy", "Europe", True),
    "BR": ("Brazil", "Latin America", True),
    "CA": ("Canada", "North America", True),
    "RU": ("Russia", "Europe", True),
    "KR": ("South Korea", "Asia", True),
    "AU": ("Australia", "Oceania", True),
    "MX": ("Mexico", "Latin America", True),
    "ID": ("Indonesia", "Asia", True),
    "TR": ("Turkey", "Europe", True),
    "SA": ("Saudi Arabia", "Middle East", True),
    "ZA": ("South Africa", "Africa", True),
}


class WorldBankCountryRiskConnector(BaseConnector):
    """Ingest non-US macro indicators + composite country-risk scores."""

    name = "World Bank Country Risk"
    connector_type = "BATCH_API"
    data_domain = "GLOBAL_MACRO"

    def __init__(
        self,
        countries: list[str] | None = None,
        start_year: int = 2015,
        end_year: int | None = None,
    ):
        self.countries = countries or list(COUNTRIES.keys())
        self.start_year = start_year
        self.end_year = end_year or date.today().year
        # World Bank has no published hard limit; be polite.
        self.rate_limiter = RateLimiter(max_requests=10, per_seconds=1.0)
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=60.0,
                headers={"User-Agent": "bloomberg-data-fabric/1.0"},
            )
        return self._client

    async def _wb_get(self, indicator: str) -> list[dict[str, Any]]:
        """Fetch one indicator for all countries across the year range.

        Returns the flat list of observation dicts (page 2 of the WB envelope).
        """
        await self.rate_limiter.acquire()
        client = await self._get_client()
        country_path = ";".join(self.countries)
        url = f"{WB_BASE_URL}/country/{country_path}/indicator/{indicator}"
        params = {
            "format": "json",
            "date": f"{self.start_year}:{self.end_year}",
            "per_page": "2000",
        }
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        payload = resp.json()
        if not isinstance(payload, list) or len(payload) < 2 or payload[1] is None:
            logger.warning("  WB: unexpected envelope for %s: %s", indicator, str(payload)[:200])
            return []
        return payload[1]

    async def extract(self) -> list[dict[str, Any]]:
        """Pull each indicator across all countries. One WB call per indicator."""
        records: list[dict[str, Any]] = []
        for indicator in WB_INDICATORS:
            try:
                obs = await self._wb_get(indicator)
                records.append({"indicator": indicator, "observations": obs})
                logger.info("  WB: %s -> %d observations", indicator, len(obs))
            except Exception as e:  # noqa: BLE001
                logger.error("  WB: failed to fetch %s: %s", indicator, e)
        return records

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Drop observations without a numeric value or an ISO3 code."""
        for rec in records:
            clean = [
                o for o in rec.get("observations", [])
                if o.get("value") is not None and o.get("countryiso3code")
            ]
            rec["observations"] = clean
        return [r for r in records if r.get("observations")]

    async def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Collapse to the latest (and prior) observation per country+indicator.

        Emits two payload sections:
          * ``macro_rows``  -> one dict per global_macro_indicators row
          * ``by_country``  -> {iso3: {indicator_type: latest_value}} for scoring
        """
        # nested: iso3 -> indicator -> list[(year, value)]
        nested: dict[str, dict[str, list[tuple[int, float]]]] = {}
        iso3_name: dict[str, str] = {}

        for rec in records:
            indicator = rec["indicator"]
            for o in rec["observations"]:
                iso3 = o["countryiso3code"]
                try:
                    year = int(o["date"])
                    val = float(o["value"])
                except (TypeError, ValueError):
                    continue
                nested.setdefault(iso3, {}).setdefault(indicator, []).append((year, val))
                name = (o.get("country") or {}).get("value")
                if name:
                    iso3_name[iso3] = name

        macro_rows: list[dict[str, Any]] = []
        by_country: dict[str, dict[str, float]] = {}

        for iso3, inds in nested.items():
            for indicator, series in inds.items():
                series.sort(key=lambda t: t[0])  # ascending by year
                latest_year, latest_val = series[-1]
                prior_val = series[-2][1] if len(series) >= 2 else None
                indicator_type, _label = WB_INDICATORS[indicator]
                macro_rows.append({
                    "country_code": iso3,
                    "indicator_type": indicator_type,
                    "period_label": str(latest_year),
                    "value": latest_val,
                    "prior_value": prior_val,
                    # WB gives an annual figure, not a statistical-release date;
                    # use period-end as an honest proxy for release_date.
                    "release_date": date(latest_year, 12, 31),
                })
                by_country.setdefault(iso3, {})[indicator_type] = latest_val

        return [{
            "macro_rows": macro_rows,
            "by_country": by_country,
            "iso3_name": iso3_name,
        }]

    # ── Deterministic country-risk formula ────────────────────────────────
    @staticmethod
    def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
        return max(lo, min(hi, x))

    @classmethod
    def _compute_country_risk(cls, ind: dict[str, float]) -> dict[str, Any] | None:
        """Composite ECONOMIC risk score in [0, 100]; higher = riskier.

        Each available indicator is mapped to a 0-100 risk sub-score via a
        clamped linear scale, then combined as a weighted mean over whichever
        sub-scores are available (weights renormalised over the present set):

          debt (GOVT_DEBT_GDP)      w=0.30  0% -> 0 risk, 150%+ -> 100
          inflation (CPI)           w=0.20  |CPI-2%| distance, 15pp -> 100
          curr. acct (CA/GDP)       w=0.20  surplus -> 0, -10% deficit -> 100
          growth (GDP_GROWTH)       w=0.20  +3% -> 0, -5% -> 100 (clamped)
          unemployment (UNEMP)      w=0.10  4% -> 0, 20% -> 100

        Returns None if no economic indicator is available for the country.
        """
        subs: dict[str, float] = {}
        weights: dict[str, float] = {}

        if (v := ind.get("GOVT_DEBT_GDP")) is not None:
            subs["debt"] = cls._clamp(v / 1.5)
            weights["debt"] = 0.30
        if (v := ind.get("CPI")) is not None:
            subs["inflation"] = cls._clamp(abs(v - 2.0) / 13.0 * 100.0)
            weights["inflation"] = 0.20
        if (v := ind.get("CURRENT_ACCOUNT_GDP")) is not None:
            subs["current_account"] = cls._clamp((-v) / 10.0 * 100.0)
            weights["current_account"] = 0.20
        if (v := ind.get("GDP_GROWTH")) is not None:
            subs["growth"] = cls._clamp((3.0 - v) / 8.0 * 100.0)
            weights["growth"] = 0.20
        if (v := ind.get("UNEMPLOYMENT")) is not None:
            subs["unemployment"] = cls._clamp((v - 4.0) / 16.0 * 100.0)
            weights["unemployment"] = 0.10

        if not subs:
            return None

        total_w = sum(weights.values())
        composite = sum(subs[k] * weights[k] for k in subs) / total_w

        if composite < 25:
            classification = "LOW"
        elif composite < 50:
            classification = "MODERATE"
        elif composite < 75:
            classification = "ELEVATED"
        else:
            classification = "HIGH"

        components = {
            "sub_scores": {k: round(v, 2) for k, v in subs.items()},
            "weights": weights,
            "inputs": {k: round(v, 4) for k, v in ind.items()},
            "formula": "clamped linear per-indicator risk, weighted mean over available subs",
        }
        return {
            "economic_risk_score": round(composite, 2),
            "composite_risk_score": round(composite, 2),
            "risk_classification": classification,
            "economic_components": components,
        }

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        """Upsert country profiles, macro indicator rows, and risk scores."""
        stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}
        if not records:
            return stats
        payload = records[0]
        macro_rows = payload["macro_rows"]
        by_country = payload["by_country"]
        iso3_name = payload["iso3_name"]
        today = date.today()

        # ISO2 static facts keyed by name so we can attach region/G20 to ISO3.
        name_to_meta = {name: (region, g20) for name, region, g20 in COUNTRIES.values()}

        # 1) Country profiles (light reference rows).
        for iso3, name in iso3_name.items():
            region, g20 = name_to_meta.get(name, (None, False))
            existing = (
                await session.execute(
                    select(CountryProfile).where(CountryProfile.country_code == iso3)
                )
            ).scalar_one_or_none()
            if existing is None:
                session.add(CountryProfile(
                    id=uuid.uuid4(), country_code=iso3, country_name=name,
                    region=region, is_g20=g20,
                ))
                stats["inserted"] += 1
            else:
                existing.country_name = name
                if region:
                    existing.region = region
                existing.is_g20 = g20
                stats["updated"] += 1

        # 2) Macro indicator rows (one per country+indicator+period).
        for row in macro_rows:
            try:
                existing = (
                    await session.execute(
                        select(GlobalMacroIndicator).where(
                            GlobalMacroIndicator.country_code == row["country_code"],
                            GlobalMacroIndicator.indicator_type == row["indicator_type"],
                            GlobalMacroIndicator.period_label == row["period_label"],
                            GlobalMacroIndicator.source == "WORLD_BANK",
                        )
                    )
                ).scalar_one_or_none()
                if existing is not None:
                    existing.value = Decimal(str(round(row["value"], 4)))
                    existing.prior_value = (
                        Decimal(str(round(row["prior_value"], 4)))
                        if row["prior_value"] is not None else None
                    )
                    existing.release_date = row["release_date"]
                    stats["updated"] += 1
                    continue
                session.add(GlobalMacroIndicator(
                    id=uuid.uuid4(),
                    country_code=row["country_code"],
                    indicator_type=row["indicator_type"],
                    period_label=row["period_label"],
                    value=Decimal(str(round(row["value"], 4))),
                    prior_value=(
                        Decimal(str(round(row["prior_value"], 4)))
                        if row["prior_value"] is not None else None
                    ),
                    forecast_value=None,  # World Bank has no forecast series.
                    source="WORLD_BANK",
                    release_date=row["release_date"],
                ))
                stats["inserted"] += 1
            except Exception as e:  # noqa: BLE001
                logger.error("  WB macro load error (%s/%s): %s",
                             row.get("country_code"), row.get("indicator_type"), e)
                stats["errors"] += 1

        # 3) Composite country-risk scores (one per country, dated today).
        for iso3, inds in by_country.items():
            risk = self._compute_country_risk(inds)
            if risk is None:
                stats["skipped"] += 1
                continue
            try:
                existing = (
                    await session.execute(
                        select(CountryRiskScore).where(
                            CountryRiskScore.country_code == iso3,
                            CountryRiskScore.as_of_date == today,
                        )
                    )
                ).scalar_one_or_none()
                if existing is not None:
                    existing.economic_risk_score = Decimal(str(risk["economic_risk_score"]))
                    existing.composite_risk_score = Decimal(str(risk["composite_risk_score"]))
                    existing.risk_classification = risk["risk_classification"]
                    existing.economic_components = risk["economic_components"]
                    stats["updated"] += 1
                    continue
                session.add(CountryRiskScore(
                    id=uuid.uuid4(),
                    country_code=iso3,
                    as_of_date=today,
                    economic_risk_score=Decimal(str(risk["economic_risk_score"])),
                    composite_risk_score=Decimal(str(risk["composite_risk_score"])),
                    risk_classification=risk["risk_classification"],
                    # No free keyless source for political / sanctions risk.
                    political_risk_score=None,
                    sanctions_risk_score=None,
                    risk_trend=None,
                    economic_components=risk["economic_components"],
                    political_components=None,
                    sanctions_components=None,
                ))
                stats["inserted"] += 1
            except Exception as e:  # noqa: BLE001
                logger.error("  WB risk load error (%s): %s", iso3, e)
                stats["errors"] += 1

        await session.flush()
        return stats

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
