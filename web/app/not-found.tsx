import Link from "next/link";

export default function NotFound() {
  return (
    <main className="flex-1 w-full grid place-items-center px-5 py-20">
      <div className="max-w-xl w-full text-center">
        <p className="text-6xl sm:text-8xl">
          <span className="sfx-burst">MISS!</span>
        </p>

        <h1 className="font-display text-4xl sm:text-5xl mt-8 leading-none">
          <span className="ink-split">NOTHING HERE</span>
        </h1>

        <p className="mt-4 text-[var(--text-dim)]">
          This page does not exist. The knowledge base covers 101 dish categories — the one
          you were after may be under a different name.
        </p>

        <div className="mt-8 flex flex-wrap gap-3 justify-center">
          <Link
            href="/dishes"
            className="ink-edge px-6 py-3 font-display uppercase tracking-wide"
            style={{ background: "var(--color-red)", color: "#f4f1e8" }}
          >
            Browse all 101
          </Link>
          <Link href="/analyze" className="ink-edge px-6 py-3 font-display uppercase tracking-wide">
            Analyse a photo
          </Link>
        </div>
      </div>
    </main>
  );
}
