import type { Metadata } from "next";

import { Analyzer } from "../components/Analyzer";
import { ApiWarmup } from "../components/ApiWarmup";
import { Beat, Caption } from "../components/comic";
import { Spider3D } from "../components/Spider3D";
import { WebShot } from "../components/WebShot";

export const metadata: Metadata = {
  title: "Analyse a photo — FoodGenome AI",
  description:
    "Upload a dish and get a calibrated prediction, a conformal candidate set, attribution and USDA-grounded nutrition.",
};

export default function AnalyzePage() {
  return (
    <main className="flex-1 w-full">
      {/* The header, warm-up bar and analyser share one positioning context so
          the web strand can be drawn from above the heading all the way down
          to the upload panel's corner. */}
      <div className="relative">
        <Spider3D
          className="absolute right-0 top-0 z-10 hidden lg:block w-[260px] h-[360px]"
          scale={1.05}
          side="right"
          fallback={<WebShot targetId="dropzone" corner="tr" pose="perch" />}
        />

        <section className="mx-auto max-w-6xl px-5 pt-10 pb-6">
          <Beat
            n="00"
            title="ANALYSE A PHOTO"
            lede="Everything below is computed from your image: the category, a calibrated confidence, the candidate set the model cannot rule out, where it looked, and nutrition traced to source."
          />
        </section>

        <section className="mx-auto max-w-6xl px-5 pb-4">
          <ApiWarmup />
        </section>

        <section className="mx-auto max-w-6xl px-5 pb-10">
          <Analyzer />
        </section>
      </div>

      <section className="mx-auto max-w-6xl px-5 pb-16">
        <Caption className="max-w-3xl">
          Your photograph is analysed and never stored. Nutrition figures are
          USDA reference values for a typical serving — real portions vary, and
          this is not dietary advice.
        </Caption>
      </section>
    </main>
  );
}
