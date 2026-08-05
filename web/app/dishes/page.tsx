import type { Metadata } from "next";

import { Beat } from "../components/comic";
import { Reveal } from "../components/Reveal";
import { Spider3D } from "../components/Spider3D";
import { WebShot } from "../components/WebShot";
import { DishBrowser } from "../components/DishBrowser";
import { getKb } from "@/lib/kb";

export const metadata: Metadata = {
  title: "All 101 dishes — FoodGenome AI",
  description:
    "Every Food-101 category with its USDA-grounded nutrition profile, serving size and provenance.",
};

export default function DishesPage() {
  const kb = getKb();

  // Sent to the client as a trimmed projection. The full knowledge base is
  // 300 kB and the browser only needs what the grid filters and sorts on;
  // shipping the rest would be a third of a megabyte of unread nutrient tables.
  const dishes = kb.entries.map((e) => ({
    slug: e.class,
    title: e.title,
    cuisine: e.cuisine,
    tags: e.tags,
    method: e.method,
    kcal: e.nutrients_per_100g.energy_kcal ?? 0,
    protein: e.nutrients_per_100g.protein_g ?? 0,
    serving: e.serving_label,
  }));

  const direct = dishes.filter((d) => d.method === "direct").length;

  return (
    <main className="flex-1 w-full">
      <Reveal>
      <div className="relative overflow-hidden">
      <section className="mx-auto max-w-6xl px-5 pt-10 pb-6">
        <Beat
          n="—"
          title="EVERY DISH"
          lede={`All ${dishes.length} Food-101 categories. ${direct} map directly to a USDA SR Legacy record; the other ${dishes.length - direct} had no record of their own and were composed from weighted ingredients, which is stated on every one.`}
        />
      </section>

        <Spider3D
          className="absolute right-1 top-0 z-10 w-[128px] h-[170px] opacity-70 sm:w-[170px] sm:h-[210px] sm:opacity-100 xl:right-2 xl:w-[330px] xl:h-[340px]"
          scale={0.8}
          side="right"
          // Not draggable here: this page's controls sit under the figure, and
          // an invisible canvas that swallows a click on the sort button is a
          // worse bug than a figure you cannot spin.
          interactive={false}
          model="/models/slinger-b.glb"
          pose={[0.1, -0.45, 0.06]}
          fallback={<WebShot targetId="dish-browser" corner="tl" pose="crawl" top={-6} />}
        />
        <section id="dish-browser" className="mx-auto max-w-6xl px-5 pb-16">
          <DishBrowser dishes={dishes} />
        </section>
      </div>
      </Reveal>
    </main>
  );
}
