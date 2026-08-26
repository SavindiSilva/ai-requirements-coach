import { Card } from '../ui/Card';
import { formatScore } from '../../lib/format';
import { getAiReviewStatus } from '../../lib/aiReviewStatus';
import type { ReviewedTicket } from '../../lib/types/reviewedTicket';

interface ReviewedTicketsTableProps {
  reviewedTickets: ReviewedTicket[];
  emptyMessage?: string;
}

export function ReviewedTicketsTable({
  reviewedTickets,
  emptyMessage = 'No tickets reviewed yet this session.',
}: ReviewedTicketsTableProps) {
  return (
    <Card className="overflow-hidden p-0">
      {reviewedTickets.length === 0 ? (
        <div className="px-5 py-8 text-center text-sm text-[var(--color-text-tertiary)]">
          {emptyMessage}
        </div>
      ) : (
        reviewedTickets.map((rt, i) => {
          const status = getAiReviewStatus(rt.stopReason);
          return (
            <div
              key={i}
              className="grid grid-cols-[80px_1fr_100px_140px_90px] items-center gap-4 border-b border-[var(--color-divider)] px-4 py-3 transition-colors duration-150 last:border-b-0 hover:bg-[color-mix(in_srgb,var(--color-text)_5%,transparent)]"
            >
              <div className="text-xs text-[var(--color-text-tertiary)]">
                {rt.issueKey ?? '—'}
              </div>
              <div className="truncate text-sm">{rt.title}</div>
              <div className="text-xs text-[var(--color-text-tertiary)]">
                Readiness{' '}
                <span className="font-medium text-[var(--color-text)]">{formatScore(rt.readiness)}/3</span>
              </div>
              <div>
                <span className={status.badgeClass}>{status.label}</span>
              </div>
              <div className="text-right text-xs text-[var(--color-text-tertiary)]">
                {new Date(rt.reviewedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </div>
            </div>
          );
        })
      )}
    </Card>
  );
}
