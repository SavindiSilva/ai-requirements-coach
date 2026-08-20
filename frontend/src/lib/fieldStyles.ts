const inputClasses =
  'w-full min-h-9 rounded-[var(--radius-md)] border bg-[var(--color-surface)] px-2.5 py-1.5 ' +
  'text-sm text-[var(--color-text)] outline-none transition-colors ' +
  'focus:border-[var(--color-accent)]';

export function fieldInputClasses(hasError: boolean): string {
  const borderColor = hasError
    ? 'border-[var(--color-danger)]'
    : 'border-[var(--color-divider)] hover:border-[color-mix(in_srgb,var(--color-text)_45%,transparent)]';
  return `${inputClasses} ${borderColor}`;
}
