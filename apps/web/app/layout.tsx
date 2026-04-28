import type { Metadata } from "next";
import { Suspense } from "react";

import { Sidebar } from "@/components/sidebar";
import { SyncPill } from "@/components/sync-pill";
import "./globals.css";

export const metadata: Metadata = {
  title: "Cogency",
  description: "Agentic case management on Salesforce.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="flex min-h-screen">
          <Sidebar />
          <main className="flex-1">
            <header className="flex h-12 items-center justify-end border-b border-[hsl(var(--border))] px-6">
              <Suspense fallback={null}>
                <SyncPill />
              </Suspense>
            </header>
            <div className="px-6 py-6">{children}</div>
          </main>
        </div>
      </body>
    </html>
  );
}
