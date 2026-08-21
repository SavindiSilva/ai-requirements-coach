import { useMutation } from '@tanstack/react-query';
import { finalizeCoaching } from '../lib/api/coaching';

export function useFinalizeCoaching() {
  return useMutation({
    mutationFn: finalizeCoaching,
  });
}
