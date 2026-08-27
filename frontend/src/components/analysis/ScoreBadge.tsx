import { badgeClasses } from '../../lib/badgeStyles';

// Color coding matches the Design prototype's scoreTagStyle: <=1 amber,
// ==2 accent purple, >=3 green — the same 0-3 scale app/analysis/schemas.py
// uses for every CriterionScore.
export function ScoreBadge({ score }: { score: number }) {
  const tone = score <= 1 ? 'warning' : score === 2 ? 'accent' : 'success';

  return (
    <span className={`min-w-[34px] font-[family-name:var(--font-mono)] tabular-nums ${badgeClasses(tone)}`}>
      {score}/3
    </span>
  );
}
