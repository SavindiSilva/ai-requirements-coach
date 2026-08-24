import { useMutation, useQueryClient } from '@tanstack/react-query';
import { recordReviewedTicket } from '../lib/api/tickets';

export function useRecordReviewedTicket() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: recordReviewedTicket,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tickets', 'reviewed'] });
    },
  });
}
