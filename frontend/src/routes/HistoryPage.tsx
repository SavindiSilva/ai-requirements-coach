import { useMemo, useState } from 'react';
import { ReviewedTicketsTable } from '../components/tickets/ReviewedTicketsTable';
import { fieldInputClasses } from '../lib/fieldStyles';
import { useReviewedTickets } from '../hooks/useReviewedTickets';
import type { ReviewedTicket } from '../lib/types/reviewedTicket';

// Stable reference so useMemo below doesn't see a "new" dependency on every
// render while the query has no data yet.
const EMPTY_TICKETS: ReviewedTicket[] = [];

export function HistoryPage() {
  const [searchTerm, setSearchTerm] = useState('');
  const reviewedTicketsQuery = useReviewedTickets();
  const reviewedTickets = reviewedTicketsQuery.data ?? EMPTY_TICKETS;

  const filteredTickets = useMemo(() => {
    const term = searchTerm.trim().toLowerCase();
    if (!term) return reviewedTickets;
    return reviewedTickets.filter(
      (rt) => rt.title.toLowerCase().includes(term) || (rt.issueKey ?? '').toLowerCase().includes(term),
    );
  }, [reviewedTickets, searchTerm]);

  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
      <h1 className="mb-1.5 text-2xl font-semibold">History</h1>
      <p className="mb-6 text-sm text-[var(--color-text-secondary)]">
        Every ticket you've reviewed, most recent first.
      </p>

      <input
        value={searchTerm}
        onChange={(e) => setSearchTerm(e.target.value)}
        placeholder="Search history..."
        className={`mb-4 w-[280px] max-w-full ${fieldInputClasses(false)}`}
      />

      <ReviewedTicketsTable
        reviewedTickets={filteredTickets}
        emptyMessage={
          reviewedTicketsQuery.isLoading
            ? 'Loading…'
            : reviewedTickets.length === 0
              ? 'No tickets reviewed yet.'
              : 'No tickets match your search.'
        }
      />
      <p className="mt-3 text-xs text-[var(--color-text-tertiary)]">
        This history is stored on the backend server, so it survives a page refresh.
      </p>
    </div>
  );
}
