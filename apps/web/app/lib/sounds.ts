// Small synthesized sound effects (Web Audio, no audio files). Browsers only allow sound after the user
// has interacted with the page once, so a wake heard before any click or tap may stay silent.

let context: AudioContext | null = null;

function audio(): AudioContext | null {
  if (typeof window === "undefined") return null;
  try {
    context ??= new AudioContext();
    if (context.state === "suspended") void context.resume();
    return context;
  } catch {
    return null;
  }
}

// One soft tone that glides between two pitches and fades out.
function tone(ctx: AudioContext, start: number, from: number, to: number, seconds: number, volume: number, type: OscillatorType) {
  const oscillator = ctx.createOscillator();
  const gain = ctx.createGain();
  oscillator.type = type;
  oscillator.frequency.setValueAtTime(from, start);
  oscillator.frequency.exponentialRampToValueAtTime(to, start + seconds);
  gain.gain.setValueAtTime(0.0001, start);
  gain.gain.exponentialRampToValueAtTime(volume, start + 0.012);
  gain.gain.exponentialRampToValueAtTime(0.0001, start + seconds);
  oscillator.connect(gain).connect(ctx.destination);
  oscillator.start(start);
  oscillator.stop(start + seconds + 0.02);
}

/** Bright two-note "boop-beep" when HomePilot wakes up and becomes alert. */
export function playAlert() {
  const ctx = audio();
  if (!ctx) return;
  const now = ctx.currentTime;
  tone(ctx, now, 520, 700, 0.11, 0.08, "sine");
  tone(ctx, now + 0.1, 780, 1180, 0.16, 0.08, "sine");
}

/** Short soft tick when the assistant is tapped or clicked. */
export function playClick() {
  const ctx = audio();
  if (!ctx) return;
  tone(ctx, ctx.currentTime, 1500, 900, 0.045, 0.05, "triangle");
}
