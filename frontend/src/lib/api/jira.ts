import { apiGet, apiPost } from './client';
import type { JiraIssueDetail, JiraIssueSummary, JiraProject, JiraStatusResponse, JiraUpdateResponse } from '../types/jira';
import type { FinalRequirementContent } from '../types/coaching';

export function getJiraStatus(): Promise<JiraStatusResponse> {
  return apiGet<JiraStatusResponse>('/api/jira/status');
}

export function getJiraProjects(): Promise<JiraProject[]> {
  return apiGet<JiraProject[]>('/api/jira/projects');
}

export function getJiraProjectIssues(projectId: string): Promise<JiraIssueSummary[]> {
  return apiGet<JiraIssueSummary[]>(`/api/jira/projects/${encodeURIComponent(projectId)}/issues`);
}

export function getJiraIssue(issueKey: string): Promise<JiraIssueDetail> {
  return apiGet<JiraIssueDetail>(`/api/jira/issues/${encodeURIComponent(issueKey)}`);
}

export function updateJiraIssue(
  issueKey: string,
  finalRequirement: FinalRequirementContent,
): Promise<JiraUpdateResponse> {
  return apiPost<JiraUpdateResponse>(
    `/api/jira/issues/${encodeURIComponent(issueKey)}/update`,
    finalRequirement,
  );
}
