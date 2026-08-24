import { apiGet, apiPost } from './client';
import type { ReviewedTicket } from '../types/reviewedTicket';

// Mirrors app/tickets/schemas.py::ReviewedTicket (snake_case on the wire).
// Kept private to this module — callers use the camelCase ReviewedTicket
// type everywhere else, same convention as useSubmitCoachingAnswer.ts's
// snake_case-to-camelCase boundary transform.
interface ReviewedTicketWire {
  issue_key: string | null;
  title: string;
  readiness: number;
  reviewed_at: number;
  stop_reason: string | null;
}

function toWire(ticket: ReviewedTicket): ReviewedTicketWire {
  return {
    issue_key: ticket.issueKey ?? null,
    title: ticket.title,
    readiness: ticket.readiness,
    reviewed_at: ticket.reviewedAt,
    stop_reason: ticket.stopReason,
  };
}

function fromWire(wire: ReviewedTicketWire): ReviewedTicket {
  return {
    issueKey: wire.issue_key ?? undefined,
    title: wire.title,
    readiness: wire.readiness,
    reviewedAt: wire.reviewed_at,
    stopReason: wire.stop_reason,
  };
}

export async function recordReviewedTicket(ticket: ReviewedTicket): Promise<ReviewedTicket> {
  const result = await apiPost<ReviewedTicketWire>('/api/tickets/reviewed', toWire(ticket));
  return fromWire(result);
}

export async function getReviewedTickets(): Promise<ReviewedTicket[]> {
  const results = await apiGet<ReviewedTicketWire[]>('/api/tickets/reviewed');
  return results.map(fromWire);
}
