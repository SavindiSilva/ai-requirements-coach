import { Card } from '../ui/Card';
import { ScoreBadge } from '../analysis/ScoreBadge';
import { FindingList } from '../analysis/FindingList';
import type { CurrentScores, FinalizeResponse } from '../../lib/types/coaching';

interface FinalRequirementViewProps {
  result: FinalizeResponse;
}

const CRITERIA: { key: keyof CurrentScores; label: string }[] = [
  { key: 'requirement_clarity', label: 'Requirement Clarity' },
  { key: 'acceptance_criteria', label: 'Acceptance Criteria' },
  { key: 'open_questions', label: 'Open Questions' },
  { key: 'scope_definition', label: 'Scope Definition' },
];

export function FinalRequirementView({ result }: FinalRequirementViewProps) {
  const { final_requirement } = result;

  return (
    <div className="flex flex-col gap-6">
      <Card className="p-5">
        <h2 className="mb-2 text-base font-medium">Development-Ready Requirement</h2>
        <p className="text-[15px] leading-relaxed">{final_requirement.user_story}</p>
      </Card>

      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
        <FindingList title="Acceptance Criteria" items={final_requirement.acceptance_criteria} />
        <FindingList title="Scope" items={final_requirement.scope} />
        <FindingList title="Assumptions" items={final_requirement.assumptions} />
        <FindingList title="Dependencies" items={final_requirement.dependencies} />
        <FindingList
          title="Remaining Gaps"
          items={result.remaining_gaps}
          emptyLabel="None — all criteria meet the readiness threshold."
        />
      </div>

      <Card className="p-5">
        <div className="mb-2 text-[10.5px] tracking-wide text-[color-mix(in_srgb,var(--color-text)_45%,transparent)] uppercase">
          Current Readiness
        </div>
        <div className="flex flex-col gap-1.5">
          {CRITERIA.map(({ key, label }) => (
            <div key={key} className="flex items-center gap-2.5">
              <ScoreBadge score={result.current_scores[key]} />
              <span className="text-xs text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
                {label}
              </span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
