import { useState } from 'react';
import { NavBar, type Screen } from '../components/layout/NavBar';
import { LoginPage } from './LoginPage';
import { DashboardPage } from './DashboardPage';
import { ReviewTicketPage } from './ReviewTicketPage';
import { HistoryPage } from './HistoryPage';
import type { ReviewedTicket } from '../lib/types/reviewedTicket';

export function AppShell() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [activeScreen, setActiveScreen] = useState<Screen>('dashboard');
  const [reviewedTickets, setReviewedTickets] = useState<ReviewedTicket[]>([]);

  // A ticket is first recorded right after analysis (stopReason: null) and,
  // if the user goes on to finish coaching, recorded again with the
  // coaching outcome — upsert by issueKey so that's an update, not a
  // second row for the same ticket.
  function upsertReviewedTicket(ticket: ReviewedTicket) {
    setReviewedTickets((prev) => {
      const withoutExisting = ticket.issueKey
        ? prev.filter((existing) => existing.issueKey !== ticket.issueKey)
        : prev;
      return [ticket, ...withoutExisting];
    });
  }

  if (!isLoggedIn) {
    return <LoginPage onSignIn={() => setIsLoggedIn(true)} />;
  }

  return (
    <>
      <NavBar active={activeScreen} onNavigate={setActiveScreen} />
      {activeScreen === 'dashboard' && (
        <DashboardPage
          reviewedTickets={reviewedTickets}
          onStartReview={() => setActiveScreen('review')}
          onViewHistory={() => setActiveScreen('history')}
        />
      )}
      {activeScreen === 'review' && (
        <ReviewTicketPage
          onTicketReviewed={upsertReviewedTicket}
          onFinishReview={() => setActiveScreen('dashboard')}
        />
      )}
      {activeScreen === 'history' && <HistoryPage reviewedTickets={reviewedTickets} />}
    </>
  );
}
