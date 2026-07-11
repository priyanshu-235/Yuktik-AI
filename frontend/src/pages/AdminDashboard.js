import React, { useEffect, useMemo, useState } from 'react';
import { format } from 'date-fns';
import { CalendarDays, ShieldCheck, Stethoscope, Users } from 'lucide-react';
import Calendar from '../components/Calendar.js';
import { api } from '../lib/api.js';
import socket from '../lib/socket.js';

export default function AdminDashboard() {
  const [stats, setStats] = useState({ total_appointments: 0, upcoming_appointments: 0, total_doctors: 0, total_users: 0 });
  const [doctors, setDoctors] = useState([]);
  const [items, setItems] = useState([]);
  const [selected, setSelected] = useState(new Date());
  const [month, setMonth] = useState(new Date());
  const [doctorFilter, setDoctorFilter] = useState('');

  const load = async (d = month) => {
    const y = d.getFullYear();
    const m = d.getMonth() + 1;
    const [s, docs, appts] = await Promise.all([
      api.get('/stats'),
      api.get('/doctors'),
      api.get(`/appointments/month/${y}/${m}`),
    ]);
    setStats(s.data);
    setDoctors(docs.data);
    setItems(appts.data || []);
  };

  useEffect(() => {
    load(month);
    const handler = () => load(month);
    socket.on('db_update', handler);
    return () => socket.off('db_update', handler);
    // eslint-disable-next-line
  }, [month]);

  const filtered = useMemo(
    () => (doctorFilter ? items.filter((a) => a.doctor_id === doctorFilter) : items),
    [items, doctorFilter]
  );
  const dayItems = useMemo(
    () => filtered.filter((a) => format(new Date(a.starts_at), 'yyyy-MM-dd') === format(selected, 'yyyy-MM-dd')),
    [filtered, selected]
  );

  const cards = [
    { key: 'appts', label: 'Total Appointments', value: stats.total_appointments, icon: CalendarDays },
    { key: 'up', label: 'Upcoming', value: stats.upcoming_appointments, icon: ShieldCheck, accent: true },
    { key: 'docs', label: 'Doctors', value: stats.total_doctors, icon: Stethoscope },
    { key: 'users', label: 'Users', value: stats.total_users, icon: Users },
  ];

  return (
    <div className="mx-auto max-w-7xl px-6 py-10 lg:py-14">
      <div className="mb-8">
        <div className="font-mono text-xs uppercase tracking-[0.25em] text-accent">Admin</div>
        <h1 className="mt-2 font-display text-4xl font-semibold tracking-tight text-primary">Overview</h1>
      </div>

      <div className="mb-8 grid grid-cols-2 gap-4 lg:grid-cols-4">
        {cards.map(({ key, label, value, icon: Icon, accent }) => (
          <div
            key={key}
            className={`rounded-2xl border p-5 ${
              accent ? 'border-primary bg-primary text-primary-foreground' : 'border-border bg-card'
            }`}
            data-testid={`stat-${key}`}
          >
            <div className="flex items-center justify-between">
              <div className={`font-mono text-[10px] uppercase tracking-widest ${accent ? 'text-primary-foreground/70' : 'text-muted-foreground'}`}>
                {label}
              </div>
              <Icon className={`h-4 w-4 ${accent ? 'text-accent' : 'text-primary/50'}`} strokeWidth={1.75} />
            </div>
            <div className="mt-3 font-display text-4xl font-semibold">{value}</div>
          </div>
        ))}
      </div>

      <div className="mb-4 flex items-center gap-3">
        <label className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">Filter by doctor</label>
        <select
          value={doctorFilter}
          onChange={(e) => setDoctorFilter(e.target.value)}
          className="rounded-full border border-border bg-card px-4 py-2 text-sm"
          data-testid="admin-doctor-filter"
        >
          <option value="">All doctors</option>
          {doctors.map((d) => (
            <option key={d.doctor_id} value={d.doctor_id}>
              {d.name} · {d.specialty}
            </option>
          ))}
        </select>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[380px_1fr]">
        <Calendar
          appointments={filtered}
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
                <div key={a.appointment_id} className="grid grid-cols-[80px_1fr_auto] items-center gap-4 px-5 py-4" data-testid={`admin-appt-${a.appointment_id}`}>
                  <div className="font-mono text-sm font-medium text-accent">
                    {format(new Date(a.starts_at), 'hh:mm a')}
                  </div>
                  <div className="min-w-0">
                    <div className="truncate font-semibold text-primary">{a.patient_name}</div>
                    <div className="truncate text-xs text-primary/60">
                      {a.doctor_name} · {a.specialty}
                    </div>
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
