import { useMutation } from '@tanstack/react-query';
import { startCoaching } from '../lib/api/coaching';

export function useStartCoaching() {
  return useMutation({
    mutationFn: startCoaching,
  });
}
