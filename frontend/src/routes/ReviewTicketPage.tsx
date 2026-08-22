import { useState } from 'react';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { AnalysisResultView } from '../components/analysis/AnalysisResultView';
import { JiraImportFlow } from '../components/jira/JiraImportFlow';
import { CoachingPage } from './CoachingPage';
import { useAnalyseTicket } from '../hooks/useAnalyseTicket';
import { useStartCoaching } from '../hooks/useStartCoaching';
import { ApiError } from '../lib/api/client';
import { formatScore } from '../lib/format';

interface ReviewedTicket {
  issueKey?: string;
  title: string;
  readiness: number;
  reviewedAt: number;
}

export function ReviewTicketPage() {
  const [showLanding, setShowLanding] = useState(true);
  const [reviewedTickets, setReviewedTickets] = useState<ReviewedTicket[]>([]);
  const mutation = useAnalyseTicket();
  const coachingMutation = useStartCoaching();

  const submittedTicket = mutation.data ? mutation.variables : undefined;

  function handleBackToJira() {
    mutation.reset();
    coachingMutation.reset();
    setShowLanding(true);
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

  if (showLanding) {
    const ticketsReviewed = reviewedTickets.length;
    const averageReadinessLabel =
      ticketsReviewed > 0
        ? `${formatScore(reviewedTickets.reduce((sum, rt) => sum + rt.readiness, 0) / ticketsReviewed)} / 3`
        : '—';

    return (
      <div className="mx-auto max-w-3xl px-6 py-10">
        <Card className="mb-8 p-9">
          <span className="mb-4 inline-flex w-max items-center rounded-full border border-[var(--color-accent)] px-3 py-1 text-[10px] font-medium tracking-[0.08em] text-[var(--color-accent)] uppercase">
            AI Requirements Coach
          </span>
          <h1 className="mb-3 text-2xl font-medium">
            Improve your software requirements before development starts
          </h1>
          <p className="mb-6 text-sm text-[color-mix(in_srgb,var(--color-text)_55%,transparent)]">
            Import a ticket from Jira and get an AI-powered readiness analysis before development
            begins.
          </p>
          <Button onClick={() => setShowLanding(false)}>Review Ticket</Button>
        </Card>

        <div className="mb-8 grid grid-cols-2 gap-3.5">
          <Card className="p-5">
            <div className="mb-2.5 text-[11px] tracking-wide text-[color-mix(in_srgb,var(--color-text)_50%,transparent)] uppercase">
              Tickets Reviewed
            </div>
            <div className="text-[28px] font-medium tracking-tight">{ticketsReviewed}</div>
          </Card>
          <Card className="p-5">
            <div className="mb-2.5 text-[11px] tracking-wide text-[color-mix(in_srgb,var(--color-text)_50%,transparent)] uppercase">
              Average Readiness Score
            </div>
            <div className="text-[28px] font-medium tracking-tight">{averageReadinessLabel}</div>
          </Card>
        </div>

        <h2 className="mb-3.5 text-[15px] font-medium">Recently Reviewed Tickets</h2>
        <Card className="overflow-hidden p-0">
          {reviewedTickets.length === 0 ? (
            <div className="px-5 py-8 text-center text-sm text-[color-mix(in_srgb,var(--color-text)_40%,transparent)]">
              No tickets reviewed yet this session.
            </div>
          ) : (
            reviewedTickets.map((rt, i) => (
              <div
                key={i}
                className="grid grid-cols-[80px_1fr_100px_90px] items-center gap-4 border-b border-[var(--color-divider)] px-5 py-3.5 last:border-b-0"
              >
                <div className="text-xs text-[color-mix(in_srgb,var(--color-text)_50%,transparent)]">
                  {rt.issueKey ?? '—'}
                </div>
                <div className="truncate text-sm">{rt.title}</div>
                <div className="text-xs text-[color-mix(in_srgb,var(--color-text)_50%,transparent)]">
                  Readiness{' '}
                  <span className="font-medium text-[var(--color-text)]">{formatScore(rt.readiness)}/3</span>
                </div>
                <div className="text-right text-xs text-[color-mix(in_srgb,var(--color-text)_40%,transparent)]">
                  {new Date(rt.reviewedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </div>
              </div>
            ))
          )}
        </Card>
        <p className="mt-3 text-xs text-[color-mix(in_srgb,var(--color-text)_35%,transparent)]">
          Stats reset when you refresh the page.
        </p>
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
                setReviewedTickets((prev) => [
                  {
                    issueKey: ticket.source_issue_key ?? undefined,
                    title: ticket.title,
                    readiness: result.overall_readiness,
                    reviewedAt: Date.now(),
                  },
                  ...prev,
                ]),
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
