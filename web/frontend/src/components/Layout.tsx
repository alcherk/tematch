import { Link, Outlet, useLocation } from 'react-router-dom';

export default function Layout({ isAdmin }: { isAdmin: boolean }) {
  const loc = useLocation();
  const nav = [
    { to: '/dashboard', label: 'Dashboard' },
    ...(isAdmin ? [{ to: '/admin', label: 'Admin' }] : []),
  ];

  return (
    <div className="flex h-screen bg-gray-50">
      <aside className="w-56 bg-white border-r p-4">
        <h1 className="text-xl font-bold mb-6">Tematch</h1>
        <nav className="space-y-2">
          {nav.map((n) => (
            <Link
              key={n.to}
              to={n.to}
              className={`block px-3 py-2 rounded ${
                loc.pathname === n.to ? 'bg-blue-100 text-blue-700' : 'text-gray-700 hover:bg-gray-100'
              }`}
            >
              {n.label}
            </Link>
          ))}
        </nav>
      </aside>
      <main className="flex-1 overflow-auto p-8">
        <Outlet />
      </main>
    </div>
  );
}
