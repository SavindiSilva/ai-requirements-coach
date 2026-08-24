import { useState } from 'react';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { CriterionCard } from './CriterionCard';
import { FindingList } from './FindingList';
import { ClarificationQuestions } from './ClarificationQuestions';
import { formatScore } from '../../lib/format';
import { READINESS_PASS_THRESHOLD } from '../../lib/readiness';
import type { AnalysisResult, TicketInput } from '../../lib/types/analysis';

interface AnalysisResultViewProps {
  ticket: TicketInput;
  result: AnalysisResult;
  onStartCoaching: () => void;
  isStartingCoaching: boolean;
  startCoachingErrorMessage: string | null;
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

export function AnalysisResultView({
  ticket,
  result,
  onStartCoaching,
  isStartingCoaching,
  startCoachingErrorMessage,
}: AnalysisResultViewProps) {
  const [isFullAnalysisExpanded, setIsFullAnalysisExpanded] = useState(false);

  const isReady = CRITERIA.every(({ key }) => result[key].score >= READINESS_PASS_THRESHOLD);

  return (
    <div className="flex flex-col gap-6">
      <Card className="p-5">
        <h2 className="mb-1.5 text-base font-medium">{ticket.title}</h2>
        <p className="mb-4 text-sm leading-relaxed text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
          {ticket.description}
        </p>
        <div>
          <div className="mb-1 text-[10.5px] tracking-wide text-[color-mix(in_srgb,var(--color-text)_45%,transparent)] uppercase">
            Overall Readiness
          </div>
          <div className="flex items-center gap-3">
            <div className="text-2xl font-medium">{formatScore(result.overall_readiness)} / 3</div>
            <span
              className={`inline-flex items-center rounded-full bg-[var(--color-neutral-800)] px-2.5 py-1 text-xs font-medium ${
                isReady ? 'text-[var(--color-success)]' : 'text-[var(--color-warning)]'
              }`}
            >
              {isReady ? 'Ready' : 'Needs Clarification'}
            </span>
          </div>
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {CRITERIA.map(({ key, label }) => (
          <CriterionCard key={key} label={label} criterion={result[key]} />
        ))}
      </div>

      <div className="flex flex-col items-start gap-3">
        {startCoachingErrorMessage && (
          <div className="rounded-[var(--radius-md)] border border-[var(--color-danger)] bg-[color-mix(in_srgb,var(--color-danger)_10%,transparent)] px-3.5 py-3 text-sm text-[var(--color-danger)]">
            {startCoachingErrorMessage}
          </div>
        )}
        <Button onClick={onStartCoaching} disabled={isStartingCoaching}>
          {isStartingCoaching ? 'Starting…' : 'Start AI Coaching'}
        </Button>
      </div>

      <button
        type="button"
        onClick={() => setIsFullAnalysisExpanded((v) => !v)}
        aria-expanded={isFullAnalysisExpanded}
        className="inline-flex w-max cursor-pointer items-center gap-1.5 text-sm text-[var(--color-accent)] hover:underline"
      >
        {isFullAnalysisExpanded ? 'Hide full analysis' : 'Show full analysis'}
        <svg
          viewBox="0 0 20 20"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className={`h-3.5 w-3.5 transition-transform duration-150 ${isFullAnalysisExpanded ? 'rotate-180' : ''}`}
        >
          <path d="M5 7.5L10 12.5L15 7.5" />
        </svg>
      </button>

      {isFullAnalysisExpanded && (
        <>
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
        </>
      )}
    </div>
  );
}
