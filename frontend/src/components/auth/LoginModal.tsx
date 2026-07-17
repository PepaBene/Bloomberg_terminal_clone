import { useEffect, useRef, useState } from 'react';
import { useLogin, useRegister } from '@/api/hooks/useAuth';
import { ApiError } from '@/api/client';

interface LoginModalProps {
  open: boolean;
  onClose: () => void;
  /** Shown above the form when the modal was opened because an action needed auth. */
  reason?: string;
}

const labelStyle: React.CSSProperties = { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' };

export function LoginModal({ open, onClose, reason }: LoginModalProps) {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [email, setEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const login = useLogin();
  const register = useRegister();

  useEffect(() => {
    if (open) {
      setError(null);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open, mode]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  const busy = login.isPending || register.isPending;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      if (mode === 'login') {
        await login.mutateAsync({ username, password });
        onClose();
      } else {
        await register.mutateAsync({ username, email, password, full_name: fullName || undefined });
        // Registration doesn't return a token -- sign in immediately with
        // the credentials just created so the flow feels like one step.
        await login.mutateAsync({ username, password });
        onClose();
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Something went wrong. Please try again.');
    }
  };

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center"
      style={{ background: 'rgba(0, 0, 0, 0.6)' }}
      onClick={onClose}
    >
      <div
        style={{
          width: '340px',
          background: 'var(--color-surface-raised)',
          border: '1px solid var(--color-surface-border)',
          borderRadius: '6px',
          boxShadow: '0 4px 16px rgba(0,0,0,0.6)',
          padding: '20px',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <h2 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)', margin: '0 0 4px 0' }}>
          {mode === 'login' ? 'Sign In' : 'Create Account'}
        </h2>
        {reason && (
          <p style={{ ...labelStyle, fontSize: 'var(--text-xs)', margin: '0 0 12px 0' }}>{reason}</p>
        )}
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginTop: reason ? 0 : '12px' }}>
          <div>
            <div style={labelStyle}>Username</div>
            <input
              ref={inputRef}
              type="text"
              className="terminal-input"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              style={{ width: '100%' }}
              required
              autoComplete="username"
            />
          </div>
          {mode === 'register' && (
            <div>
              <div style={labelStyle}>Email</div>
              <input
                type="email"
                className="terminal-input"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                style={{ width: '100%' }}
                required
                autoComplete="email"
              />
            </div>
          )}
          {mode === 'register' && (
            <div>
              <div style={labelStyle}>Full Name (optional)</div>
              <input
                type="text"
                className="terminal-input"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                style={{ width: '100%' }}
                autoComplete="name"
              />
            </div>
          )}
          <div>
            <div style={labelStyle}>Password</div>
            <input
              type="password"
              className="terminal-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={{ width: '100%' }}
              required
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            />
          </div>
          {error && (
            <div style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xs)', color: 'var(--color-signal-negative)' }}>{error}</div>
          )}
          <button type="submit" className="btn-primary" disabled={busy} style={{ marginTop: '4px' }}>
            {busy ? (mode === 'login' ? 'Signing in...' : 'Creating account...') : mode === 'login' ? 'Sign In' : 'Create Account'}
          </button>
        </form>
        <button
          className="btn-ghost"
          onClick={() => setMode(mode === 'login' ? 'register' : 'login')}
          style={{ marginTop: '10px', width: '100%', fontSize: 'var(--text-xs)' }}
        >
          {mode === 'login' ? "Don't have an account? Create one" : 'Already have an account? Sign in'}
        </button>
      </div>
    </div>
  );
}
