export function Empty({
  title,
  hint,
  cta,
}: {
  title: string;
  hint?: string;
  cta?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-[hsl(var(--border))] py-16 text-center">
      <div className="text-sm font-medium">{title}</div>
      {hint ? (
        <div className="mt-1 text-sm text-[hsl(var(--muted-foreground))]">{hint}</div>
      ) : null}
      {cta ? <div className="mt-4">{cta}</div> : null}
    </div>
  );
}
