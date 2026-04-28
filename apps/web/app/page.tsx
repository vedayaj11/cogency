export default function Home() {
  return (
    <main className="mx-auto max-w-4xl px-6 py-16">
      <h1 className="text-4xl font-semibold tracking-tight">Cogency</h1>
      <p className="mt-3 text-lg opacity-80">
        Agentic case management on Salesforce. Pre-development scaffold.
      </p>

      <section className="mt-10 grid grid-cols-1 gap-4 md:grid-cols-2">
        <Card href="/workspace" title="Workspace" desc="Case detail + co-pilot" />
        <Card href="/inbox" title="Inbox" desc="Pending approvals" />
        <Card href="/aops" title="AOPs" desc="Procedures, versions, deploys" />
        <Card href="/evals" title="Evals" desc="Golden sets, runs, diffs" />
      </section>
    </main>
  );
}

function Card({ href, title, desc }: { href: string; title: string; desc: string }) {
  return (
    <a
      href={href}
      className="rounded-lg border border-[hsl(var(--border))] p-5 transition hover:bg-[hsl(var(--muted))]"
    >
      <div className="text-base font-medium">{title}</div>
      <div className="mt-1 text-sm opacity-70">{desc}</div>
    </a>
  );
}
