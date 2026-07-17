// ---------------------------------------------------------------------------
// AI Research Hub
// ---------------------------------------------------------------------------
import { useNavigate } from 'react-router-dom';
import { CompanyIntelCard } from '@/components/intelligence';
import type { IntelModule } from '@/components/intelligence';
import { useCompanyIntelligence } from '@/hooks';
import { useSecurityStore } from '@/stores/securityContext';

// --- Skeleton ----------------------------------------------------------------

function Skeleton({ width = '100%', height = '1em' }: { width?: string; height?: string }) {
  return (
    <div
      style={{
        width,
        height,
        background: 'linear-gradient(90deg, var(--color-surface-raised) 25%, var(--color-surface-overlay) 50%, var(--color-surface-raised) 75%)',
        backgroundSize: '200% 100%',
        animation: 'shimmer 1.5s infinite',
        borderRadius: 'var(--radius-sm)',
      }}
    />
  );
}

// --- Static Research Cards (these describe available modules, not API data) ---

interface ResearchCard {
  id: string;
  title: string;
  description: string;
  icon: string;
  accentColor: string;
  status: 'Available' | 'Beta' | 'Coming Soon';
}

const RESEARCH_CARDS: ResearchCard[] = [
  {
    id: 'primer',
    title: 'Company Primer',
    description: 'Generate comprehensive company analysis reports covering business model, financials, competitive positioning, and risk factors. Powered by filings and earnings transcripts.',
    icon: '\u{1F4D1}',
    accentColor: 'var(--color-chart-1)',
    status: 'Available',
  },
  {
    id: 'briefing',
    title: 'Morning Briefing',
    description: 'AI-generated daily market summary tailored to your portfolio holdings. Covers overnight moves, earnings, macro events, and sector developments.',
    icon: '\u{2600}',
    accentColor: 'var(--color-chart-3)',
    status: 'Available',
  },
  {
    id: 'anomaly',
    title: 'Anomaly Detection',
    description: 'Automated scanning for unusual patterns in financial data: earnings quality flags, accounting anomalies, unusual volume, and deviation from sector trends.',
    icon: '\u{26A0}',
    accentColor: 'var(--color-signal-warning)',
    status: 'Available',
  },
  {
    id: 'search',
    title: 'Semantic Search',
    description: 'Natural language search across SEC filings, earnings call transcripts, research notes, and financial data. Ask questions like "Which companies mentioned AI capex guidance?"',
    icon: '\u{1F50D}',
    accentColor: 'var(--color-chart-6)',
    status: 'Beta',
  },
  {
    id: 'thesis',
    title: 'Investment Thesis',
    description: 'Build and track investment theses with AI-assisted driver analysis, risk identification, and catalyst mapping. Compare bull/bear scenarios with quantified outcomes.',
    icon: '\u{1F4CA}',
    accentColor: 'var(--color-chart-2)',
    status: 'Beta',
  },
  {
    id: 'qa',
    title: 'Analyst Q&A',
    description: 'Ask natural language questions about any company and get sourced answers grounded in financial data, filings, and transcripts. Full citation chain for verification.',
    icon: '\u{1F4AC}',
    accentColor: 'var(--color-chart-4)',
    status: 'Available',
  },
  {
    id: 'modelBuilder',
    title: 'Model Builder',
    description: 'Auto-assemble scored analytical models across economic, market, industry, corporate, and company scopes — company models pull real fundamentals, DCF/comps valuation, and Piotroski/Altman scores on file.',
    icon: '\u{1F9EE}',
    accentColor: 'var(--color-chart-5)',
    status: 'Available',
  },
];

function statusBadgeClass(status: ResearchCard['status']): string {
  switch (status) {
    case 'Available':   return 'terminal-badge terminal-badge-positive';
    case 'Beta':        return 'terminal-badge terminal-badge-warning';
    case 'Coming Soon': return 'terminal-badge';
  }
}

// --- Component ---------------------------------------------------------------

const CARD_ROUTES: Record<string, string> = {
  primer: '/research/primers',
  briefing: '/research/briefings',
  anomaly: '/research/anomalies',
  search: '/research/search',
  thesis: '/research/thesis',
  qa: '/research/qa',
  modelBuilder: '/research/model-builder',
};

