"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { Button } from "@/components/ui/button";

type AOPOption = { name: string; description: string | null };

export function RunAOPButton({
  caseId,
  options,
}: {
  caseId: string;
  options: AOPOption[];
}) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string>(options[0]?.name ?? "");

  if (options.length === 0) {
    return (
      <div className="text-xs text-[hsl(var(--muted-foreground))]">
        Deploy an AOP first via <code>POST /v1/aops</code>.
      </div>
    );
  }

  async function handleRun() {
    setError(null);
    if (!selected) return;
    try {
      const res = await fetch("/api/v1/aop_runs", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ aop_name: selected, case_id: caseId }),
      });
      if (!res.ok) {
        setError(await res.text());
        return;
      }
      // Refresh the case detail to pick up the new aop_run row.
      startTransition(() => router.refresh());
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <select
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          className="h-8 flex-1 rounded-md border border-[hsl(var(--border))] bg-transparent px-2 text-sm"
        >
          {options.map((o) => (
            <option key={o.name} value={o.name}>
              {o.name}
            </option>
          ))}
        </select>
        <Button onClick={handleRun} disabled={pending} variant="primary" size="sm">
          {pending ? "Starting…" : "Run AOP"}
        </Button>
      </div>
      {error ? <div className="text-xs text-rose-500">{error}</div> : null}
    </div>
  );
}
