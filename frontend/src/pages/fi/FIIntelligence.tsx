// ---------------------------------------------------------------------------
// FI Intelligence — Cross-Asset Signals, Credit Briefing, Issuance Intel
// ---------------------------------------------------------------------------
import { useCreditBriefing, useFIIssuanceToday, useCrossAssetSignals } from '@/hooks';

interface CreditMarketBriefing {
  id: string;
  briefing_date: string;
  credit_regime: string | null;
  ig_oas_bps: number | null;
  hy_oas_bps: number | null;
  ig_oas_1w_change: number | null;
  hy_oas_1w_change: number | null;
  fallen_angels_this_period: Record<string, unknown> | null;
  rising_stars_this_period: Record<string, unknown> | null;
  narrative: string | null;
}

interface IssuanceEvent {
  id: string;
  entity_id: string | null;
  issue_date: string;
  coupon_rate: number | null;
  maturity_date: string | null;
  size_mm: number | null;
  spread_at_issue_bps: number | null;
  rating: string | null;
  use_of_proceeds: string | null;
  oversubscribed: boolean;
}

interface CrossAssetSignalRow {
  id: string;
  entity_id: string;
  signal_date: string;
  signal_type: string | null;
  equity_return_pct: number | null;
  spread_change_bps: number | null;
  severity: string | null;
  narrative: string | null;
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

const dataStyle: React.CSSProperties = {
  fontFamily: 'var(--font-data)',
  fontVariantNumeric: 'tabular-nums',
  fontSize: 'var(--text-base)',
  color: 'var(--color-text-primary)',
};

// --- Component ---------------------------------------------------------------
//
// The "Earnings Call Transcript" and "Earnings Surprise Chart" panels that
// used to live here were removed rather than fixed: they rendered a
// fabricated Apple/Tim Cook transcript with invented quotes and a made-up
// EPS-surprise series, backed by zero API call of any kind. Wiring them for
// real would need a specific entity in context (a per-company transcript
// makes no sense on this market-wide, entity-agnostic FI dashboard, which
// has no security selector), and even then the real transcript endpoint
// (`TranscriptResponse`) only exposes aggregate tone scores, not
// paragraph-level speaker/text content the transcript viewer needs — so
// there's no real data this page could show here without fabricating it
// again. Removed rather than faked.
//
// Routing fix: this page previously called useFIBriefing/useCreditSpreads/
// useNewIssuance/useDistressedCredit, all of which hit the unrelated
// generic `/v1/fi/*` reference-data router (no producer backs those tables)
// and fell back to hardcoded mock arrays on every load. Switched to the
// real, producer-backed Pillar 3 `/v3/fi/*` endpoints
// (src/api/routers/fi_intelligence.py) with honest empty states instead of
// a mock fallback. `useCrossAssetSignals` (CrossAssetSignal table) has no
// ingestion producer anywhere in the codebase yet — the panel below is
// wired correctly and will populate the moment one exists, but is expected
// to render empty today. Same for per-issuer fallen-angel/rising-star
// detail: `generate_fi_briefings.py` intentionally leaves
// fallen_angels_this_period/rising_stars_this_period null (documented as
// needing a rating-migration history connector this codebase doesn't have)
// -- shown as a dict below rather than fabricated into a fake issuer table.

function formatBps(v: number | null): string {
  return v == null ? '—' : `${v >= 0 ? '+' : ''}${v.toFixed(0)}bps`;
}

export default function FIIntelligence() {
  const { data: creditBriefings, isLoading: briefingsLoading } = useCreditBriefing();
  const { data: issuance, isLoading: issuanceLoading } = useFIIssuanceToday();
  const { data: signals, isLoading: signalsLoading } = useCrossAssetSignals();

  const latestBriefing = ((creditBriefings as CreditMarketBriefing[] | undefined) ?? [])[0];
  const issuanceEvents = (issuance as IssuanceEvent[] | undefined) ?? [];
  const signalRows = (signals as CrossAssetSignalRow[] | undefined) ?? [];

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          Fixed Income Intelligence
        </h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>Cross-asset signals, credit market briefing, and issuance intelligence</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--panel-gap)', alignItems: 'start' }}>
        {/* Cross-Asset Signals */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Cross-Asset Signals</h2>
          {signalsLoading ? (
            <p style={labelStyle}>Loading…</p>
          ) : signalRows.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {signalRows.map((s) => (
                <div key={s.id} style={{ padding: '8px', background: 'var(--color-surface-overlay)', borderRadius: '4px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', fontWeight: 500 }}>{s.signal_type ?? 'Signal'}</span>
                    <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-sm)', fontWeight: 600, color: s.severity === 'HIGH' ? 'var(--color-signal-negative)' : 'var(--color-text-secondary)' }}>{s.severity ?? '—'}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>{s.narrative ?? `${s.equity_return_pct ?? '—'}% equity vs ${formatBps(s.spread_change_bps)} spread`}</span>
                    <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>{s.signal_date}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p style={labelStyle}>No cross-asset divergence signals recorded.</p>
          )}
        </div>

        {/* Credit Market Briefing */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Credit Market Briefing</h2>
          {briefingsLoading ? (
            <p style={labelStyle}>Loading…</p>
          ) : latestBriefing ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '8px' }}>
                <div>
                  <div style={labelStyle}>Regime</div>
                  <div style={{ ...dataStyle, fontWeight: 600 }}>{latestBriefing.credit_regime ?? '—'}</div>
                </div>
                <div>
                  <div style={labelStyle}>Date</div>
                  <div style={dataStyle}>{latestBriefing.briefing_date}</div>
                </div>
                <div>
                  <div style={labelStyle}>IG OAS</div>
                  <div style={dataStyle}>{latestBriefing.ig_oas_bps != null ? `${latestBriefing.ig_oas_bps.toFixed(0)}bps` : '—'} <span style={{ color: 'var(--color-text-tertiary)', fontSize: 'var(--text-xs)' }}>({formatBps(latestBriefing.ig_oas_1w_change)} 1w)</span></div>
                </div>
                <div>
                  <div style={labelStyle}>HY OAS</div>
                  <div style={dataStyle}>{latestBriefing.hy_oas_bps != null ? `${latestBriefing.hy_oas_bps.toFixed(0)}bps` : '—'} <span style={{ color: 'var(--color-text-tertiary)', fontSize: 'var(--text-xs)' }}>({formatBps(latestBriefing.hy_oas_1w_change)} 1w)</span></div>
                </div>
              </div>
              {latestBriefing.narrative && (
                <p style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', lineHeight: 1.5, margin: 0 }}>{latestBriefing.narrative}</p>
              )}
              <p style={labelStyle}>
                {latestBriefing.fallen_angels_this_period || latestBriefing.rising_stars_this_period
                  ? 'Rating-migration detail available in this briefing.'
                  : 'No fallen-angel/rising-star rating migrations recorded this period.'}
              </p>
            </div>
          ) : (
            <p style={labelStyle}>No credit market briefing available.</p>
          )}
        </div>

