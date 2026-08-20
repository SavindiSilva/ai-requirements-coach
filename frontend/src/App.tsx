import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReviewTicketPage } from './routes/ReviewTicketPage';

const queryClient = new QueryClient();

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ReviewTicketPage />
    </QueryClientProvider>
  );
}

export default App;
