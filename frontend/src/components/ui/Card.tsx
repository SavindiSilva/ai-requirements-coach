import type { HTMLAttributes } from 'react';

export function Card({ className = '', ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={`rounded-[var(--radius-2xl)] border border-[var(--color-border-subtle)] bg-[linear-gradient(180deg,rgba(255,255,255,0.045),rgba(255,255,255,0.015))] shadow-[var(--shadow-card)] backdrop-blur-[8px] transition-shadow duration-200 ${className}`}
      {...props}
    />
  );
}
