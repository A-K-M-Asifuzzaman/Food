import type { Metadata } from "next";

import { Analyzer } from "../components/Analyzer";
import { Beat, Caption } from "../components/comic";

export const metadata: Metadata = {
  title: "Analyse a photo — FoodGenome AI",
  description:
    "Upload a dish and get a calibrated prediction, a conformal candidate set, attribution and USDA-grounded nutrition.",
};

export default function AnalyzePage() {
  return (
    <main className="flex-1 w-full">
      <section className="mx-auto max-w-6xl px-5 pt-10 pb-6">
        <Beat
          n="00"
          title="ANALYSE A PHOTO"
          lede="Everything below is computed from your image: the category, a calibrated confidence, the candidate set the model cannot rule out, where it looked, and nutrition traced to source."
        />
      </section>

      <section className="mx-auto max-w-6xl px-5 pb-10">
        <Analyzer />
      </section>

      <section className="mx-auto max-w-6xl px-5 pb-16">
        <Caption className="max-w-3xl">
          Your photograph is analysed and never stored. Nutrition figures are USDA reference
          values for a typical serving — real portions vary, and this is not dietary advice.
        </Caption>
      </section>
    </main>
  );
}
