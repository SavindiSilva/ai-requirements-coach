import { useQuery } from '@tanstack/react-query';
import { getJiraStatus } from '../lib/api/jira';

export function useJiraStatus() {
  return useQuery({
    queryKey: ['jira', 'status'],
    queryFn: getJiraStatus,
  });
}
