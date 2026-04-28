import { Empty } from "@/components/ui/empty";

export default function RunsIndex() {
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Runs</h1>
      <Empty
        title="Open a run from a case"
        hint="Run history per-case appears on the case workspace. Direct deep-links work at /runs/{run_id}."
      />
    </div>
  );
}
