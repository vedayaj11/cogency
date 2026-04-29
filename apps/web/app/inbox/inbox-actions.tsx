"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { Button } from "@/components/ui/button";

type Action = "approve" | "reject" | "take_over";

export function InboxActions({ id, status }: { id: string; status: string }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [active, setActive] = useState<Action | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [rejectReason, setRejectReason] = useState("");

  if (status !== "pending") {
    return <span className="text-xs text-[hsl(var(--muted-foreground))]">resolved</span>;
  }

  async function fire(action: Action, reason?: string) {
    setError(null);
    setActive(action);
    try {
      const res = await fetch(`/api/v1/inbox/${id}/${action}`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ reason: reason ?? null }),
      });
      if (!res.ok) {
        setError(await res.text());
        return;
      }
      startTransition(() => router.refresh());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setActive(null);
    }
  }

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-1.5">
        <Button
          variant="primary"
          size="sm"
          disabled={pending}
          onClick={() => fire("approve")}
        >
          {active === "approve" ? "…" : "Approve"}
        </Button>
        <Button
          variant="danger"
          size="sm"
          disabled={pending}
          onClick={() => setShowRejectModal(true)}
        >
          Reject
        </Button>
        <Button
          variant="secondary"
          size="sm"
          disabled={pending}
          onClick={() => fire("take_over")}
        >
          {active === "take_over" ? "…" : "Take over"}
        </Button>
      </div>
      {error ? <div className="text-xs text-rose-500">{error}</div> : null}

      {showRejectModal ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-md rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--background))] p-4 shadow-xl">
            <h3 className="text-sm font-semibold">Reject inbox item</h3>
            <p className="mt-1 text-xs text-[hsl(var(--muted-foreground))]">
              A reason is required and is recorded in the audit log.
            </p>
            <textarea
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              rows={4}
              className="mt-3 w-full rounded-md border border-[hsl(var(--border))] bg-transparent p-2 text-sm"
              placeholder="Why are you rejecting this?"
            />
            <div className="mt-3 flex items-center justify-end gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setShowRejectModal(false);
                  setRejectReason("");
                }}
              >
                Cancel
              </Button>
              <Button
                variant="danger"
                size="sm"
                disabled={pending || rejectReason.trim().length === 0}
                onClick={async () => {
                  setShowRejectModal(false);
                  await fire("reject", rejectReason.trim());
                  setRejectReason("");
                }}
              >
                {active === "reject" ? "Rejecting…" : "Reject"}
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
