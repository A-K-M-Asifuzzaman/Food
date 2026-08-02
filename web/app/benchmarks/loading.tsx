import { WebLoader } from "../components/WebLoader";

export default function Loading() {
  return (
    <main className="flex-1 w-full grid place-items-center px-5 py-24">
      <WebLoader label="Spinning the strand" sub="benchmarks" />
    </main>
  );
}
