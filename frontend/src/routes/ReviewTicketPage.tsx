import { Button } from '../components/ui/Button';
import { AnalysisResultView } from '../components/analysis/AnalysisResultView';
import { JiraImportFlow } from '../components/jira/JiraImportFlow';
import { CoachingPage } from './CoachingPage';
import { useAnalyseTicket } from '../hooks/useAnalyseTicket';
import { useStartCoaching } from '../hooks/useStartCoaching';
import { ApiError } from '../lib/api/client';
import type { ReviewedTicket } from '../lib/types/reviewedTicket';

interface ReviewTicketPageProps {
  onTicketReviewed: (ticket: ReviewedTicket) => void;
  onFinishReview: () => void;
}

export function ReviewTicketPage({ onTicketReviewed, onFinishReview }: ReviewTicketPageProps) {
  const mutation = useAnalyseTicket();
  const coachingMutation = useStartCoaching();

  const submittedTicket = mutation.data ? mutation.variables : undefined;

  function handleBackToJira() {
    mutation.reset();
    coachingMutation.reset();
    onFinishReview();
  }

  function handleStartCoaching() {
    if (submittedTicket) coachingMutation.mutate(submittedTicket);
  }

  if (coachingMutation.isSuccess && submittedTicket) {
    return (
      <CoachingPage
        ticket={submittedTicket}
        coaching={coachingMutation.data}
        onBackToJira={handleBackToJira}
        onTicketReviewed={onTicketReviewed}
      />
    );
  }

  if (mutation.isSuccess && submittedTicket) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-10">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-2xl font-medium">Requirement Analysis</h1>
          <Button variant="secondary" onClick={handleBackToJira}>
            Review Another Ticket
          </Button>
        </div>
        <AnalysisResultView ticket={submittedTicket} result={mutation.data} />

        <div className="mt-6 flex flex-col items-start gap-3">
          {coachingMutation.isError && (
            <div className="rounded-[var(--radius-md)] border border-[var(--color-danger)] bg-[color-mix(in_srgb,var(--color-danger)_10%,transparent)] px-3.5 py-3 text-sm text-[var(--color-danger)]">
              {coachingMutation.error instanceof ApiError
                ? coachingMutation.error.message
                : 'Something went wrong. Please try again.'}
            </div>
          )}
          <Button onClick={handleStartCoaching} disabled={coachingMutation.isPending}>
            {coachingMutation.isPending ? 'Starting…' : 'Start AI Coaching'}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-6 py-10">
      <h1 className="mb-1.5 text-2xl font-medium">Review a Ticket</h1>
      <p className="mb-6 text-sm text-[color-mix(in_srgb,var(--color-text)_55%,transparent)]">
        Import a ticket from Jira and improve its requirements before development starts.
      </p>

      <div className="flex flex-col gap-3">
        <JiraImportFlow
          onTicketReady={(ticket) =>
            mutation.mutate(ticket, {
              onSuccess: (result) =>
                onTicketReviewed({
                  issueKey: ticket.source_issue_key ?? undefined,
                  title: ticket.title,
                  readiness: result.overall_readiness,
                  reviewedAt: Date.now(),
                  stopReason: null,
                }),
            })
          }
        />

        {mutation.isPending && (
          <p className="text-sm text-[color-mix(in_srgb,var(--color-text)_60%,transparent)]">Analysing…</p>
        )}
        {mutation.isError && (
          <div className="rounded-[var(--radius-md)] border border-[var(--color-danger)] bg-[color-mix(in_srgb,var(--color-danger)_10%,transparent)] px-3.5 py-3 text-sm text-[var(--color-danger)]">
            {mutation.error instanceof ApiError
              ? mutation.error.message
              : 'Something went wrong. Please try again.'}
          </div>
        )}
      </div>
    </div>
  );
}
