// Mirrors app/jira/schemas.py. Keep in sync by hand — do not add fields the
// backend doesn't actually return.

import type { RelatedIssue } from './analysis';

export type { RelatedIssue };

export interface JiraStatusResponse {
  connected: boolean;
}

export interface JiraProject {
  id: string;
  key: string;
  name: string;
}

export interface JiraIssueSummary {
  key: string;
  summary: string;
  status: string; // Jira's own workflow status — kept separate from AI review status
  issue_type: string;
}

export interface JiraIssueDetail extends JiraIssueSummary {
  description: string;
  links: RelatedIssue[];
}
