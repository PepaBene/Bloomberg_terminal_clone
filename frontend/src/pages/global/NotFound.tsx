// ---------------------------------------------------------------------------
// 404 — Not Found
// ---------------------------------------------------------------------------
import { useNavigate } from 'react-router-dom';

export default function NotFound() {
  const navigate = useNavigate();

  return (
    <div
      className="animate-in"
      style={{
        padding: '16px',
        height: '100%',
        overflow: 'auto',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '16px',
      }}
    >
      <span style={{ fontSize: '48px', fontFamily: 'var(--font-data)', fontWeight: 700, color: 'var(--color-text-tertiary)' }}>
        404
      </span>
      <h1 style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
        Page Not Found
      </h1>
      <p style={{ fontFamily: 'var(--font-ui)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)', margin: 0, textAlign: 'center', maxWidth: '400px' }}>
        The page you're looking for doesn't exist or has been moved.
      </p>
      <div style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
        <button
          onClick={() => navigate(-1)}
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-sm)',
            fontWeight: 500,
            padding: '8px 20px',
            background: 'var(--color-surface-overlay)',
            color: 'var(--color-text-primary)',
            border: '1px solid var(--color-surface-border)',
            borderRadius: '4px',
            cursor: 'pointer',
          }}
        >
          Go Back
        </button>
        <button
          onClick={() => navigate('/')}
          style={{
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-sm)',
            fontWeight: 500,
            padding: '8px 20px',
            background: 'var(--color-accent-primary)',
            color: '#fff',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
          }}
        >
          Home
        </button>
      </div>
    </div>
  );
}
