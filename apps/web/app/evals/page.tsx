import Link from "next/link";

import { Badge, statusVariant } from "@/components/ui/badge";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { Empty } from "@/components/ui/empty";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { api } from "@/lib/api";
import { formatCost, formatRelative } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function EvalsPage() {
  const [datasets, runs] = await Promise.all([
    api.listGoldenDatasets().catch(() => ({ items: [] })),
    api.listEvalRuns().catch(() => ({ items: [] })),
  ]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Evals</h1>
        <p className="text-sm text-[hsl(var(--muted-foreground))]">
          Golden datasets + LLM-judge runs gating AOP deploys (PRD §6.6).
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Golden datasets</CardTitle>
          <span className="text-xs text-[hsl(var(--muted-foreground))]">
            {datasets.items.length} dataset{datasets.items.length === 1 ? "" : "s"}
          </span>
        </CardHeader>
        <CardBody>
          {datasets.items.length === 0 ? (
            <Empty
              title="No golden datasets"
              hint="Seed one via scripts/seed_golden_dataset.py or POST /v1/golden_datasets."
            />
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>Name</TH>
                  <TH>AOP</TH>
                  <TH>Cases</TH>
                  <TH>Description</TH>
                  <TH>Created</TH>
                </TR>
              </THead>
              <TBody>
                {datasets.items.map((d) => (
                  <TR key={d.id}>
                    <TD>
                      <span className="font-mono text-xs">{d.name}</span>
                    </TD>
                    <TD>
                      {d.aop_name ? (
                        <Badge variant="info">{d.aop_name}</Badge>
                      ) : (
                        <span className="text-xs text-[hsl(var(--muted-foreground))]">
                          (any)
                        </span>
                      )}
                    </TD>
                    <TD>{d.cases_count}</TD>
                    <TD className="max-w-md text-[hsl(var(--muted-foreground))]">
                      <span className="line-clamp-2">{d.description ?? "—"}</span>
                    </TD>
                    <TD className="text-[hsl(var(--muted-foreground))]">
                      {formatRelative(d.created_at)}
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recent eval runs</CardTitle>
        </CardHeader>
        <CardBody>
          {runs.items.length === 0 ? (
            <Empty
              title="No eval runs yet"
              hint='Trigger one with `POST /v1/eval_runs {"aop_name":"case_manager","dataset_id":"..."}`.'
            />
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>Run</TH>
                  <TH>AOP</TH>
                  <TH>Dataset</TH>
                  <TH>Pass rate</TH>
                  <TH>Cases</TH>
                  <TH>Cost</TH>
                  <TH>Status</TH>
                  <TH>Started</TH>
                </TR>
              </THead>
              <TBody>
                {runs.items.map((r) => (
                  <TR key={r.id}>
                    <TD className="font-mono text-xs">
                      <Link href={`/evals/${r.id}`} className="hover:underline">
                        {r.id.slice(0, 8)}
                      </Link>
                    </TD>
                    <TD>
                      <span className="font-mono text-xs">
                        {r.aop_name ?? "—"}
                        {r.aop_version_number ? `@v${r.aop_version_number}` : ""}
                      </span>
                    </TD>
                    <TD className="font-mono text-xs">{r.dataset_name ?? "—"}</TD>
                    <TD>
                      {r.pass_rate != null ? (
                        <PassRate rate={r.pass_rate} />
                      ) : (
                        <span className="text-xs text-[hsl(var(--muted-foreground))]">—</span>
                      )}
                    </TD>
                    <TD className="text-[hsl(var(--muted-foreground))]">
                      {r.cases_passed}/{r.cases_total}
                    </TD>
                    <TD>{r.cost_usd != null ? formatCost(r.cost_usd) : "—"}</TD>
                    <TD>
                      <Badge variant={statusVariant(r.status)}>{r.status}</Badge>
                    </TD>
                    <TD className="text-[hsl(var(--muted-foreground))]">
                      {formatRelative(r.started_at)}
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
