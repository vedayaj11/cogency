"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

/**
 * Polls the parent server component every `intervalMs` while any run is in
 * a non-terminal state (`pending` or `running`). Stops once everything has
 * settled — `router.refresh()` re-runs the server component which re-renders
 * this client component with the updated `statuses` prop.
 */
export function AutoRefresh({
  statuses,
  intervalMs = 3000,
}: {
  statuses: string[];
  intervalMs?: number;
}) {
  const router = useRouter();
  const hasActiveRun = statuses.some((s) => s === "pending" || s === "running");

  useEffect(() => {
    if (!hasActiveRun) return;
    const t = setInterval(() => router.refresh(), intervalMs);
    return () => clearInterval(t);
  }, [hasActiveRun, intervalMs, router]);

  return null;
}
