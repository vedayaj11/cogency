import { api } from "@/lib/api";
import { formatRelative } from "@/lib/format";
import { Badge } from "@/components/ui/badge";

export async function SyncPill() {
  let status: Awaited<ReturnType<typeof api.syncStatus>> | null = null;
  try {
    status = await api.syncStatus();
  } catch {
    return (
      <Badge variant="muted">API unreachable</Badge>
    );
  }

  if (!status.connected) {
    return (
      <div className="flex items-center gap-2 text-xs">
        <Badge variant="warning">Salesforce not connected</Badge>
        <span className="text-[hsl(var(--muted-foreground))]">
          {status.cases_mirrored} cases mirrored
        </span>
      </div>
    );
  }
  return (
    <div className="flex items-center gap-2 text-xs">
      <Badge variant="success">Synced</Badge>
      <span className="text-[hsl(var(--muted-foreground))]">
        {status.cases_mirrored} cases · last run {formatRelative(status.last_run_at)}
      </span>
    </div>
  );
}
