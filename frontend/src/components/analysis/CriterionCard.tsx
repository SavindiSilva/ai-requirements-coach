import { useState } from 'react';
import { Card } from '../ui/Card';
import { ScoreBadge } from './ScoreBadge';
import type { CriterionScore } from '../../lib/types/analysis';

interface CriterionCardProps {
  label: string;
  criterion: CriterionScore;
}

export function CriterionCard({ label, criterion }: CriterionCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <Card className="p-4">
      <button
        type="button"
        onClick={() => setIsExpanded((v) => !v)}
        aria-expanded={isExpanded}
        className="flex w-full cursor-pointer items-center justify-between gap-3 text-left"
      >
        <div className="flex items-center gap-3">
          <ScoreBadge score={criterion.score} />
          <div className="text-sm font-medium">{label}</div>
        </div>
        <svg
          viewBox="0 0 20 20"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className={`h-4 w-4 flex-none text-[var(--color-text-tertiary)] transition-transform duration-150 ${
            isExpanded ? 'rotate-180' : ''
          }`}
        >
          <path d="M5 7.5L10 12.5L15 7.5" />
        </svg>
      </button>
      {isExpanded && (
        <p className="mt-3 text-sm leading-relaxed text-[var(--color-text-secondary)]">
          {criterion.evidence}
        </p>
      )}
    </Card>
  );
}
