import { WebLoader } from "../../components/WebLoader";

export default function Loading() {
  return (
    <main className="flex-1 w-full grid place-items-center px-5 py-24">
      <WebLoader label="Reading the record" sub="USDA FoodData Central" />
    </main>
  );
}
