import { useQuery } from '@tanstack/react-query';
import { getJiraIssue } from '../lib/api/jira';

export function useJiraIssue(issueKey: string | null) {
  return useQuery({
    queryKey: ['jira', 'issues', issueKey],
    queryFn: () => getJiraIssue(issueKey as string),
    enabled: issueKey !== null,
  });
}
