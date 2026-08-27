import { useState } from 'react';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { ScoreBadge } from '../analysis/ScoreBadge';
import { FindingList } from '../analysis/FindingList';
import { useUpdateJiraIssue } from '../../hooks/useUpdateJiraIssue';
import { ApiError } from '../../lib/api/client';
import type { CurrentScores, FinalizeResponse } from '../../lib/types/coaching';
import type { TicketInput } from '../../lib/types/analysis';

interface FinalRequirementViewProps {
  result: FinalizeResponse;
  ticket: TicketInput;
  onBackToJira: () => void;
}

const CRITERIA: { key: keyof CurrentScores; label: string }[] = [
  { key: 'requirement_clarity', label: 'Requirement Clarity' },
  { key: 'acceptance_criteria', label: 'Acceptance Criteria' },
  { key: 'open_questions', label: 'Open Questions' },
  { key: 'scope_definition', label: 'Scope Definition' },
];

export function FinalRequirementView({ result, ticket, onBackToJira }: FinalRequirementViewProps) {
  const { final_requirement } = result;
  const [showConfirm, setShowConfirm] = useState(false);
  const [showDetails, setShowDetails] = useState(false);
  const updateMutation = useUpdateJiraIssue();

  const issueKey = ticket.source_issue_key;

  function handleConfirmUpdate() {
    if (!issueKey) return;
    updateMutation.mutate({ issueKey, finalRequirement: final_requirement });
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Card className="p-5">
          <div className="mb-2 text-[10.5px] tracking-wide text-[var(--color-text-muted)] uppercase">
            Original
          </div>
          <h3 className="mb-1.5 text-sm font-medium">{ticket.title}</h3>
          <p className="text-sm leading-relaxed text-[var(--color-text-muted)]">
            {ticket.description}
          </p>
        </Card>

        <Card className="border border-[var(--color-accent)] p-5">
          <div className="mb-2 text-[10.5px] tracking-wide text-[var(--color-accent)] uppercase">
            Improved
          </div>
          <p className="text-[15px] leading-relaxed">{final_requirement.user_story}</p>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
        <FindingList title="Acceptance Criteria" items={final_requirement.acceptance_criteria} />
        <FindingList title="Scope" items={final_requirement.scope} />
      </div>

      <Card className="flex flex-wrap items-center gap-x-5 gap-y-2 px-4 py-3">
        <span className="text-[10.5px] tracking-wide text-[var(--color-text-muted)] uppercase">
          Readiness
        </span>
        {CRITERIA.map(({ key, label }) => (
          <span key={key} className="flex items-center gap-1.5">
            <ScoreBadge score={result.current_scores[key]} />
            <span className="text-xs text-[var(--color-text-muted)]">{label}</span>
          </span>
        ))}
      </Card>

      <button
        type="button"
        onClick={() => setShowDetails((v) => !v)}
        aria-expanded={showDetails}
        className="inline-flex w-max cursor-pointer items-center gap-1.5 text-sm text-[var(--color-accent)] hover:underline"
      >
        {showDetails ? 'Hide details' : 'Show details'}
        <svg
          viewBox="0 0 20 20"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className={`h-3.5 w-3.5 transition-transform duration-150 ${showDetails ? 'rotate-180' : ''}`}
        >
          <path d="M5 7.5L10 12.5L15 7.5" />
        </svg>
      </button>

      {showDetails && (
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
          <FindingList title="Assumptions" items={final_requirement.assumptions} />
          <FindingList title="Dependencies" items={final_requirement.dependencies} />
          <FindingList
            title="Remaining Gaps"
            items={result.remaining_gaps}
            emptyLabel="None — all criteria meet the readiness threshold."
          />
        </div>
      )}

      {issueKey && (
        <Card className="p-5">
          {updateMutation.isSuccess ? (
            <>
              <p className="mb-1.5 text-[15px] leading-relaxed text-[var(--color-success)]">
                {issueKey} was updated in Jira.
              </p>
              <p className="mb-4 text-sm text-[var(--color-text-muted)]">
                The issue description now contains the full development-ready requirement above.
              </p>
              <Button onClick={onBackToJira}>Back to Issue List</Button>
            </>
          ) : (
            <>
              <div className="mb-2 text-[10.5px] tracking-wide text-[var(--color-text-muted)] uppercase">
                Push to Jira
              </div>

              {!showConfirm && (
                <>
                  <p className="mb-4 text-sm text-[var(--color-text-muted)]">
                    Approving will overwrite the description of {issueKey} in Jira with the
                    development-ready requirement above. No other Jira fields are changed.
                  </p>
                  <Button onClick={() => setShowConfirm(true)}>Approve &amp; Update Jira</Button>
                </>
              )}

              {showConfirm && (
                <>
                  <p className="mb-4 text-sm leading-relaxed">
                    This will replace the current description of <strong>{issueKey}</strong> in
                    Jira. This cannot be undone from here. Continue?
                  </p>

                  {updateMutation.isError && (
                    <div className="mb-4 rounded-[var(--radius-xl)] border border-[var(--color-danger)] bg-[color-mix(in_srgb,var(--color-danger)_10%,transparent)] px-3.5 py-3 text-sm text-[var(--color-danger)]">
                      {updateMutation.error instanceof ApiError
                        ? updateMutation.error.message
                        : 'Something went wrong. Please try again.'}
                    </div>
                  )}

                  <div className="flex gap-2">
                    <Button onClick={handleConfirmUpdate} disabled={updateMutation.isPending}>
                      {updateMutation.isPending
                        ? 'Updating…'
                        : updateMutation.isError
                          ? 'Retry'
                          : 'Confirm & Update Jira'}
                    </Button>
                    <Button
                      variant="secondary"
                      onClick={() => setShowConfirm(false)}
                      disabled={updateMutation.isPending}
                    >
                      Cancel
                    </Button>
                  </div>
                </>
              )}
            </>
          )}
        </Card>
      )}
    </div>
  );
}
