// ---------------------------------------------------------------------------
// Economic Calendar — Full Release Calendar
//
// GET /v3/news/calendar/economic (src/api/routers/economic_calendar.py) is
// already used by the Home page's small "Economic Calendar" widget, but the
// NavRail's Macro flyout "Calendar" sub-item fell back to the parent /macro
// page instead of a dedicated full view. Wired here as its own route with a
// wider date window and importance filter.
// ---------------------------------------------------------------------------
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
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
const selectStyle: React.CSSProperties = {
  fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)',
  padding: '6px 10px', borderRadius: '4px',
  border: '1px solid var(--color-surface-border)',
  background: 'var(--color-surface-raised)', color: 'var(--color-text-primary)',
};

interface EconomicReleaseDTO {
  id: string;
  release_type: string;
  release_category: string | null;
  release_date: string;
  importance: string | null;
  consensus_value: number | null;
  prior_value: number | null;
  actual_value: number | null;
  surprise_value: number | null;
}
interface EconomicCalendarListDTO { releases: EconomicReleaseDTO[]; total_count: number }

function importanceBadgeClass(importance: string | null): string {
  switch ((importance ?? '').toUpperCase()) {
    case 'HIGH': return 'terminal-badge terminal-badge-negative';
    case 'MEDIUM': return 'terminal-badge terminal-badge-neutral';
    default: return 'terminal-badge';
  }
}

export default function EconomicCalendarPage() {
  const [importance, setImportance] = useState('');
  const { data, isLoading } = useQuery<EconomicCalendarListDTO>({
    queryKey: ['macro', 'calendar', importance],
    queryFn: () => api.get('/v3/news/calendar/economic', { days_ahead: 30, ...(importance ? { importance } : {}) }),
    retry: 0,
  });
  const releases = data?.releases ?? [];

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: '16px' }}>
        <div>
          <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
            Economic Calendar
          </h1>
          <p style={{ ...labelStyle, marginTop: '4px' }}>Upcoming economic releases, next 30 days</p>
        </div>
        <select value={importance} onChange={(e) => setImportance(e.target.value)} style={selectStyle}>
          <option value="">All Importance</option>
          <option value="HIGH">High</option>
          <option value="MEDIUM">Medium</option>
          <option value="LOW">Low</option>
        </select>
      </div>

      <div style={panelStyle}>
        {isLoading ? (
          <EmptyState icon="⏳" title="Loading…" />
        ) : releases.length === 0 ? (
          <EmptyState icon="📅" title="No releases scheduled" description="No economic releases match this filter in the next 30 days." />
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Date', 'Release', 'Category', 'Importance', 'Consensus', 'Prior', 'Actual', 'Surprise'].map((h) => (
                  <th key={h} style={{ ...labelStyle, textAlign: 'left', padding: 'var(--table-cell-py) var(--table-cell-px)', borderBottom: '1px solid var(--color-surface-border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {releases.map((r) => (
                <tr key={r.id} style={{ height: 'var(--table-row-height)' }}>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontSize: 'var(--text-sm)' }}>{r.release_date}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 500 }}>{r.release_type}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', color: 'var(--color-text-secondary)' }}>{r.release_category ?? '—'}</td>
                  <td style={{ padding: 'var(--table-cell-py) var(--table-cell-px)' }}><span className={importanceBadgeClass(r.importance)}>{r.importance ?? '—'}</span></td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{r.consensus_value ?? '—'}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)' }}>{r.prior_value ?? '—'}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', fontWeight: 600 }}>{r.actual_value ?? '—'}</td>
                  <td style={{ ...dataStyle, padding: 'var(--table-cell-py) var(--table-cell-px)', color: (r.surprise_value ?? 0) >= 0 ? 'var(--color-signal-positive)' : 'var(--color-signal-negative)' }}>{r.surprise_value ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
