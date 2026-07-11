import React from 'react';
import { Link, NavLink, useNavigate } from 'react-router-dom';
import { LogOut, Leaf } from 'lucide-react';
import { useAuth } from '../context/AuthContext.js';

export default function Nav() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const items = user
    ? user.role === 'admin'
      ? [
          { to: '/admin', label: 'Overview' },
          { to: '/admin/calendar', label: 'Calendar' },
          { to: '/admin/users', label: 'Users' },
          { to: '/talk', label: 'Voice' },
        ]
      : user.role === 'doctor'
      ? [
          { to: '/doctor', label: 'My Calendar' },
          { to: '/talk', label: 'Voice' },
        ]
      : [
          { to: '/', label: 'Home' },
          { to: '/talk', label: 'Talk to Asha' },
          { to: '/appointments', label: 'My Appointments' },
        ]
    : [];

  return (
    <header
      className="sticky top-0 z-40 border-b border-border bg-background/95 backdrop-blur-sm"
      data-testid="app-nav"
    >
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
        <Link to="/" className="flex items-center gap-2 group" data-testid="nav-logo">
          <span className="grid h-9 w-9 place-items-center rounded-full bg-primary text-primary-foreground">
            <Leaf className="h-4 w-4" strokeWidth={1.75} />
          </span>
          <div className="leading-tight">
            <div className="font-display text-lg font-semibold tracking-tight text-primary">yuktikAI</div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">Digitix Clinic</div>
          </div>
        </Link>

        <nav className="hidden items-center gap-1 md:flex">
          {items.map((it) => (
            <NavLink
              key={it.to}
              to={it.to}
              end={it.to === '/'}
              className={({ isActive }) =>
                `rounded-full px-4 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-primary text-primary-foreground'
                    : 'text-primary/70 hover:bg-primary/5 hover:text-primary'
                }`
              }
              data-testid={`nav-link-${it.label.toLowerCase().replace(/\s+/g, '-')}`}
            >
              {it.label}
            </NavLink>
          ))}
        </nav>

        <div className="flex items-center gap-3">
          {user ? (
            <>
              <div className="hidden text-right md:block">
                <div className="text-sm font-medium text-primary">{user.name}</div>
                <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                  {user.role}
                </div>
              </div>
              {user.picture ? (
                <img
                  src={user.picture}
                  alt={user.name}
                  className="h-9 w-9 rounded-full border border-border object-cover"
                />
              ) : (
                <span className="grid h-9 w-9 place-items-center rounded-full border border-border bg-secondary/40 font-medium">
                  {user.name?.[0]?.toUpperCase()}
                </span>
              )}
              <button
                onClick={logout}
                className="grid h-9 w-9 place-items-center rounded-full border border-border text-primary/70 transition-colors hover:bg-primary hover:text-primary-foreground"
                title="Sign out"
                data-testid="logout-btn"
              >
                <LogOut className="h-4 w-4" strokeWidth={1.75} />
              </button>
            </>
          ) : (
            <button
              onClick={() => navigate('/login')}
              className="rounded-full bg-primary px-5 py-2 text-sm font-medium text-primary-foreground transition-transform active:scale-95"
              data-testid="sign-in-btn"
            >
              Sign in
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
