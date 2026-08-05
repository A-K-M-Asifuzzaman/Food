"use client";

import { useEffect, useState } from "react";

import { armAudio, isMuted, loadPreference, setMuted, thwip } from "@/lib/sfx";

/** Mute control for the web-shot sound.
 *
 *  Sound that cannot be switched off is a bug, and one buried in a settings page
 *  is barely better — the control belongs next to the sound. Toggling it on
 *  fires a thwip, because a mute button that goes quiet when you enable audio
 *  gives you no way to know it worked.
 *
 *  Nothing plays until the reader has interacted with the page regardless:
 *  browsers refuse to open an AudioContext before a gesture, and `armAudio`
 *  waits for one.
 */
export function SoundToggle() {
  const [ready, setReady] = useState(false);
  const [off, setOff] = useState(false);

  useEffect(() => {
    setOff(loadPreference());
    setReady(true);
    return armAudio();
  }, []);

  // Same reasoning as the theme control: a button that renders one state on the
  // server and flips on hydration is worse than a held space for one frame.
  if (!ready) {
    return <div className="w-8 h-8 shrink-0" aria-hidden="true" />;
  }

  const toggle = () => {
    const next = !off;
    setOff(next);
    setMuted(next);
    if (!next) thwip(0.8);
  };

  return (
    <button
      type="button"
      role="switch"
      aria-checked={!off}
      aria-label={off ? "Turn web-shot sound on" : "Turn web-shot sound off"}
      title={off ? "Sound off" : "Sound on"}
      onClick={toggle}
      className="grid place-items-center w-8 h-8 shrink-0 ink-edge"
      style={{ background: "var(--panel)" }}
    >
      <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
        <path
          d="M4 9.5h3.5L12 5.5v13L7.5 14.5H4Z"
          fill="var(--line)"
          stroke="var(--line)"
          strokeWidth="1.4"
          strokeLinejoin="round"
        />
        {off ? (
          <path
            d="M16 9.5l5 5M21 9.5l-5 5"
            stroke="var(--color-red)"
            strokeWidth="2"
            strokeLinecap="round"
            fill="none"
          />
        ) : (
          // Two arcs rather than three: at 16px the third is a smudge.
          <g stroke="var(--line)" strokeWidth="1.7" fill="none" strokeLinecap="round">
            <path d="M15.5 9.2a4 4 0 0 1 0 5.6" />
            <path d="M18 7a7.4 7.4 0 0 1 0 10" />
          </g>
        )}
      </svg>
    </button>
  );
}
