import { useMemo, useState } from 'react';
import { ReviewedTicketsTable } from '../components/tickets/ReviewedTicketsTable';
import { fieldInputClasses } from '../lib/fieldStyles';
import type { ReviewedTicket } from '../lib/types/reviewedTicket';

interface HistoryPageProps {
  reviewedTickets: ReviewedTicket[];
}

export function HistoryPage({ reviewedTickets }: HistoryPageProps) {
  const [searchTerm, setSearchTerm] = useState('');

  const filteredTickets = useMemo(() => {
    const term = searchTerm.trim().toLowerCase();
    if (!term) return reviewedTickets;
    return reviewedTickets.filter(
      (rt) => rt.title.toLowerCase().includes(term) || (rt.issueKey ?? '').toLowerCase().includes(term),
    );
  }, [reviewedTickets, searchTerm]);

  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
      <h1 className="mb-1.5 text-2xl font-medium">History</h1>
      <p className="mb-6 text-sm text-[color-mix(in_srgb,var(--color-text)_55%,transparent)]">
        Every ticket you've reviewed this session, most recent first.
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
          reviewedTickets.length === 0
            ? 'No tickets reviewed yet this session.'
            : 'No tickets match your search.'
        }
      />
      <p className="mt-3 text-xs text-[color-mix(in_srgb,var(--color-text)_35%,transparent)]">
        This list resets when you refresh the page.
      </p>
    </div>
  );
}
