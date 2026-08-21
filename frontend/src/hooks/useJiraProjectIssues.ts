import { useQuery } from '@tanstack/react-query';
import { getJiraProjectIssues } from '../lib/api/jira';

export function useJiraProjectIssues(projectId: string | null) {
  return useQuery({
    queryKey: ['jira', 'projects', projectId, 'issues'],
    queryFn: () => getJiraProjectIssues(projectId as string),
    enabled: projectId !== null,
  });
}
