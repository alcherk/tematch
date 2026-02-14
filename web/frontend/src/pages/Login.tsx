import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiFetch } from '../api';

declare global {
  interface Window {
    onTelegramAuth: (user: Record<string, unknown>) => void;
  }
}

export default function Login() {
  const navigate = useNavigate();
  const widgetRef = useRef<HTMLDivElement>(null);
  const [devId, setDevId] = useState(() => localStorage.getItem('devLoginId') || '');
  const [error, setError] = useState('');

  useEffect(() => {
    window.onTelegramAuth = async (user) => {
      await apiFetch('/api/auth/telegram-login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(user),
      });
      window.location.href = '/dashboard';
    };

    const script = document.createElement('script');
    script.src = 'https://telegram.org/js/telegram-widget.js?22';
    script.setAttribute('data-telegram-login', import.meta.env.VITE_BOT_USERNAME || 'tematch_bot');
    script.setAttribute('data-size', 'large');
    script.setAttribute('data-onauth', 'onTelegramAuth(user)');
    script.setAttribute('data-request-access', 'write');
    script.async = true;
    widgetRef.current?.appendChild(script);
  }, [navigate]);

  const devLogin = async () => {
    setError('');
    try {
      await apiFetch('/api/auth/dev-login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ telegram_id: parseInt(devId) }),
      });
      localStorage.setItem('devLoginId', devId);
      window.location.href = '/dashboard';
    } catch {
      setError('Login failed — check telegram_id');
    }
  };

  return (
    <div className="flex items-center justify-center h-screen" style={{ background: 'var(--bg-deep)' }}>
      {/* Subtle grid background */}
      <div style={{
        position: 'fixed', inset: 0, opacity: 0.03,
        backgroundImage: 'linear-gradient(var(--cyan) 1px, transparent 1px), linear-gradient(90deg, var(--cyan) 1px, transparent 1px)',
        backgroundSize: '60px 60px',
        pointerEvents: 'none',
      }} />

      <div className="text-center animate-in" style={{ position: 'relative', zIndex: 1 }}>
        {/* Brand */}
        <h1 style={{
          fontFamily: 'var(--font-brand)',
          fontSize: '2.2rem',
          color: 'var(--cyan)',
          letterSpacing: '0.25em',
          textShadow: '0 0 30px rgba(0, 240, 255, 0.3)',
        }}>
          TEMATCH
        </h1>
        <p style={{
          fontFamily: 'var(--font-heading)',
          fontSize: '0.7rem',
          color: 'var(--text-muted)',
          letterSpacing: '0.3em',
          textTransform: 'uppercase',
          marginTop: '0.5rem',
        }}>
          Content Curator Dashboard
        </p>

        {/* Telegram widget */}
        <div ref={widgetRef} className="mt-10" />

        {/* Divider */}
        <hr className="cyber-divider" style={{ maxWidth: '300px', margin: '2rem auto' }} />

        {/* Dev login */}
        <p className="cyber-label" style={{ marginBottom: '0.75rem' }}>Dev Access</p>
        <div className="flex gap-2 justify-center">
          <input
            value={devId}
            onChange={(e) => setDevId(e.target.value)}
            placeholder="Telegram ID"
            className="cyber-input"
            style={{ width: '160px' }}
            onKeyDown={(e) => e.key === 'Enter' && devLogin()}
          />
          <button onClick={devLogin} className="cyber-btn cyber-btn-solid">
            Enter
          </button>
        </div>
        {error && (
          <p style={{ color: 'var(--neon-red)', fontFamily: 'var(--font-mono)', fontSize: '0.75rem', marginTop: '0.75rem' }}>
            {error}
          </p>
        )}
      </div>
    </div>
  );
}
