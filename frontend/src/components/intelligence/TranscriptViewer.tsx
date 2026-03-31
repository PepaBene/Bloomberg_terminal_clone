import { useState, useCallback } from 'react';
import clsx from 'clsx';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface TranscriptParagraph {
  speaker: string;
  role: string;
  text: string;
  sentiment?: 'positive' | 'negative' | 'hedging' | 'neutral';
}

export interface TranscriptSection {
  title: string;
  paragraphs: TranscriptParagraph[];
}

export interface ToneScores {
  confidence: number;
  hedging: number;
  forwardLooking: number;
}

export interface TranscriptViewerProps {
  sections: TranscriptSection[];
  toneScores?: ToneScores;
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const ROLE_BADGE: Record<string, { color: string; bg: string }> = {
  CEO: {
    color: 'var(--accent-primary)',
    bg: 'color-mix(in srgb, var(--accent-primary) 15%, transparent)',
  },
  CFO: {
    color: 'var(--chart-3)',
    bg: 'color-mix(in srgb, var(--chart-3) 15%, transparent)',
  },
  COO: {
    color: 'var(--signal-highlight)',
    bg: 'color-mix(in srgb, var(--signal-highlight) 15%, transparent)',
  },
  Analyst: {
    color: 'var(--text-secondary)',
    bg: 'color-mix(in srgb, var(--text-secondary) 15%, transparent)',
  },
};

const SENTIMENT_BG: Record<string, string> = {
  positive: 'color-mix(in srgb, var(--signal-positive) 8%, transparent)',
  negative: 'color-mix(in srgb, var(--signal-negative) 8%, transparent)',
  hedging: 'color-mix(in srgb, var(--signal-warning) 8%, transparent)',
  neutral: 'transparent',
};

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function TranscriptViewer({
  sections,
  toneScores,
  className,
}: TranscriptViewerProps) {
  const [activeSection, setActiveSection] = useState<number>(0);

  const handleSectionClick = useCallback((idx: number) => {
    setActiveSection(idx);
  }, []);

  return (
    <div
      className={clsx('animate-in', className)}
      style={{
        display: 'flex',
        background: 'var(--surface-base)',
        border: '1px solid var(--surface-border)',
        borderRadius: 'var(--radius-sm)',
        overflow: 'hidden',
        minHeight: 300,
      }}
    >
      {/* Main transcript area */}
      <div style={{ display: 'flex', flex: 1, flexDirection: 'column', minWidth: 0 }}>
        {/* Section tabs */}
        <div
          style={{
            display: 'flex',
            gap: 0,
            borderBottom: '1px solid var(--surface-border)',
          }}
        >
          {sections.map((s, idx) => (
            <button
              key={s.title}
              type="button"
              onClick={() => handleSectionClick(idx)}
              style={{
                padding: 'var(--space-2) var(--space-4)',
                fontFamily: 'var(--font-ui)',
                fontSize: 'var(--text-xs)',
                fontWeight: 600,
                color: idx === activeSection
                  ? 'var(--accent-primary)'
                  : 'var(--text-tertiary)',
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
                background: 'transparent',
                border: 'none',
                borderBottom: idx === activeSection
                  ? '2px solid var(--accent-primary)'
                  : '2px solid transparent',
                cursor: 'pointer',
                transition: 'color var(--transition-fast), border-color var(--transition-fast)',
              }}
              onMouseEnter={(e) => {
                if (idx !== activeSection) {
                  e.currentTarget.style.color = 'var(--text-secondary)';
                }
              }}
              onMouseLeave={(e) => {
                if (idx !== activeSection) {
                  e.currentTarget.style.color = 'var(--text-tertiary)';
                }
              }}
            >
              {s.title}
            </button>
          ))}
        </div>

        {/* Paragraphs */}
        <div style={{ flex: 1, overflow: 'auto', padding: 'var(--space-3) var(--space-4)' }}>
          {sections[activeSection]?.paragraphs.map((p, idx) => (
            <ParagraphRow key={idx} paragraph={p} />
          ))}
        </div>
      </div>

      {/* Tone scores sidebar */}
      {toneScores && (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--space-3)',
            flexShrink: 0,
            width: 180,
            padding: 'var(--space-3) var(--space-4)',
            borderLeft: '1px solid var(--surface-border)',
            background: 'var(--surface-raised)',
          }}
        >
          <span
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-xs)',
              fontWeight: 600,
              color: 'var(--text-secondary)',
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
            }}
          >
            Tone Analysis
          </span>
          <ToneBar label="Confidence" value={toneScores.confidence} />
          <ToneBar label="Hedging" value={toneScores.hedging} />
          <ToneBar label="Forward-Looking" value={toneScores.forwardLooking} />
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Paragraph row                                                      */
/* ------------------------------------------------------------------ */