export default function ResearchHub() {
  const navigate = useNavigate();

  const activeSecurity = useSecurityStore((s) => s.primary);
  const activeEntityId = activeSecurity?.entity_id;
  const activeTicker = activeSecurity?.ticker ?? '--';
  const { data: apiIntel, isLoading: intelLoading } = useCompanyIntelligence(activeEntityId);

  const activeModules = (apiIntel as Record<string, any>)?.modules as IntelModule[] | undefined;

  return (
    <div className="animate-in" style={{ padding: '16px', height: '100%', overflow: 'auto' }}>

      {/* Header */}
      <div style={{ marginBottom: '16px' }}>
        <h1 className="terminal-section-title" style={{ fontSize: 'var(--text-xl)', margin: 0 }}>
          AI Research Hub
        </h1>
        <p className="terminal-label" style={{ marginTop: '4px' }}>
          AI-powered research tools for fundamental analysis and intelligence gathering
        </p>
      </div>

      {/* Quick Intelligence — active security intel card */}
      {activeEntityId ? (
        <div style={{ marginBottom: 'var(--panel-gap, 8px)' }}>
          <h2 className="terminal-section-title" style={{ fontSize: 'var(--text-md)', margin: '0 0 8px 0' }}>
            Quick Intelligence &mdash; {activeTicker}
          </h2>
          <div style={{ maxWidth: 400 }}>
            {intelLoading ? (
              <div className="terminal-panel" style={{ display: 'flex', flexDirection: 'column', gap: '8px', padding: '16px' }}>
                <Skeleton width="140px" height="18px" />
                <Skeleton width="100%" height="16px" />
                <Skeleton width="100%" height="16px" />
                <Skeleton width="100%" height="16px" />
              </div>
            ) : activeModules ? (
              <CompanyIntelCard modules={activeModules} />
            ) : (
              <div className="terminal-panel" style={{ padding: '16px', textAlign: 'center' }}>
                <span className="terminal-label">No intelligence data available for {activeTicker}</span>
              </div>
            )}
          </div>
        </div>
      ) : (
        <div style={{ marginBottom: 'var(--panel-gap, 8px)' }}>
          <div className="terminal-panel" style={{ padding: '16px', textAlign: 'center' }}>
            <span className="terminal-label">Select a security to view Quick Intelligence</span>
          </div>
        </div>
      )}

      {/* Cards Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px' }}>
        {RESEARCH_CARDS.map((card) => (
          <div
            key={card.id}
            className="terminal-panel"
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '12px',
              cursor: 'pointer',
              borderTop: `2px solid ${card.accentColor}`,
              transition: 'background 0.15s',
            }}
            onMouseOver={(e) => { (e.currentTarget as HTMLDivElement).style.background = 'var(--color-surface-raised)'; }}
            onMouseOut={(e) => { (e.currentTarget as HTMLDivElement).style.background = 'var(--color-surface-base)'; }}
          >
            {/* Card Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '18px' }}>{card.icon}</span>
                <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-md)', fontWeight: 600, color: 'var(--color-text-primary)' }}>
                  {card.title}
                </span>
              </div>
              <span className={statusBadgeClass(card.status)}>{card.status}</span>
            </div>

            {/* Description */}
            <p style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-sm)',
              color: 'var(--color-text-secondary)',
              lineHeight: 1.5,
              margin: 0,
              flex: 1,
            }}>
              {card.description}
            </p>

            {/* Launch Button */}
            <button
              onClick={() => {
                const route = CARD_ROUTES[card.id];
                if (route) navigate(route);
              }}
              style={{
                fontFamily: 'var(--font-ui)',
                fontSize: 'var(--text-sm)',
                fontWeight: 500,
                padding: '6px 16px',
                background: card.status === 'Coming Soon' ? 'var(--color-surface-border)' : card.accentColor,
                color: card.status === 'Coming Soon' ? 'var(--color-text-tertiary)' : '#fff',
                border: 'none',
                borderRadius: '4px',
                cursor: card.status === 'Coming Soon' ? 'not-allowed' : 'pointer',
                alignSelf: 'flex-start',
              }}
              disabled={card.status === 'Coming Soon'}
            >
              {card.status === 'Coming Soon' ? 'Coming Soon' : 'Launch'}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
