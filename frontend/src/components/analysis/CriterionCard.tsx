import { Card } from '../ui/Card';
import { ScoreBadge } from './ScoreBadge';
import type { CriterionScore } from '../../lib/types/analysis';

interface CriterionCardProps {
  label: string;
  criterion: CriterionScore;
}

export function CriterionCard({ label, criterion }: CriterionCardProps) {
  return (
    <Card className="p-4">
      <div className="mb-2 flex items-center gap-3">
        <ScoreBadge score={criterion.score} />
        <div className="text-sm font-medium">{label}</div>
      </div>
      <p className="text-sm leading-relaxed text-[color-mix(in_srgb,var(--color-text)_75%,transparent)]">
        {criterion.evidence}
      </p>
    </Card>
  );
}
