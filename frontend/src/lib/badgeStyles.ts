// Central pill/badge styling — every status, score and priority indicator
// in the app should build its classes from here so size, shape and color
// saturation stay identical everywhere a badge appears.

export type BadgeTone = 'success' | 'warning' | 'danger' | 'accent' | 'neutral';

const toneClasses: Record<BadgeTone, string> = {
  success: 'bg-[color-mix(in_srgb,var(--color-success)_16%,transparent)] text-[var(--color-success)]',
  warning: 'bg-[color-mix(in_srgb,var(--color-warning)_16%,transparent)] text-[var(--color-warning)]',
  danger: 'bg-[color-mix(in_srgb,var(--color-danger)_16%,transparent)] text-[var(--color-danger)]',
  accent:
    'bg-[color-mix(in_srgb,var(--color-accent-600)_24%,transparent)] text-[var(--color-text)]',
  neutral: 'bg-[var(--color-surface-muted)] text-[var(--color-text-muted)]',
};

export function badgeClasses(tone: BadgeTone, size: 'sm' | 'md' = 'md'): string {
  const sizeClasses = size === 'sm' ? 'h-[20px] px-2 text-[11px]' : 'h-[22px] px-2.5 text-xs';
  return `inline-flex items-center justify-center rounded-[var(--radius-md)] font-medium whitespace-nowrap ${sizeClasses} ${toneClasses[tone]}`;
}

// Jira priorities aren't backed by any color mapping today — this is a
// presentation-only heuristic over the free-text priority name Jira
// returns, so unrecognised priorities safely fall back to neutral.
export function priorityTone(priority: string | null | undefined): BadgeTone {
  const p = (priority ?? '').toLowerCase();
  if (p.includes('highest') || p.includes('urgent') || p.includes('blocker')) return 'danger';
  if (p.includes('high')) return 'warning';
  if (p.includes('medium')) return 'accent';
  if (p.includes('low')) return 'neutral';
  return 'neutral';
}