function ParagraphRow({ paragraph }: { paragraph: TranscriptParagraph }) {
  const badge = ROLE_BADGE[paragraph.role] ?? {
    color: 'var(--text-tertiary)',
    bg: 'color-mix(in srgb, var(--text-tertiary) 15%, transparent)',
  };
  const bgColor = SENTIMENT_BG[paragraph.sentiment ?? 'neutral'] ?? 'transparent';

  return (
    <div
      style={{
        display: 'flex',
        gap: 'var(--space-3)',
        padding: 'var(--space-2) 0',
        borderBottom: '1px solid var(--surface-border)',
      }}
    >
      {/* Speaker badge */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'flex-start',
          gap: 'var(--space-1)',
          flexShrink: 0,
          width: 100,
        }}
      >
        <span
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-sm)',
            fontWeight: 600,
            color: 'var(--text-primary)',
            lineHeight: 1.3,
          }}
        >
          {paragraph.speaker}
        </span>
        <span
          style={{
            fontFamily: 'var(--font-data)',
            fontSize: 'var(--text-xs)',
            fontWeight: 500,
            fontVariantNumeric: 'tabular-nums',
            color: badge.color,
            background: badge.bg,
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            padding: '1px var(--space-1)',
            borderRadius: 'var(--radius-sm)',
            whiteSpace: 'nowrap',
          }}
        >
          {paragraph.role}
        </span>
      </div>

      {/* Text */}
      <div
        style={{
          flex: 1,
          fontFamily: 'var(--font-ui)',
          fontSize: 'var(--text-sm)',
          color: 'var(--text-primary)',
          lineHeight: 1.6,
          padding: 'var(--space-1) var(--space-2)',
          background: bgColor,
          borderRadius: 'var(--radius-sm)',
        }}
      >
        {paragraph.text}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Tone bar                                                           */
/* ------------------------------------------------------------------ */

function ToneBar({ label, value }: { label: string; value: number }) {
  const pct = Math.max(0, Math.min(100, value));
  const barColor = qualityTierColor(pct);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
        <span
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-xs)',
            color: 'var(--text-primary)',
          }}
        >
          {label}
        </span>
        <span
          style={{
            fontFamily: 'var(--font-data)',
            fontSize: 'var(--text-xs)',
            fontVariantNumeric: 'tabular-nums',
            color: barColor,
          }}
        >
          {pct}%
        </span>
      </div>
      <div
        style={{
          height: 4,
          borderRadius: 'var(--radius-sm)',
          background: 'var(--surface-overlay)',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            height: '100%',
            width: `${pct}%`,
            background: barColor,
            borderRadius: 'var(--radius-sm)',
            transition: 'width var(--transition-normal)',
          }}
        />
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function qualityTierColor(pct: number): string {
  if (pct >= 80) return 'var(--quality-5)';
  if (pct >= 60) return 'var(--quality-4)';
  if (pct >= 40) return 'var(--quality-3)';
  if (pct >= 20) return 'var(--quality-2)';
  return 'var(--quality-1)';
}
