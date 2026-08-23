import { useState, type FormEvent } from 'react';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Field } from '../components/ui/Field';
import { fieldInputClasses } from '../lib/fieldStyles';
import { ScoreBadge } from '../components/analysis/ScoreBadge';
import { FinalRequirementView } from '../components/coaching/FinalRequirementView';
import { useSubmitCoachingAnswer } from '../hooks/useSubmitCoachingAnswer';
import { useFinalizeCoaching } from '../hooks/useFinalizeCoaching';
import { ApiError } from '../lib/api/client';
import type { CoachingStartResponse, CurrentScores } from '../lib/types/coaching';
import type { TicketInput } from '../lib/types/analysis';
import type { ReviewedTicket } from '../lib/types/reviewedTicket';

interface CoachingPageProps {
  ticket: TicketInput;
  coaching: CoachingStartResponse;
  onBackToJira: () => void;
  onTicketReviewed: (ticket: ReviewedTicket) => void;
}

interface SessionState {
  question: string | null;
  why: string | null;
  currentScores: CurrentScores;
  questionsAsked: string[];
  answers: string[];
  questionCount: number;
  isComplete: boolean;
  stopReason: string | null;
}

const CRITERIA: { key: keyof CurrentScores; label: string }[] = [
  { key: 'requirement_clarity', label: 'Requirement Clarity' },
  { key: 'acceptance_criteria', label: 'Acceptance Criteria' },
  { key: 'open_questions', label: 'Open Questions' },
  { key: 'scope_definition', label: 'Scope Definition' },
];

const STOP_REASON_LABELS: Record<string, string> = {
  max_questions_reached: 'Maximum number of clarification questions reached.',
  readiness_threshold_met: 'Readiness threshold met — this ticket is sufficiently clear.',
};

export function CoachingPage({ ticket, coaching, onBackToJira, onTicketReviewed }: CoachingPageProps) {
  const [session, setSession] = useState<SessionState>(() => ({
    question: coaching.question,
    why: coaching.why,
    currentScores: coaching.current_scores,
    questionsAsked: [],
    answers: [],
    questionCount: 0,
    isComplete: false,
    stopReason: null,
  }));
  const [answer, setAnswer] = useState('');
  const [answerError, setAnswerError] = useState<string | undefined>();
  const submitMutation = useSubmitCoachingAnswer();
  const finalizeMutation = useFinalizeCoaching();

  function handleFinalize() {
    finalizeMutation.mutate(coaching.session_id, {
      onSuccess: (result) => {
        const scores = result.current_scores;
        const readiness =
          (scores.requirement_clarity +
            scores.acceptance_criteria +
            scores.open_questions +
            scores.scope_definition) /
          4;
        onTicketReviewed({
          issueKey: ticket.source_issue_key ?? undefined,
          title: ticket.title,
          readiness,
          reviewedAt: Date.now(),
          stopReason: result.stop_reason,
        });
      },
    });
  }

  function handleSubmitAnswer(e: FormEvent) {
    e.preventDefault();
    if (!answer.trim()) {
      setAnswerError('Answer is required.');
      return;
    }
    setAnswerError(undefined);

    submitMutation.mutate(
      { sessionId: coaching.session_id, answer },
      {
        onSuccess: (result) => {
          setSession({
            question: result.question,
            why: result.why,
            currentScores: result.currentScores,
            questionsAsked: result.questionsAsked,
            answers: result.answers,
            questionCount: result.questionCount,
            isComplete: result.isComplete,
            stopReason: result.stopReason,
          });
          setAnswer('');
        },
      },
    );
  }

  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
      <h1 className="mb-6 text-2xl font-medium">AI Coaching Conversation</h1>

      <div className="grid grid-cols-1 gap-6 sm:grid-cols-[280px_1fr] sm:items-start">
        <Card className="p-5">
          <h2 className="mb-2 text-base font-medium">{ticket.title}</h2>
          <p className="mb-4 text-sm leading-relaxed text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
            {ticket.description}
          </p>
          <div className="border-t border-[var(--color-divider)] pt-3.5">
            <div className="mb-2 text-[10.5px] tracking-wide text-[color-mix(in_srgb,var(--color-text)_45%,transparent)] uppercase">
              Readiness
            </div>
            <div className="flex flex-col gap-1.5">
              {CRITERIA.map(({ key, label }) => (
                <div key={key} className="flex items-center gap-2.5">
                  <ScoreBadge score={session.currentScores[key]} />
                  <span className="text-xs text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
                    {label}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </Card>

        <div className="flex flex-col gap-4">
          {finalizeMutation.isSuccess ? (
            <FinalRequirementView
              result={finalizeMutation.data}
              ticket={ticket}
              onBackToJira={onBackToJira}
            />
          ) : session.isComplete ? (
            <>
              <Card className="p-5">
                <p className="text-[15px] leading-relaxed">Coaching complete.</p>
                <p className="mt-1.5 text-sm text-[color-mix(in_srgb,var(--color-text)_60%,transparent)]">
                  {session.stopReason
                    ? (STOP_REASON_LABELS[session.stopReason] ?? session.stopReason)
                    : ''}
                </p>
              </Card>

              {finalizeMutation.isError && (
                <div className="rounded-[var(--radius-md)] border border-[var(--color-danger)] bg-[color-mix(in_srgb,var(--color-danger)_10%,transparent)] px-3.5 py-3 text-sm text-[var(--color-danger)]">
                  {finalizeMutation.error instanceof ApiError
                    ? finalizeMutation.error.message
                    : 'Something went wrong. Please try again.'}
                </div>
              )}

              <Button onClick={handleFinalize} disabled={finalizeMutation.isPending}>
                {finalizeMutation.isPending
                  ? 'Generating…'
                  : finalizeMutation.isError
                    ? 'Retry'
                    : 'View Development-Ready Ticket'}
              </Button>
            </>
          ) : (
            <>
              <Card className="p-5">
                <p className="mb-2 text-xs text-[var(--color-accent-300)]">
                  Why this matters — {session.why}
                </p>
                <p className="text-[15px] leading-relaxed">{session.question}</p>
              </Card>

              <form onSubmit={handleSubmitAnswer}>
                <Field label="Your Answer" htmlFor="answer" error={answerError}>
                  <textarea
                    id="answer"
                    value={answer}
                    onChange={(e) => setAnswer(e.target.value)}
                    placeholder="Type your answer..."
                    rows={4}
                    className={`${fieldInputClasses(!!answerError)} resize-y`}
                    disabled={submitMutation.isPending}
                  />
                </Field>

                {submitMutation.isError && (
                  <div className="mb-4 rounded-[var(--radius-md)] border border-[var(--color-danger)] bg-[color-mix(in_srgb,var(--color-danger)_10%,transparent)] px-3.5 py-3 text-sm text-[var(--color-danger)]">
                    {submitMutation.error instanceof ApiError
                      ? submitMutation.error.message
                      : 'Something went wrong. Please try again.'}
                  </div>
                )}

                <Button type="submit" disabled={submitMutation.isPending}>
                  {submitMutation.isPending ? 'Submitting…' : 'Submit Answer'}
                </Button>
              </form>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
