import type { SVGProps } from 'react';

// ReqPilot's mark: a two-tone compass needle — guidance toward a fixed,
// clear bearing. Colors are drawn from the app's own accent tokens so the
// mark stays in sync with tokens.css automatically.
export function Logo(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true" {...props}>
      <g transform="rotate(8 16 16)">
        <path d="M16 4 L24.5 16 L16 28 Z" fill="var(--color-accent-600)" />
        <path d="M16 4 L7.5 16 L16 28 Z" fill="var(--color-accent-300)" />
        <circle cx="16" cy="16" r="1.6" fill="var(--color-bg)" />
      </g>
    </svg>
  );
}
