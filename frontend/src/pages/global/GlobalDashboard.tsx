// ---------------------------------------------------------------------------
// Global Intelligence Dashboard
//
// Honesty pass: every panel was previously silent mock (countryRisks / GDP /
// geoEvents / commodities via `apiX ?? MOCK`, plus a hardcoded central-banks
// block and reads of composite/political/economic fields off /v3/global/countries
// that don't exist on that endpoint). The old useGlobalIndices/useFXRates hooks
// hit /v3/global/indices and /v3/global/fx/rates, which the backend does NOT
// expose.
//
// Now wired to real backend endpoints:
//   - Country list        -> GET /v3/global/countries              (metadata only)
//   - Per-country risk     -> GET /v3/global/countries/{code}/risk  (bounded sample)
//   - Geopolitical events  -> GET /v3/global/events/geopolitical
// Panels with no backend (global indices / FX / commodity quotes) and the
// central-bank block render honest empty states instead of fabricated rows.
// ---------------------------------------------------------------------------
import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';
import { CountryRiskRanking, GeopoliticalEventCard } from '@/components/global';
import type { CountryRisk as CountryRiskType, GeopoliticalEvent } from '@/components/global';
import { EmptyState } from '@/components/feedback';

const panelStyle: React.CSSProperties = {
  background: 'var(--color-surface-base)',
  border: '1px solid var(--color-surface-border)',
  borderRadius: '4px',
  padding: 'var(--panel-padding)',
  overflow: 'auto',
};

const sectionTitle: React.CSSProperties = {
  fontFamily: 'var(--font-ui)',
  fontSize: 'var(--text-lg)',
  fontWeight: 600,
  color: 'var(--color-text-primary)',
  margin: '0 0 12px 0',
};

const labelStyle: React.CSSProperties = {
  fontFamily: 'var(--font-ui)',
  fontSize: 'var(--text-sm)',
  color: 'var(--color-text-secondary)',
};

// --- DTOs (mirror backend response schemas) ----------------------------------

interface CountryProfileDTO {
  country_code: string;
  country_name: string;
  region?: string | null;
  income_group?: string | null;
  is_g20: boolean;
  is_eu: boolean;
  population?: number | null;
  gdp_usd?: number | null;
}

interface CountryRiskScoreDTO {
  country_code: string;
  as_of_date: string;
  political_risk_score?: number | null;
  economic_risk_score?: number | null;
  sanctions_risk_score?: number | null;
  composite_risk_score?: number | null;
  risk_classification?: string | null;
  risk_trend?: string | null;
}

interface GeopoliticalEventDTO {
  event_type?: string | null;
  title: string;
  description?: string | null;
  countries_involved?: string[] | null;
  severity?: string | null;
  status?: string | null;
  start_date?: string | null;
  commodity_impact?: string[] | Record<string, unknown> | null;
  sector_impact?: string[] | Record<string, unknown> | null;
}

interface CountryRiskSample {
  code: string;
  scores: CountryRiskScoreDTO[];
}

// Risk scores require one /risk call per country; bound the fan-out so the
// dashboard shows a real ranking sample rather than firing hundreds of requests.
const RISK_SAMPLE_SIZE = 12;

function asStringList(value: unknown): string[] | undefined {
  return Array.isArray(value) ? value.map(String) : undefined;
}

// --- Component ---------------------------------------------------------------

