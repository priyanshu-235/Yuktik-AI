import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowUpRight, Calendar, HeartPulse, Mic, Stethoscope } from 'lucide-react';
import { api } from '../lib/api.js';
import { useAuth } from '../context/AuthContext.js';

export default function Home() {
  const { user } = useAuth();
  const [doctors, setDoctors] = useState([]);
  const [nextAppt, setNextAppt] = useState(null);

  useEffect(() => {
    api.get('/doctors').then(({ data }) => setDoctors(data)).catch(() => {});
    api.get('/appointments').then(({ data }) => {
      const upcoming = (data || []).find((a) => new Date(a.starts_at) >= new Date() && a.status === 'confirmed');
      setNextAppt(upcoming || null);
    }).catch(() => {});
  }, []);

  return (
    <div className="mx-auto max-w-7xl px-6 py-10 lg:py-16">
      <div className="mb-10 flex flex-wrap items-end justify-between gap-6">
        <div>
          <div className="font-mono text-xs uppercase tracking-[0.25em] text-accent">
            {user ? `Namaste, ${user.name.split(' ')[0]}` : 'Namaste'}
          </div>
          <h1 className="mt-2 font-display text-4xl font-semibold tracking-tight text-primary lg:text-5xl">
            Talk. Triage. <span className="text-accent">Book.</span>
          </h1>
          <p className="mt-3 max-w-lg text-primary/70">
            Ask Asha anything about the clinic — from doctor timings to booking an appointment. In
            English or हिंदी.
          </p>
        </div>
        <Link
          to="/talk"
          className="group inline-flex items-center gap-2 rounded-full bg-accent px-6 py-3 font-medium text-accent-foreground transition-transform active:scale-95"
          data-testid="cta-talk"
        >
          <Mic className="h-4 w-4" strokeWidth={1.75} />
          Start talking
          <ArrowUpRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" strokeWidth={1.75} />
        </Link>
      </div>

      {/* Bento grid */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-6 md:gap-6">
        {/* Big voice card */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="relative overflow-hidden rounded-2xl border border-border bg-primary p-8 text-primary-foreground md:col-span-4 md:row-span-2 md:p-10"
        >
          <div className="bg-grain absolute inset-0" />
          <div className="relative flex h-full flex-col justify-between gap-6">
            <div>
              <div className="font-mono text-xs uppercase tracking-[0.25em] text-primary-foreground/60">
                Voice agent · Asha
              </div>
              <h2 className="mt-2 font-display text-3xl font-semibold leading-tight tracking-tight lg:text-4xl">
                One button. One conversation.<br />
                <span className="text-accent">Zero forms.</span>
              </h2>
              <p className="mt-3 max-w-md text-primary-foreground/70">
                Tap the mic, speak naturally. Asha handles FAQs, symptom triage, and books your
                appointment.
              </p>
            </div>
            <Link
              to="/talk"
              className="inline-flex w-fit items-center gap-2 rounded-full bg-accent px-6 py-3 font-medium text-accent-foreground transition-transform active:scale-95"
              data-testid="voice-card-cta"
            >
              <Mic className="h-4 w-4" />
              Open voice studio
            </Link>
          </div>
        </motion.div>

        {/* Next appointment */}
        <div className="rounded-2xl border border-border bg-card p-6 md:col-span-2">
          <div className="flex items-center gap-2 text-muted-foreground">
            <Calendar className="h-4 w-4" strokeWidth={1.75} />
            <span className="font-mono text-[10px] uppercase tracking-widest">Next appointment</span>
          </div>
          {nextAppt ? (
            <div className="mt-4 space-y-2">
              <div className="font-display text-2xl font-semibold text-primary">
                {new Date(nextAppt.starts_at).toLocaleString('en-IN', {
                  weekday: 'short',
                  day: 'numeric',
                  month: 'short',
                  hour: 'numeric',
                  minute: '2-digit',
                })}
              </div>
              <div className="text-sm text-primary/70">{nextAppt.doctor_name}</div>
              <Link
                to="/appointments"
                className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-accent hover:underline"
              >
                View ticket <ArrowUpRight className="h-3 w-3" />
              </Link>
            </div>
          ) : (
            <div className="mt-4 text-sm text-primary/60">Nothing scheduled yet.</div>
          )}
        </div>

        {/* Symptom checker */}
        <Link
          to="/talk?flow=triage"
          className="group rounded-2xl border border-border bg-card p-6 transition-all hover:-translate-y-0.5 hover:shadow-md md:col-span-2"
          data-testid="triage-card"
        >
          <div className="flex items-center gap-2 text-muted-foreground">
            <HeartPulse className="h-4 w-4" strokeWidth={1.75} />
            <span className="font-mono text-[10px] uppercase tracking-widest">Symptom checker</span>
          </div>
          <div className="mt-4 font-display text-xl font-semibold text-primary">Not sure who to see?</div>
          <p className="mt-2 text-sm text-primary/70">
            Describe how you feel. Asha suggests the right specialty.
          </p>
        </Link>

        {/* Doctors list */}
        <div className="rounded-2xl border border-border bg-card p-6 md:col-span-6">
          <div className="mb-5 flex items-center justify-between">
            <div className="flex items-center gap-2 text-muted-foreground">
              <Stethoscope className="h-4 w-4" strokeWidth={1.75} />
              <span className="font-mono text-[10px] uppercase tracking-widest">Our specialists</span>
            </div>
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {doctors.map((d) => (
              <div
                key={d.doctor_id}
                className="flex items-start gap-4 rounded-xl border border-border/60 bg-background p-4 transition-all hover:-translate-y-0.5 hover:shadow-sm"
                data-testid={`doctor-card-${d.doctor_id}`}
              >
                <img
                  src={d.picture}
                  alt={d.name}
                  className="h-14 w-14 shrink-0 rounded-full border border-border object-cover"
                  onError={(e) => { e.currentTarget.style.visibility = 'hidden'; }}
                />
                <div className="min-w-0">
                  <div className="truncate font-display font-semibold text-primary">{d.name}</div>
                  <div className="font-mono text-[10px] uppercase tracking-widest text-accent">
                    {d.specialty}
                  </div>
                  <div className="mt-1 line-clamp-2 text-xs text-primary/60">{d.availability}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
