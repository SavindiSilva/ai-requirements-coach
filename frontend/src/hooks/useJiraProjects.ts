import { useQuery } from '@tanstack/react-query';
import { getJiraProjects } from '../lib/api/jira';

export function useJiraProjects(enabled: boolean) {
  return useQuery({
    queryKey: ['jira', 'projects'],
    queryFn: getJiraProjects,
    enabled,
  });
}
