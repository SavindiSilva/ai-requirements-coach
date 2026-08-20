import { useMutation } from '@tanstack/react-query';
import { analyseTicket } from '../lib/api/analysis';

export function useAnalyseTicket() {
  return useMutation({
    mutationFn: analyseTicket,
  });
}
