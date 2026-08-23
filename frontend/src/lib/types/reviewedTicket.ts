export interface ReviewedTicket {
  issueKey?: string;
  title: string;
  readiness: number;
  reviewedAt: number;
  /** Coaching's stop_reason once coaching has finished; null if only analysed so far. */
  stopReason: string | null;
}
