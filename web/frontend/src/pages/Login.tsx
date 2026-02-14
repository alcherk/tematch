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
  const [devId, setDevId] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    window.onTelegramAuth = async (user) => {
      await apiFetch('/api/auth/telegram-login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(user),
      });
      window.location.href = '/dashboard'; // full reload to refresh auth state
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
      window.location.href = '/dashboard'; // full reload to refresh auth state
    } catch {
      setError('Login failed — check telegram_id');
    }
  };

  return (
    <div className="flex items-center justify-center h-screen bg-gray-50">
      <div className="text-center">
        <h1 className="text-3xl font-bold mb-8">Tematch Dashboard</h1>
        <div ref={widgetRef} />
        {/* Dev login — only works when WEB_DEV_LOGIN=true on server */}
        <div className="mt-8 border-t pt-6">
          <p className="text-sm text-gray-400 mb-2">Dev login</p>
          <div className="flex gap-2 justify-center">
            <input
              value={devId}
              onChange={(e) => setDevId(e.target.value)}
              placeholder="Telegram ID"
              className="border rounded px-3 py-1 text-sm w-40"
            />
            <button
              onClick={devLogin}
              className="bg-gray-600 text-white px-4 py-1 rounded text-sm hover:bg-gray-700"
            >
              Login
            </button>
          </div>
          {error && <p className="text-red-500 text-sm mt-2">{error}</p>}
        </div>
      </div>
    </div>
  );
}
