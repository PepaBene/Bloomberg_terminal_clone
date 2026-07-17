// ---------------------------------------------------------------------------
// Country Risk Dashboard
//
// Honesty pass: the previous version called useCountryRisk() with NO country
// argument (so it never fired), rendered a fully mocked 15-country risk table
// plus mock geopolitical events, hardcoded KPI counts, and read nonexistent
// score fields (composite/political/economic) off /v3/global/countries.
//
// Now wired to real backend endpoints:
//   - Country list       -> GET /v3/global/countries              (selector source)
//   - Selected risk      -> GET /v3/global/countries/{code}/risk  (score history)
//   - Selected events    -> GET /v3/global/countries/{code}/events
// KPIs reflect the selected country's latest real risk score; empty states are
// shown when no data exists.
// ---------------------------------------------------------------------------
import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';
import { GeopoliticalEventCard } from '@/components/global';
import type { GeopoliticalEvent } from '@/components/global';
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

const dataStyle: React.CSSProperties = {
  fontFamily: 'var(--font-data)',
  fontVariantNumeric: 'tabular-nums',
  fontSize: 'var(--text-base)',
  color: 'var(--color-text-primary)',
};

// --- DTOs (mirror backend response schemas) ----------------------------------

interface CountryProfileDTO {
  country_code: string;
  country_name: string;
  region?: string | null;
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
  title: string;
  description?: string | null;
  countries_involved?: string[] | null;
  severity?: string | null;
  status?: string | null;
  start_date?: string | null;
  commodity_impact?: string[] | Record<string, unknown> | null;
  sector_impact?: string[] | Record<string, unknown> | null;
}

const CLASSIFICATION_COLORS: Record<string, string> = {
  LOW: 'var(--color-signal-positive)',
  MODERATE: 'var(--color-accent-primary)',
  ELEVATED: 'var(--color-signal-warning)',
  HIGH: 'var(--color-signal-negative)',
  EXTREME: '#B91C1C',
};

function classificationColor(c: string): string {
  return CLASSIFICATION_COLORS[c.toUpperCase()] ?? 'var(--color-signal-neutral)';
}

function fmtScore(v: number | null | undefined): string {
  return v == null ? '—' : v.toFixed(1);
}

function asStringList(value: unknown): string[] | undefined {
  return Array.isArray(value) ? value.map(String) : undefined;
}

// --- Component ---------------------------------------------------------------

