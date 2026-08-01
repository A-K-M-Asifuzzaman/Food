import type { Metadata } from "next";
import { Anton, JetBrains_Mono, Source_Sans_3 } from "next/font/google";
import "./globals.css";

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
    <html
      lang="en"
      className={`${anton.variable} ${sourceSans.variable} ${jetbrains.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
