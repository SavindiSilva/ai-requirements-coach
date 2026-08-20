import { Card } from '../ui/Card';
import { CriterionCard } from './CriterionCard';
import { FindingList } from './FindingList';
import { ClarificationQuestions } from './ClarificationQuestions';
import { formatScore } from '../../lib/format';
import type { AnalysisResult, TicketInput } from '../../lib/types/analysis';

interface AnalysisResultViewProps {
  ticket: TicketInput;
  result: AnalysisResult;
}

type CriterionKey =
  | 'requirement_clarity'
  | 'acceptance_criteria'
  | 'open_questions'
  | 'scope_definition';

const CRITERIA: { key: CriterionKey; label: string }[] = [
  { key: 'requirement_clarity', label: 'Requirement Clarity' },
  { key: 'acceptance_criteria', label: 'Acceptance Criteria' },
  { key: 'open_questions', label: 'Open Questions' },
  { key: 'scope_definition', label: 'Scope Definition' },
];

export function AnalysisResultView({ ticket, result }: AnalysisResultViewProps) {
  return (
    <div className="flex flex-col gap-6">
      <Card className="p-5">
        <h2 className="mb-1.5 text-lg font-medium">{ticket.title}</h2>
        <p className="mb-4 text-sm leading-relaxed text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
          {ticket.description}
        </p>
        <div>
          <div className="mb-1 text-[10.5px] tracking-wide text-[color-mix(in_srgb,var(--color-text)_45%,transparent)] uppercase">
            Overall Readiness
          </div>
          <div className="text-2xl font-medium">{formatScore(result.overall_readiness)} / 3</div>
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {CRITERIA.map(({ key, label }) => (
          <CriterionCard key={key} label={label} criterion={result[key]} />
        ))}
      </div>

      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
        <FindingList title="What Is Clear" items={result.what_is_clear} />
        <FindingList title="What Is Missing" items={result.what_is_missing} />
        <FindingList title="What Is Ambiguous" items={result.what_is_ambiguous} />
        <FindingList title="Assumptions" items={result.assumptions} />
        <FindingList title="Possible Dependencies" items={result.possible_dependencies} />
        <FindingList title="Scope Problems" items={result.scope_problems} />
        <FindingList title="Missing Acceptance Criteria" items={result.missing_acceptance_criteria} />
        <FindingList title="Important Open Questions" items={result.important_open_questions} />
      </div>

      <ClarificationQuestions questions={result.clarification_questions} />
    </div>
  );
}