export default function CountryRisk() {
  const { data: countriesRaw, isLoading: loadingCountries } = useQuery({
    queryKey: ['global', 'countries'],
    queryFn: () => api.get<CountryProfileDTO[]>('/v3/global/countries'),
    retry: 0,
  });
  const countries = useMemo(
    () => (Array.isArray(countriesRaw) ? countriesRaw : []),
    [countriesRaw],
  );

  const [selectedCode, setSelectedCode] = useState<string | null>(null);
  const effectiveCode = selectedCode ?? countries[0]?.country_code ?? null;
  const selectedCountry = countries.find((c) => c.country_code === effectiveCode);

  const { data: riskRaw, isLoading: loadingRisk } = useQuery({
    queryKey: ['global', 'country-risk', effectiveCode],
    enabled: !!effectiveCode,
    retry: 0,
    queryFn: () =>
      api.get<CountryRiskScoreDTO[]>(`/v3/global/countries/${effectiveCode}/risk`, { limit: 24 }),
  });
  const riskHistory = useMemo(
    () => (Array.isArray(riskRaw) ? riskRaw : []),
    [riskRaw],
  );
  const latestRisk = riskHistory[0];

  const { data: eventsRaw, isLoading: loadingEvents } = useQuery({
    queryKey: ['global', 'country-events', effectiveCode],
    enabled: !!effectiveCode,
    retry: 0,
    queryFn: () => api.get<GeopoliticalEventDTO[]>(`/v3/global/countries/${effectiveCode}/events`),
  });
  const eventCards: GeopoliticalEvent[] = useMemo(() => {
    const rows = Array.isArray(eventsRaw) ? eventsRaw : [];
    return rows.map((e) => ({
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

  const kpis: { label: string; value: string; color?: string }[] = [
    { label: 'Composite Risk', value: fmtScore(latestRisk?.composite_risk_score) },
    { label: 'Political Risk', value: fmtScore(latestRisk?.political_risk_score) },
    { label: 'Economic Risk', value: fmtScore(latestRisk?.economic_risk_score) },
    { label: 'Sanctions Risk', value: fmtScore(latestRisk?.sanctions_risk_score) },
  ];

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>

      {/* Header + country selector */}
      <div style={{ marginBottom: '16px', display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '16px', flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
            Country Risk
          </h1>
          <p style={{ ...labelStyle, marginTop: '4px' }}>
            Political, economic and sanctions risk scores plus geopolitical events by country
          </p>
        </div>
        {countries.length > 0 && (
          <select
            value={effectiveCode ?? ''}
            onChange={(e) => setSelectedCode(e.target.value)}
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-sm)',
              padding: '6px 10px',
              borderRadius: '4px',
              background: 'var(--color-surface-base)',
              border: '1px solid var(--color-surface-border)',
              color: 'var(--color-text-primary)',
              minWidth: '220px',
            }}
          >
            {countries.map((c) => (
              <option key={c.country_code} value={c.country_code}>
                {c.country_code} — {c.country_name}
              </option>
            ))}
          </select>
        )}
      </div>

      {loadingCountries ? (
        <div style={panelStyle}><EmptyState icon="⏳" title="Loading countries…" /></div>
      ) : countries.length === 0 ? (
        <div style={panelStyle}>
          <EmptyState
            icon="🗺️"
            title="No country data"
            description="No tracked countries have been ingested for this deployment yet."
          />
        </div>
      ) : (
        <>
          {/* KPI Row — selected country's latest real scores */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
            {kpis.map((kpi) => (
              <div key={kpi.label} style={{ ...panelStyle, padding: '12px 16px' }}>
                <div style={labelStyle}>{kpi.label}</div>
                <div style={{ ...dataStyle, fontSize: 'var(--text-xl)', fontWeight: 700, marginTop: '4px', color: kpi.color || 'var(--color-text-primary)' }}>
                  {kpi.value}
                </div>
              </div>
            ))}
          </div>

          {/* 2-column layout */}
          <div style={{ display: 'grid', gridTemplateColumns: '65fr 35fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>

            {/* Risk score history for selected country */}
            <div style={panelStyle}>
              <h2 style={sectionTitle}>
                Risk Score History{selectedCountry ? ` — ${selectedCountry.country_name}` : ''}
              </h2>
              {loadingRisk ? (
                <EmptyState icon="⏳" title="Loading risk scores…" />
              ) : riskHistory.length === 0 ? (
                <EmptyState
                  icon="📊"
                  title="No risk scores"
                  description="No risk scores have been recorded for this country."
                />
              ) : (
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr>
                      {['As of', 'Composite', 'Political', 'Economic', 'Sanctions', 'Class', 'Trend'].map((h) => (
                        <th
                          key={h}
                          style={{
                            ...labelStyle,
                            textAlign: h === 'As of' || h === 'Class' || h === 'Trend' ? 'left' : 'right',
                            fontSize: 'var(--text-xs)',
                            padding: 'var(--table-cell-py) var(--table-cell-px)',
                            borderBottom: '1px solid var(--color-surface-border)',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {riskHistory.map((r, i) => {
                      const clsColor = classificationColor(r.risk_classification ?? '');
                      return (
                        <tr key={`${r.as_of_date}-${i}`} style={{ height: 'var(--table-row-height)', borderBottom: '1px solid var(--color-surface-border)' }}>
                          <td style={{ ...dataStyle, fontSize: 'var(--text-sm)', color: 'var(--color-text-tertiary)', padding: 'var(--table-cell-py) var(--table-cell-px)', whiteSpace: 'nowrap' }}>{r.as_of_date}</td>
                          <td style={{ ...dataStyle, fontSize: 'var(--text-sm)', textAlign: 'right', fontWeight: 600, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{fmtScore(r.composite_risk_score)}</td>
                          <td style={{ ...dataStyle, fontSize: 'var(--text-sm)', textAlign: 'right', color: 'var(--color-text-secondary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{fmtScore(r.political_risk_score)}</td>
                          <td style={{ ...dataStyle, fontSize: 'var(--text-sm)', textAlign: 'right', color: 'var(--color-text-secondary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{fmtScore(r.economic_risk_score)}</td>
                          <td style={{ ...dataStyle, fontSize: 'var(--text-sm)', textAlign: 'right', color: 'var(--color-text-secondary)', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{fmtScore(r.sanctions_risk_score)}</td>
                          <td style={{ padding: 'var(--table-cell-py) var(--table-cell-px)' }}>
                            {r.risk_classification ? (
                              <span style={{
                                fontFamily: 'var(--font-data)',
                                fontSize: 'var(--text-xs)',
                                fontWeight: 500,
                                color: clsColor,
                                textTransform: 'uppercase',
                                letterSpacing: '0.06em',
                                padding: '2px 8px',
                                border: `1px solid ${clsColor}`,
                                borderRadius: '9999px',
                                whiteSpace: 'nowrap',
                              }}>
                                {r.risk_classification}
                              </span>
                            ) : '—'}
                          </td>
                          <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)', padding: 'var(--table-cell-py) var(--table-cell-px)', whiteSpace: 'nowrap' }}>
                            {r.risk_trend ?? '—'}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>

            {/* Geopolitical events for the selected country */}
            <div style={panelStyle}>
              <h2 style={sectionTitle}>Geopolitical Events</h2>
              {loadingEvents ? (
                <EmptyState icon="⏳" title="Loading events…" />
              ) : eventCards.length === 0 ? (
                <EmptyState
                  icon="📰"
                  title="No geopolitical events"
                  description="No active geopolitical events reference this country."
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
        </>
      )}
    </div>
  );
}
