import { useQuery } from '@tanstack/react-query';
import { getReviewedTickets } from '../lib/api/tickets';

export function useReviewedTickets() {
  return useQuery({
    queryKey: ['tickets', 'reviewed'],
    queryFn: getReviewedTickets,
  });
}
