import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertCircle, Sparkles } from 'lucide-react';
import { api } from '../lib/api.js';
import { useAuth } from '../context/AuthContext.js';

const HERO = 'https://images.unsplash.com/photo-1666214280391-8ff5bd3c0bf0?auto=format&fit=crop&w=1600&q=70';
const GSI_SCRIPT = 'https://accounts.google.com/gsi/client';

function loadGsi() {
  return new Promise((resolve, reject) => {
    if (window.google?.accounts?.id) return resolve(window.google);
    const existing = document.querySelector(`script[src="${GSI_SCRIPT}"]`);
    if (existing) {
      existing.addEventListener('load', () => resolve(window.google));
      existing.addEventListener('error', reject);
      return;
    }
    const s = document.createElement('script');
    s.src = GSI_SCRIPT;
    s.async = true;
    s.defer = true;
    s.onload = () => resolve(window.google);
    s.onerror = reject;
    document.head.appendChild(s);
  });
}

export default function Login() {
  const navigate = useNavigate();
  const { setUser } = useAuth();
  const [clientId, setClientId] = useState('');
  const [configLoading, setConfigLoading] = useState(true);
  const [error, setError] = useState(null);
  const [pending, setPending] = useState(false);
  const btnRef = useRef(null);

  // Fetch the Google client id from the backend
  useEffect(() => {
    let alive = true;
    api
      .get('/auth/config')
      .then(({ data }) => {
        if (!alive) return;
        setClientId(data.google_client_id || '');
      })
      .catch(() => setError('Could not fetch auth configuration.'))
      .finally(() => alive && setConfigLoading(false));
    return () => {
      alive = false;
    };
  }, []);

  // Init GSI once we have the client id
  useEffect(() => {
    if (!clientId) return;
    let mounted = true;

    const handleCredential = async (response) => {
      if (!response?.credential) return;
      setPending(true);
      setError(null);
      try {
        const { data } = await api.post('/auth/google', { credential: response.credential });
        // Also stash token in localStorage as a Bearer fallback (mobile clients, tests)
        if (data.session_token) {
          window.localStorage.setItem('session_token', data.session_token);
        }
        setUser(data);
        const target =
          data.role === 'admin' ? '/admin' : data.role === 'doctor' ? '/doctor' : '/';
        navigate(target, { replace: true, state: { user: data } });
      } catch (err) {
        setError(err?.response?.data?.detail || 'Login failed. Please try again.');
      } finally {
        if (mounted) setPending(false);
      }
    };

    loadGsi()
      .then((google) => {
        if (!mounted || !google) return;
        google.accounts.id.initialize({
          client_id: clientId,
          callback: handleCredential,
          ux_mode: 'popup',
          auto_select: false,
        });
        if (btnRef.current) {
          google.accounts.id.renderButton(btnRef.current, {
            type: 'standard',
            theme: 'outline',
            size: 'large',
            text: 'signin_with',
            shape: 'pill',
            logo_alignment: 'left',
            width: 320,
          });
        }
      })
      .catch(() => setError('Could not load Google Sign-In.'));

    return () => {
      mounted = false;
    };
  }, [clientId, navigate, setUser]);

  return (
    <div className="grid min-h-screen grid-cols-1 lg:grid-cols-5">
      {/* Left panel - editorial */}
      <div className="relative overflow-hidden lg:col-span-3">
        <img src={HERO} alt="Clinic" className="absolute inset-0 h-full w-full object-cover" />
        <div className="absolute inset-0 bg-primary/85" />
        <div className="bg-grain absolute inset-0" />
        <div className="relative flex h-full min-h-screen flex-col justify-between p-10 lg:p-16">
          <div className="flex items-center gap-2 text-primary-foreground">
            <span className="h-2 w-2 rounded-full bg-accent" />
            <span className="font-mono text-xs uppercase tracking-[0.25em]">yuktikAI · Digitix Clinic</span>
          </div>

          <div className="max-w-lg space-y-6 text-primary-foreground">
            <div className="inline-flex items-center gap-2 rounded-full border border-primary-foreground/20 px-3 py-1.5 text-xs uppercase tracking-widest">
              <Sparkles className="h-3 w-3" />
              Voice-first appointments
            </div>
            <h1 className="font-display text-5xl font-semibold leading-[1.05] tracking-tight lg:text-6xl">
              Talk to Asha.<br />
              <span className="text-accent">Book in under a minute.</span>
            </h1>
            <p className="max-w-md text-lg text-primary-foreground/80">
              An AI voice assistant that answers your questions, triages symptoms, and books you with
              the right doctor — in English or हिंदी.
            </p>
          </div>

          <div className="grid max-w-md grid-cols-3 gap-4 text-primary-foreground/90">
            {[
              { k: '6', l: 'Specialists' },
              { k: '<60s', l: 'To book' },
              { k: 'Hi/En', l: 'Languages' },
            ].map((s) => (
              <div key={s.l} className="border-l border-primary-foreground/20 pl-3">
                <div className="font-display text-3xl font-semibold">{s.k}</div>
                <div className="font-mono text-[10px] uppercase tracking-widest text-primary-foreground/60">
                  {s.l}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Right panel - sign in */}
      <div className="flex items-center justify-center bg-background p-10 lg:col-span-2">
        <div className="w-full max-w-sm space-y-8">
          <div>
            <div className="font-mono text-xs uppercase tracking-[0.25em] text-accent">Welcome</div>
            <h2 className="mt-2 font-display text-3xl font-semibold tracking-tight text-primary">
              Sign in to continue
            </h2>
            <p className="mt-3 text-sm text-primary/70">
              Use your Google account. Patients, doctors, and administrators all start here.
            </p>
          </div>

          {configLoading ? (
            <div className="text-sm text-muted-foreground">Loading sign-in…</div>
          ) : !clientId ? (
            <div
              className="flex items-start gap-2 rounded-xl border border-accent/40 bg-accent/5 p-4 text-sm text-primary"
              data-testid="google-not-configured"
            >
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
              <div>
                <div className="font-semibold">Google sign-in not configured.</div>
                <div className="mt-1 text-primary/70">
                  Set <code className="font-mono text-xs">GOOGLE_CLIENT_ID</code> in
                  <code className="mx-1 font-mono text-xs">/app/backend/.env</code>
                  from your Google Cloud OAuth 2.0 Client ID, then restart the backend.
                </div>
              </div>
            </div>
          ) : (
            <div>
              <div ref={btnRef} data-testid="google-signin-btn" />
              {pending && (
                <div className="mt-3 text-xs text-muted-foreground">Signing you in…</div>
              )}
            </div>
          )}

          {error && (
            <div className="flex items-start gap-2 rounded-xl border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <div>{error}</div>
            </div>
          )}

          <p className="text-xs leading-relaxed text-muted-foreground">
            By continuing you accept the Digitix Clinic terms and privacy notice. Your voice recordings are used
            only to serve your request.
          </p>
        </div>
      </div>
    </div>
  );
}
