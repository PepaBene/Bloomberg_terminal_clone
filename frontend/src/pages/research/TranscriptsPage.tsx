// ---------------------------------------------------------------------------
// Transcripts — Earnings Call Transcript Intelligence
//
// GET /v3/earnings/{entity_id}/calls (src/api/routers/earnings_p2.py) has
// real tone/hedging/confidence NLP scoring on ingested earnings calls, but
// nothing in the frontend ever called it -- the NavRail's Research flyout
// "Transcripts" sub-item fell back to the parent /research page. Wired here
// as its own route.
// ---------------------------------------------------------------------------
import { useQuery } from '@tanstack/react-query';
import { useSecurityStore } from '@/stores/securityContext';
import { EmptyState } from '@/components/feedback';
import { api } from '@/api/client';

const panelStyle: React.CSSProperties = {
  background: 'var(--color-surface-base)',
  border: '1px solid var(--color-surface-border)',
  borderRadius: '4px',
  padding: 'var(--panel-padding)',
  overflow: 'auto',
};
const labelStyle: React.CSSProperties = {
  fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)',
};
const dataStyle: React.CSSProperties = {
  fontFamily: 'var(--font-data)', fontVariantNumeric: 'tabular-nums',
  fontSize: 'var(--text-base)', color: 'var(--color-text-primary)',
};

interface TranscriptDTO {
  id: string;
  call_date: string;
  fiscal_year: number | null;
  fiscal_quarter: number | null;
  call_type: string | null;
  overall_tone: number | null;
  hedging_ratio: number | null;
  confidence_ratio: number | null;
  forward_looking_pct: number | null;
  management_outlook: string | null;
  source_url: string | null;
}

function fmtScore(v: number | null): string {
  return v == null ? '—' : v.toFixed(2);
}

export default function TranscriptsPage() {
  const primary = useSecurityStore((s) => s.primary);
  const entityId = primary?.entity_id;

  const { data, isLoading } = useQuery<TranscriptDTO[]>({
    queryKey: ['research', 'transcripts', entityId],
    queryFn: () => api.get(`/v3/earnings/${entityId}/calls`),
    enabled: !!entityId,
    retry: 0,
  });
  const transcripts = Array.isArray(data) ? data : [];

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          Earnings Call Transcripts
        </h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>
          {primary?.ticker ?? '—'} {primary?.name ? `— ${primary.name}` : ''}
        </p>
      </div>

      <div style={panelStyle}>
        {!entityId ? (
          <EmptyState icon="🎙️" title="No company selected" description="Search for a company to view its earnings call transcripts." />
        ) : isLoading ? (
          <EmptyState icon="⏳" title="Loading…" />
        ) : transcripts.length === 0 ? (
          <EmptyState icon="🎙️" title="No transcripts available" description="No earnings call transcripts have been ingested for this company yet." />
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Call Date', 'Period', 'Type', 'Overall Tone', 'Hedging Ratio', 'Confidence', 'Forward-Looking %', 'Outlook'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: 'left', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {transcripts.map((t) => (
                <tr key={t.id} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>
                    {t.source_url ? <a href={t.source_url} target="_blank" rel="noreferrer" style={{ color: 'var(--color-accent-primary)' }}>{t.call_date}</a> : t.call_date}
                  </td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>
                    {t.fiscal_year ? `FY${t.fiscal_year}${t.fiscal_quarter ? ` Q${t.fiscal_quarter}` : ''}` : '—'}
                  </td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{t.call_type ?? '—'}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', color: (t.overall_tone ?? 0) >= 0 ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)' }}>{fmtScore(t.overall_tone)}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{fmtScore(t.hedging_ratio)}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{fmtScore(t.confidence_ratio)}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{t.forward_looking_pct != null ? `${t.forward_looking_pct.toFixed(1)}%` : '—'}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-text-secondary)', fontSize: 'var(--text-sm)' }}>{t.management_outlook ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
