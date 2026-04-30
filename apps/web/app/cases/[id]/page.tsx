import Link from "next/link";
import { notFound } from "next/navigation";

import { Badge, statusVariant } from "@/components/ui/badge";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { Empty } from "@/components/ui/empty";
import { api } from "@/lib/api";
import { formatCost, formatRelative } from "@/lib/format";

import { AutoRefresh } from "@/components/auto-refresh";
import { RunAOPButton } from "./run-aop-button";

export const dynamic = "force-dynamic";

export default async function CaseDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  const [detail, aops] = await Promise.all([
    api.getCase(id).catch(() => null),
    api.listAops().catch(() => ({ items: [] })),
  ]);

  if (!detail) notFound();

  const deployed = aops.items.filter((a) => a.current_version_id !== null);
  const isAutoManaged = detail.runs.some((r) => r.aop_name === "case_manager");

  return (
    <div className="space-y-4">
      <AutoRefresh statuses={detail.runs.map((r) => r.status)} />
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 text-xs text-[hsl(var(--muted-foreground))]">
            <Link href="/cases" className="hover:underline">
              Workspace
            </Link>
            <span>/</span>
            <span className="font-mono">{detail.case_number ?? detail.id.slice(0, 8)}</span>
          </div>
          <h1 className="mt-1 text-xl font-semibold">{detail.subject ?? "(no subject)"}</h1>
          <div className="mt-1 flex items-center gap-2 text-xs">
            <Badge variant={statusVariant(detail.status)}>{detail.status ?? "—"}</Badge>
            {detail.priority ? <Badge variant="muted">{detail.priority}</Badge> : null}
            {isAutoManaged ? <Badge variant="success">Auto-managed</Badge> : null}
            {detail.origin ? (
              <span className="text-[hsl(var(--muted-foreground))]">via {detail.origin}</span>
            ) : null}
            <span className="text-[hsl(var(--muted-foreground))]">
              · last updated {formatRelative(detail.system_modstamp)}
            </span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-12 gap-4">
        {/* Left: customer panel */}
        <div className="col-span-3 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Customer</CardTitle>
            </CardHeader>
            <CardBody className="space-y-2 text-sm">
              {detail.contact ? (
                <>
                  <div className="font-medium">
                    {[detail.contact.first_name, detail.contact.last_name]
                      .filter(Boolean)
                      .join(" ") || "—"}
                  </div>
                  <div className="text-[hsl(var(--muted-foreground))]">
                    {detail.contact.email ?? "no email on file"}
                  </div>
                  <div className="pt-2 text-xs">
                    <KV k="Contact ID" v={detail.contact.id} mono />
                    {detail.contact.account_id ? (
                      <KV k="Account ID" v={detail.contact.account_id} mono />
                    ) : null}
                  </div>
                </>
              ) : (
                <div className="text-[hsl(var(--muted-foreground))]">No related contact in mirror.</div>
              )}
            </CardBody>
          </Card>

          {Object.keys(detail.custom_fields).length > 0 ? (
            <Card>
              <CardHeader>
                <CardTitle>Custom fields</CardTitle>
              </CardHeader>
              <CardBody className="space-y-1 text-xs">
                {Object.entries(detail.custom_fields).map(([k, v]) => (
                  <KV key={k} k={k} v={String(v)} />
                ))}
              </CardBody>
            </Card>
          ) : null}
        </div>

        {/* Center: case description + timeline */}
        <div className="col-span-6 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Description</CardTitle>
            </CardHeader>
            <CardBody>
              <pre className="whitespace-pre-wrap text-sm leading-relaxed">
                {detail.description ?? "(no description)"}
              </pre>
            </CardBody>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Timeline</CardTitle>
              <span className="text-xs text-[hsl(var(--muted-foreground))]">
                Created {formatRelative(detail.created_date)}
              </span>
            </CardHeader>
            <CardBody>
              <div className="space-y-3 text-sm">
                <TimelineEntry
                  when={detail.created_date}
                  title="Case opened"
                  body="Case ingested from Salesforce."
                />
                {detail.runs.map((r) => (
                  <TimelineEntry
                    key={r.id}
                    when={r.started_at}
                    title={
                      <>
                        <Link href={`/runs/${r.id}`} className="hover:underline">
                          <code className="font-mono text-xs">{r.aop_name ?? "aop"}</code>
                        </Link>{" "}
                        run <span className="font-mono text-xs">{r.id.slice(0, 8)}</span>{" "}
                        — <Badge variant={statusVariant(r.status)}>{r.status}</Badge>
                      </>
                    }
                    body={`Cost ${formatCost(r.cost_usd)}${
                      r.ended_at ? ` · finished ${formatRelative(r.ended_at)}` : " · running"
                    }`}
                  />
                ))}
              </div>
            </CardBody>
          </Card>
        </div>

        {/* Right: AOP execution + actions */}
        <div className="col-span-3 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Run an AOP</CardTitle>
            </CardHeader>
            <CardBody>
              <RunAOPButton
                caseId={detail.id}
                options={deployed.map((a) => ({ name: a.name, description: a.description }))}
              />
            </CardBody>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Recent runs</CardTitle>
            </CardHeader>
            <CardBody>
              {detail.runs.length === 0 ? (
                <Empty title="No runs yet" hint="Trigger one with the panel above." />
              ) : (
                <ul className="space-y-2 text-sm">
                  {detail.runs.map((r) => (
                    <li key={r.id} className="rounded-md border border-[hsl(var(--border))] p-2">
                      <Link href={`/runs/${r.id}`} className="block hover:underline">
                        <div className="flex items-center justify-between gap-2">
                          <span className="truncate font-mono text-xs">
                            {r.aop_name ?? r.id.slice(0, 8)}
                          </span>
                          <Badge variant={statusVariant(r.status)}>{r.status}</Badge>
                        </div>
                        <div className="mt-1 text-xs text-[hsl(var(--muted-foreground))]">
                          {formatCost(r.cost_usd)} · {formatRelative(r.started_at)}
                        </div>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </CardBody>
          </Card>
        </div>
      </div>
    </div>
  );
}

function KV({ k, v, mono }: { k: string; v: string; mono?: boolean }) {
  return (
    <div className="flex items-start justify-between gap-2 py-0.5">
      <span className="text-[hsl(var(--muted-foreground))]">{k}</span>
      <span className={mono ? "font-mono" : undefined}>{v}</span>
    </div>
  );
}

function TimelineEntry({
  when,
  title,
  body,
}: {
  when: string | null | undefined;
  title: React.ReactNode;
  body: React.ReactNode;
}) {
  return (
    <div className="flex gap-3">
      <div className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-[hsl(var(--muted-foreground))]" />
      <div className="flex-1">
        <div className="flex items-center justify-between">
          <div className="text-sm">{title}</div>
          <div className="text-xs text-[hsl(var(--muted-foreground))]">{formatRelative(when)}</div>
        </div>
        <div className="text-xs text-[hsl(var(--muted-foreground))]">{body}</div>
      </div>
    </div>
  );
}
