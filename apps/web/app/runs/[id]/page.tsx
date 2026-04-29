import Link from "next/link";
import { notFound } from "next/navigation";

import { Badge, statusVariant } from "@/components/ui/badge";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { formatCost, formatRelative, formatTokens } from "@/lib/format";

import { AutoRefresh } from "@/components/auto-refresh";

export const dynamic = "force-dynamic";

export default async function RunPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const run = await api.getRun(id).catch(() => null);
  if (!run) notFound();

  return (
    <div className="space-y-4">
      <AutoRefresh statuses={[run.status]} />
      <div>
        <div className="flex items-center gap-2 text-xs text-[hsl(var(--muted-foreground))]">
          <Link href={`/cases/${run.case_id}`} className="hover:underline">
            Case {run.case_id}
          </Link>
          <span>/</span>
          <span className="font-mono">{run.id.slice(0, 8)}</span>
        </div>
        <div className="mt-1 flex items-center gap-3">
          <h1 className="text-xl font-semibold">AOP run</h1>
          <Badge variant={statusVariant(run.status)}>{run.status}</Badge>
        </div>
        <div className="mt-1 flex items-center gap-3 text-xs text-[hsl(var(--muted-foreground))]">
          <span>Started {formatRelative(run.started_at)}</span>
          {run.ended_at ? <span>· Ended {formatRelative(run.ended_at)}</span> : null}
          <span>· Cost {formatCost(run.cost_usd)}</span>
          <span>
            · Tokens {formatTokens(run.token_in)} in / {formatTokens(run.token_out)} out
          </span>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Steps</CardTitle>
          <span className="text-xs text-[hsl(var(--muted-foreground))]">
            {run.steps.length} step{run.steps.length === 1 ? "" : "s"}
          </span>
        </CardHeader>
        <CardBody className="space-y-3">
          {run.steps.length === 0 ? (
            <div className="text-sm text-[hsl(var(--muted-foreground))]">
              Run is still in progress. Refresh the page in a few seconds.
            </div>
          ) : (
            run.steps.map((step) => (
              <Step key={`${step.step_index}-${step.tool_name}`} step={step} />
            ))
          )}
        </CardBody>
      </Card>
    </div>
  );
}

function Step({ step }: { step: NonNullable<Awaited<ReturnType<typeof api.getRun>>>["steps"][number] }) {
  const isFinal = step.tool_name === "(final_message)";
  const isGuardrail = step.tool_name === "(guardrail)";
  return (
    <div className="rounded-md border border-[hsl(var(--border))]">
      <div className="flex items-center justify-between border-b border-[hsl(var(--border))] px-3 py-2">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs text-[hsl(var(--muted-foreground))]">
            {String(step.step_index).padStart(2, "0")}
          </span>
          <span className="text-sm font-medium">{step.tool_name}</span>
          <Badge variant={statusVariant(step.status)}>{step.status}</Badge>
          {step.latency_ms != null ? (
            <span className="text-xs text-[hsl(var(--muted-foreground))]">
              {step.latency_ms}ms
            </span>
          ) : null}
        </div>
      </div>
      <div className="grid grid-cols-2 divide-x divide-[hsl(var(--border))]">
        <Pane label="Input" data={step.input} mono />
        <Pane
          label={isFinal ? "Final message" : isGuardrail ? "Violation" : "Output"}
          data={step.output}
          mono={!isFinal}
        />
      </div>
      {step.error ? (
        <div className="border-t border-[hsl(var(--border))] bg-rose-500/5 px-3 py-2 text-xs text-rose-600">
          {step.error}
        </div>
      ) : null}
    </div>
  );
}

function Pane({ label, data, mono }: { label: string; data: unknown; mono?: boolean }) {
  return (
    <div className="px-3 py-2">
      <div className="mb-1 text-xs uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
        {label}
      </div>
      <pre
        className={
          "max-h-72 overflow-auto whitespace-pre-wrap text-xs " +
          (mono ? "font-mono" : "")
        }
      >
        {data ? JSON.stringify(data, null, 2) : "—"}
      </pre>
    </div>
  );
}
