import { cn } from "@/lib/cn";

type Variant = "default" | "success" | "warning" | "danger" | "muted" | "info";

const styles: Record<Variant, string> = {
  default: "bg-[hsl(var(--muted))] text-[hsl(var(--foreground))]",
  success: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
  warning: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
  danger: "bg-rose-500/15 text-rose-700 dark:text-rose-300",
  muted: "bg-[hsl(var(--muted))] text-[hsl(var(--muted-foreground))]",
  info: "bg-sky-500/15 text-sky-700 dark:text-sky-300",
};

export function Badge({
  children,
  variant = "default",
  className,
}: {
  children: React.ReactNode;
  variant?: Variant;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium",
        styles[variant],
        className,
      )}
    >
      {children}
    </span>
  );
}

export function statusVariant(status: string | null | undefined): Variant {
  if (!status) return "muted";
  const s = status.toLowerCase();
  if (s.includes("resolved") || s === "closed" || s === "deployed") return "success";
  if (s.includes("escalated") || s === "pending") return "warning";
  if (s.includes("failed") || s === "halted_by_guardrail") return "danger";
  if (s === "running" || s === "draft") return "info";
  return "muted";
}
