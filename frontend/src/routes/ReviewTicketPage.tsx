import { Button } from '../components/ui/Button';
import { AnalysisResultView } from '../components/analysis/AnalysisResultView';
import { JiraImportFlow } from '../components/jira/JiraImportFlow';
import { CoachingPage } from './CoachingPage';
import { useAnalyseTicket } from '../hooks/useAnalyseTicket';
import { useStartCoaching } from '../hooks/useStartCoaching';
import { useRecordReviewedTicket } from '../hooks/useRecordReviewedTicket';
import { ApiError } from '../lib/api/client';

interface ReviewTicketPageProps {
  onFinishReview: () => void;
}

export function ReviewTicketPage({ onFinishReview }: ReviewTicketPageProps) {
  const mutation = useAnalyseTicket();
  const coachingMutation = useStartCoaching();
  const recordReviewedTicketMutation = useRecordReviewedTicket();

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
      />
    );
  }

  if (mutation.isSuccess && submittedTicket) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-10">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-2xl font-semibold">Requirement Analysis</h1>
          <Button variant="secondary" onClick={handleBackToJira}>
            Review Another Ticket
          </Button>
        </div>
        <AnalysisResultView
          ticket={submittedTicket}
          result={mutation.data}
          onStartCoaching={handleStartCoaching}
          isStartingCoaching={coachingMutation.isPending}
          startCoachingErrorMessage={
            coachingMutation.isError
              ? coachingMutation.error instanceof ApiError
                ? coachingMutation.error.message
                : 'Something went wrong. Please try again.'
              : null
          }
        />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-6 py-10">
      <h1 className="mb-1.5 text-2xl font-semibold">Review a Ticket</h1>
      <p className="mb-6 text-sm text-[var(--color-text-muted)]">
        Import a ticket from Jira and improve its requirements before development starts.
      </p>

      <div className="flex flex-col gap-3">
        <JiraImportFlow
          onTicketReady={(ticket) =>
            mutation.mutate(ticket, {
              onSuccess: (result) =>
                recordReviewedTicketMutation.mutate({
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
          <p className="text-sm text-[var(--color-text-muted)]">Analysing…</p>
        )}
        {mutation.isError && (
          <div className="rounded-[var(--radius-xl)] border border-[var(--color-danger)] bg-[color-mix(in_srgb,var(--color-danger)_10%,transparent)] px-3.5 py-3 text-sm text-[var(--color-danger)]">
            {mutation.error instanceof ApiError
              ? mutation.error.message
              : 'Something went wrong. Please try again.'}
          </div>
        )}
      </div>
    </div>
  );
}
