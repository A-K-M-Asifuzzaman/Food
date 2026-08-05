/** The web-shot sound, synthesised.
 *
 *  Shipping an audio file was the obvious route and the wrong one: the sound
 *  everybody pictures is a licensed asset, and a royalty-free stand-in is a
 *  download on every page load to play something two hundred milliseconds long.
 *  Web Audio builds it from noise and a swept filter for nothing.
 *
 *  What a thwip actually is, acoustically: a burst of broadband noise whose
 *  bright content collapses fast — the hiss of something leaving under pressure
 *  — with a pitched whip under it that falls as the strand pays out. Two
 *  layers, one envelope each.
 *
 *  Browsers refuse to start an AudioContext before the reader has interacted
 *  with the page, so the context is created lazily on the first gesture and
 *  every call before that is a silent no-op rather than an error.
 */

const STORAGE_KEY = "foodgenome:sound";

let ctx: AudioContext | null = null;
let noiseBuffer: AudioBuffer | null = null;
let unlocked = false;
let muted = false;
let lastPlayed = 0;

export function isMuted(): boolean {
  return muted;
}

/** Read the stored preference. Sound is opt-out, but nothing can play until a
 *  gesture unlocks the context anyway, so this never surprises anyone on load. */
export function loadPreference(): boolean {
  if (typeof window === "undefined") return false;
  muted = window.localStorage.getItem(STORAGE_KEY) === "off";
  return muted;
}

export function setMuted(next: boolean): void {
  muted = next;
  try {
    window.localStorage.setItem(STORAGE_KEY, next ? "off" : "on");
  } catch {
    // Private browsing denies writes. The preference lasts the session instead.
  }
}

function buildNoise(context: AudioContext): AudioBuffer {
  const length = Math.floor(context.sampleRate * 0.4);
  const buffer = context.createBuffer(1, length, context.sampleRate);
  const data = buffer.getChannelData(0);
  for (let i = 0; i < length; i++) data[i] = Math.random() * 2 - 1;
  return buffer;
}

/** Attach once. The first gesture of any kind opens the context. */
export function armAudio(): () => void {
  if (typeof window === "undefined") return () => {};
  loadPreference();

  const open = () => {
    if (unlocked) return;
    const Ctor = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Ctor) return;
    ctx = new Ctor();
    noiseBuffer = buildNoise(ctx);
    unlocked = true;
    void ctx.resume();
  };

  const events: (keyof WindowEventMap)[] = ["pointerdown", "keydown", "touchstart"];
  events.forEach((e) => window.addEventListener(e, open, { once: true, passive: true }));
  return () => events.forEach((e) => window.removeEventListener(e, open));
}

/**
 * Fire one web-shot.
 *
 * `strength` scales loudness and brightness together — a short strand across a
 * card should not sound like one crossing the viewport.
 */
export function thwip(strength = 1): void {
  if (!unlocked || muted || !ctx || !noiseBuffer) return;

  // Several WebShots can mount at once on a route change. Without this they
  // stack into a single loud smear instead of reading as one sound.
  const now = ctx.currentTime;
  if (now - lastPlayed < 0.06) return;
  lastPlayed = now;

  if (ctx.state === "suspended") void ctx.resume();

  const level = Math.max(0.15, Math.min(1, strength));
  const vary = 0.9 + Math.random() * 0.2;
  const out = ctx.createGain();
  out.gain.value = 0.5 * level;
  out.connect(ctx.destination);

  // Layer one: the hiss. Bandpass swept down hard is what makes it read as
  // something released under tension rather than a plain noise burst.
  const noise = ctx.createBufferSource();
  noise.buffer = noiseBuffer;
  noise.playbackRate.value = vary;

  const band = ctx.createBiquadFilter();
  band.type = "bandpass";
  band.Q.value = 1.1;
  band.frequency.setValueAtTime(4200 * vary, now);
  band.frequency.exponentialRampToValueAtTime(620, now + 0.16);

  const hiss = ctx.createGain();
  hiss.gain.setValueAtTime(0.0001, now);
  hiss.gain.exponentialRampToValueAtTime(0.9, now + 0.006);
  hiss.gain.exponentialRampToValueAtTime(0.0001, now + 0.19);

  noise.connect(band).connect(hiss).connect(out);

  // Layer two: the pitched whip underneath, falling as the strand pays out.
  const tone = ctx.createOscillator();
  tone.type = "triangle";
  tone.frequency.setValueAtTime(880 * vary, now);
  tone.frequency.exponentialRampToValueAtTime(170, now + 0.13);

  const toneGain = ctx.createGain();
  toneGain.gain.setValueAtTime(0.0001, now);
  toneGain.gain.exponentialRampToValueAtTime(0.32, now + 0.008);
  toneGain.gain.exponentialRampToValueAtTime(0.0001, now + 0.15);

  tone.connect(toneGain).connect(out);

  // The impact when it lands, a beat after it leaves.
  const tap = ctx.createBufferSource();
  tap.buffer = noiseBuffer;
  const tapFilter = ctx.createBiquadFilter();
  tapFilter.type = "lowpass";
  tapFilter.frequency.value = 1100;
  const tapGain = ctx.createGain();
  const hit = now + 0.17;
  tapGain.gain.setValueAtTime(0.0001, hit);
  tapGain.gain.exponentialRampToValueAtTime(0.28 * level, hit + 0.004);
  tapGain.gain.exponentialRampToValueAtTime(0.0001, hit + 0.08);
  tap.connect(tapFilter).connect(tapGain).connect(out);

  noise.start(now);
  noise.stop(now + 0.22);
  tone.start(now);
  tone.stop(now + 0.16);
  tap.start(hit);
  tap.stop(hit + 0.1);

  noise.onended = () => out.disconnect();
}
