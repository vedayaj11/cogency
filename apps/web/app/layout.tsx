import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Cogency",
  description: "Agentic case management on Salesforce.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
