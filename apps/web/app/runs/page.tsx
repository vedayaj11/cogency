import Link from "next/link";

import { Badge, statusVariant } from "@/components/ui/badge";
import { Empty } from "@/components/ui/empty";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { api } from "@/lib/api";
import { formatCost, formatRelative, formatTokens } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function RunsPage({
  searchParams,
}: {
  searchParams: Promise<{ status?: string; aop_name?: string }>;
}) {
  const { status, aop_name } = await searchParams;
  const data = await api.listRuns({ status, aop_name }).catch(() => ({ items: [], total: 0 }));

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-xl font-semibold">Runs</h1>
          <p className="text-sm text-[hsl(var(--muted-foreground))]">
            Every AOP execution across all cases. Click a row for the full step-by-step trace.
          </p>
        </div>
        <form className="flex items-center gap-2" action="/runs">
          <select
            name="status"
            defaultValue={status ?? ""}
            className="h-8 rounded-md border border-[hsl(var(--border))] bg-transparent px-2 text-sm"
          >
            <option value="">Any status</option>
            <option value="resolved">Resolved</option>
            <option value="escalated_human">Escalated</option>
            <option value="failed">Failed</option>
            <option value="running">Running</option>
          </select>
          <input
            name="aop_name"
            defaultValue={aop_name ?? ""}
            placeholder="AOP name"
            className="h-8 w-48 rounded-md border border-[hsl(var(--border))] bg-transparent px-2 text-sm"
          />
          <button
            type="submit"
            className="h-8 rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--background))] px-3 text-sm hover:bg-[hsl(var(--muted))]"
          >
            Filter
          </button>
        </form>
      </div>

      {data.items.length === 0 ? (
        <Empty
          title="No runs yet"
          hint="Trigger an AOP from a case workspace to see runs here."
        />
      ) : (
        <>
          <Table>
            <THead>
              <TR>
                <TH>Run</TH>
                <TH>AOP</TH>
                <TH>Case</TH>
                <TH>Status</TH>
                <TH>Cost</TH>
                <TH>Tokens</TH>
                <TH>Started</TH>
                <TH>Duration</TH>
              </TR>
            </THead>
            <TBody>
              {data.items.map((r) => (
                <TR key={r.id}>
                  <TD className="font-mono text-xs">
                    <Link href={`/runs/${r.id}`} className="hover:underline">
                      {r.id.slice(0, 8)}
                    </Link>
                  </TD>
                  <TD>
                    <span className="font-mono text-xs">{r.aop_name ?? "—"}</span>
                  </TD>
                  <TD className="font-mono text-xs">
                    <Link href={`/cases/${r.case_id}`} className="hover:underline">
                      {r.case_id.slice(0, 14)}…
                    </Link>
                  </TD>
                  <TD>
                    <Badge variant={statusVariant(r.status)}>{r.status}</Badge>
                  </TD>
                  <TD>{formatCost(r.cost_usd)}</TD>
                  <TD className="text-[hsl(var(--muted-foreground))]">
                    {formatTokens(r.token_in)} / {formatTokens(r.token_out)}
                  </TD>
                  <TD className="text-[hsl(var(--muted-foreground))]">
                    {formatRelative(r.started_at)}
                  </TD>
                  <TD className="text-[hsl(var(--muted-foreground))]">
                    {r.ended_at
                      ? `${Math.round(
                          (new Date(r.ended_at).getTime() - new Date(r.started_at).getTime()) / 1000,
                        )}s`
                      : "—"}
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
          <div className="text-xs text-[hsl(var(--muted-foreground))]">
            Showing {data.items.length} of {data.total}
          </div>
        </>
      )}
    </div>
  );
}
