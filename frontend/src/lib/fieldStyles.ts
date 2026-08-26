const inputClasses =
  'w-full min-h-9 rounded-[var(--radius-md)] border bg-[var(--color-surface)] px-2.5 py-1.5 ' +
  'text-sm text-[var(--color-text)] outline-none transition-[border-color,box-shadow] duration-150 ' +
  'focus:border-[var(--color-accent-600)] focus:shadow-[0_0_0_3px_color-mix(in_srgb,var(--color-accent-600)_22%,transparent)]';

export function fieldInputClasses(hasError: boolean): string {
  const borderColor = hasError
    ? 'border-[var(--color-danger)]'
    : 'border-[var(--color-divider)] hover:border-[var(--color-text-tertiary)]';
  return `${inputClasses} ${borderColor}`;
}
