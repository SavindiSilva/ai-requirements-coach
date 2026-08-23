import { useState, type FormEvent } from 'react';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { Field } from '../components/ui/Field';
import { fieldInputClasses } from '../lib/fieldStyles';

interface LoginPageProps {
  onSignIn: () => void;
}

const CHECKLIST_ITEMS = [
  'Detects missing triggers, recipients and channels',
  'Coaches your team with clarification questions',
  'Outputs development-ready user stories',
];

export function LoginPage({ onSignIn }: LoginPageProps) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    onSignIn();
  }

  return (
    <div className="flex min-h-screen">
      <div className="dot-grid-bg hidden flex-1 flex-col justify-between px-14 py-14 lg:flex">
        <div>
          <div className="mb-9 flex items-center gap-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-[var(--color-accent)] text-sm font-medium text-[var(--color-neutral-100)]">
              ✦
            </div>
            <div className="text-base font-medium tracking-[-0.01em]">AI Requirements Coach</div>
          </div>

          <h1 className="mb-3 max-w-[420px] text-[27px] leading-[1.25] font-medium tracking-[-0.015em]">
            Improve your software requirements before development starts
          </h1>
          <p className="mb-8 text-sm leading-[1.6] text-[color-mix(in_srgb,var(--color-text)_55%,transparent)]">
            AI-powered requirement coaching for software teams.
          </p>

          <div className="flex flex-col gap-3">
            {CHECKLIST_ITEMS.map((item) => (
              <div
                key={item}
                className="flex items-center gap-2.5 text-sm text-[color-mix(in_srgb,var(--color-text)_80%,transparent)]"
              >
                <span className="flex h-5 w-5 flex-none items-center justify-center rounded-full bg-[color-mix(in_srgb,var(--color-accent)_18%,transparent)] text-[11px] text-[var(--color-accent)]">
                  ✓
                </span>
                {item}
              </div>
            ))}
          </div>
        </div>

        <Card className="max-w-[420px] p-5">
          <div className="mb-1 text-[10px] tracking-wide text-[color-mix(in_srgb,var(--color-text)_45%,transparent)] uppercase">
            Before
          </div>
          <div className="mb-4 text-sm text-[color-mix(in_srgb,var(--color-text)_70%,transparent)]">
            Add notification feature
          </div>
          <div className="mb-1 text-[10px] tracking-wide text-[var(--color-accent-300)] uppercase">
            After Coaching
          </div>
          <div className="text-sm leading-relaxed text-[var(--color-text)]">
            As a user, I want to receive notifications when important events occur so that I do not
            miss updates — with 3 acceptance criteria.
          </div>
        </Card>
      </div>

      <div className="flex flex-1 items-center justify-center px-[12vw] py-6 lg:px-16">
        <div className="w-[400px] max-w-full">
          <form onSubmit={handleSubmit}>
            <Field label="Email" htmlFor="email">
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                className={fieldInputClasses(false)}
              />
            </Field>
            <Field label="Password" htmlFor="password">
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className={fieldInputClasses(false)}
              />
            </Field>

            <div className="mb-[22px] text-right">
              <button
                type="button"
                className="cursor-pointer text-[12.5px] text-[color-mix(in_srgb,var(--color-text)_55%,transparent)] hover:text-[var(--color-text)]"
              >
                Forgot password?
              </button>
            </div>

            <Button type="submit" className="mb-[11px] w-full justify-center">
              Sign In
            </Button>

            <div className="my-5 flex items-center gap-2.5">
              <div className="h-px flex-1 bg-[color-mix(in_srgb,var(--color-text)_12%,transparent)]" />
              <div className="text-[11px] text-[color-mix(in_srgb,var(--color-text)_40%,transparent)]">OR</div>
              <div className="h-px flex-1 bg-[color-mix(in_srgb,var(--color-text)_12%,transparent)]" />
            </div>

            <Button type="button" variant="secondary" className="w-full justify-center">
              <span className="h-3.5 w-3.5 rounded-[3px] bg-[conic-gradient(#4285F4_0_25%,#34A853_25%_50%,#FBBC05_50%_75%,#EA4335_75%_100%)]" />
              Continue with Google
            </Button>
          </form>

          <p className="mt-6 text-[13px] text-[color-mix(in_srgb,var(--color-text)_55%,transparent)]">
            Don't have an account?{' '}
            <button type="button" className="cursor-pointer text-[var(--color-accent)] hover:underline">
              Create account
            </button>
          </p>
          <p className="mt-7 text-[11.5px] text-[color-mix(in_srgb,var(--color-text)_35%,transparent)]">
            Prototype demo — no real authentication is performed.
          </p>
        </div>
      </div>
    </div>
  );
}
