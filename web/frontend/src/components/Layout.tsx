import { Link, Outlet, useLocation } from 'react-router-dom';

export default function Layout({ isAdmin }: { isAdmin: boolean }) {
  const loc = useLocation();
  const nav = [
    { to: '/dashboard', label: 'Dashboard', icon: '◈' },
    ...(isAdmin ? [{ to: '/admin', label: 'Admin', icon: '⬡' }] : []),
  ];

  return (
    <div className="flex h-screen" style={{ background: 'var(--bg-deep)' }}>
      <aside className="w-56 cyber-sidebar flex flex-col">
        <div className="p-5 pb-8">
          <h1 style={{ fontFamily: 'var(--font-brand)', color: 'var(--cyan)', fontSize: '1.1rem', letterSpacing: '0.2em' }}>
            TEMATCH
          </h1>
          <p style={{ fontFamily: 'var(--font-mono)', fontSize: '0.6rem', color: 'var(--text-muted)', marginTop: '4px', letterSpacing: '0.1em' }}>
            CONTENT CURATOR v1.0
          </p>
        </div>
        <nav className="flex-1 px-3 space-y-1">
          {nav.map((n) => (
            <Link
              key={n.to}
              to={n.to}
              className={`cyber-nav-link ${loc.pathname === n.to ? 'cyber-nav-link-active' : ''}`}
            >
              <span style={{ marginRight: '0.5rem', opacity: 0.6 }}>{n.icon}</span>
              {n.label}
            </Link>
          ))}
        </nav>
        <div className="p-4" style={{ borderTop: '1px solid var(--border-dim)' }}>
          <p style={{ fontFamily: 'var(--font-mono)', fontSize: '0.6rem', color: 'var(--text-muted)', letterSpacing: '0.05em' }}>
            SYS.ONLINE
            <span className="status-dot status-green ml-2" style={{ width: '5px', height: '5px' }} />
          </p>
        </div>
      </aside>
      <main className="flex-1 overflow-auto p-8">
        <Outlet />
      </main>
    </div>
  );
}
