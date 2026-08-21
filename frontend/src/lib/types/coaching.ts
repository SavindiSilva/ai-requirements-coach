// Mirrors app/coaching/schemas.py. Keep in sync by hand — do not add fields
// the backend doesn't actually return.

import type { AnalysisResult } from './analysis';

export interface CurrentScores {
  requirement_clarity: number; // 0-3
  acceptance_criteria: number; // 0-3
  open_questions: number; // 0-3
  scope_definition: number; // 0-3
}

export interface CoachingStartResponse {
  session_id: string;
  question: string;
  why: string;
  current_scores: CurrentScores;
}

export interface CoachingMessageResponse {
  session_id: string;
  question: string;
  answer: string;
  question_count: number;
  questions_asked: string[];
  answers: string[];
  current_scores: CurrentScores; // stale — pre-reanalysis snapshot, do not render as "updated"
}

export interface ReanalyzeResponse {
  session_id: string;
  analysis: AnalysisResult;
  question_count: number;
  questions_asked: string[];
  answers: string[];
}

export interface CoachingNextResponse {
  session_id: string;
  is_complete: boolean;
  stop_reason: string | null;
  question: string | null;
  why: string | null;
  question_count: number;
  current_scores: CurrentScores; // authoritative post-reanalysis value
}

export interface FinalRequirementContent {
  user_story: string;
  acceptance_criteria: string[];
  scope: string[];
  assumptions: string[];
  dependencies: string[];
}

export interface FinalizeResponse {
  session_id: string;
  is_complete: boolean;
  stop_reason: string | null;
  final_requirement: FinalRequirementContent;
  remaining_gaps: string[];
  current_scores: CurrentScores;
  question_count: number;
}
