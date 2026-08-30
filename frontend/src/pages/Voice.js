import React, { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { AlertCircle, Sparkles, User, Bot, Ticket } from 'lucide-react';
import MicButton from '../components/MicButton.js';
import { api } from '../lib/api.js';

export default function Voice() {
  const [sessionId, setSessionId] = useState(null);
  const [turns, setTurns] = useState([]);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState(null);
  const audioRef = useRef(null);
  const listRef = useRef(null);
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const flow = params.get('flow');

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.post('/voice/session');
        setSessionId(data.session_id);
        // Seed a friendly opening (client-side, no LLM call)
        const opener =
          flow === 'triage'
            ? "Hi, I'm Asha. Tell me what's bothering you and I'll guide you to the right doctor."
            : "Hi, I'm Asha from Digitix Clinic. Ask me anything, or say 'book an appointment' to get started.";
        setTurns([{ role: 'assistant', text: opener, at: Date.now() }]);
      } catch (err) {
        setError('Could not start voice session.');
      }
    })();
  }, [flow]);

  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [turns]);

  async function handleCapture(blob) {
    if (!sessionId) return;
    setProcessing(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append('session_id', sessionId);
      fd.append('audio', blob, 'turn.webm');
      const { data } = await api.post('/voice/turn', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 90000,
      });

      setTurns((prev) => [
        ...prev,
        { role: 'user', text: data.transcript || '…', at: Date.now() },
        {
          role: 'assistant',
          text: data.reply || '',
          at: Date.now(),
          ticket: data.ticket,
          showTicketButton: false,
        },
      ]);

      if (data.audio_base64) {
        await playReplyAudio(data.audio_base64, data.audio_mime);
      }

      if (data.ticket?.appointment_id) {
        setTurns((prev) => {
          const next = [...prev];
          for (let i = next.length - 1; i >= 0; i--) {
            if (next[i].role === 'assistant' && next[i].ticket?.appointment_id) {
              next[i] = { ...next[i], showTicketButton: true };
              break;
            }
          }
          return next;
        });
      }
    } catch (err) {
      console.error(err);
      const msg = err?.response?.data?.detail || err?.message || 'Something went wrong.';
      setError(String(msg));
    } finally {
      setProcessing(false);
    }
  }

  async function handleTextSend(text) {
    if (!sessionId || !text.trim()) return;
    setProcessing(true);
    setError(null);
    try {
      const { data } = await api.post('/voice/turn/text', { session_id: sessionId, text });
      setTurns((prev) => [
        ...prev,
        { role: 'user', text, at: Date.now() },
        {
          role: 'assistant',
          text: data.reply || '',
          at: Date.now(),
          ticket: data.ticket,
          showTicketButton: Boolean(data.ticket?.appointment_id),
        },
      ]);
    } catch (err) {
      const msg = err?.response?.data?.detail || err?.message;
      setError(String(msg));
    } finally {
      setProcessing(false);
    }
  }

  function playReplyAudio(b64, mime) {
    return new Promise((resolve) => {
      const el = audioRef.current;
      if (!el || !b64) {
        resolve();
        return;
      }
      const done = () => {
        el.onended = null;
        el.onerror = null;
        resolve();
      };
      el.onended = done;
      el.onerror = done;
      el.src = `data:${mime || 'audio/wav'};base64,${b64}`;
      const play = el.play();
      if (play && play.catch) play.catch(done);
    });
  }

  return (
    <div className="mx-auto grid max-w-6xl grid-cols-1 gap-8 px-6 py-10 lg:grid-cols-5 lg:py-14">
      {/* Left: mic + captions */}
      <div className="lg:col-span-3">
        <div className="mb-6">
          <div className="font-mono text-xs uppercase tracking-[0.25em] text-accent">
            {flow === 'triage' ? 'Symptom checker' : 'Voice studio'}
          </div>
          <h1 className="mt-2 font-display text-4xl font-semibold tracking-tight text-primary">
            Say hello to Asha
          </h1>
          <p className="mt-2 max-w-md text-primary/70">
            Tap and hold — err, tap once to start, tap again to send. Speak naturally in
            English or Hindi.
          </p>
        </div>

        <div className="flex flex-col items-center justify-center rounded-2xl border border-border bg-card p-10 lg:min-h-[420px]">
          <MicButton onCapture={handleCapture} processing={processing} disabled={!sessionId} />
          <div className="mt-8 text-center">
            <div className="inline-flex items-center gap-2 text-xs text-muted-foreground">
              <Sparkles className="h-3 w-3" />
              Powered by Sarvam · Gemini
            </div>
          </div>
        </div>

        {error && (
          <div className="mt-4 flex items-start gap-2 rounded-xl border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive" data-testid="voice-error">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <div>{error}</div>
          </div>
        )}

        {/* Text fallback */}
        <TextFallback onSend={handleTextSend} disabled={processing || !sessionId} />
      </div>

      {/* Right: transcript */}
      <div className="lg:col-span-2">
        <div className="rounded-2xl border border-border bg-card">
          <div className="border-b border-border px-5 py-4">
            <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
              Transcript
            </div>
            <div className="font-display text-lg font-semibold text-primary">Live conversation</div>
          </div>
          <div
            ref={listRef}
            className="max-h-[520px] space-y-3 overflow-y-auto px-5 py-5"
            data-testid="transcript-list"
          >
            <AnimatePresence initial={false}>
              {turns.map((t, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.25 }}
                  className={`flex gap-2 ${t.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  {t.role === 'assistant' && (
                    <span className="mt-1 grid h-6 w-6 shrink-0 place-items-center rounded-full bg-primary text-primary-foreground">
                      <Bot className="h-3 w-3" />
                    </span>
                  )}
                  <div className="flex max-w-[80%] flex-col gap-2">
                    <div
                      className={`whitespace-pre-wrap rounded-2xl px-4 py-2 text-sm ${
                        t.role === 'user'
                          ? 'rounded-br-sm bg-primary text-primary-foreground'
                          : 'rounded-bl-sm bg-background text-primary'
                      }`}
                      data-testid={`turn-${t.role}-${i}`}
                    >
                      {t.text || '…'}
                    </div>
                    {t.role === 'assistant' && t.showTicketButton && t.ticket?.appointment_id && (
                      <button
                        type="button"
                        onClick={() => navigate(`/ticket/${t.ticket.appointment_id}`)}
                        className="inline-flex w-fit items-center gap-2 rounded-full bg-accent px-4 py-2 text-xs font-medium uppercase tracking-widest text-accent-foreground transition-transform active:scale-95"
                        data-testid={`show-ticket-${i}`}
                      >
                        <Ticket className="h-3.5 w-3.5" />
                        Show ticket
                      </button>
                    )}
                  </div>
                  {t.role === 'user' && (
                    <span className="mt-1 grid h-6 w-6 shrink-0 place-items-center rounded-full bg-accent text-accent-foreground">
                      <User className="h-3 w-3" />
                    </span>
                  )}
                </motion.div>
              ))}
            </AnimatePresence>
            {processing && (
              <div className="flex gap-2">
                <span className="mt-1 grid h-6 w-6 shrink-0 place-items-center rounded-full bg-primary text-primary-foreground">
                  <Bot className="h-3 w-3" />
                </span>
                <div className="flex items-center gap-1 rounded-2xl rounded-bl-sm bg-background px-4 py-2 text-primary">
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary [animation-delay:-0.3s]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary [animation-delay:-0.15s]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary" />
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      <audio ref={audioRef} className="hidden" />
    </div>
  );
}

function TextFallback({ onSend, disabled }) {
  const [text, setText] = useState('');
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (!text.trim()) return;
        onSend(text);
        setText('');
      }}
      className="mt-4 flex items-center gap-2 rounded-full border border-border bg-card px-4 py-2"
    >
      <input
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Or type here to test without mic…"
        className="flex-1 bg-transparent py-2 text-sm outline-none placeholder:text-muted-foreground"
        disabled={disabled}
        data-testid="text-fallback-input"
      />
      <button
        type="submit"
        disabled={disabled || !text.trim()}
        className="rounded-full bg-primary px-4 py-2 text-xs font-medium uppercase tracking-widest text-primary-foreground transition-transform active:scale-95 disabled:opacity-50"
        data-testid="text-fallback-send"
      >
        Send
      </button>
    </form>
  );
}
