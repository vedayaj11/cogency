import Link from "next/link";

import { Badge, statusVariant } from "@/components/ui/badge";
import { Empty } from "@/components/ui/empty";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { api } from "@/lib/api";
import { formatRelative } from "@/lib/format";

import { InboxActions } from "./inbox-actions";

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
            Cases the AI escalated for human review. Actions write to the audit log.
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
            <option value="taken_over">Taken over</option>
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
              <TH>Status</TH>
              <TH>Created</TH>
              <TH>Actions</TH>
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
                  {it.recommended_action &&
                  typeof it.recommended_action === "object" &&
                  "decision" in it.recommended_action ? (
                    <div className="mt-1 text-xs text-[hsl(var(--muted-foreground))]">
                      {(() => {
                        const d = (it.recommended_action as { decision: { action: string; by: string; reason?: string } }).decision;
                        return (
                          <>
                            <span className="font-medium">{d.action}</span> by {d.by}
                            {d.reason ? <> — “{d.reason}”</> : null}
                          </>
                        );
                      })()}
                    </div>
                  ) : null}
                </TD>
                <TD>
                  <Badge variant={statusVariant(it.status)}>{it.status}</Badge>
                </TD>
                <TD className="text-[hsl(var(--muted-foreground))]">
                  {formatRelative(it.created_at)}
                </TD>
                <TD>
                  <InboxActions id={it.id} status={it.status} />
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      )}
    </div>
  );
}
