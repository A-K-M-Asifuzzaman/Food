"use client";

import {
  GoogleAuthProvider,
  type User,
  createUserWithEmailAndPassword,
  onAuthStateChanged,
  signInWithEmailAndPassword,
  signInWithPopup,
  signOut as fbSignOut,
  updateProfile,
} from "firebase/auth";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { firebaseAuth } from "@/lib/firebase";

/** Sign-in state for the whole app.
 *
 *  A prediction is attributed to an account, so the account has to be known
 *  before the analyser will run. This provider holds that state and, more
 *  usefully, hands out `authFetch` — a fetch that attaches a fresh ID token.
 *
 *  Tokens are the part that goes wrong quietly. Firebase ID tokens expire after
 *  an hour, so a page left open overnight would start getting 401s from an
 *  interface that still shows the user as signed in. `getIdToken()` refreshes
 *  on demand, which is why every request goes through here rather than caching
 *  a token at sign-in.
 */

type AuthState = {
  user: User | null;
  /** True until Firebase has restored (or ruled out) a persisted session. */
  loading: boolean;
  isAdmin: boolean;
  signInWithGoogle: () => Promise<void>;
  signInWithPassword: (email: string, password: string) => Promise<void>;
  registerWithPassword: (name: string, email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  /** fetch() with a fresh Firebase ID token attached. */
  authFetch: (input: string, init?: RequestInit) => Promise<Response>;
};

const Ctx = createContext<AuthState | null>(null);

/** Accounts the interface offers the console to. The server checks this again
 *  and is the authority — a client deciding it is an admin is not a check. */
const ADMIN_EMAILS = ["zasif855@gmail.com"];

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    return onAuthStateChanged(firebaseAuth(), (u) => {
      setUser(u);
      setLoading(false);
    });
  }, []);

  const authFetch = useCallback(
    async (input: string, init: RequestInit = {}) => {
      const current = firebaseAuth().currentUser;
      const headers = new Headers(init.headers);
      if (current) headers.set("Authorization", `Bearer ${await current.getIdToken()}`);
      return fetch(input, { ...init, headers });
    },
    [],
  );

  const value = useMemo<AuthState>(
    () => ({
      user,
      loading,
      isAdmin: !!user?.email && ADMIN_EMAILS.includes(user.email.toLowerCase()),
      signInWithGoogle: async () => {
        await signInWithPopup(firebaseAuth(), new GoogleAuthProvider());
      },
      signInWithPassword: async (email, password) => {
        await signInWithEmailAndPassword(firebaseAuth(), email, password);
      },
      registerWithPassword: async (name, email, password) => {
        const cred = await createUserWithEmailAndPassword(firebaseAuth(), email, password);
        if (name) await updateProfile(cred.user, { displayName: name });
      },
      signOut: async () => {
        await fbSignOut(firebaseAuth());
      },
      authFetch,
    }),
    [user, loading, authFetch],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
