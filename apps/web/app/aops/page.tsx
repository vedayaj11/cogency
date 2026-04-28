import { Badge } from "@/components/ui/badge";
import { Empty } from "@/components/ui/empty";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { api } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function AOPsPage() {
  const data = await api.listAops().catch(() => ({ items: [] }));

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">AOPs</h1>
        <p className="text-sm text-[hsl(var(--muted-foreground))]">
          Agent Operating Procedures authored against the local tool catalog.
        </p>
      </div>

      {data.items.length === 0 ? (
        <Empty
          title="No AOPs yet"
          hint={
            "Author a new AOP via POST /v1/aops. The reference refund procedure lives at aops/refund_under_500.md."
          }
        />
      ) : (
        <Table>
          <THead>
            <TR>
              <TH>Name</TH>
              <TH>Description</TH>
              <TH>Versions</TH>
              <TH>Current</TH>
            </TR>
          </THead>
          <TBody>
            {data.items.map((aop) => (
              <TR key={aop.id}>
                <TD className="font-mono text-xs">{aop.name}</TD>
                <TD className="max-w-xl">
                  <span className="line-clamp-2">{aop.description ?? "—"}</span>
                </TD>
                <TD>
                  <Badge variant="muted">{aop.versions_count}</Badge>
                </TD>
                <TD>
                  {aop.current_version_number != null ? (
                    <Badge variant="info">v{aop.current_version_number}</Badge>
                  ) : (
                    <span className="text-[hsl(var(--muted-foreground))] text-xs">undeployed</span>
                  )}
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      )}
    </div>
  );
}
