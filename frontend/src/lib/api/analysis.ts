import { apiPost } from './client';
import type { AnalysisResult, TicketInput } from '../types/analysis';

export function analyseTicket(ticket: TicketInput): Promise<AnalysisResult> {
  return apiPost<AnalysisResult>('/api/analyse', ticket);
}
