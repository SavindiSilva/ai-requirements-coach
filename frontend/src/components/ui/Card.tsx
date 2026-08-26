import type { HTMLAttributes } from 'react';

export function Card({ className = '', ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={`rounded-[var(--radius-md)] bg-[var(--color-surface)] shadow-[var(--shadow-card)] transition-shadow duration-200 ${className}`}
      {...props}
    />
  );
}
