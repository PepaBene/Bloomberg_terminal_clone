import { useState, useCallback, useRef, useEffect } from 'react';
import type { CSSProperties, FormEvent } from 'react';
import { api } from '@/api/client';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: string[];
  isStreaming?: boolean;
}

export interface QAChatProps {
  ticker?: string;
  initialQuestion?: string;
}

export function QAChat({ ticker, initialQuestion }: QAChatProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState(initialQuestion ?? '');
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSubmit = useCallback(async (e: FormEvent) => {
    e.preventDefault();
    const question = input.trim();
    if (!question || loading) return;

    const userMsg: Message = {
      id: `u-${Date.now()}`,
      role: 'user',
      content: question,
    };

    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    const placeholderId = `a-${Date.now()}`;
    setMessages(prev => [...prev, {
      id: placeholderId,
      role: 'assistant',
      content: '',
      isStreaming: true,
    }]);

    try {
      const res = await api.post('/v3/research/qa/ask', {
        question,
        ticker,
        context: messages.slice(-6).map(m => ({ role: m.role, content: m.content })),
      });

      const data = res as { answer?: string; citations?: string[] };
      setMessages(prev => prev.map(m =>
        m.id === placeholderId
          ? { ...m, content: data.answer ?? 'No response.', citations: data.citations ?? [], isStreaming: false }
          : m
      ));
    } catch {
      setMessages(prev => prev.map(m =>
        m.id === placeholderId
          ? { ...m, content: 'Unable to get a response. Please try again.', isStreaming: false }
          : m
      ));
    } finally {
      setLoading(false);
    }
  }, [input, loading, ticker, messages]);

  const containerStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
    background: 'var(--color-surface-base)',
    border: '1px solid var(--color-surface-border)',
    borderRadius: 'var(--radius-md)',
    overflow: 'hidden',
  };

  const headerStyle: CSSProperties = {
    padding: 'var(--space-2) var(--space-3)',
    borderBottom: '1px solid var(--color-surface-border)',
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--space-2)',
    flexShrink: 0,
  };

  const messagesStyle: CSSProperties = {
    flex: 1,
    overflowY: 'auto',
    padding: 'var(--space-3)',
    display: 'flex',
    flexDirection: 'column',
    gap: 'var(--space-3)',
  };

  const inputRowStyle: CSSProperties = {
    padding: 'var(--space-2) var(--space-3)',
    borderTop: '1px solid var(--color-surface-border)',
    display: 'flex',
    gap: 'var(--space-2)',
    flexShrink: 0,
  };

  return (
    <div className="animate-in" style={containerStyle}>
      <div style={headerStyle}>
        <span style={{
          fontFamily: 'var(--font-ui)',
          fontSize: 'var(--text-sm)',
          fontWeight: 600,
          color: 'var(--color-text-primary)',
        }}>
          Analyst Q&A
        </span>
        {ticker && (
          <span style={{
            fontFamily: 'var(--font-data)',
            fontSize: 'var(--text-xs)',
            fontWeight: 700,
            color: 'var(--color-accent-primary)',
            background: 'color-mix(in srgb, var(--color-accent-primary) 12%, transparent)',
            padding: '1px 6px',
            borderRadius: 'var(--radius-sm)',
          }}>
            {ticker}
          </span>
        )}
      </div>

      <div ref={scrollRef} style={messagesStyle}>
        {messages.length === 0 && (
          <div style={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexDirection: 'column',
            gap: 'var(--space-2)',
            color: 'var(--color-text-tertiary)',
          }}>
            <span style={{ fontSize: 24 }}>💬</span>
            <span style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)' }}>
              Ask anything about {ticker ?? 'any company'}
            </span>
          </div>
        )}
        {messages.map(msg => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        {loading && (
          <div style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-xs)',
            color: 'var(--color-text-tertiary)',
            display: 'flex',
            gap: '4px',
          }}>
            <span className="animate-in">Thinking</span>
            <span style={{ animation: 'fadeIn 0.5s ease infinite alternate' }}>...</span>
          </div>
        )}
      </div>

      <form onSubmit={handleSubmit} style={inputRowStyle}>
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder={ticker ? `Ask about ${ticker}…` : 'Ask a question…'}
          disabled={loading}
          style={{
            flex: 1,
            background: 'var(--color-surface-raised)',
            border: '1px solid var(--color-surface-border)',
            borderRadius: 'var(--radius-sm)',
            padding: '0 var(--space-2)',
            height: 28,
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-sm)',
            color: 'var(--color-text-primary)',
            outline: 'none',
          }}
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          style={{
            background: loading || !input.trim() ? 'var(--color-surface-raised)' : 'var(--color-accent-primary)',
            color: loading || !input.trim() ? 'var(--color-text-tertiary)' : 'var(--color-text-inverse)',
            border: 'none',
            borderRadius: 'var(--radius-sm)',
            padding: '0 var(--space-3)',
            height: 28,
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-sm)',
            fontWeight: 500,
            cursor: loading || !input.trim() ? 'not-allowed' : 'pointer',
          }}
        >
          Ask
        </button>
      </form>
    </div>
  );
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user';

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: isUser ? 'flex-end' : 'flex-start',
      gap: '4px',
    }}>
      <div style={{
        maxWidth: '80%',
        background: isUser ? 'var(--color-accent-primary)' : 'var(--color-surface-raised)',
        border: `1px solid ${isUser ? 'transparent' : 'var(--color-surface-border)'}`,
        borderRadius: 'var(--radius-md)',
        padding: 'var(--space-2) var(--space-3)',
        fontFamily: 'var(--font-ui)',
        fontSize: 'var(--text-sm)',
        color: isUser ? 'var(--color-text-inverse)' : 'var(--color-text-primary)',
        lineHeight: 1.5,
      }}>
        {message.isStreaming ? (
          <span style={{ opacity: 0.6 }}>●●●</span>
        ) : message.content}
      </div>
      {message.citations && message.citations.length > 0 && (
        <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', maxWidth: '80%' }}>
          {message.citations.map((c, i) => (
            <span key={i} style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 'var(--text-xs)',
              color: 'var(--color-text-tertiary)',
              background: 'var(--color-surface-overlay)',
              border: '1px solid var(--color-surface-border)',
              padding: '1px 6px',
              borderRadius: 'var(--radius-sm)',
            }}>
              {c}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export default QAChat;