        {/* Issuance Intelligence */}
        <div style={{ ...panelStyle, gridColumn: '1 / -1' }}>
          <h2 style={sectionTitle}>Issuance Intelligence — Today</h2>
          {issuanceLoading ? (
            <p style={labelStyle}>Loading…</p>
          ) : issuanceEvents.length > 0 ? (
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {['Date', 'Issuer', 'Size', 'Maturity', 'Coupon', 'Spread', 'Rating'].map((h) => (
                    <th key={h} style={{ ...labelStyle, textAlign: h === 'Issuer' ? 'left' : 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {issuanceEvents.map((d) => (
                  <tr key={d.id} style={{ height: 'var(--table-row-height)' }}>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{d.issue_date}</td>
                    <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{d.entity_id ? d.entity_id.slice(0, 8) : '—'}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{d.size_mm != null ? `$${d.size_mm.toFixed(0)}mm` : '—'}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{d.maturity_date ?? '—'}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{d.coupon_rate != null ? `${d.coupon_rate.toFixed(3)}%` : '—'}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{formatBps(d.spread_at_issue_bps)}</td>
                    <td style={{ ...dataStyle, textAlign: 'right', padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{d.rating ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p style={labelStyle}>No new bond issuances recorded today.</p>
          )}
        </div>
      </div>
    </div>
  );
}
