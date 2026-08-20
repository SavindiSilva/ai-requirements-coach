// Mirrors app/analysis/schemas.py. Keep in sync by hand — do not add fields
// the backend doesn't actually return.

export interface TicketInput {
  title: string;
  description: string;
}

export interface CriterionScore {
  score: number; // 0-3
  evidence: string;
}

export interface ClarificationQuestion {
  question: string;
  reason: string;
}

export interface AnalysisContent {
  requirement_clarity: CriterionScore;
  acceptance_criteria: CriterionScore;
  open_questions: CriterionScore;
  scope_definition: CriterionScore;

  what_is_clear: string[];
  what_is_missing: string[];
  what_is_ambiguous: string[];
  assumptions: string[];
  possible_dependencies: string[];
  scope_problems: string[];
  missing_acceptance_criteria: string[];
  important_open_questions: string[];
  clarification_questions: ClarificationQuestion[];
}

export interface AnalysisResult extends AnalysisContent {
  overall_readiness: number; // 0-3
}
