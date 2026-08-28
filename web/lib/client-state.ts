"use client";

import { useCallback, useSyncExternalStore } from "react";

/**
 * Reading the browser after mount, without the setState-in-an-effect cascade.
 *
 * Every control in the header has the same shape of problem: the server cannot know the
 * reader's theme, media queries or stored preferences, so the value has to arrive on the
 * client. Doing that in an effect means rendering once with a wrong value and then
 * setting state to correct it. useSyncExternalStore states the two snapshots up front
 * instead, so React hydrates against the server value and re-renders against the real
 * one in the same commit.
 */

const noSubscription = () => () => {};

/** False through the server render and hydration, true on every client render after. */
export function useHydrated(): boolean {
  return useSyncExternalStore(
    noSubscription,
    () => true,
    () => false,
  );
}

/** A media query, kept live. Assumed false until the client has hydrated. */
export function useMediaQuery(query: string): boolean {
  const subscribe = useCallback(
    (listener: () => void) => {
      const mq = window.matchMedia(query);
      mq.addEventListener("change", listener);
      return () => mq.removeEventListener("change", listener);
    },
    [query],
  );
  const snapshot = useCallback(() => window.matchMedia(query).matches, [query]);
  return useSyncExternalStore(subscribe, snapshot, () => false);
}
