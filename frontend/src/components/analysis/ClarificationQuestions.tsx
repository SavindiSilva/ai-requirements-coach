import { Card } from '../ui/Card';
import type { ClarificationQuestion } from '../../lib/types/analysis';

export function ClarificationQuestions({ questions }: { questions: ClarificationQuestion[] }) {
  if (questions.length === 0) return null;

  return (
    <div>
      <h3 className="mb-2 text-[10.5px] font-medium tracking-wide text-[color-mix(in_srgb,var(--color-text)_45%,transparent)] uppercase">
        Clarification Questions
      </h3>
      <div className="flex flex-col gap-2.5">
        {questions.map((q, i) => (
          <Card key={i} className="p-4">
            <p className="mb-1.5 text-sm font-medium">{q.question}</p>
            <p className="text-xs text-[var(--color-accent-300)]">Why this matters — {q.reason}</p>
          </Card>
        ))}
      </div>
    </div>
  );
}
