"use client";

import { type FirebaseApp, getApps, initializeApp } from "firebase/app";
import { type Auth, getAuth } from "firebase/auth";

/** Firebase client initialisation.
 *
 *  These values are not secrets. A Firebase web config identifies the project;
 *  it does not authorise anything, which is why Google ships it in a copyable
 *  snippet and why it is fine in a public repository. What actually protects
 *  the data is two things: the security rules in `firestore.rules`, which deny
 *  every client read and write outright, and the ID token check on the API.
 *
 *  Nothing here talks to Firestore. The browser's only job is to sign a user in
 *  and hand their ID token to our own service, which verifies it against
 *  Google's public keys before it will attribute a prediction to anyone.
 *
 *  Read from the environment so a fork can point at its own project without
 *  editing source, with this project's values as the fallback.
 */
const config = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY ?? "AIzaSyAfcxq0DZCD_09NC7kJMaZ7Fourq93V8AI",
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN ?? "foodgenome-ai-491de.firebaseapp.com",
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID ?? "foodgenome-ai-491de",
  storageBucket:
    process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET ?? "foodgenome-ai-491de.firebasestorage.app",
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_SENDER_ID ?? "920833953227",
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID ?? "1:920833953227:web:23cfdd496927ef8f913a4e",
};

let app: FirebaseApp | null = null;

export function firebaseApp(): FirebaseApp {
  if (!app) app = getApps()[0] ?? initializeApp(config);
  return app;
}

export function firebaseAuth(): Auth {
  return getAuth(firebaseApp());
}
