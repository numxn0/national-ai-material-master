import React, { useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  UploadCloud,
  GitCompare,
  CheckSquare,
  Layers,
  ChevronRight
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { getAuthenticatedUser, login, logout } from '@/services/api';

interface ShellProps {
  children: React.ReactNode;
}

export const Shell: React.FC<ShellProps> = ({ children }) => {
  const location = useLocation();
  const [user, setUser] = useState<any | null>(getAuthenticatedUser());
  const [username, setUsername] = useState('demo_admin');
  const [password, setPassword] = useState('');
  const [authError, setAuthError] = useState<string | null>(null);

  const navItems = [
    {
      label: 'Dashboard',
      path: '/dashboard',
      icon: LayoutDashboard,
    },
    {
      label: 'Upload Materials',
      path: '/upload',
      icon: UploadCloud,
    },
    {
      label: 'Duplicate Review',
      path: '/matching',
      icon: GitCompare,
    },
    {
      label: 'Approval & Audit',
      path: '/approvals',
      icon: CheckSquare,
    },
  ];

  const getPageTitle = () => {
    switch (location.pathname) {
      case '/dashboard':
      case '/':
        return 'Dashboard Overview';
      case '/upload':
        return 'Upload Materials';
      case '/matching':
        return 'Duplicate Review';
      case '/approvals':
      case '/audit':
        return 'Approval & Audit';
      default:
        return 'Dashboard';
    }
  };

  return (
    <div className="flex h-screen w-full bg-gray-50 text-gray-900 overflow-hidden font-sans">
      {/* Clean White Sidebar */}
      <aside className="w-64 border-r border-gray-200 bg-white flex flex-col justify-between shrink-0 shadow-sm">
        <div>
          {/* Logo / Branding */}
          <div className="p-5 border-b border-gray-200 flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-blue-600 flex items-center justify-center text-white font-bold shadow-sm">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-sm font-bold text-gray-900 leading-tight">
                National AI <br />
                <span className="text-gray-600 font-normal">Material Master</span>
              </h1>
            </div>
          </div>

          {/* Navigation Items */}
          <nav className="p-3 space-y-1">
            <p className="px-3 py-1 text-[11px] font-semibold uppercase tracking-wider text-gray-400">
              Navigation
            </p>
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive =
                location.pathname === item.path ||
                (item.path === '/dashboard' && location.pathname === '/') ||
                (item.path === '/approvals' && location.pathname === '/audit');

              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  className={
                    cn(
                      'flex items-center gap-3 px-3 py-2.5 rounded-md text-xs font-medium transition-colors',
                      isActive
                        ? 'bg-blue-50 text-blue-700 font-semibold border-l-2 border-blue-600'
                        : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                    )
                  }
                >
                  <Icon className={cn('w-4 h-4', isActive ? 'text-blue-600' : 'text-gray-500')} />
                  <span>{item.label}</span>
                </NavLink>
              );
            })}
          </nav>
        </div>

        {/* Minimal Footer */}
        <div className="p-4 border-t border-gray-200 text-xs text-gray-500 space-y-1">
          <div className="flex items-center justify-between">
            <span className="font-medium text-gray-700">Govt. of India</span>
            <span className="text-[11px] text-gray-400 font-mono">v1.0 Demo</span>
          </div>
          <p className="text-[11px] text-gray-400">{user ? 'Production APIs • Authenticated' : 'Demo routes available • Login for production'}</p>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden bg-white">
        {/* Top Header */}
        <header className="h-14 border-b border-gray-200 bg-white px-6 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <span>National Material Master</span>
            <ChevronRight className="w-3.5 h-3.5 text-gray-400" />
            <span className="text-gray-900 font-semibold">{getPageTitle()}</span>
          </div>

          <div className="flex items-center gap-2 text-xs text-gray-500">
            {user ? (
              <>
                <span className="px-2.5 py-1 rounded bg-green-50 text-green-700 font-medium border border-green-200">
                  {user.display_name} • {(user.roles || []).join(', ')}
                </span>
                <button
                  onClick={() => {
                    logout();
                    setUser(null);
                  }}
                  className="px-2.5 py-1 rounded border border-gray-300 bg-white text-gray-700 hover:bg-gray-50"
                >
                  Logout
                </button>
              </>
            ) : (
              <form
                className="flex items-center gap-2"
                onSubmit={async (event) => {
                  event.preventDefault();
                  setAuthError(null);
                  try {
                    setUser(await login(username, password));
                    setPassword('');
                  } catch (err: any) {
                    setAuthError(err.message || 'Login failed');
                  }
                }}
              >
                <input
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="w-28 rounded border border-gray-300 px-2 py-1 text-xs"
                  placeholder="Username"
                />
                <input
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  type="password"
                  className="w-32 rounded border border-gray-300 px-2 py-1 text-xs"
                  placeholder="Password"
                />
                <button className="px-2.5 py-1 rounded bg-blue-600 text-white font-medium">
                  Login
                </button>
                {authError && <span className="text-red-600 max-w-48 truncate">{authError}</span>}
              </form>
            )}
          </div>
        </header>

        {/* Page Content Body */}
        <main className="flex-1 overflow-y-auto p-6 bg-gray-50">
          {children}
        </main>
      </div>
    </div>
  );
};
