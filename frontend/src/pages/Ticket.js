import React, { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowLeft, CheckCircle2, Download, MapPin, Phone } from 'lucide-react';
import { api, BACKEND_URL } from '../lib/api.js';

export default function Ticket() {
  const { id } = useParams();
  const [appt, setAppt] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api
      .get(`/appointments/${id}`)
      .then(({ data }) => setAppt(data))
      .catch((err) => setError(err?.response?.data?.detail || 'Could not load ticket'));
  }, [id]);

  if (error) {
    return (
      <div className="mx-auto max-w-md p-10 text-center">
        <p className="text-primary/70">{error}</p>
        <Link to="/" className="mt-4 inline-block text-accent hover:underline">
          Back home
        </Link>
      </div>
    );
  }
  if (!appt) return <div className="p-10 text-muted-foreground">Loading…</div>;

  const dt = new Date(appt.starts_at);
  const pdfUrl = `${BACKEND_URL}/api/appointments/${appt.appointment_id}/ticket.pdf`;

  return (
    <div className="mx-auto max-w-3xl px-6 py-12">
      <Link to="/" className="inline-flex items-center gap-2 text-sm text-primary/70 hover:text-primary" data-testid="back-home-link">
        <ArrowLeft className="h-4 w-4" /> Back to home
      </Link>

      <div className="mt-6 flex items-center gap-3 text-accent">
        <CheckCircle2 className="h-5 w-5" strokeWidth={1.75} />
        <span className="font-mono text-xs uppercase tracking-[0.25em]">Appointment confirmed</span>
      </div>
      <h1 className="mt-2 font-display text-4xl font-semibold tracking-tight text-primary">
        You're all set.
      </h1>

      {/* Ticket - boarding pass style */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="relative mt-8 overflow-hidden rounded-2xl border border-primary bg-card"
        data-testid="ticket-card"
      >
        <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_1fr]">
          {/* Main */}
          <div className="p-8">
            <div className="flex items-center gap-2 text-muted-foreground">
              <span className="h-2 w-2 rounded-full bg-accent" />
              <span className="font-mono text-[10px] uppercase tracking-widest">yuktikAI · Digitix</span>
            </div>
            <div className="mt-5 space-y-6">
              <Field label="Patient" value={appt.patient_name} testId="ticket-patient" />
              <Field label="Doctor" value={appt.doctor_name} sub={appt.specialty} testId="ticket-doctor" />
              <div className="grid grid-cols-2 gap-6">
                <Field
                  label="Date"
                  value={dt.toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' })}
                  testId="ticket-date"
                />
                <Field
                  label="Time"
                  value={dt.toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit' })}
                  testId="ticket-time"
                />
              </div>
              {appt.notes && <Field label="Notes" value={appt.notes} />}
            </div>
          </div>

          {/* Perforation */}
          <div className="relative hidden md:block">
            <div className="absolute inset-y-0 left-1/2 -translate-x-1/2 border-l border-dashed border-primary/30" />
            <div className="absolute -top-3 left-1/2 h-6 w-6 -translate-x-1/2 rounded-full bg-background" />
            <div className="absolute -bottom-3 left-1/2 h-6 w-6 -translate-x-1/2 rounded-full bg-background" />
          </div>

          {/* Stub */}
          <div className="border-t border-dashed border-primary/30 bg-primary p-8 text-primary-foreground md:border-l-0 md:border-t-0">
            <div className="font-mono text-[10px] uppercase tracking-widest text-primary-foreground/60">
              Ticket ID
            </div>
            <div className="mt-1 break-all font-mono text-2xl font-medium text-accent" data-testid="ticket-id">
              {appt.appointment_id.toUpperCase()}
            </div>
            <div className="mt-6 space-y-3 text-sm text-primary-foreground/85">
              <div className="flex items-start gap-2">
                <MapPin className="mt-0.5 h-4 w-4 shrink-0" strokeWidth={1.5} />
                <span>4th Floor, GreenView Plaza,<br />MG Road, Bengaluru 560001</span>
              </div>
              <div className="flex items-center gap-2">
                <Phone className="h-4 w-4 shrink-0" strokeWidth={1.5} />
                <span className="font-mono text-xs">+91 91234 56789</span>
              </div>
            </div>
          </div>
        </div>
      </motion.div>

      <a
        href={pdfUrl}
        target="_blank"
        rel="noreferrer"
        className="mt-6 inline-flex items-center gap-2 rounded-full bg-accent px-6 py-3 font-medium text-accent-foreground transition-transform active:scale-95"
        data-testid="download-pdf-btn"
      >
        <Download className="h-4 w-4" />
        Download PDF ticket
      </a>
    </div>
  );
}

function Field({ label, value, sub, testId }) {
  return (
    <div>
      <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">{label}</div>
      <div className="mt-1 font-display text-xl font-semibold leading-tight text-primary" data-testid={testId}>{value}</div>
      {sub && <div className="text-sm text-primary/60">{sub}</div>}
    </div>
  );
}
