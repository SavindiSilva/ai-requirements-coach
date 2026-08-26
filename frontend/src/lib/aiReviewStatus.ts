// Mirrors app/coaching/stop_condition.py's MAX_QUESTIONS_REACHED /
// READINESS_THRESHOLD_MET string values — kept in sync by hand.
//
// A ticket's AI Review status is only meaningful once it has actually been
// through coaching (a ReviewedTicket record with a non-null stop_reason
// exists). Before that — no record at all, or a record whose coaching
// hasn't finished (stop_reason still null) — it's "Not Reviewed". This is
// deliberately NOT the readiness >= threshold check used pre-coaching by
// AnalysisResultView (lib/readiness.ts's READINESS_PASS_THRESHOLD): once a
// real stop_reason exists, it's the more accurate signal (e.g. a ticket
// that hit max_questions_reached should read "Needs Clarification" even if
// its average readiness happens to be >= the threshold).

import { badgeClasses, type BadgeTone } from './badgeStyles';

export const STOP_REASON_READY = 'readiness_threshold_met';
export const STOP_REASON_NEEDS_CLARIFICATION = 'max_questions_reached';

export interface AiReviewStatus {
  label: string;
  tone: BadgeTone;
  badgeClass: string;
}

export function getAiReviewStatus(stopReason: string | null | undefined): AiReviewStatus {
  if (stopReason === STOP_REASON_READY) {
    return { label: 'Ready', tone: 'success', badgeClass: badgeClasses('success', 'sm') };
  }
  if (stopReason === STOP_REASON_NEEDS_CLARIFICATION) {
    return {
      label: 'Needs Clarification',
      tone: 'warning',
      badgeClass: badgeClasses('warning', 'sm'),
    };
  }
  return { label: 'Not Reviewed', tone: 'neutral', badgeClass: badgeClasses('neutral', 'sm') };
}
