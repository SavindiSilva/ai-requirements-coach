import { useState } from 'react';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { useJiraStatus } from '../../hooks/useJiraStatus';
import { useJiraProjects } from '../../hooks/useJiraProjects';
import { useJiraProjectIssues } from '../../hooks/useJiraProjectIssues';
import { useJiraIssue } from '../../hooks/useJiraIssue';
import { API_BASE_URL, ApiError } from '../../lib/api/client';
import type { TicketInput } from '../../lib/types/analysis';

interface JiraImportFlowProps {
  onTicketReady: (ticket: TicketInput) => void;
}

function ErrorBanner({ error }: { error: unknown }) {
  return (
    <div className="rounded-[var(--radius-md)] border border-[var(--color-danger)] bg-[color-mix(in_srgb,var(--color-danger)_10%,transparent)] px-3.5 py-3 text-sm text-[var(--color-danger)]">
      {error instanceof ApiError ? error.message : 'Something went wrong. Please try again.'}
    </div>
  );
}

export function JiraImportFlow({ onTicketReady }: JiraImportFlowProps) {
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [selectedIssueKey, setSelectedIssueKey] = useState<string | null>(null);

  const statusQuery = useJiraStatus();
  const connected = statusQuery.data?.connected ?? false;

  const projectsQuery = useJiraProjects(connected && !selectedProjectId);
  const issuesQuery = useJiraProjectIssues(connected && selectedProjectId && !selectedIssueKey ? selectedProjectId : null);
  const issueQuery = useJiraIssue(connected && selectedIssueKey ? selectedIssueKey : null);

  function handleConnect() {
    window.location.href = `${API_BASE_URL}/jira/authorize`;
  }

  function handleUseTicket() {
    const issue = issueQuery.data;
    if (!issue) return;
    onTicketReady({
      title: issue.summary,
      description: issue.description,
      related_issues: issue.links.length > 0 ? issue.links : undefined,
    });
  }

  if (statusQuery.isLoading) {
    return <p className="text-sm text-[color-mix(in_srgb,var(--color-text)_60%,transparent)]">Checking Jira connection…</p>;
  }

  if (statusQuery.isError) {
    return <ErrorBanner error={statusQuery.error} />;
  }

  if (!connected) {
    return (
      <Card className="p-5">
        <p className="mb-4 text-sm leading-relaxed text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
          Connect your Jira account to import a ticket directly instead of entering one manually.
        </p>
        <Button onClick={handleConnect}>Connect Jira</Button>
      </Card>
    );
  }

  if (!selectedProjectId) {
    return (
      <div className="flex flex-col gap-3">
        <h2 className="text-base font-medium">Select a Project</h2>
        {projectsQuery.isLoading && (
          <p className="text-sm text-[color-mix(in_srgb,var(--color-text)_60%,transparent)]">Loading projects…</p>
        )}
        {projectsQuery.isError && <ErrorBanner error={projectsQuery.error} />}
        {projectsQuery.data && projectsQuery.data.length === 0 && (
          <p className="text-sm text-[color-mix(in_srgb,var(--color-text)_40%,transparent)]">
            No accessible Jira projects were found.
          </p>
        )}
        <div className="flex flex-col gap-2">
          {projectsQuery.data?.map((project) => (
            <Card
              key={project.id}
              className="cursor-pointer p-4 hover:bg-[color-mix(in_srgb,var(--color-text)_6%,transparent)]"
              onClick={() => setSelectedProjectId(project.id)}
            >
              <div className="text-sm font-medium">{project.name}</div>
              <div className="text-xs text-[color-mix(in_srgb,var(--color-text)_50%,transparent)]">{project.key}</div>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  if (!selectedIssueKey) {
    return (
      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-medium">Select an Issue</h2>
          <Button variant="secondary" onClick={() => setSelectedProjectId(null)}>
            Back to Projects
          </Button>
        </div>
        {issuesQuery.isLoading && (
          <p className="text-sm text-[color-mix(in_srgb,var(--color-text)_60%,transparent)]">Loading issues…</p>
        )}
        {issuesQuery.isError && <ErrorBanner error={issuesQuery.error} />}
        {issuesQuery.data && issuesQuery.data.length === 0 && (
          <p className="text-sm text-[color-mix(in_srgb,var(--color-text)_40%,transparent)]">
            No issues were found in this project.
          </p>
        )}
        <div className="flex flex-col gap-2">
          {issuesQuery.data?.map((issue) => (
            <Card
              key={issue.key}
              className="cursor-pointer p-4 hover:bg-[color-mix(in_srgb,var(--color-text)_6%,transparent)]"
              onClick={() => setSelectedIssueKey(issue.key)}
            >
              <div className="mb-1 flex items-center gap-2">
                <span className="text-xs text-[color-mix(in_srgb,var(--color-text)_50%,transparent)]">{issue.key}</span>
                <span className="inline-flex h-[20px] items-center rounded-[var(--radius-sm)] bg-[var(--color-neutral-800)] px-2 text-[11px] text-[color-mix(in_srgb,var(--color-text)_70%,transparent)]">
                  {issue.status}
                </span>
              </div>
              <div className="text-sm font-medium">{issue.summary}</div>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-medium">Review Ticket</h2>
        <Button variant="secondary" onClick={() => setSelectedIssueKey(null)}>
          Back to Issues
        </Button>
      </div>
      {issueQuery.isLoading && (
        <p className="text-sm text-[color-mix(in_srgb,var(--color-text)_60%,transparent)]">Loading issue…</p>
      )}
      {issueQuery.isError && <ErrorBanner error={issueQuery.error} />}
      {issueQuery.data && (
        <Card className="p-5">
          <div className="mb-2 flex items-center gap-2">
            <span className="text-xs text-[color-mix(in_srgb,var(--color-text)_50%,transparent)]">{issueQuery.data.key}</span>
            <span className="inline-flex h-[20px] items-center rounded-[var(--radius-sm)] bg-[var(--color-neutral-800)] px-2 text-[11px] text-[color-mix(in_srgb,var(--color-text)_70%,transparent)]">
              {issueQuery.data.status}
            </span>
            <span className="text-[11px] text-[color-mix(in_srgb,var(--color-text)_45%,transparent)]">
              {issueQuery.data.issue_type}
            </span>
          </div>
          <h3 className="mb-2 text-base font-medium">{issueQuery.data.summary}</h3>
          <p className="mb-4 whitespace-pre-wrap text-sm leading-relaxed text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
            {issueQuery.data.description || '(No description)'}
          </p>

          {issueQuery.data.links.length > 0 && (
            <div className="mb-4 border-t border-[var(--color-divider)] pt-3.5">
              <div className="mb-2 text-[10.5px] tracking-wide text-[color-mix(in_srgb,var(--color-text)_45%,transparent)] uppercase">
                Related Jira Issues
              </div>
              <ul className="flex flex-col gap-1 text-sm text-[color-mix(in_srgb,var(--color-text)_75%,transparent)]">
                {issueQuery.data.links.map((link, i) => (
                  <li key={i}>
                    <span className="text-[color-mix(in_srgb,var(--color-text)_50%,transparent)]">{link.relationship}:</span>{' '}
                    {link.key}
                    {link.summary ? ` — ${link.summary}` : ''}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <Button onClick={handleUseTicket}>Use This Ticket</Button>
        </Card>
      )}
    </div>
  );
}
