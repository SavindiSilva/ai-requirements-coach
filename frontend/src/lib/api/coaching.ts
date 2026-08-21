import { apiPost } from './client';
import type {
  CoachingMessageResponse,
  CoachingNextResponse,
  CoachingStartResponse,
  FinalizeResponse,
  ReanalyzeResponse,
} from '../types/coaching';
import type { TicketInput } from '../types/analysis';

export function startCoaching(ticket: TicketInput): Promise<CoachingStartResponse> {
  return apiPost<CoachingStartResponse>('/api/coaching/start', ticket);
}

export function submitAnswer(sessionId: string, answer: string): Promise<CoachingMessageResponse> {
  return apiPost<CoachingMessageResponse>(`/api/coaching/${sessionId}/message`, { answer });
}

export function reanalyzeCoaching(sessionId: string): Promise<ReanalyzeResponse> {
  return apiPost<ReanalyzeResponse>(`/api/coaching/${sessionId}/reanalyze`, {});
}

export function nextCoachingStep(sessionId: string): Promise<CoachingNextResponse> {
  return apiPost<CoachingNextResponse>(`/api/coaching/${sessionId}/next`, {});
}

export function finalizeCoaching(sessionId: string): Promise<FinalizeResponse> {
  return apiPost<FinalizeResponse>(`/api/coaching/${sessionId}/finalize`, {});
}
