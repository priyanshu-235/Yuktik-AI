import React, { useEffect, useRef, useState } from 'react';
import { Mic, Loader2, Square } from 'lucide-react';
import { motion } from 'framer-motion';

/**
 * Records mic audio into a WebM blob and calls onCapture(blob).
 * Modes: idle | recording | processing (controlled by parent via `processing`)
 */
export default function MicButton({ onCapture, processing = false, disabled = false }) {
  const [recording, setRecording] = useState(false);
  const [level, setLevel] = useState(0);
  const mediaRef = useRef(null);
  const chunksRef = useRef([]);
  const streamRef = useRef(null);
  const audioCtxRef = useRef(null);
  const analyserRef = useRef(null);
  const rafRef = useRef(null);

  useEffect(() => {
    return () => {
      stopStream();
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, []);

  function stopStream() {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (audioCtxRef.current) {
      audioCtxRef.current.close().catch(() => {});
      audioCtxRef.current = null;
    }
  }

  async function start() {
    if (recording || processing || disabled) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      // Waveform level
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      const ctx = new AudioCtx();
      audioCtxRef.current = ctx;
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      analyserRef.current = analyser;
      const source = ctx.createMediaStreamSource(stream);
      source.connect(analyser);
      const buf = new Uint8Array(analyser.frequencyBinCount);

      const tick = () => {
        analyser.getByteTimeDomainData(buf);
        let sum = 0;
        for (let i = 0; i < buf.length; i++) {
          const v = (buf[i] - 128) / 128;
          sum += v * v;
        }
        const rms = Math.sqrt(sum / buf.length);
        setLevel(Math.min(1, rms * 4));
        rafRef.current = requestAnimationFrame(tick);
      };
      tick();

      const mime = 'audio/webm'; // Will be converted to WAV on stop
      const rec = new MediaRecorder(stream, { mimeType: mime });
      mediaRef.current = rec;
      chunksRef.current = [];
      rec.ondataavailable = (e) => e.data.size && chunksRef.current.push(e.data);
      rec.onstop = async () => {
        const webmBlob = new Blob(chunksRef.current, { type: mime });
        stopStream();
        setLevel(0);
        // Convert WebM to WAV for Sarvam compatibility
        const wavBlob = await convertToWav(webmBlob);
        onCapture?.(wavBlob);
      };
      rec.start();
      setRecording(true);
    } catch (err) {
      console.error('mic error', err);
      alert('Mic access denied. Please allow microphone access.');
    }
  }

  async function convertToWav(webmBlob) {
    const arrayBuffer = await webmBlob.arrayBuffer();
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);

    const numberOfChannels = audioBuffer.numberOfChannels;
    const sampleRate = audioBuffer.sampleRate;
    const format = 1; // PCM
    const bitsPerSample = 16;

    const bytesPerSample = bitsPerSample / 8;
    const blockAlign = numberOfChannels * bytesPerSample;
    const byteRate = sampleRate * blockAlign;
    const dataSize = audioBuffer.length * blockAlign;
    const buffer = new ArrayBuffer(44 + dataSize);
    const view = new DataView(buffer);

    // WAV header
    writeString(view, 0, 'RIFF');
    view.setUint32(4, 36 + dataSize, true);
    writeString(view, 8, 'WAVE');
    writeString(view, 12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, format, true);
    view.setUint16(22, numberOfChannels, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, byteRate, true);
    view.setUint16(32, blockAlign, true);
    view.setUint16(34, bitsPerSample, true);
    writeString(view, 36, 'data');
    view.setUint32(40, dataSize, true);

    // Write audio data
    const offset = 44;
    for (let i = 0; i < audioBuffer.numberOfChannels; i++) {
      const channelData = audioBuffer.getChannelData(i);
      let channelOffset = offset;
      for (let j = 0; j < channelData.length; j++) {
        const sample = Math.max(-1, Math.min(1, channelData[j]));
        const intSample = sample < 0 ? sample * 0x8000 : sample * 0x7FFF;
        view.setInt16(channelOffset, intSample, true);
        channelOffset += 2;
      }
    }

    return new Blob([buffer], { type: 'audio/wav' });
  }

  function writeString(view, offset, string) {
    for (let i = 0; i < string.length; i++) {
      view.setUint8(offset + i, string.charCodeAt(i));
    }
  }

  function stop() {
    if (!recording) return;
    setRecording(false);
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    try {
      mediaRef.current?.stop();
    } catch (_) {}
  }

  const busy = recording || processing;
  const label = processing
    ? 'Thinking…'
    : recording
    ? 'Tap to stop'
    : 'Tap to speak';

  return (
    <div className="flex flex-col items-center gap-4">
      <div className="relative">
        {/* Pulse rings when idle */}
        {!busy && (
          <>
            <span
              className="pointer-events-none absolute inset-0 rounded-full bg-accent/40 animate-pulse-ring"
              aria-hidden
            />
            <span
              className="pointer-events-none absolute inset-0 rounded-full bg-accent/30 animate-pulse-ring"
              style={{ animationDelay: '0.8s' }}
              aria-hidden
            />
          </>
        )}
        <motion.button
          type="button"
          onClick={recording ? stop : start}
          disabled={processing || disabled}
          animate={
            recording
              ? { scale: 1 + level * 0.15, boxShadow: `0 0 0 ${8 + level * 30}px hsl(var(--accent) / 0.18)` }
              : { scale: 1, boxShadow: '0 8px 24px hsl(150 47% 11% / 0.15)' }
          }
          transition={{ type: 'spring', stiffness: 140, damping: 14 }}
          whileTap={{ scale: 0.97 }}
          className={`relative grid h-40 w-40 place-items-center rounded-full text-primary-foreground transition-colors ${
            processing
              ? 'bg-primary/70 cursor-wait'
              : recording
              ? 'bg-primary'
              : 'bg-accent hover:bg-accent/90'
          } disabled:opacity-70`}
          data-testid="mic-record-btn"
          aria-label={label}
        >
          {processing ? (
            <Loader2 className="h-14 w-14 animate-spin" strokeWidth={1.5} />
          ) : recording ? (
            <Square className="h-12 w-12 fill-current" strokeWidth={0} />
          ) : (
            <Mic className="h-16 w-16" strokeWidth={1.5} />
          )}
        </motion.button>
      </div>
      <div className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
        {label}
      </div>
    </div>
  );
}
