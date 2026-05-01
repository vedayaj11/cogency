import Link from "next/link";
import { notFound } from "next/navigation";

import { AutoRefresh } from "@/components/auto-refresh";
import { Badge, statusVariant } from "@/components/ui/badge";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { api } from "@/lib/api";
import { formatCost, formatRelative } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function EvalRunPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const run = await api.getEvalRun(id).catch(() => null);
  if (!run) notFound();

  const inProgress = run.status === "pending" || run.status === "running";

  return (
    <div className="space-y-4">
      <AutoRefresh statuses={[run.status]} intervalMs={5000} />

      <div>
        <div className="flex items-center gap-2 text-xs text-[hsl(var(--muted-foreground))]">
          <Link href="/evals" className="hover:underline">Evals</Link>
          <span>/</span>
          <span className="font-mono">{run.id.slice(0, 8)}</span>
        </div>
        <div className="mt-1 flex items-center gap-3">
          <h1 className="text-xl font-semibold">
            <span className="font-mono">{run.aop_name}</span>
            {run.aop_version_number ? (
              <span className="text-[hsl(var(--muted-foreground))]"> @v{run.aop_version_number}</span>
            ) : null}
          </h1>
          <Badge variant={statusVariant(run.status)}>{run.status}</Badge>
          {run.pass_rate != null ? (
            <PassRate rate={run.pass_rate} />
          ) : null}
        </div>
        <div className="mt-1 flex items-center gap-3 text-xs text-[hsl(var(--muted-foreground))]">
          <span>against {run.dataset_name}</span>
          <span>· started {formatRelative(run.started_at)}</span>
          {run.ended_at ? <span>· ended {formatRelative(run.ended_at)}</span> : null}
          <span>· {run.cases_passed}/{run.cases_total} passed</span>
          <span>· {formatCost(run.cost_usd ?? 0)}</span>
          {run.judge_model ? (
            <span>· judge: <code className="font-mono">{run.judge_model}</code></span>
          ) : null}
        </div>
      </div>

      {run.aggregate_scores ? (
        <Card>
          <CardHeader>
            <CardTitle>Aggregate rubric</CardTitle>
          </CardHeader>
          <CardBody>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              {Object.entries(run.aggregate_scores).map(([k, v]) => (
                <ScoreTile key={k} label={k} score={v} />
              ))}
            </div>
          </CardBody>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Per-case results</CardTitle>
          <span className="text-xs text-[hsl(var(--muted-foreground))]">
            {run.results.length} result{run.results.length === 1 ? "" : "s"}
          </span>
        </CardHeader>
        <CardBody>
          {run.results.length === 0 ? (
            <div className="text-sm text-[hsl(var(--muted-foreground))]">
              {inProgress ? "Running… results stream in as cases complete." : "No results."}
            </div>
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>Pass</TH>
                  <TH>Aggregate</TH>
                  <TH>tc</TH>
                  <TH>pa</TH>
                  <TH>tn</TH>
                  <TH>ca</TH>
                  <TH>Run</TH>
                  <TH>Status</TH>
                  <TH>Reasoning</TH>
                </TR>
              </THead>
              <TBody>
                {run.results.map((r) => (
                  <TR key={r.id}>
                    <TD>
                      {r.passed ? (
                        <Badge variant="success">pass</Badge>
                      ) : (
                        <Badge variant="danger">fail</Badge>
                      )}
                    </TD>
                    <TD className="font-mono text-xs">{r.aggregate.toFixed(2)}</TD>
                    <TD className="font-mono text-xs">{(r.scores.task_completion ?? 0).toFixed(2)}</TD>
                    <TD className="font-mono text-xs">{(r.scores.policy_adherence ?? 0).toFixed(2)}</TD>
                    <TD className="font-mono text-xs">{(r.scores.tone ?? 0).toFixed(2)}</TD>
                    <TD className="font-mono text-xs">{(r.scores.citation_accuracy ?? 0).toFixed(2)}</TD>
                    <TD>
                      {r.aop_run_id ? (
                        <Link href={`/runs/${r.aop_run_id}`} className="font-mono text-xs hover:underline">
                          {r.aop_run_id.slice(0, 8)}
                        </Link>
                      ) : (
                        <span className="text-xs text-[hsl(var(--muted-foreground))]">—</span>
                      )}
                    </TD>
                    <TD>
                      <Badge variant={statusVariant(r.execution_status ?? "")}>
                        {r.execution_status ?? "—"}
                      </Badge>
                    </TD>
                    <TD className="max-w-lg text-xs text-[hsl(var(--muted-foreground))]">
                      <span className="line-clamp-2">{r.judge_reasoning ?? "—"}</span>
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          )}
        </CardBody>
      </Card>
    </div>
  );
}

function PassRate({ rate }: { rate: number }) {
  const pct = Math.round(rate * 100);
  const variant = rate >= 0.85 ? "success" : rate >= 0.5 ? "warning" : "danger";
  return <Badge variant={variant}>{pct}%</Badge>;
}

function ScoreTile({ label, score }: { label: string; score: number }) {
  const variant = score >= 0.85 ? "success" : score >= 0.5 ? "warning" : "danger";
  return (
    <div className="rounded-md border border-[hsl(var(--border))] p-3">
      <div className="text-xs text-[hsl(var(--muted-foreground))] capitalize">
        {label.replace(/_/g, " ")}
      </div>
      <div className="mt-1 flex items-center gap-2">
        <span className="font-mono text-lg">{score.toFixed(2)}</span>
        <Badge variant={variant}>{Math.round(score * 100)}%</Badge>
      </div>
    </div>
  );
}
