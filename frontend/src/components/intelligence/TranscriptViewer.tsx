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

const ROLE_COLORS: Record<string, string> = {
  CEO: 'var(--color-signal-positive)',
  CFO: 'var(--color-accent-primary)',
  COO: 'var(--color-signal-highlight)',
  Analyst: 'var(--color-signal-neutral)',
};

const SENTIMENT_BG: Record<string, string> = {
  positive: 'rgba(45, 184, 125, 0.08)',
  negative: 'rgba(224, 82, 82, 0.08)',
  hedging: 'rgba(224, 146, 58, 0.08)',
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
      className={clsx('flex', className)}
      style={{
        background: 'var(--color-surface-base)',
        border: '1px solid var(--color-surface-border)',
        borderRadius: 'var(--border-radius-md, 4px)',
        overflow: 'hidden',
        minHeight: 300,
      }}
    >
      {/* Main transcript area */}
      <div className="flex flex-1 flex-col" style={{ minWidth: 0 }}>
        {/* Section tabs */}
        <div
          className="flex gap-0"
          style={{
            borderBottom: '1px solid var(--color-surface-border)',
          }}
        >
          {sections.map((s, idx) => (
            <button
              key={s.title}
              type="button"
              onClick={() => handleSectionClick(idx)}
              style={{
                padding: '8px 16px',
                fontFamily: 'var(--font-ui)',
                fontSize: 'var(--text-xs)',
                fontWeight: 600,
                color: idx === activeSection
                  ? 'var(--color-accent-primary)'
                  : 'var(--color-text-secondary)',
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
                background: idx === activeSection
                  ? 'var(--color-surface-raised)'
                  : 'transparent',
                border: 'none',
                borderBottom: idx === activeSection
                  ? '2px solid var(--color-accent-primary)'
                  : '2px solid transparent',
                cursor: 'pointer',
                transition: 'color 0.15s',
              }}
            >
              {s.title}
            </button>
          ))}
        </div>

        {/* Paragraphs */}
        <div className="flex-1 overflow-auto" style={{ padding: '12px 16px' }}>
          {sections[activeSection]?.paragraphs.map((p, idx) => (
            <ParagraphRow key={idx} paragraph={p} />
          ))}
        </div>
      </div>

      {/* Tone scores sidebar */}
      {toneScores && (
        <div
          className="flex flex-col gap-3 shrink-0"
          style={{
            width: 180,
            padding: '12px 16px',
            borderLeft: '1px solid var(--color-surface-border)',
            background: 'var(--color-surface-raised)',
          }}
        >
          <span
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-xs)',
              fontWeight: 600,
              color: 'var(--color-text-secondary)',
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
  const roleColor = ROLE_COLORS[paragraph.role] ?? 'var(--color-text-tertiary)';
  const bgColor = SENTIMENT_BG[paragraph.sentiment ?? 'neutral'] ?? 'transparent';

  return (
    <div
      style={{
        display: 'flex',
        gap: 12,
        padding: '8px 0',
        borderBottom: '1px solid var(--color-surface-border)',
      }}
    >
      {/* Speaker badge */}
      <div
        className="flex flex-col items-start gap-1 shrink-0"
        style={{ width: 100 }}
      >
        <span
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-sm)',
            fontWeight: 600,
            color: 'var(--color-text-primary)',
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
            color: roleColor,
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            padding: '1px 6px',
            border: `1px solid ${roleColor}`,
            borderRadius: '9999px',
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
          color: 'var(--color-text-primary)',
          lineHeight: 1.6,
          padding: '4px 8px',
          background: bgColor,
          borderRadius: 4,
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
  const barColor =
    pct >= 60
      ? 'var(--color-signal-positive)'
      : pct >= 30
        ? 'var(--color-signal-neutral)'
        : 'var(--color-signal-warning)';

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-baseline justify-between">
        <span
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: '10px',
            color: 'var(--color-text-primary)',
          }}
        >
          {label}
        </span>
        <span
          style={{
            fontFamily: 'var(--font-data)',
            fontSize: '10px',
            color: barColor,
            fontVariantNumeric: 'tabular-nums',
          }}
        >
          {pct}%
        </span>
      </div>
      <div
        style={{
          height: 4,
          borderRadius: 2,
          background: 'var(--color-surface-overlay, rgba(255,255,255,0.06))',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            height: '100%',
            width: `${pct}%`,
            background: barColor,
            borderRadius: 2,
            transition: 'width var(--transition-normal, 0.2s)',
          }}
        />
      </div>
    </div>
  );
}
