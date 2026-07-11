import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Calendar, Download, Ticket } from 'lucide-react';
import { api, BACKEND_URL } from '../lib/api.js';

export default function MyAppointments() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get('/appointments')
      .then(({ data }) => setItems(data || []))
      .finally(() => setLoading(false));
  }, []);

  const upcoming = items.filter((a) => new Date(a.starts_at) >= new Date() && a.status === 'confirmed');
  const past = items.filter((a) => new Date(a.starts_at) < new Date() || a.status !== 'confirmed');

  return (
    <div className="mx-auto max-w-5xl px-6 py-10 lg:py-14">
      <div className="mb-8">
        <div className="font-mono text-xs uppercase tracking-[0.25em] text-accent">Your bookings</div>
        <h1 className="mt-2 font-display text-4xl font-semibold tracking-tight text-primary">
          My appointments
        </h1>
      </div>

      {loading ? (
        <p className="text-muted-foreground">Loading…</p>
      ) : items.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border p-10 text-center">
          <div className="mx-auto grid h-12 w-12 place-items-center rounded-full bg-secondary/40">
            <Calendar className="h-5 w-5 text-primary" />
          </div>
          <p className="mt-4 text-primary/70">No appointments yet.</p>
          <Link
            to="/talk"
            className="mt-4 inline-block rounded-full bg-accent px-5 py-2 text-sm font-medium text-accent-foreground"
          >
            Book with voice
          </Link>
        </div>
      ) : (
        <div className="space-y-8">
          {upcoming.length > 0 && (
            <Section title="Upcoming" list={upcoming} />
          )}
          {past.length > 0 && (
            <Section title="Past" list={past} muted />
          )}
        </div>
      )}
    </div>
  );
}

function Section({ title, list, muted }) {
  return (
    <div>
      <h2 className="mb-3 font-mono text-xs uppercase tracking-[0.25em] text-muted-foreground">
        {title}
      </h2>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {list.map((a) => {
          const dt = new Date(a.starts_at);
          return (
            <Link
              key={a.appointment_id}
              to={`/ticket/${a.appointment_id}`}
              className={`group rounded-2xl border border-border bg-card p-5 transition-all hover:-translate-y-0.5 hover:shadow-md ${
                muted ? 'opacity-70' : ''
              }`}
              data-testid={`appt-card-${a.appointment_id}`}
            >
              <div className="flex items-start justify-between">
                <div>
                  <div className="font-display text-xl font-semibold text-primary">
                    {dt.toLocaleDateString('en-IN', {
                      weekday: 'short',
                      day: 'numeric',
                      month: 'short',
                    })}
                  </div>
                  <div className="font-mono text-sm text-accent">
                    {dt.toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit' })}
                  </div>
                </div>
                <span
                  className={`rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-widest ${
                    a.status === 'confirmed'
                      ? 'bg-accent/10 text-accent'
                      : 'bg-secondary/40 text-primary'
                  }`}
                >
                  {a.status}
                </span>
              </div>
              <div className="mt-4">
                <div className="font-semibold text-primary">{a.doctor_name}</div>
                <div className="text-sm text-primary/60">{a.specialty}</div>
              </div>
              <div className="mt-4 flex items-center justify-between">
                <span className="inline-flex items-center gap-1 font-mono text-[10px] text-muted-foreground">
                  <Ticket className="h-3 w-3" />
                  {a.appointment_id.toUpperCase()}
                </span>
                <a
                  href={`${BACKEND_URL}/api/appointments/${a.appointment_id}/ticket.pdf`}
                  target="_blank"
                  rel="noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  className="inline-flex items-center gap-1 text-xs font-medium text-primary/70 hover:text-primary"
                  data-testid={`download-pdf-${a.appointment_id}`}
                >
                  <Download className="h-3 w-3" /> PDF
                </a>
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
