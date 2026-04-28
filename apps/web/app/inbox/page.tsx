import Link from "next/link";

import { Badge, statusVariant } from "@/components/ui/badge";
import { Empty } from "@/components/ui/empty";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { api } from "@/lib/api";
import { formatRelative } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function InboxPage({
  searchParams,
}: {
  searchParams: Promise<{ status?: string }>;
}) {
  const { status } = await searchParams;
  const data = await api.listInbox(status ?? "pending").catch(() => ({ items: [] }));

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-xl font-semibold">Inbox</h1>
          <p className="text-sm text-[hsl(var(--muted-foreground))]">
            Cases the AI escalated for human review.
          </p>
        </div>
        <form className="flex items-center gap-2" action="/inbox">
          <select
            name="status"
            defaultValue={status ?? "pending"}
            className="h-8 rounded-md border border-[hsl(var(--border))] bg-transparent px-2 text-sm"
          >
            <option value="pending">Pending</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
            <option value="">All</option>
          </select>
          <button className="h-8 rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--background))] px-3 text-sm hover:bg-[hsl(var(--muted))]">
            Filter
          </button>
        </form>
      </div>

      {data.items.length === 0 ? (
        <Empty
          title="No items in this view"
          hint="Items show up here when an AOP run halts on requires_approval_if."
        />
      ) : (
        <Table>
          <THead>
            <TR>
              <TH>Case</TH>
              <TH>Reason</TH>
              <TH>Confidence</TH>
              <TH>Status</TH>
              <TH>Created</TH>
            </TR>
          </THead>
          <TBody>
            {data.items.map((it) => (
              <TR key={it.id}>
                <TD className="font-mono text-xs">
                  <Link href={`/cases/${it.case_id}`} className="hover:underline">
                    {it.case_id}
                  </Link>
                </TD>
                <TD className="max-w-md">
                  <span className="line-clamp-2">{it.escalation_reason}</span>
                </TD>
                <TD className="text-[hsl(var(--muted-foreground))]">
                  {it.confidence != null ? `${(it.confidence * 100).toFixed(0)}%` : "—"}
                </TD>
                <TD>
                  <Badge variant={statusVariant(it.status)}>{it.status}</Badge>
                </TD>
                <TD className="text-[hsl(var(--muted-foreground))]">
                  {formatRelative(it.created_at)}
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      )}
    </div>
  );
}
