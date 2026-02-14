import { lazy, Suspense, useEffect, useState } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { apiFetch } from './api';
import Layout from './components/Layout';
import ChannelMessages from './pages/ChannelMessages';
import Dashboard from './pages/Dashboard';
import Login from './pages/Login';

const Admin = lazy(() => import('./pages/Admin'));

function App() {
  const [user, setUser] = useState<{ telegram_id: number; is_admin: boolean } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch<{ telegram_id: number; is_admin: boolean }>('/api/auth/me')
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="flex items-center justify-center h-screen" style={{ background: 'var(--bg-deep)' }}>
      <p className="cyber-mono" style={{ color: 'var(--text-muted)', letterSpacing: '0.15em' }}>LOADING...</p>
    </div>
  );

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={user ? <Navigate to="/dashboard" /> : <Login />} />
        <Route element={user ? <Layout isAdmin={user.is_admin} /> : <Navigate to="/login" />}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/channels/:id" element={<ChannelMessages />} />
          <Route path="/admin" element={user?.is_admin ? <Suspense fallback={<p className="cyber-mono" style={{ color: 'var(--text-muted)' }}>Loading...</p>}><Admin /></Suspense> : <Navigate to="/dashboard" />} />
        </Route>
        <Route path="*" element={<Navigate to="/dashboard" />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
