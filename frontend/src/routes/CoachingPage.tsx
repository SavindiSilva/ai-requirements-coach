import { useState, type FormEvent } from 'react';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Field } from '../components/ui/Field';
import { Logo } from '../components/ui/Logo';
import { fieldInputClasses } from '../lib/fieldStyles';
import { ScoreBadge } from '../components/analysis/ScoreBadge';
import { FinalRequirementView } from '../components/coaching/FinalRequirementView';
import { useSubmitCoachingAnswer } from '../hooks/useSubmitCoachingAnswer';
import { useFinalizeCoaching } from '../hooks/useFinalizeCoaching';
import { useRecordReviewedTicket } from '../hooks/useRecordReviewedTicket';
import { ApiError } from '../lib/api/client';
import type { CoachingStartResponse, CurrentScores } from '../lib/types/coaching';
import type { TicketInput } from '../lib/types/analysis';
import { useAuth } from '../lib/auth';

interface CoachingPageProps {
  ticket: TicketInput;
  coaching: CoachingStartResponse;
  onBackToJira: () => void;
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

// One completed question/why/answer round, accumulated locally as the
// conversation progresses so the full thread stays visible — this is
// display-only state, not sent anywhere; the backend already returns
// each question one at a time via SessionState above.
interface ConversationTurn {
  question: string;
  why: string;
  answer: string;
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

function initialsFromEmail(email: string): string {
  const local = email.split('@')[0] ?? email;
  const parts = local.split(/[._-]+/).filter(Boolean);
  const chars =
    parts.length >= 2
      ? [parts[0][0], parts[1][0]]
      : [local.slice(0, 2)];

  return chars.join('').slice(0, 2).toUpperCase();
}

function AiAvatar() {
  return (
    <div className="flex h-7 w-7 flex-none items-center justify-center">
      <Logo className="h-7 w-7" />
    </div>
  );
}

function UserAvatar({ initials }: { initials: string }) {
  return (
    <span className="flex h-7 w-7 flex-none items-center justify-center rounded-full border border-[color-mix(in_srgb,var(--color-text)_16%,transparent)] bg-[var(--color-surface-2)] text-[11px] font-medium text-[var(--color-accent)]">
      {initials}
    </span>
  );
}

function AiMessage({ why, question }: { why: string; question: string }) {
  return (
    <div className="flex items-start gap-2.5">
      <AiAvatar />
      <div className="max-w-[85%] rounded-[var(--radius-xl)] bg-[var(--color-surface)] p-4 shadow-[var(--shadow-sm)]">
        {why && (
          <p className="mb-1.5 text-xs text-[var(--color-accent)]">
            Why this matters — {why}
          </p>
        )}
        <p className="text-sm leading-relaxed">{question}</p>
      </div>
    </div>
  );
}

function UserMessage({
  answer,
  initials,
}: {
  answer: string;
  initials: string;
}) {
  return (
    <div className="flex items-start justify-end gap-2.5">
      <div className="max-w-[85%] rounded-[var(--radius-xl)] bg-[var(--color-surface-muted)] p-4 shadow-[var(--shadow-sm)]">
        <p className="text-sm leading-relaxed text-[var(--color-text)]">
          {answer}
        </p>
      </div>
      <UserAvatar initials={initials} />
    </div>
  );
}

export function CoachingPage({
  ticket,
  coaching,
  onBackToJira,
}: CoachingPageProps) {
  const { session: authSession } = useAuth();
  const email = authSession?.user.email ?? '';
  const userInitials = email ? initialsFromEmail(email) : '';

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

  const [history, setHistory] = useState<ConversationTurn[]>([]);
  const [answer, setAnswer] = useState('');
  const [answerError, setAnswerError] = useState<string | undefined>();

  const submitMutation = useSubmitCoachingAnswer();
  const finalizeMutation = useFinalizeCoaching();
  const recordReviewedTicketMutation = useRecordReviewedTicket();

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

        recordReviewedTicketMutation.mutate({
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

    const questionJustAnswered = session.question;
    const whyJustAnswered = session.why ?? '';
    const answerJustSubmitted = answer;

    submitMutation.mutate(
      { sessionId: coaching.session_id, answer },
      {
        onSuccess: (result) => {
          if (questionJustAnswered !== null) {
            setHistory((prev) => [
              ...prev,
              {
                question: questionJustAnswered,
                why: whyJustAnswered,
                answer: answerJustSubmitted,
              },
            ]);
          }

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

  // Once finalize succeeds, FinalRequirementView is the whole page: no
  // sidebar (it has no readiness/ticket info of its own to duplicate —
  // FinalRequirementView already renders the original ticket via its
  // "Original" column and its own compact readiness row) and no
  // "AI Coaching Conversation" heading (replaced with a heading that
  // matches this state, since FinalRequirementView itself renders no
  // page-level heading of its own).
  if (finalizeMutation.isSuccess) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-10">
        <h1 className="mb-6 text-2xl font-semibold">
          Development-Ready Requirement
        </h1>

        <FinalRequirementView
          result={finalizeMutation.data}
          ticket={ticket}
          onBackToJira={onBackToJira}
        />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
      <h1 className="mb-6 text-2xl font-semibold">
        AI Coaching Conversation
      </h1>

      <div className="grid grid-cols-1 gap-6 sm:grid-cols-[280px_1fr] sm:items-start">
        <Card className="p-5">
          <h2 className="mb-2 text-base font-medium">{ticket.title}</h2>

          <p className="mb-4 text-sm leading-relaxed text-[var(--color-text-muted)]">
            {ticket.description}
          </p>

          <div className="border-t border-[var(--color-border-subtle)] pt-3.5">
            <div className="mb-2 text-[10.5px] tracking-wide text-[var(--color-text-muted)] uppercase">
              Readiness
            </div>

            <div className="flex flex-col gap-1.5">
              {CRITERIA.map(({ key, label }) => (
                <div key={key} className="flex items-center gap-2.5">
                  <ScoreBadge score={session.currentScores[key]} />

                  <span className="text-xs text-[var(--color-text-muted)]">
                    {label}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </Card>

        <div className="flex flex-col gap-4">
          {history.map((turn, i) => (
            <div key={i} className="flex flex-col gap-3">
              <AiMessage why={turn.why} question={turn.question} />

              <UserMessage
                answer={turn.answer}
                initials={userInitials}
              />
            </div>
          ))}

          {session.isComplete ? (
            <>
              <Card className="p-5">
                <p className="text-[15px] leading-relaxed">
                  Coaching complete.
                </p>

                <p className="mt-1.5 text-sm text-[var(--color-text-muted)]">
                  {session.stopReason
                    ? (STOP_REASON_LABELS[session.stopReason] ??
                      session.stopReason)
                    : ''}
                </p>
              </Card>

              {finalizeMutation.isError && (
                <div className="rounded-[var(--radius-xl)] border border-[var(--color-danger)] bg-[color-mix(in_srgb,var(--color-danger)_10%,transparent)] px-3.5 py-3 text-sm text-[var(--color-danger)]">
                  {finalizeMutation.error instanceof ApiError
                    ? finalizeMutation.error.message
                    : 'Something went wrong. Please try again.'}
                </div>
              )}

              <Button
                onClick={handleFinalize}
                disabled={finalizeMutation.isPending}
              >
                {finalizeMutation.isPending
                  ? 'Generating…'
                  : finalizeMutation.isError
                    ? 'Retry'
                    : 'View Development-Ready Ticket'}
              </Button>
            </>
          ) : (
            <>
              <AiMessage
                why={session.why ?? ''}
                question={session.question ?? ''}
              />

              <div className="flex items-start justify-end gap-2.5">
                <form
                  onSubmit={handleSubmitAnswer}
                  className="max-w-[85%] flex-1"
                >
                  <div className="rounded-[var(--radius-xl)] bg-[var(--color-surface-2)] p-4 shadow-[var(--shadow-sm)]">
                    <Field
                      label="Your Answer"
                      htmlFor="answer"
                      error={answerError}
                    >
                      <textarea
                        id="answer"
                        value={answer}
                        onChange={(e) => setAnswer(e.target.value)}
                        placeholder="Type your answer..."
                        rows={4}
                        className={`${fieldInputClasses(
                          !!answerError,
                        )} resize-y`}
                        disabled={submitMutation.isPending}
                      />
                    </Field>

                    {submitMutation.isError && (
                      <div className="mb-4 rounded-[var(--radius-xl)] border border-[var(--color-danger)] bg-[color-mix(in_srgb,var(--color-danger)_10%,transparent)] px-3.5 py-3 text-sm text-[var(--color-danger)]">
                        {submitMutation.error instanceof ApiError
                          ? submitMutation.error.message
                          : 'Something went wrong. Please try again.'}
                      </div>
                    )}

                    <Button
                      type="submit"
                      disabled={submitMutation.isPending}
                    >
                      {submitMutation.isPending
                        ? 'Submitting…'
                        : 'Submit Answer'}
                    </Button>
                  </div>
                </form>

                <UserAvatar initials={userInitials} />
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}