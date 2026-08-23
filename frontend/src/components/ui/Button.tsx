import type { ButtonHTMLAttributes } from 'react';

type Variant = 'primary' | 'secondary';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
}

const base =
  'inline-flex items-center justify-center gap-2 rounded-[var(--radius-md)] px-4 py-2 ' +
  'text-sm font-medium font-[family-name:var(--font-heading)] cursor-pointer ' +
  'transition-colors disabled:cursor-not-allowed disabled:opacity-[45%]';

const variants: Record<Variant, string> = {
  primary:
    'bg-transparent border border-[var(--color-accent)] text-[var(--color-accent)] shadow-[var(--shadow-accent-glow)] ' +
    'hover:bg-[color-mix(in_srgb,var(--color-accent)_12%,transparent)] ' +
    'active:bg-[color-mix(in_srgb,var(--color-accent)_22%,transparent)]',
  secondary:
    'bg-transparent border border-[var(--color-divider)] text-[var(--color-text)] ' +
    'hover:bg-[color-mix(in_srgb,var(--color-text)_10%,transparent)] ' +
    'active:bg-[color-mix(in_srgb,var(--color-text)_14%,transparent)]',
};

export function Button({ variant = 'primary', className = '', ...props }: ButtonProps) {
  return <button className={`${base} ${variants[variant]} ${className}`} {...props} />;
}
