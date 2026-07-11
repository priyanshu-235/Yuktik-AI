import React, { useEffect, useState } from 'react';
import { UserCog } from 'lucide-react';
import { api } from '../lib/api.js';

export default function AdminUsers() {
  const [users, setUsers] = useState([]);
  const [doctors, setDoctors] = useState([]);
  const [savingId, setSavingId] = useState(null);
  const [error, setError] = useState(null);

  const load = async () => {
    const [u, d] = await Promise.all([api.get('/auth/users'), api.get('/doctors')]);
    setUsers(u.data);
    setDoctors(d.data);
  };

  useEffect(() => {
    load().catch((e) => setError(String(e?.response?.data?.detail || e.message)));
  }, []);

  const updateRole = async (u, role, doctor_id) => {
    setSavingId(u.user_id);
    try {
      await api.post(`/auth/users/${u.user_id}/role`, { role, doctor_id });
      await load();
    } catch (e) {
      setError(String(e?.response?.data?.detail || e.message));
    } finally {
      setSavingId(null);
    }
  };

  return (
    <div className="mx-auto max-w-6xl px-6 py-10 lg:py-14">
      <div className="mb-8">
        <div className="font-mono text-xs uppercase tracking-[0.25em] text-accent">Admin</div>
        <h1 className="mt-2 font-display text-4xl font-semibold tracking-tight text-primary">Users & Roles</h1>
      </div>

      {error && (
        <div className="mb-6 rounded-xl border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="overflow-hidden rounded-2xl border border-border bg-card">
        <table className="w-full text-sm">
          <thead className="bg-secondary/20 text-left font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
            <tr>
              <th className="px-5 py-3">User</th>
              <th className="px-5 py-3">Email</th>
              <th className="px-5 py-3">Role</th>
              <th className="px-5 py-3">Doctor profile</th>
              <th className="px-5 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {users.map((u) => (
              <tr key={u.user_id} data-testid={`user-row-${u.user_id}`}>
                <td className="px-5 py-4">
                  <div className="flex items-center gap-3">
                    {u.picture ? (
                      <img src={u.picture} alt="" className="h-8 w-8 rounded-full border border-border" />
                    ) : (
                      <span className="grid h-8 w-8 place-items-center rounded-full bg-secondary/40 font-medium">
                        {u.name?.[0]?.toUpperCase()}
                      </span>
                    )}
                    <div>
                      <div className="font-medium text-primary">{u.name}</div>
                      <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                        {u.user_id}
                      </div>
                    </div>
                  </div>
                </td>
                <td className="px-5 py-4 text-primary/70">{u.email}</td>
                <td className="px-5 py-4">
                  <RoleSelect
                    value={u.role}
                    onChange={(role) => updateRole(u, role, role === 'doctor' ? u.doctor_id : null)}
                    disabled={savingId === u.user_id}
                    testId={`role-select-${u.user_id}`}
                  />
                </td>
                <td className="px-5 py-4">
                  {u.role === 'doctor' ? (
                    <select
                      className="rounded-full border border-border bg-background px-3 py-1.5 text-sm"
                      value={u.doctor_id || ''}
                      onChange={(e) => updateRole(u, 'doctor', e.target.value || null)}
                      disabled={savingId === u.user_id}
                      data-testid={`doctor-select-${u.user_id}`}
                    >
                      <option value="">— link to profile —</option>
                      {doctors.map((d) => (
                        <option key={d.doctor_id} value={d.doctor_id}>
                          {d.name} · {d.specialty}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <span className="text-primary/40">—</span>
                  )}
                </td>
                <td className="px-5 py-4">
                  {savingId === u.user_id && (
                    <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                      <UserCog className="h-3 w-3 animate-pulse" /> saving…
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function RoleSelect({ value, onChange, disabled, testId }) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      disabled={disabled}
      className="rounded-full border border-border bg-background px-3 py-1.5 text-sm"
      data-testid={testId}
    >
      <option value="patient">patient</option>
      <option value="doctor">doctor</option>
      <option value="admin">admin</option>
    </select>
  );
}
