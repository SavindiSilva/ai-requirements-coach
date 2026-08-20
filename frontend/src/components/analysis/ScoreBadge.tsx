// Color coding matches the Design prototype's scoreTagStyle: <=1 amber,
// ==2 accent purple, >=3 green — the same 0-3 scale app/analysis/schemas.py
// uses for every CriterionScore.
export function ScoreBadge({ score }: { score: number }) {
  const colorClasses =
    score <= 1
      ? 'bg-[var(--color-neutral-800)] text-[var(--color-warning)]'
      : score === 2
        ? 'bg-[var(--color-accent-800)] text-[var(--color-accent-100)]'
        : 'bg-[var(--color-neutral-800)] text-[var(--color-success)]';

  return (
    <span
      className={`inline-flex min-w-[34px] h-[22px] items-center justify-center rounded-[var(--radius-sm)] text-xs font-medium ${colorClasses}`}
    >
      {score}/3
    </span>
  );
}
