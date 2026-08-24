import { useEffect, useState } from 'react';
import { NavBar, type Screen } from '../components/layout/NavBar';
import { LoginPage } from './LoginPage';
import { DashboardPage } from './DashboardPage';
import { ReviewTicketPage } from './ReviewTicketPage';
import { HistoryPage } from './HistoryPage';

// Cosmetic login/nav state only — not real authentication. Persisted to
// sessionStorage (not plain useState) so it survives a same-tab page
// reload, including the reload Jira's OAuth redirect triggers when it
// lands back on this app after consent.
const IS_LOGGED_IN_KEY = 'aiRequirementsCoach.isLoggedIn';
const ACTIVE_SCREEN_KEY = 'aiRequirementsCoach.activeScreen';
const VALID_SCREENS: Screen[] = ['dashboard', 'review', 'history'];

function readStoredIsLoggedIn(): boolean {
  return sessionStorage.getItem(IS_LOGGED_IN_KEY) === 'true';
}

function readStoredScreen(): Screen {
  const stored = sessionStorage.getItem(ACTIVE_SCREEN_KEY);
  return stored && (VALID_SCREENS as string[]).includes(stored) ? (stored as Screen) : 'dashboard';
}

export function AppShell() {
  const [isLoggedIn, setIsLoggedIn] = useState(readStoredIsLoggedIn);
  const [activeScreen, setActiveScreen] = useState<Screen>(readStoredScreen);

  useEffect(() => {
    sessionStorage.setItem(IS_LOGGED_IN_KEY, String(isLoggedIn));
  }, [isLoggedIn]);

  useEffect(() => {
    sessionStorage.setItem(ACTIVE_SCREEN_KEY, activeScreen);
  }, [activeScreen]);

  if (!isLoggedIn) {
    return <LoginPage onSignIn={() => setIsLoggedIn(true)} />;
  }

  return (
    <>
      <NavBar active={activeScreen} onNavigate={setActiveScreen} />
      {activeScreen === 'dashboard' && (
        <DashboardPage
          onStartReview={() => setActiveScreen('review')}
          onViewHistory={() => setActiveScreen('history')}
        />
      )}
      {activeScreen === 'review' && (
        <ReviewTicketPage onFinishReview={() => setActiveScreen('dashboard')} />
      )}
      {activeScreen === 'history' && <HistoryPage />}
    </>
  );
}
