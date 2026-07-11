import React, { useEffect, useMemo, useState } from 'react';
import { format } from 'date-fns';
import Calendar from '../components/Calendar.js';
import { api } from '../lib/api.js';
import { useAuth } from '../context/AuthContext.js';
import socket from '../lib/socket.js';

export default function DoctorDashboard() {
  const { user } = useAuth();
  const [month, setMonth] = useState(() => new Date());
  const [items, setItems] = useState([]);
  const [selected, setSelected] = useState(new Date());

  const fetchMonth = async (d) => {
    const y = d.getFullYear();
    const m = d.getMonth() + 1;
    const { data } = await api.get(`/appointments/month/${y}/${m}`);
    setItems(data || []);
  };

  useEffect(() => {
    fetchMonth(month);
    const handler = () => fetchMonth(month);
    socket.on('db_update', handler);
    return () => socket.off('db_update', handler);
    // eslint-disable-next-line
  }, [month]);

  const dayItems = useMemo(
    () => items.filter((a) => format(new Date(a.starts_at), 'yyyy-MM-dd') === format(selected, 'yyyy-MM-dd')),
    [items, selected]
  );

  return (
    <div className="mx-auto max-w-6xl px-6 py-10 lg:py-14">
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="font-mono text-xs uppercase tracking-[0.25em] text-accent">Doctor view</div>
          <h1 className="mt-2 font-display text-4xl font-semibold tracking-tight text-primary">
            {user?.name}
          </h1>
          {!user?.doctor_id && (
            <p className="mt-2 text-sm text-destructive" data-testid="doctor-unlinked-msg">
              Your account is not linked to a doctor profile yet. Ask an admin to link you.
            </p>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[380px_1fr]">
        <Calendar
          appointments={items}
          selectedDate={selected}
          onSelect={(d) => {
            setSelected(d);
            if (d.getMonth() !== month.getMonth() || d.getFullYear() !== month.getFullYear()) {
              setMonth(d);
            }
          }}
        />

        <div className="rounded-2xl border border-border bg-card">
          <div className="border-b border-border px-5 py-4">
            <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
              {format(selected, 'EEEE, do MMMM yyyy')}
            </div>
            <div className="font-display text-lg font-semibold text-primary">
              {dayItems.length} appointment{dayItems.length === 1 ? '' : 's'}
            </div>
          </div>
          <div className="divide-y divide-border">
            {dayItems.length === 0 ? (
              <div className="p-8 text-center text-sm text-primary/60">Nothing scheduled.</div>
            ) : (
              dayItems.map((a) => (
                <div key={a.appointment_id} className="flex items-center gap-4 px-5 py-4" data-testid={`day-appt-${a.appointment_id}`}>
                  <div className="w-24 shrink-0">
                    <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">Time</div>
                    <div className="font-mono text-sm font-medium text-accent">
                      {format(new Date(a.starts_at), 'hh:mm a')}
                    </div>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="truncate font-semibold text-primary">{a.patient_name}</div>
                    <div className="text-xs text-primary/60">{a.patient_phone || '—'} · {a.notes || 'No notes'}</div>
                  </div>
                  <span className="rounded-full bg-accent/10 px-2 py-0.5 text-[10px] uppercase tracking-widest text-accent">
                    {a.status}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
