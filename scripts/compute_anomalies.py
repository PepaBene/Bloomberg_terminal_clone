"""Populate detected_anomalies from real price/volume/earnings data.

The anomaly_detection_engine.py pure-computation engine (price momentum,
volume spike, earnings surprise, fundamental shift, sentiment, supply
chain, peer divergence detectors) has existed with zero callers anywhere
in the codebase -- nothing ever fed it real data and persisted a
DetectedAnomaly row, so the Research > Anomalies page (GET
/v4/research/anomalies/active) could never return anything no matter how
healthy ingestion was upstream.

This computes the two detectors that only need data already ingested at
scale (eod_prices: 6,088 securities / 2.49M rows; earnings_surprises:
18,428 rows) -- price-momentum and volume-spike anomalies from the last
90 trading days, and earnings-surprise anomalies from each entity's own
surprise history. Fundamental-shift/sentiment/supply-chain/peer-divergence
need inputs (fundamentals history, sentiment time series, supplier/
customer news, peer groups) that are either sparse or not assembled
anywhere yet -- left for a follow-up rather than run against thin data.

Idempotent: skips (entity_id, anomaly_type, anomaly_window_end) already
recorded, so safe to run on a schedule without duplicating rows.

Usage:
    python -m scripts.compute_anomalies
"""

from __future__ import annotations