export default function GlobalDashboard() {
  const { data: countriesRaw, isLoading: loadingCountries } = useQuery({
    queryKey: ['global', 'countries'],
    queryFn: () => api.get<CountryProfileDTO[]>('/v3/global/countries'),
    retry: 0,
  });
  const countries = useMemo(
    () => (Array.isArray(countriesRaw) ? countriesRaw : []),
    [countriesRaw],
  );

  const sampleCodes = useMemo(
    () => countries.slice(0, RISK_SAMPLE_SIZE).map((c) => c.country_code),
    [countries],
  );

  const { data: riskSamplesRaw, isLoading: loadingRisk } = useQuery({
    queryKey: ['global', 'risk-sample', sampleCodes],
    enabled: sampleCodes.length > 0,
    retry: 0,
    queryFn: async (): Promise<CountryRiskSample[]> => {
      return Promise.all(
        sampleCodes.map(async (code) => {
          try {
            const scores = await api.get<CountryRiskScoreDTO[]>(
              `/v3/global/countries/${code}/risk`,
              { limit: 12 },
            );
            return { code, scores: Array.isArray(scores) ? scores : [] };
          } catch {
            return { code, scores: [] };
          }
        }),
      );
    },
  });

  const nameByCode = useMemo(
    () => new Map(countries.map((c) => [c.country_code, c.country_name])),
    [countries],
  );

  // Only countries that actually returned a composite score become rows — no
  // fabricated ranks.
  const riskRows: CountryRiskType[] = useMemo(() => {
    return (riskSamplesRaw ?? [])
      .filter((s) => s.scores.length > 0 && s.scores[0]!.composite_risk_score != null)
      .map((s) => {
        const latest = s.scores[0]!;
        const history = [...s.scores]
          .reverse()
          .map((row) => row.composite_risk_score ?? 0);
        return {
          code: s.code,
          name: nameByCode.get(s.code) ?? s.code,
          composite: latest.composite_risk_score ?? 0,
          political: latest.political_risk_score ?? 0,
          economic: latest.economic_risk_score ?? 0,
          sanctions: latest.sanctions_risk_score ?? 0,
          classification: latest.risk_classification ?? 'N/A',
          trend: latest.risk_trend ?? 'stable',
          history,
        };
      });
  }, [riskSamplesRaw, nameByCode]);

  const { data: eventsRaw, isLoading: loadingEvents } = useQuery({
    queryKey: ['global', 'geopolitical-events'],
    queryFn: () => api.get<GeopoliticalEventDTO[]>('/v3/global/events/geopolitical'),
    retry: 0,
  });
  const eventCards: GeopoliticalEvent[] = useMemo(() => {
    const rows = Array.isArray(eventsRaw) ? eventsRaw : [];
    return rows.slice(0, 6).map((e) => ({
      title: e.title,
      description: e.description ?? '',
      severity: e.severity ?? 'MEDIUM',
      countries: Array.isArray(e.countries_involved) ? e.countries_involved.map(String) : [],
      startDate: e.start_date ?? '',
      status: e.status ?? '',
      commodityImpact: asStringList(e.commodity_impact),
      sectorImpact: asStringList(e.sector_impact),
    }));
  }, [eventsRaw]);

  const riskLoading = loadingCountries || loadingRisk;

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>

      {/* Header */}
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          Global Intelligence
        </h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>
          Country risk, geopolitical events, commodities, and central bank policy monitoring
        </p>
      </div>

      {/* Global indices / GDP growth — no backend source exists */}
      <div style={{ ...panelStyle, marginBottom: 'var(--panel-gap)' }}>
        <h2 style={sectionTitle}>Global Growth &amp; Indices</h2>
        <EmptyState
          icon="🌐"
          title="No global indices data"
          description="This deployment does not expose a global indices / GDP-growth comparison endpoint."
        />
      </div>

      {/* 2-column layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '65fr 35fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>

        {/* Left Column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--panel-gap)' }}>

          {/* Country Risk Rankings (bounded real sample) */}
          <div style={panelStyle}>
            <h2 style={sectionTitle}>Country Risk Rankings</h2>
            {riskLoading ? (
              <EmptyState icon="⏳" title="Loading risk scores…" />
            ) : riskRows.length === 0 ? (
              <EmptyState
                icon="🗺️"
                title="No risk scores available"
                description="No country risk scores have been ingested for this deployment yet."
              />
            ) : (
              <CountryRiskRanking countries={riskRows} />
            )}
          </div>

          {/* Top Geopolitical Events */}
          <div style={panelStyle}>
            <h2 style={sectionTitle}>Top Geopolitical Events</h2>
            {loadingEvents ? (
              <EmptyState icon="⏳" title="Loading events…" />
            ) : eventCards.length === 0 ? (
              <EmptyState
                icon="📰"
                title="No geopolitical events"
                description="No active geopolitical events are recorded."
              />
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {eventCards.map((ev, idx) => (
                  <GeopoliticalEventCard key={idx} event={ev} />
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right Column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--panel-gap)' }}>

          {/* Commodity quotes — /v3/global/commodities is metadata only (no live
              price/change), so an honest empty state instead of fabricated ticks */}
          <div style={panelStyle}>
            <h2 style={sectionTitle}>Commodities</h2>
            <EmptyState
              icon="🛢️"
              title="No commodity quotes"
              description="Live commodity prices are not exposed here. See the Commodity Dashboard for metadata and price history."
            />
          </div>

          {/* Central bank rates — no wired source on this dashboard */}
          <div style={panelStyle}>
            <h2 style={sectionTitle}>Central Bank Rates</h2>
            <EmptyState
              icon="🏦"
              title="No central bank data"
              description="Central bank policy rates are not wired into this dashboard."
            />
          </div>
        </div>
      </div>
    </div>
  );
}
