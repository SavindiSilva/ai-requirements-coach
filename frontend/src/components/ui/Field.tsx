import type { ReactNode } from 'react';

interface FieldProps {
  label: string;
  htmlFor: string;
  error?: string;
  children: ReactNode;
}

export function Field({ label, htmlFor, error, children }: FieldProps) {
  return (
    <div className="mb-4">
      <label
        htmlFor={htmlFor}
        className="mb-1.5 block text-xs text-[color-mix(in_srgb,var(--color-text)_70%,transparent)]"
      >
        {label}
      </label>
      {children}
      {error && <p className="mt-1.5 text-xs text-[var(--color-danger)]">{error}</p>}
    </div>
  );
}
