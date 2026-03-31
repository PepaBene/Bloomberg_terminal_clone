import { useState, useEffect } from 'react';
import type { CSSProperties } from 'react';
import { api } from '@/api/client';
import { SignalBadge } from '@/components/ui/SignalBadge';
import type { SignalVariant } from '@/components/ui/SignalBadge';

export interface CorporateActionQueueProps {
  portfolioId: string;
}

interface CorporateAction {
  id: string;
  type: 'SPLIT' | 'DIV' | 'MERGER' | string;
  ticker: string;
  description: string;
  date: string;
  status?: string;
}

function actionVariant(type: string): SignalVariant {
  switch (type) {
    case 'SPLIT': return 'warning';
    case 'DIV': return 'positive';
    case 'MERGER': return 'neutral';
    default: return 'neutral';
  }
}

export function CorporateActionQueue({ portfolioId }: CorporateActionQueueProps) {
  const [actions, setActions] = useState<CorporateAction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [applying, setApplying] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .get(`/v1/portfolios/${portfolioId}/corporate-actions`)
      .then((data: unknown) => {
        if (!cancelled) {
          setActions(Array.isArray(data) ? (data as CorporateAction[]) : []);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [portfolioId]);

  const handleApply = async (action: CorporateAction) => {
    setApplying(action.id);
    try {
      await api.post(
        `/v1/portfolios/${portfolioId}/corporate-actions/${action.id}/apply`,
        {},
      );
      setActions((prev) => prev.filter((a) => a.id !== action.id));
    } catch {
      // no-op: could show toast
    } finally {
      setApplying(null);
    }
  };

  const rootStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: 'var(--space-2)',
  };

  const cardStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--space-3)',
    padding: 'var(--space-3)',
    background: 'var(--color-surface-raised)',
    border: '1px solid var(--color-surface-border)',
    borderRadius: 'var(--radius-sm)',
  };

  if (loading) {
    return (
      <div className="animate-in" style={{ color: 'var(--color-text-tertiary)', fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', padding: 'var(--space-4)' }}>
        Loading corporate actions...
      </div>
    );
  }

  if (error) {
    return (
      <div className="animate-in" style={{ color: 'var(--color-signal-negative)', fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', padding: 'var(--space-4)' }}>
        {error}
      </div>
    );
  }

  if (actions.length === 0) {
    return (
      <div className="animate-in" style={{ color: 'var(--color-text-tertiary)', fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', padding: 'var(--space-4)' }}>
        No pending corporate actions.
      </div>
    );
  }

  return (
    <div className="animate-in" style={rootStyle}>
      {actions.map((action) => (
        <div key={action.id} style={cardStyle}>
          <SignalBadge label={action.type} variant={actionVariant(action.type)} />

          <span
            style={{
              fontFamily: 'var(--font-data)',
              fontWeight: 700,
              fontSize: 'var(--text-sm)',
              color: 'var(--color-accent-primary)',
              minWidth: '60px',
            }}
          >
            {action.ticker}
          </span>

          <span
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-sm)',
              color: 'var(--color-text-primary)',
              flex: 1,
            }}
          >
            {action.description}
          </span>

          <span
            style={{
              fontFamily: 'var(--font-data)',
              fontSize: 'var(--text-xs)',
              color: 'var(--color-text-tertiary)',
              whiteSpace: 'nowrap',
            }}
          >
            {action.date}
          </span>

          <button
            type="button"
            onClick={() => handleApply(action)}
            disabled={applying === action.id}
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-xs)',
              fontWeight: 600,
              padding: '3px 10px',
              height: '24px',
              background: 'var(--color-accent-primary)',
              color: 'var(--color-surface-void)',
              border: 'none',
              borderRadius: 'var(--radius-sm)',
              cursor: applying === action.id ? 'not-allowed' : 'pointer',
              opacity: applying === action.id ? 0.6 : 1,
              whiteSpace: 'nowrap',
            }}
          >
            {applying === action.id ? 'Applying...' : 'Apply'}
          </button>
        </div>
      ))}
    </div>
  );
}

export default CorporateActionQueue;
