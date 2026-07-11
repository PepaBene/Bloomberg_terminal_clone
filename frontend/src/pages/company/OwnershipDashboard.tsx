// ---------------------------------------------------------------------------
// Ownership Dashboard — Institutional Holders, Insider Ownership, Short Interest
// ---------------------------------------------------------------------------
import { useMemo, useState } from 'react';
import { OwnershipSummary } from '@/components/company/OwnershipSummary';
import type { Holder } from '@/components/company/OwnershipSummary';
import { OwnershipChangeTable, ShortInterestChart, ActivistBanner } from '@/components/ownership';
import type { OwnershipChange, ShortInterestDataPoint, ActivistInfo } from '@/components/ownership';
import { useParams } from 'react-router-dom';
import { useSecurityStore } from '@/stores/securityContext';
import { useInstitutionalHoldings, useInsiderHoldings, useOwnershipSummary, useShortInterest, useFundHoldings } from '@/hooks';

// --- API response shapes (subset of backend schemas actually read) ---------
// `GET /v1/securities/{id}/ownership/institutional` and `/ownership/insider`
// and `/short-interest` all return `PaginatedResponse` (`{data: [...], meta}`),
// not a bare array (src/api/routers/ownership.py).

interface InstitutionalHoldingApi {
  institution_id: string;
  shares_held: number | null;
  market_value: number | null;
  percent_of_outstanding: number | null;
  shares_change: number | null;
}

interface InsiderHoldingApi {
  insider_name: string | null;
  transaction_date: string | null;
  shares_transacted: number | null;
  shares_owned_after: number | null;
}

// Mirrors `OwnershipSummaryResponse` (src/schemas/ownership.py:64) — a single
// object (not paginated); it has no `.changes` field.
interface OwnershipSummaryApi {
  institutional_percent: number | null;
  insider_percent: number | null;
}

interface ShortInterestApi {
  settlement_date: string;
  shares_short: number | null;
  short_percent_float: number | null;
  days_to_cover: number | null;
}

interface FundHoldingApi {
  fundName?: string;
  name?: string;
  shares?: number;
  pctOfFund?: number;
  marketValue?: number;
}

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

// --- Default empty data (populated by API) -----------------------------------

const topHolders: Holder[] = [];

const ownershipSummary = [
  { label: 'Institutional', value: '—' },
  { label: 'Insider', value: '—' },
  { label: 'Retail / Other', value: '—' },
  { label: 'Shares Outstanding', value: '—' },
  { label: 'Float', value: '—' },
  { label: '# Institutions', value: '—' },
];

const ownershipChanges: OwnershipChange[] = [];

const shortInterestHistory: ShortInterestDataPoint[] = [];

const activistInfo: ActivistInfo = {
  name: '',
  position: '',
  filingDate: '',
  stake: 0,
  intent: '',
};

// --- Component ---------------------------------------------------------------

export default function OwnershipDashboard() {
  const [showBanner, setShowBanner] = useState(true);

  const { entityId } = useParams<{ entityId: string }>();
  const primary = useSecurityStore((s) => s.primary);
  const resolvedId = entityId ?? primary?.entity_id ?? primary?.security_id;

  const { data: apiHolders } = useInstitutionalHoldings(resolvedId);
  const { data: apiInsiders } = useInsiderHoldings(resolvedId);
  const { data: apiOwnership } = useOwnershipSummary(resolvedId);
  const { data: apiShort } = useShortInterest(resolvedId);
  const { data: apiFundHoldings } = useFundHoldings(resolvedId);

  const activeHolders = (apiHolders as any[]) ?? topHolders;
  const activeChanges = (apiOwnership as any)?.changes ?? ownershipChanges;
  const activeShortHistory = (apiShort as any[]) ?? shortInterestHistory;

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>

      {/* Activist Banner at top */}
      {showBanner && (
        <div style={{ marginBottom: 'var(--panel-gap)' }}>
          <ActivistBanner activist={activistInfo} onDismiss={() => setShowBanner(false)} />
        </div>
      )}

      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          Ownership Dashboard
        </h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>{primary?.ticker ?? '—'} &mdash; {primary?.name ?? '—'}</p>
      </div>

      {/* Summary Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 'var(--panel-gap)', marginBottom: 'var(--panel-gap)' }}>
        {ownershipSummary.map((s) => (
          <div key={s.label} style={{ ...panelStyle, textAlign: 'center', padding: '10px' }}>
            <div style={{ ...labelStyle, marginBottom: '4px' }}>{s.label}</div>
            <div style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)' }}>{s.value}</div>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '65fr 35fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        {/* OwnershipSummary Component */}
        <OwnershipSummary
          holders={activeHolders}
          insiderPct={0.07}
          institutionalPct={60.8}
        />

        {/* ShortInterestChart Component */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Short Interest (12M)</h2>
          <ShortInterestChart data={activeShortHistory} />
        </div>
      </div>

      {/* OwnershipChangeTable below */}
      <div style={{ ...panelStyle, marginTop: 'var(--panel-gap)' }}>
        <h2 style={sectionTitle}>Quarterly Ownership Changes</h2>
        <OwnershipChangeTable changes={activeChanges} />
      </div>

      {/* Fund Holdings (N-PORT) */}
      {(apiFundHoldings as any[])?.length > 0 && (
        <div style={{ ...panelStyle, marginTop: 'var(--panel-gap)' }}>
          <h2 style={sectionTitle}>Fund Holdings (N-PORT)</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Fund Name', 'Shares', '% of Fund', 'Market Value'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: h === 'Fund Name' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(apiFundHoldings as any[]).map((f: any, i: number) => (
                <tr key={i} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{f.fundName ?? f.name}</td>
                  <td style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{f.shares?.toLocaleString() ?? '—'}</td>
                  <td style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)', textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{f.pctOfFund != null ? `${f.pctOfFund.toFixed(2)}%` : '—'}</td>
                  <td style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{f.marketValue != null ? `$${(f.marketValue / 1e6).toFixed(0)}M` : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
