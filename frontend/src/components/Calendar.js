import React, { useMemo, useState } from 'react';
import {
  addMonths,
  eachDayOfInterval,
  endOfMonth,
  endOfWeek,
  format,
  isSameDay,
  isSameMonth,
  startOfMonth,
  startOfWeek,
  subMonths,
} from 'date-fns';
import { ChevronLeft, ChevronRight } from 'lucide-react';

export default function Calendar({ appointments = [], selectedDate, onSelect }) {
  const [current, setCurrent] = useState(selectedDate || new Date());

  const days = useMemo(() => {
    const start = startOfWeek(startOfMonth(current));
    const end = endOfWeek(endOfMonth(current));
    return eachDayOfInterval({ start, end });
  }, [current]);

  const countMap = useMemo(() => {
    const m = new Map();
    appointments.forEach((a) => {
      const k = format(new Date(a.starts_at), 'yyyy-MM-dd');
      m.set(k, (m.get(k) || 0) + 1);
    });
    return m;
  }, [appointments]);

  return (
    <div className="rounded-2xl border border-border bg-card p-5" data-testid="calendar">
      <div className="mb-4 flex items-center justify-between">
        <button
          onClick={() => setCurrent(subMonths(current, 1))}
          className="grid h-9 w-9 place-items-center rounded-full border border-border transition-colors hover:bg-primary hover:text-primary-foreground"
          aria-label="Previous month"
          data-testid="calendar-prev"
        >
          <ChevronLeft className="h-4 w-4" strokeWidth={1.75} />
        </button>
        <div className="text-center">
          <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
            {format(current, 'yyyy')}
          </div>
          <div className="font-display text-xl font-semibold text-primary">
            {format(current, 'MMMM')}
          </div>
        </div>
        <button
          onClick={() => setCurrent(addMonths(current, 1))}
          className="grid h-9 w-9 place-items-center rounded-full border border-border transition-colors hover:bg-primary hover:text-primary-foreground"
          aria-label="Next month"
          data-testid="calendar-next"
        >
          <ChevronRight className="h-4 w-4" strokeWidth={1.75} />
        </button>
      </div>

      <div className="mb-2 grid grid-cols-7 gap-1 text-center font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
        {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((d) => (
          <div key={d} className="py-1">{d}</div>
        ))}
      </div>

      <div className="grid grid-cols-7 gap-1">
        {days.map((d) => {
          const key = format(d, 'yyyy-MM-dd');
          const count = countMap.get(key) || 0;
          const inMonth = isSameMonth(d, current);
          const isToday = isSameDay(d, new Date());
          const isSel = selectedDate && isSameDay(d, selectedDate);
          return (
            <button
              key={key}
              onClick={() => onSelect?.(d)}
              className={`relative aspect-square rounded-lg text-sm transition-colors ${
                isSel
                  ? 'bg-primary text-primary-foreground'
                  : inMonth
                  ? 'text-primary hover:bg-secondary/30'
                  : 'text-primary/30'
              } ${isToday && !isSel ? 'ring-1 ring-accent' : ''}`}
              data-testid={`calendar-day-${key}`}
            >
              <span className="absolute left-1.5 top-1 font-mono text-[11px]">{format(d, 'd')}</span>
              {count > 0 && (
                <span
                  className={`absolute bottom-1.5 right-1.5 min-w-[16px] rounded-full px-1 font-mono text-[9px] font-medium ${
                    isSel ? 'bg-accent text-accent-foreground' : 'bg-accent/15 text-accent'
                  }`}
                >
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
