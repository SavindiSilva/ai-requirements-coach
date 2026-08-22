import { useState, type FormEvent } from 'react';
import { Button } from '../components/ui/Button';
import { Field } from '../components/ui/Field';
import { fieldInputClasses } from '../lib/fieldStyles';
import { AnalysisResultView } from '../components/analysis/AnalysisResultView';
import { JiraImportFlow } from '../components/jira/JiraImportFlow';
import { CoachingPage } from './CoachingPage';
import { useAnalyseTicket } from '../hooks/useAnalyseTicket';
import { useStartCoaching } from '../hooks/useStartCoaching';
import { ApiError } from '../lib/api/client';
import type { TicketInput } from '../lib/types/analysis';

interface FieldErrors {
  title?: string;
  description?: string;
}

type TicketSource = 'manual' | 'jira';

function validate(ticket: TicketInput): FieldErrors {
  const errors: FieldErrors = {};
  if (!ticket.title.trim()) errors.title = 'Title is required.';
  if (!ticket.description.trim()) errors.description = 'Description is required.';
  return errors;
}

export function ReviewTicketPage() {
  const [source, setSource] = useState<TicketSource>('manual');
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const mutation = useAnalyseTicket();
  const coachingMutation = useStartCoaching();

  const submittedTicket = mutation.data ? mutation.variables : undefined;

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const ticket: TicketInput = { title, description };
    const errors = validate(ticket);
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;
    mutation.mutate(ticket);
  }

  function handleReset(nextSource: TicketSource = 'manual') {
    mutation.reset();
    coachingMutation.reset();
    setSource(nextSource);
    setTitle('');
    setDescription('');
    setFieldErrors({});
  }

  function handleStartCoaching() {
    if (submittedTicket) coachingMutation.mutate(submittedTicket);
  }

  if (coachingMutation.isSuccess && submittedTicket) {
    return (
      <CoachingPage
        ticket={submittedTicket}
        coaching={coachingMutation.data}
        onBackToJira={() => handleReset('jira')}
      />
    );
  }

  if (mutation.isSuccess && submittedTicket) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-10">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-2xl font-medium">Requirement Analysis</h1>
          <Button variant="secondary" onClick={() => handleReset()}>
            Review Another Ticket
          </Button>
        </div>
        <AnalysisResultView ticket={submittedTicket} result={mutation.data} />

        <div className="mt-6 flex flex-col items-start gap-3">
          {coachingMutation.isError && (
            <div className="rounded-[var(--radius-md)] border border-[var(--color-danger)] bg-[color-mix(in_srgb,var(--color-danger)_10%,transparent)] px-3.5 py-3 text-sm text-[var(--color-danger)]">
              {coachingMutation.error instanceof ApiError
                ? coachingMutation.error.message
                : 'Something went wrong. Please try again.'}
            </div>
          )}
          <Button onClick={handleStartCoaching} disabled={coachingMutation.isPending}>
            {coachingMutation.isPending ? 'Starting…' : 'Start AI Coaching'}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-xl px-6 py-10">
      <h1 className="mb-1.5 text-2xl font-medium">Review a Ticket</h1>
      <p className="mb-6 text-sm text-[color-mix(in_srgb,var(--color-text)_55%,transparent)]">
        Enter a ticket's title and description to get an AI-powered readiness analysis.
      </p>

      <div className="mb-6 flex gap-2">
        <Button
          variant={source === 'manual' ? 'primary' : 'secondary'}
          onClick={() => setSource('manual')}
        >
          Manual Entry
        </Button>
        <Button variant={source === 'jira' ? 'primary' : 'secondary'} onClick={() => setSource('jira')}>
          Import from Jira
        </Button>
      </div>

      {source === 'jira' ? (
        <div className="flex flex-col gap-3">
          <JiraImportFlow onTicketReady={(ticket) => mutation.mutate(ticket)} />

          {mutation.isPending && (
            <p className="text-sm text-[color-mix(in_srgb,var(--color-text)_60%,transparent)]">Analysing…</p>
          )}
          {mutation.isError && (
            <div className="rounded-[var(--radius-md)] border border-[var(--color-danger)] bg-[color-mix(in_srgb,var(--color-danger)_10%,transparent)] px-3.5 py-3 text-sm text-[var(--color-danger)]">
              {mutation.error instanceof ApiError
                ? mutation.error.message
                : 'Something went wrong. Please try again.'}
            </div>
          )}
        </div>
      ) : (
        <form onSubmit={handleSubmit} noValidate>
          <Field label="Title" htmlFor="title" error={fieldErrors.title}>
            <input
              id="title"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Add notification feature"
              className={fieldInputClasses(!!fieldErrors.title)}
              disabled={mutation.isPending}
            />
          </Field>

          <Field label="Description" htmlFor="description" error={fieldErrors.description}>
            <textarea
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe what needs to be built..."
              rows={6}
              className={`${fieldInputClasses(!!fieldErrors.description)} resize-y`}
              disabled={mutation.isPending}
            />
          </Field>

          {mutation.isError && (
            <div className="mb-4 rounded-[var(--radius-md)] border border-[var(--color-danger)] bg-[color-mix(in_srgb,var(--color-danger)_10%,transparent)] px-3.5 py-3 text-sm text-[var(--color-danger)]">
              {mutation.error instanceof ApiError
                ? mutation.error.message
                : 'Something went wrong. Please try again.'}
            </div>
          )}

          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? 'Analysing…' : 'Analyse Ticket'}
          </Button>
        </form>
      )}
    </div>
  );
}
