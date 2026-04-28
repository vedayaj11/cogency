import Link from "next/link";

import { api } from "@/lib/api";
import { formatRelative } from "@/lib/format";
import { Badge, statusVariant } from "@/components/ui/badge";
import { Empty } from "@/components/ui/empty";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";

export const dynamic = "force-dynamic";

export default async function CasesPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; status?: string }>;
}) {
  const { q, status } = await searchParams;
  let data: Awaited<ReturnType<typeof api.listCases>>;
  try {
    data = await api.listCases({ q, status });
  } catch (err) {
    return <ErrorState message={(err as Error).message} />;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-xl font-semibold">Workspace</h1>
          <p className="text-sm text-[hsl(var(--muted-foreground))]">
            Cases mirrored from Salesforce. Click a row to open the case workspace.
          </p>
        </div>
        <form className="flex items-center gap-2" action="/cases">
          <input
            name="q"
            defaultValue={q ?? ""}
            placeholder="Search subject, number, description"
            className="h-8 w-72 rounded-md border border-[hsl(var(--border))] bg-transparent px-2 text-sm"
          />
          <select
            name="status"
            defaultValue={status ?? ""}
            className="h-8 rounded-md border border-[hsl(var(--border))] bg-transparent px-2 text-sm"
          >
            <option value="">All statuses</option>
            <option value="New">New</option>
            <option value="Working">Working</option>
            <option value="Escalated">Escalated</option>
            <option value="Closed">Closed</option>
          </select>
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
          title="No cases mirrored yet"
          hint="Trigger a Salesforce backfill via POST /v1/integrations/salesforce/backfill or run scripts/backfill_cases.py."
        />
      ) : (
        <>
          <Table>
            <THead>
              <TR>
                <TH>Case #</TH>
                <TH>Subject</TH>
                <TH>Status</TH>
                <TH>Priority</TH>
                <TH>Updated</TH>
                <TH>Runs</TH>
              </TR>
            </THead>
            <TBody>
              {data.items.map((c) => (
                <TR key={c.id}>
                  <TD className="font-mono text-xs">
                    <Link href={`/cases/${c.id}`} className="hover:underline">
                      {c.case_number ?? c.id.slice(0, 8)}
                    </Link>
                  </TD>
                  <TD>
                    <Link href={`/cases/${c.id}`} className="line-clamp-1 hover:underline">
                      {c.subject ?? "—"}
                    </Link>
                  </TD>
                  <TD>
                    <Badge variant={statusVariant(c.status)}>{c.status ?? "—"}</Badge>
                  </TD>
                  <TD className="text-[hsl(var(--muted-foreground))]">{c.priority ?? "—"}</TD>
                  <TD className="text-[hsl(var(--muted-foreground))]">
                    {formatRelative(c.system_modstamp)}
                  </TD>
                  <TD>
                    {c.has_runs ? (
                      <Badge variant="info">has runs</Badge>
                    ) : (
                      <span className="text-[hsl(var(--muted-foreground))]">—</span>
                    )}
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

function ErrorState({ message }: { message: string }) {
  return (
    <Empty
      title="Couldn't load cases"
      hint={`API error: ${message}. Make sure the API service is running on http://localhost:8000.`}
    />
  );
}
