import type { ButtonHTMLAttributes } from 'react';

type Variant = 'primary' | 'secondary';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
}

const base =
  'inline-flex items-center justify-center gap-2 rounded-[var(--radius-md)] px-4 py-2 ' +
  'text-sm font-medium font-[family-name:var(--font-heading)] cursor-pointer ' +
  'transition-[background-color,box-shadow,border-color,transform] duration-150 ' +
  'active:translate-y-px disabled:cursor-not-allowed disabled:opacity-[45%] disabled:active:translate-y-0';

const variants: Record<Variant, string> = {
  primary:
    'border border-transparent bg-[var(--color-accent-600)] text-[var(--color-neutral-100)] shadow-[var(--shadow-button-primary)] ' +
    'hover:bg-[color-mix(in_srgb,var(--color-accent-600)_88%,white)] hover:shadow-[var(--shadow-button-primary-hover)] ' +
    'active:bg-[color-mix(in_srgb,var(--color-accent-600)_85%,black)]',
  secondary:
    'bg-transparent border border-[var(--color-divider)] text-[var(--color-text)] ' +
    'hover:border-[color-mix(in_srgb,var(--color-text)_32%,transparent)] hover:bg-[color-mix(in_srgb,var(--color-text)_8%,transparent)] ' +
    'active:bg-[color-mix(in_srgb,var(--color-text)_14%,transparent)]',
};

export function Button({ variant = 'primary', className = '', ...props }: ButtonProps) {
  return <button className={`${base} ${variants[variant]} ${className}`} {...props} />;
}
