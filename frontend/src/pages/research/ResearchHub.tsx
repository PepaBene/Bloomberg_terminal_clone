// ---------------------------------------------------------------------------
// AI Research Hub
// ---------------------------------------------------------------------------

const panelStyle: React.CSSProperties = {
  background: 'var(--color-surface-base)',
  border: '1px solid var(--color-surface-border)',
  borderRadius: '4px',
  padding: 'var(--panel-padding)',
};

const labelStyle: React.CSSProperties = {
  fontFamily: 'var(--font-ui)',
  fontSize: 'var(--text-sm)',
  color: 'var(--color-text-secondary)',
};

// --- Mock Data ---------------------------------------------------------------

interface ResearchCard {
  id: string;
  title: string;
  description: string;
  icon: string;
  accentColor: string;
  status: 'Available' | 'Beta' | 'Coming Soon';
}

const researchCards: ResearchCard[] = [
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
];

function statusBadge(status: ResearchCard['status']): React.CSSProperties {
  const base: React.CSSProperties = {
    fontFamily: 'var(--font-ui)',
    fontSize: 'var(--text-xs)',
    padding: '2px 8px',
    borderRadius: '2px',
    fontWeight: 500,
  };
  switch (status) {
    case 'Available':
      return { ...base, background: 'rgba(45, 184, 125, 0.15)', color: 'var(--color-signal-positive)' };
    case 'Beta':
      return { ...base, background: 'rgba(212, 168, 67, 0.15)', color: 'var(--color-signal-highlight)' };
    case 'Coming Soon':
      return { ...base, background: 'rgba(84, 95, 107, 0.15)', color: 'var(--color-text-tertiary)' };
  }
}

// --- Component ---------------------------------------------------------------

export default function ResearchHub() {
  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>

      {/* Header */}
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          AI Research Hub
        </h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>
          AI-powered research tools for fundamental analysis and intelligence gathering
        </p>
      </div>

      {/* Cards Grid — 3 columns */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px' }}>
        {researchCards.map((card) => (
          <div
            key={card.id}
            style={{
              ...panelStyle,
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
              <span style={statusBadge(card.status)}>{card.status}</span>
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
