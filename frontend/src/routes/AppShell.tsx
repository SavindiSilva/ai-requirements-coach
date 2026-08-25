import { useEffect, useState } from 'react';
import { NavBar, type Screen } from '../components/layout/NavBar';
import { LoginPage } from './LoginPage';
import { DashboardPage } from './DashboardPage';
import { ReviewTicketPage } from './ReviewTicketPage';
import { HistoryPage } from './HistoryPage';
import { useAuth } from '../lib/auth';

// Active-screen nav state only — persisted to sessionStorage so it
// survives a same-tab page reload, including the reload Jira's OAuth
// redirect triggers when it lands back on this app after consent.
const ACTIVE_SCREEN_KEY = 'aiRequirementsCoach.activeScreen';
const VALID_SCREENS: Screen[] = ['dashboard', 'review', 'history'];

function readStoredScreen(): Screen {
  const stored = sessionStorage.getItem(ACTIVE_SCREEN_KEY);
  return stored && (VALID_SCREENS as string[]).includes(stored) ? (stored as Screen) : 'dashboard';
}

export function AppShell() {
  const { session, isLoading } = useAuth();
  const [activeScreen, setActiveScreen] = useState<Screen>(readStoredScreen);

  useEffect(() => {
    sessionStorage.setItem(ACTIVE_SCREEN_KEY, activeScreen);
  }, [activeScreen]);

  if (isLoading) {
    return null;
  }

  if (!session) {
    return <LoginPage />;
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
