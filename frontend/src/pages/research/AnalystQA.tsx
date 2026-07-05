// ---------------------------------------------------------------------------
// Analyst Q&A — Chat-Style Interface with Suggested Questions
// ---------------------------------------------------------------------------
import { useState } from 'react';
import { api } from '@/api/client';
import { RESEARCH } from '@/api/endpoints';
const panelStyle: React.CSSProperties = { background: 'var(--color-surface-base)', border: '1px solid var(--color-surface-border)', borderRadius: '4px', padding: 'var(--panel-padding)', overflow: 'auto' };
const sectionTitle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)', margin: '0 0 12px 0' };
const labelStyle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' };

// F-003: removed the prepopulated multi-turn Apple/MSFT/GOOGL chat
// transcript. A user opening the page fresh now sees an empty chat
// instead of a fabricated conversation about a specific company.
const suggestedQuestions: string[] = [
  'Summarise the latest 10-K risk factors',
  'Compare gross margins for two tickers over the last 8 quarters',
  'Which companies have the highest buyback yield?',
  'What changed between Q1 and Q4 earnings calls for a given ticker?',
];

interface ChatMessage {
  role: 'user' | 'assistant';
  text: string;
  time: string;
  sources?: string[];
  confidence?: number;
}

export default function AnalystQA() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [asking, setAsking] = useState(false);

  const handleAsk = async () => {
    if (!input.trim() || asking) return;
    const userMsg: ChatMessage = { role: 'user', text: input, time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) };
    setMessages(prev => [...prev, userMsg]);
    const question = input;
    setInput('');
    setAsking(true);
    try {
      const isFollowUp = messages.length > 0;
      const endpoint = isFollowUp ? RESEARCH.qa.followUp : RESEARCH.qa.ask;
      const res = await api.post(endpoint, { question });
      const data = res as Record<string, any>;
      const answer: ChatMessage = {
        role: 'assistant',
        text: data?.answer ?? data?.text ?? 'No response available.',
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        sources: data?.sources ?? [],
        confidence: data?.confidence ?? 0,
      };
      setMessages(prev => [...prev, answer]);
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Unknown error';
      console.error('Q&A request failed:', err);
      setMessages(prev => [...prev, {
        role: 'assistant',
        text: `Error: Unable to get response. ${errorMsg}`,
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        sources: [],
        confidence: 0,
      }]);
    }
    setAsking(false);
  };

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto', display: 'flex', flexDirection: 'column' }}>
      <div style={{ marginBottom: '16px' }}>
        <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>Analyst Q&amp;A</h1>
        <p style={{ ...labelStyle, marginTop: '4px' }}>AI-powered research assistant with source attribution</p>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '65fr 35fr', gap: 'var(--panel-gap)', flex: 1, alignItems: 'start' }}>
        {/* Chat Area */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {messages.length === 0 && (
            <div style={{ ...panelStyle, textAlign: 'center', padding: '32px' }}>
              <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-lg)', color: 'var(--color-text-tertiary)', marginBottom: '8px' }}>
                Ask a question to get started
              </div>
              <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-tertiary)' }}>
                Try one of the suggested questions, or type your own below.
              </div>
            </div>
          )}
          {messages.map((msg, i) => (
            <div key={i} style={{ ...panelStyle, background: msg.role === 'user' ? 'var(--color-surface-overlay)' : 'var(--color-surface-base)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', fontWeight: 600, color: msg.role === 'user' ? 'var(--color-accent-primary)' : 'var(--color-signal-positive)' }}>
                  {msg.role === 'user' ? 'You' : 'AI Analyst'}
                </span>
                <span style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>{msg.time}</span>
              </div>
              <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', lineHeight: 1.6, whiteSpace: 'pre-line' }}>{msg.text}</div>
              {msg.role === 'assistant' && (
                <div style={{ marginTop: '8px', display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
                  <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>Sources:</span>
                  {msg.sources?.map((s) => (
                    <span key={s} style={{ fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', color: 'var(--color-accent-primary)', background: 'var(--color-surface-overlay)', padding: '1px 5px', borderRadius: '2px' }}>{s}</span>
                  ))}
                  <span style={{ marginLeft: 'auto', fontFamily: 'var(--font-data)', fontSize: 'var(--text-xs)', color: 'var(--color-signal-positive)' }}>Confidence: {msg.confidence}%</span>
                </div>
              )}
            </div>
          ))}
          {/* Loading spinner while waiting for response */}
          {asking && (
            <div style={{ ...panelStyle, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{
                width: '16px',
                height: '16px',
                border: '2px solid var(--color-surface-border)',
                borderTopColor: 'var(--color-accent-primary)',
                borderRadius: '50%',
                animation: 'spin 0.8s linear infinite',
              }} />
              <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-tertiary)' }}>AI Analyst is thinking...</span>
              <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
            </div>
          )}
          {/* Input Box */}
          <div style={{ ...panelStyle, display: 'flex', gap: '8px', alignItems: 'center' }}>
            <input
              type="text"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleAsk()}
              placeholder="Ask a question about any company, sector, or market..."
              style={{ flex: 1, fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', background: 'var(--color-surface-overlay)', border: '1px solid var(--color-surface-border)', borderRadius: '3px', padding: '8px 12px' }}
            />
            <button onClick={handleAsk} disabled={asking} style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-text-inverse)', background: asking ? 'var(--color-surface-border)' : 'var(--color-accent-primary)', padding: '6px 16px', borderRadius: '3px', cursor: asking ? 'not-allowed' : 'pointer', border: 'none' }}>
              {asking ? 'Asking...' : 'Ask'}
            </button>
          </div>
        </div>
        {/* Suggested Questions */}
        <div style={panelStyle}>
          <h2 style={sectionTitle}>Suggested Questions</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {suggestedQuestions.map((q, i) => (
              <div key={i} onClick={() => setInput(q)} style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-accent-primary)', padding: '8px', background: 'var(--color-surface-overlay)', borderRadius: '4px', cursor: 'pointer', lineHeight: 1.4 }}>{q}</div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
