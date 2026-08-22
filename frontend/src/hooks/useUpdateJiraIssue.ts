import { useMutation } from '@tanstack/react-query';
import { updateJiraIssue } from '../lib/api/jira';
import type { FinalRequirementContent } from '../lib/types/coaching';

interface UpdateJiraIssueInput {
  issueKey: string;
  finalRequirement: FinalRequirementContent;
}

export function useUpdateJiraIssue() {
  return useMutation({
    mutationFn: ({ issueKey, finalRequirement }: UpdateJiraIssueInput) =>
      updateJiraIssue(issueKey, finalRequirement),
  });
}
