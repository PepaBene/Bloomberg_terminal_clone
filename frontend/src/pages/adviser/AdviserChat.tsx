// ---------------------------------------------------------------------------
// Financial Adviser — streaming chat over a portfolio's live positions
// (AI_THREE_LAYER_REBUILD_PLAN.md §5.3/§8). Talks to
// src/api/routers/adviser_chat.py: POST /v5/adviser/conversations to open a
// thread, then POST .../messages, which streams the adviser's reasoning as
// Server-Sent Events (see api/client.ts's `stream()`) rather than a single
// JSON response.
// ---------------------------------------------------------------------------
import { useState, useRef, useEffect } from 'react';
import { api, ApiError } from '@/api/client';
import { ADVISER } from '@/api/endpoints';
import { usePortfolios } from '@/api/hooks/usePortfolios';
import type { Portfolio } from '@/types/portfolio';

const panelStyle: React.CSSProperties = { background: 'var(--color-surface-base)', border: '1px solid var(--color-surface-border)', borderRadius: '4px', padding: 'var(--panel-padding)', overflow: 'auto' };
const sectionTitle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)', margin: '0 0 12px 0' };
const labelStyle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' };

interface ChatMessage {
  role: 'user' | 'assistant' | 'error';
  text: string;
  time: string;
  disclaimer?: string;
}

interface Recommendation {
  id: string;
  kind: string;
  action: Record<string, unknown> | null;
  rationale: string;
  confidence: number | null;
  status: string;
}

interface StepEventData {
  tool_calls: string[];
  note: string | null;
}

interface DoneEventData {
  reply: string;
  disclaimer: string;
  recommendations: Recommendation[];
}

