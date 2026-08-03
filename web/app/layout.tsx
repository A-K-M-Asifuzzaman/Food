import type { Metadata } from "next";
import { Anton, JetBrains_Mono, Source_Sans_3 } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "./components/AuthProvider";
import { RouteTransition } from "./components/RouteTransition";
import { SiteFooter } from "./components/SiteFooter";
import { SiteHeader } from "./components/SiteHeader";
import { THEME_INIT_SCRIPT } from "./components/ThemeToggle";
import { buildSearchIndex } from "@/lib/search";

// Display is heavy and condensed for headings and SFX; body is a humanist sans
// because this is a nutrition app and figures must read unambiguously; mono
// carries tabular figures so nutrition columns align.
const anton = Anton({ variable: "--font-anton", subsets: ["latin"], weight: "400" });
const sourceSans = Source_Sans_3({ variable: "--font-source-sans", subsets: ["latin"] });
const jetbrains = JetBrains_Mono({ variable: "--font-jetbrains", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "FoodGenome AI — read the genome of your plate",
  description:
    "Photograph a dish and get a calibrated prediction, a conformal candidate set, and USDA-grounded nutrition across 101 food categories.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    /* suppressHydrationWarning is load-bearing on both elements. The theme
       script below stamps data-theme on <html> before React hydrates — that is
       the whole point of running it pre-paint — so the server markup cannot
       match by construction. On <body> it absorbs attributes injected by
       browser extensions, which are outside our control and would otherwise
       fill a console with a warning about markup we did not write. */
    <html
      lang="en"
      suppressHydrationWarning
      className={`${anton.variable} ${sourceSans.variable} ${jetbrains.variable} h-full antialiased`}
    >
      {/* Applied before first paint. Running this in an effect instead would
          show a dark-mode reader a full white frame on every navigation. */}
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body suppressHydrationWarning className="min-h-full flex flex-col">
        <AuthProvider>
          <RouteTransition />
          <SiteHeader searchIndex={buildSearchIndex()} />
          {children}
          <SiteFooter />
        </AuthProvider>
      </body>
    </html>
  );
}