import asyncio
import calendar
import json
import logging
import sys
import uuid
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from src.database import get_session_factory
from src.engines.anomaly_detection_engine import (
    detect_earnings_surprise_anomaly,
    detect_price_momentum_anomaly,
    detect_volume_spike,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("compute_anomalies")

LOOKBACK_DAYS = 90

_PRICE_SERIES_SQL = text(
    """
    SELECT s.security_id, s.issuer_entity_id, ep.price_date, ep.close, ep.volume
    FROM securities s
    JOIN eod_prices ep ON ep.security_id = s.security_id
    WHERE s.issuer_entity_id IS NOT NULL
      AND ep.price_date >= (SELECT max(price_date) FROM eod_prices) - INTERVAL '120 days'
    ORDER BY s.security_id, ep.price_date
    """
)

_SURPRISE_SQL = text(
    """
    SELECT entity_id, fiscal_year, fiscal_quarter, actual_eps, consensus_eps, eps_surprise_pct
    FROM earnings_surprises
    WHERE actual_eps IS NOT NULL AND consensus_eps IS NOT NULL
    ORDER BY entity_id, fiscal_year, fiscal_quarter
    """
)

_EXISTS_SQL = text(
    """
    SELECT 1 FROM detected_anomalies
    WHERE entity_id = :entity_id AND anomaly_type = :anomaly_type
      AND anomaly_window_end = :window_end
    LIMIT 1
    """
)

_INSERT_SQL = text(
    """
    INSERT INTO detected_anomalies (
        id, entity_id, anomaly_type, severity_score, anomaly_window_start,
        anomaly_window_end, lookback_period, observed_value, expected_value,
        z_score, percentile_rank, contextual_analysis, ai_narrative,
        recommended_actions, confidence_level, is_acknowledged
    ) VALUES (
        :id, :entity_id, :anomaly_type, :severity_score, :window_start,
        :window_end, :lookback_period, :observed_value, :expected_value,
        :z_score, :percentile_rank, CAST(:contextual_analysis AS JSONB), :ai_narrative,
        CAST(:recommended_actions AS JSONB), :confidence_level, false
    )
    """
)


def _fiscal_quarter_end(fiscal_year: int, fiscal_quarter: int) -> date:
    month = min(max(fiscal_quarter, 1), 4) * 3
    return date(fiscal_year, month, calendar.monthrange(fiscal_year, month)[1])


async def _persist(session, entity_id, anomaly_type, window_end, window_start, result) -> bool:
    exists = (
        await session.execute(
            _EXISTS_SQL,
            {"entity_id": entity_id, "anomaly_type": anomaly_type, "window_end": window_end},
        )
    ).first()
    if exists:
        return False

    ev = result.evidence
    await session.execute(
        _INSERT_SQL,
        {
            "id": uuid.uuid4(),
            "entity_id": entity_id,
            "anomaly_type": anomaly_type,
            "severity_score": round(result.severity_score, 2),
            "window_start": window_start,
            "window_end": window_end,
            "lookback_period": f"{LOOKBACK_DAYS}d",
            "observed_value": round(ev.observed_value, 4),
            "expected_value": round(ev.expected_value, 4),
            "z_score": round(ev.z_score, 4),
            "percentile_rank": round(ev.percentile_rank, 2),
            "contextual_analysis": json.dumps({
                "historical_precedent": result.context.historical_precedent,
                "estimated_impact": result.context.estimated_impact,
            }),
            "ai_narrative": result.narrative_template,
            # AnomalyResponse (src/schemas/anomaly_detection_schema.py) types
            # this column as a dict, not the list the model docstring
            # suggests -- wrap to match what the API actually validates.
            "recommended_actions": json.dumps({
                "actions": [
                    {"action": a.action, "urgency": a.urgency, "resource_required": a.resource_required}
                    for a in result.actions
                ]
            }),
            "confidence_level": round(result.confidence, 2),
        },
    )
    return True


async def run() -> None:
    factory = get_session_factory()
    inserted = 0
    scanned_securities = 0

    async with factory() as session:
        rows = (await session.execute(_PRICE_SERIES_SQL)).all()

        by_security: dict = {}
        for security_id, entity_id, price_date, close, volume in rows:
            by_security.setdefault(security_id, {"entity_id": entity_id, "series": []})
            by_security[security_id]["series"].append((price_date, float(close) if close is not None else None, volume))

        for security_id, data in by_security.items():
            series = [r for r in data["series"] if r[1] is not None]
            if len(series) < 20:
                continue
            scanned_securities += 1

            closes = [c for _, c, _ in series]
            returns = [
                (closes[i] - closes[i - 1]) / closes[i - 1]
                for i in range(1, len(closes))
                if closes[i - 1] not in (0, None)
            ]
            if len(returns) < 10:
                continue

            current_return = returns[-1]
            hist_returns = returns[:-1]
            window_end = series[-1][0]
            window_start = series[max(0, len(series) - LOOKBACK_DAYS)][0]

            pm = detect_price_momentum_anomaly(returns=hist_returns, current_return=current_return)
            if pm is not None:
                if await _persist(session, data["entity_id"], "price_momentum", window_end, window_start, pm):
                    inserted += 1

            volumes = [float(v) for _, _, v in series if v is not None]
            if len(volumes) >= 10:
                vs = detect_volume_spike(volumes=volumes[:-1], current_volume=volumes[-1])
                if vs is not None:
                    if await _persist(session, data["entity_id"], "volume_spike", window_end, window_start, vs):
                        inserted += 1

        await session.commit()
        logger.info(
            "Price/volume scan: %d securities scanned, %d anomalies inserted",
            scanned_securities, inserted,
        )

        # Earnings surprise anomalies -- historical distribution per entity
        surprise_rows = (await session.execute(_SURPRISE_SQL)).all()
        by_entity: dict = {}
        for entity_id, fy, fq, actual_eps, consensus_eps, surprise_pct in surprise_rows:
            by_entity.setdefault(entity_id, []).append(
                (fy, fq, float(actual_eps), float(consensus_eps), float(surprise_pct) if surprise_pct is not None else None)
            )

        earnings_inserted = 0
        for entity_id, entries in by_entity.items():
            if len(entries) < 4:
                continue
            entries.sort(key=lambda e: (e[0], e[1]))
            *history, latest = entries
            hist_surprises = [e[4] for e in history if e[4] is not None]
            if len(hist_surprises) < 3:
                continue
            _, _, actual_eps, consensus_eps, _ = latest
            # A near-zero consensus EPS denominator blows up the % surprise
            # (e.g. "beat by 5586%") into a meaningless-looking outlier that
            # would dominate the critical bucket -- skip rather than let
            # noisy small-denominator data crowd out real anomalies.
            if abs(consensus_eps) < 0.05:
                continue
            es = detect_earnings_surprise_anomaly(
                actual_eps=actual_eps, consensus_eps=consensus_eps,
                historical_surprises=hist_surprises,
            )
            if es is not None:
                fy, fq = latest[0], latest[1]
                window_end = _fiscal_quarter_end(fy, fq)
                if await _persist(session, entity_id, "earnings_surprise", window_end, window_end, es):
                    earnings_inserted += 1

        await session.commit()
        logger.info("Earnings surprise scan: %d entities scanned, %d anomalies inserted",
                     len(by_entity), earnings_inserted)


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
