import { useMutation } from '@tanstack/react-query';
import { nextCoachingStep, reanalyzeCoaching, submitAnswer } from '../lib/api/coaching';
import type { CurrentScores } from '../lib/types/coaching';

interface SubmitCoachingAnswerInput {
  sessionId: string;
  answer: string;
}

export interface SubmitCoachingAnswerResult {
  questionsAsked: string[];
  answers: string[];
  questionCount: number;
  isComplete: boolean;
  stopReason: string | null;
  question: string | null;
  why: string | null;
  currentScores: CurrentScores;
}

// One user-facing "Submit Answer" action requires 3 sequential backend
// round-trips (see app/coaching/router.py) — /message records the answer,
// /reanalyze recomputes scores from it, /next decides the following
// question or completion. Composed into one mutation so the UI has a single
// loading/error state for the whole turn instead of reconciling three.
export function useSubmitCoachingAnswer() {
  return useMutation({
    mutationFn: async ({
      sessionId,
      answer,
    }: SubmitCoachingAnswerInput): Promise<SubmitCoachingAnswerResult> => {
      const messageResult = await submitAnswer(sessionId, answer);
      await reanalyzeCoaching(sessionId);
      const nextResult = await nextCoachingStep(sessionId);

      return {
        questionsAsked: messageResult.questions_asked,
        answers: messageResult.answers,
        questionCount: nextResult.question_count,
        isComplete: nextResult.is_complete,
        stopReason: nextResult.stop_reason,
        question: nextResult.question,
        why: nextResult.why,
        currentScores: nextResult.current_scores,
      };
    },
  });
}