function timeNow(): string {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function statusColor(status: string): string {
  if (status === 'ACCEPTED') return 'var(--color-signal-positive)';
  if (status === 'DISMISSED') return 'var(--color-signal-negative)';
  return 'var(--color-signal-warning)';
}

export default function AdviserChat() {
  const { data: portfoliosData } = usePortfolios();
  const portfolios = (portfoliosData as Portfolio[] | undefined) ?? [];

  const [portfolioId, setPortfolioId] = useState('');
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [input, setInput] = useState('');
  const [starting, setStarting] = useState(false);
  const [sending, setSending] = useState(false);
  const [statusNote, setStatusNote] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages, statusNote]);

  const startConversation = async () => {
    if (!portfolioId || starting) return;
    setStarting(true);
    setMessages([]);
    setRecommendations([]);
    try {
      const convo = await api.post<{ id: string }>(ADVISER.createConversation, { portfolio_id: portfolioId });
      setConversationId(convo.id);
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail : err instanceof Error ? err.message : 'Unknown error';
      setMessages([{ role: 'error', text: `Could not start conversation: ${detail}`, time: timeNow() }]);
      setConversationId(null);
    }
    setStarting(false);
  };

  const handleSend = async () => {
    if (!input.trim() || !conversationId || sending) return;
    const question = input;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', text: question, time: timeNow() }]);
    setSending(true);
    setStatusNote(null);

    try {
      for await (const evt of api.stream(ADVISER.sendMessage(conversationId), { message: question })) {
        if (evt.event === 'step') {
          const step = evt.data as StepEventData;
          const toolNote = step.tool_calls.length > 0 ? `Using: ${step.tool_calls.join(', ')}` : null;
          setStatusNote(step.note || toolNote || 'Thinking...');
        } else if (evt.event === 'done') {
          const done = evt.data as DoneEventData;
          setMessages(prev => [...prev, { role: 'assistant', text: done.reply, time: timeNow(), disclaimer: done.disclaimer }]);
          setRecommendations(done.recommendations ?? []);
          setStatusNote(null);
        } else if (evt.event === 'error') {
          const data = evt.data as { message?: string };
          setMessages(prev => [...prev, { role: 'error', text: data.message || 'The adviser hit an error.', time: timeNow() }]);
          setStatusNote(null);
        }
      }
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail : err instanceof Error ? err.message : 'Unknown error';
      setMessages(prev => [...prev, { role: 'error', text: `Request failed: ${detail}`, time: timeNow() }]);
      setStatusNote(null);
    }
    setSending(false);
  };

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto', display: 'flex', flexDirection: 'column' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>Financial Adviser</h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>AI portfolio adviser — grounded in your live positions, drift, and compliance rules</p>
      </div>

      <div style={{ ...panelStyle, marginBottom: '12px', display: 'flex', gap: '8px', alignItems: 'center' }}>
        <span style={labelStyle}>Portfolio:</span>
        <select
          value={portfolioId}
          onChange={e => { setPortfolioId(e.target.value); setConversationId(null); setMessages([]); setRecommendations([]); }}
          style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', background: 'var(--color-surface-overlay)', border: '1px solid var(--color-surface-border)', borderRadius: '3px', padding: '6px 10px', minWidth: '220px' }}
        >
          <option value="">Select a portfolio...</option>
          {portfolios.map(p => (
            <option key={p.id} value={p.id}>{p.portfolio_name}</option>
          ))}
        </select>
        <button
          onClick={startConversation}
          disabled={!portfolioId || starting}
          style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-inverse)', background: !portfolioId || starting ? 'var(--color-surface-border)' : 'var(--color-accent-primary)', padding: '6px 16px', borderRadius: '3px', cursor: !portfolioId || starting ? 'not-allowed' : 'pointer', border: 'none' }}
        >
          {starting ? 'Starting...' : conversationId ? 'Restart conversation' : 'Start conversation'}
        </button>
        {conversationId && (
          <span style={{ ...labelStyle, fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>
            Conversation active — not personalized investment advice, for informational purposes only.
          </span>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '65fr 35fr', gap: 'var(--panel-gap)', flex: 1, alignItems: 'start', minHeight: 0 }}>
        {/* Chat area */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', height: '100%' }}>
          <div ref={scrollRef} style={{ display: 'flex', flexDirection: 'column', gap: '12px', overflow: 'auto', flex: 1 }}>
            {!conversationId && messages.length === 0 && (
              <div style={{ ...panelStyle, textAlign: 'center', padding: '32px' }}>
                <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-lg)', color: 'var(--color-text-tertiary)', marginBottom: '8px' }}>
                  Pick a portfolio and start a conversation
                </div>
                <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-tertiary)' }}>
                  Ask about drift, rebalancing trades, or a what-if scenario, grounded in that portfolio's real positions.
                </div>
              </div>
            )}
            {messages.map((msg, i) => (
              <div key={i} style={{ ...panelStyle, background: msg.role === 'user' ? 'var(--color-surface-overlay)' : 'var(--color-surface-base)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                  <span style={{
                    fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', fontWeight: 600,
                    color: msg.role === 'user' ? 'var(--color-accent-primary)' : msg.role === 'error' ? 'var(--color-signal-negative)' : 'var(--color-signal-positive)',
                  }}>
                    {msg.role === 'user' ? 'You' : msg.role === 'error' ? 'Error' : 'Adviser'}
                  </span>
                  <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>{msg.time}</span>
                </div>
                <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', lineHeight: 1.6, whiteSpace: 'pre-line' }}>{msg.text}</div>
                {msg.disclaimer && (
                  <div style={{ marginTop: '8px', fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)', fontStyle: 'italic' }}>
                    {msg.disclaimer}
                  </div>
                )}
              </div>
            ))}
            {sending && (
              <div style={{ ...panelStyle, display: 'flex', alignItems: 'center', gap: '8px' }}>
                <div style={{
                  width: '16px', height: '16px', border: '2px solid var(--color-surface-border)',
                  borderTopColor: 'var(--color-accent-primary)', borderRadius: '50%', animation: 'spin 0.8s linear infinite',
                }} />
                <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-tertiary)' }}>
                  {statusNote || 'Adviser is thinking...'}
                </span>
                <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
              </div>
            )}
          </div>
          {/* Input box */}
          <div style={{ ...panelStyle, display: 'flex', gap: '8px', alignItems: 'center' }}>
            <input
              type="text"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSend()}
              disabled={!conversationId || sending}
              placeholder={conversationId ? 'Ask about drift, a what-if trade, or a rebalance...' : 'Start a conversation to begin chatting'}
              style={{ flex: 1, fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', background: 'var(--color-surface-overlay)', border: '1px solid var(--color-surface-border)', borderRadius: '3px', padding: '8px 12px' }}
            />
            <button
              onClick={handleSend}
              disabled={!conversationId || sending || !input.trim()}
              style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-inverse)', background: !conversationId || sending || !input.trim() ? 'var(--color-surface-border)' : 'var(--color-accent-primary)', padding: '6px 16px', borderRadius: '3px', cursor: !conversationId || sending || !input.trim() ? 'not-allowed' : 'pointer', border: 'none' }}
            >
              {sending ? 'Sending...' : 'Send'}
            </button>
          </div>
        </div>

        {/* Recommendations panel */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Recommendations</h2>
          {recommendations.length === 0 ? (
            <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-tertiary)' }}>
              None yet this turn. The adviser only proposes a recommendation when it has cited evidence and the trade passes a real compliance check.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {recommendations.map(rec => (
                <div key={rec.id} style={{ background: 'var(--color-surface-overlay)', borderRadius: '4px', padding: '10px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                    <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-text-primary)' }}>{rec.kind}</span>
                    <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', color: statusColor(rec.status) }}>{rec.status}</span>
                  </div>
                  <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', lineHeight: 1.5 }}>{rec.rationale}</div>
                  {rec.confidence != null && (
                    <div style={{ marginTop: '4px', fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>
                      Confidence: {Math.round(rec.confidence * 100)}%
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
