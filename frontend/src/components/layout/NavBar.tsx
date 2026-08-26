import { useAuth } from '../../lib/auth';
import { Logo } from '../ui/Logo';

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

function initialsFromEmail(email: string): string {
  const local = email.split('@')[0] ?? email;
  const parts = local.split(/[._-]+/).filter(Boolean);
  const chars = parts.length >= 2 ? [parts[0][0], parts[1][0]] : [local.slice(0, 2)];
  return chars.join('').slice(0, 2).toUpperCase();
}

export function NavBar({ active, onNavigate }: NavBarProps) {
  const { session, signOut } = useAuth();
  const email = session?.user.email ?? '';
  return (
    <div className="sticky top-0 z-20 bg-[var(--color-surface)]">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3.5">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2.5">
            <Logo className="h-6 w-6 flex-none" />
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
                    ? 'font-medium bg-[color-mix(in_srgb,var(--color-accent-600)_24%,transparent)] text-[var(--color-accent-100)] shadow-[inset_0_0_0_1px_color-mix(in_srgb,var(--color-accent-600)_45%,transparent)]'
                    : 'font-normal text-[var(--color-text-secondary)] hover:bg-[color-mix(in_srgb,var(--color-text)_8%,transparent)] hover:text-[var(--color-text)]'
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
              {email}
            </div>
            <button
              type="button"
              onClick={() => void signOut()}
              className="cursor-pointer text-[11px] whitespace-nowrap text-[var(--color-text-tertiary)] hover:text-[var(--color-text)]"
            >
              Sign out
            </button>
          </div>
          <span className="flex h-[30px] w-[30px] items-center justify-center rounded-full border border-[color-mix(in_srgb,var(--color-text)_16%,transparent)] bg-[var(--color-neutral-900)] text-[11.5px] font-medium text-[var(--color-accent-300)]">
            {email ? initialsFromEmail(email) : ''}
          </span>
        </div>
      </div>
      <div className="h-px bg-[linear-gradient(to_right,transparent,color-mix(in_srgb,var(--color-text)_16%,transparent)_48px,color-mix(in_srgb,var(--color-text)_16%,transparent)_calc(100%-48px),transparent)]" />
    </div>
  );
}
