"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Inbox, ListOrdered, ScrollText, Workflow } from "lucide-react";
import { cn } from "@/lib/cn";

const NAV: { href: string; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { href: "/cases", label: "Workspace", icon: ListOrdered },
  { href: "/inbox", label: "Inbox", icon: Inbox },
  { href: "/aops", label: "AOPs", icon: Workflow },
  { href: "/runs", label: "Runs", icon: ScrollText },
];

export function Sidebar() {
  const path = usePathname();
  return (
    <aside className="flex w-56 shrink-0 flex-col border-r border-[hsl(var(--border))] px-3 py-4">
      <Link href="/" className="px-2 pb-6 text-lg font-semibold tracking-tight">
        Cogency
      </Link>
      <nav className="flex flex-col gap-1">
        {NAV.map((item) => {
          const active = path === item.href || path.startsWith(item.href + "/");
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-2 rounded-md px-2 py-1.5 text-sm",
                active
                  ? "bg-[hsl(var(--muted))] font-medium"
                  : "text-[hsl(var(--muted-foreground))] hover:bg-[hsl(var(--muted))]",
              )}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
