import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { ReviewedTicketsTable } from '../components/tickets/ReviewedTicketsTable';
import { formatScore } from '../lib/format';
import { READINESS_PASS_THRESHOLD } from '../lib/readiness';
import { useReviewedTickets } from '../hooks/useReviewedTickets';

interface DashboardPageProps {
  onStartReview: () => void;
  onViewHistory: () => void;
}

export function DashboardPage({ onStartReview, onViewHistory }: DashboardPageProps) {
  const reviewedTicketsQuery = useReviewedTickets();
  const reviewedTickets = reviewedTicketsQuery.data ?? [];
  const ticketsReviewed = reviewedTickets.length;
  const averageReadinessLabel =
    ticketsReviewed > 0
      ? `${formatScore(reviewedTickets.reduce((sum, rt) => sum + rt.readiness, 0) / ticketsReviewed)} / 3`
      : '—';
  const ticketsReady = reviewedTickets.filter((rt) => rt.readiness >= READINESS_PASS_THRESHOLD).length;

  return (
    <div className="mx-auto max-w-6xl px-6 py-10">
      <Card className="mb-6 p-9">
        <span className="mb-4 inline-flex w-max items-center rounded-full border border-[var(--color-accent)] px-3 py-1 text-[10px] font-medium tracking-[0.08em] text-[var(--color-accent)] uppercase">
          ReqPilot
        </span>
        <h1 className="mb-1.5 text-2xl font-medium">
          Improve your software requirements before development starts
        </h1>
        <p className="mb-6 text-sm text-[color-mix(in_srgb,var(--color-text)_55%,transparent)]">
          Import a ticket from Jira and get an AI-powered readiness analysis before development
          begins.
        </p>
        <Button onClick={onStartReview}>Review Ticket</Button>
      </Card>

      <div className="mb-6 grid grid-cols-1 gap-3.5 sm:grid-cols-3">
        <Card className="p-5">
          <div className="mb-2.5 text-[10.5px] tracking-wide text-[color-mix(in_srgb,var(--color-text)_45%,transparent)] uppercase">
            Tickets Reviewed
          </div>
          <div className="text-[28px] font-medium tracking-tight">{ticketsReviewed}</div>
        </Card>
        <Card className="p-5">
          <div className="mb-2.5 text-[10.5px] tracking-wide text-[color-mix(in_srgb,var(--color-text)_45%,transparent)] uppercase">
            Average Readiness Score
          </div>
          <div className="text-[28px] font-medium tracking-tight">{averageReadinessLabel}</div>
        </Card>
        <Card className="p-5">
          <div className="mb-2.5 text-[10.5px] tracking-wide text-[color-mix(in_srgb,var(--color-text)_45%,transparent)] uppercase">
            Tickets Ready
          </div>
          <div className="text-[28px] font-medium tracking-tight">{ticketsReady}</div>
        </Card>
      </div>

      <div className="mb-3.5 flex items-baseline justify-between">
        <h2 className="text-base font-medium">Recently Reviewed Tickets</h2>
        <button
          type="button"
          onClick={onViewHistory}
          className="cursor-pointer text-[12.5px] text-[var(--color-accent)] hover:underline"
        >
          View all
        </button>
      </div>
      <ReviewedTicketsTable
        reviewedTickets={reviewedTickets}
        emptyMessage={reviewedTicketsQuery.isLoading ? 'Loading…' : 'No tickets reviewed yet.'}
      />
      <p className="mt-3 text-xs text-[color-mix(in_srgb,var(--color-text)_35%,transparent)]">
        This history is stored on the backend server, so it survives a page refresh.
      </p>
    </div>
  );
}
