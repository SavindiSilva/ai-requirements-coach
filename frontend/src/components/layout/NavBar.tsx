export type Screen = 'dashboard' | 'review' | 'history';

interface NavBarProps {
  active: Screen;
  onNavigate: (screen: Screen) => void;
}

const NAV_ITEMS: { screen: Screen; label: string }[] = [
  { screen: 'dashboard', label: 'Dashboard' },
  { screen: 'review', label: 'Review Ticket' },
  { screen: 'history', label: 'History' },
];

export function NavBar({ active, onNavigate }: NavBarProps) {
  return (
    <div className="sticky top-0 z-20 bg-[var(--color-surface)]">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3.5">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2.5">
            <div className="flex h-6 w-6 items-center justify-center rounded-full bg-[var(--color-accent)] text-xs font-medium text-[var(--color-neutral-100)]">
              ✦
            </div>
            <span className="text-sm font-medium font-[family-name:var(--font-heading)]">
              ReqPilot
            </span>
          </div>
          <nav className="flex items-center gap-1">
            {NAV_ITEMS.map(({ screen, label }) => (
              <button
                key={screen}
                onClick={() => onNavigate(screen)}
                className={`rounded-full px-[13px] py-1.5 text-[13.5px] transition-colors cursor-pointer ${
                  active === screen
                    ? 'font-medium bg-[var(--color-accent-800)] text-[var(--color-accent-100)]'
                    : 'font-normal text-[color-mix(in_srgb,var(--color-text)_65%,transparent)] hover:bg-[color-mix(in_srgb,var(--color-text)_8%,transparent)] hover:text-[var(--color-text)]'
                }`}
              >
                {label}
              </button>
            ))}
          </nav>
        </div>

        <div className="flex items-center gap-2.5">
          <div className="text-right">
            <div className="text-[12.5px] font-medium whitespace-nowrap text-[var(--color-text)]">
              Savindi Silva
            </div>
            <div className="text-[11px] whitespace-nowrap text-[color-mix(in_srgb,var(--color-text)_45%,transparent)]">
              Acme Inc.
            </div>
          </div>
          <span className="flex h-[30px] w-[30px] items-center justify-center rounded-full border border-[color-mix(in_srgb,var(--color-text)_16%,transparent)] bg-[var(--color-neutral-900)] text-[11.5px] font-medium text-[var(--color-accent-300)]">
            SS
          </span>
        </div>
      </div>
      <div className="h-px bg-[linear-gradient(to_right,transparent,color-mix(in_srgb,var(--color-text)_16%,transparent)_48px,color-mix(in_srgb,var(--color-text)_16%,transparent)_calc(100%-48px),transparent)]" />
    </div>
  );
}
