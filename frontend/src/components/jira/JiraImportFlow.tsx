import { useMemo, useState } from 'react';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { KnowledgeContextPanel } from '../knowledge/KnowledgeContextPanel';
import { fieldInputClasses } from '../../lib/fieldStyles';
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

const selectedCardClasses = 'shadow-[0_0_0_1px_var(--color-accent)]';

export function JiraImportFlow({ onTicketReady }: JiraImportFlowProps) {
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [selectedIssueKey, setSelectedIssueKey] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('All');

  const statusQuery = useJiraStatus();
  const connected = statusQuery.data?.connected ?? false;

  // Both queries stay enabled once a project/issue is picked, since the
  // project grid and issue list remain mounted alongside the sidebar
  // instead of being replaced by it.
  const projectsQuery = useJiraProjects(connected);
  const issuesQuery = useJiraProjectIssues(connected && selectedProjectId ? selectedProjectId : null);
  const issueQuery = useJiraIssue(connected && selectedIssueKey ? selectedIssueKey : null);

  // Derived from whatever statuses this project's issues actually use,
  // rather than a hardcoded workflow — Jira status names are per-project.
  const statusOptions = useMemo(() => {
    const statuses = new Set<string>();
    issuesQuery.data?.forEach((issue) => statuses.add(issue.status));
    return Array.from(statuses).sort();
  }, [issuesQuery.data]);

  const filteredIssues = useMemo(() => {
    if (!issuesQuery.data) return undefined;
    const term = searchTerm.trim().toLowerCase();
    return issuesQuery.data.filter((issue) => {
      const matchesTerm =
        !term || issue.key.toLowerCase().includes(term) || issue.summary.toLowerCase().includes(term);
      const matchesStatus = statusFilter === 'All' || issue.status === statusFilter;
      return matchesTerm && matchesStatus;
    });
  }, [issuesQuery.data, searchTerm, statusFilter]);

  function handleConnect() {
    window.location.href = `${API_BASE_URL}/jira/authorize`;
  }

  function handleSelectProject(projectId: string) {
    setSelectedProjectId(projectId);
    setSelectedIssueKey(null);
    setSearchTerm('');
    setStatusFilter('All');
  }

  function handleChangeProject() {
    setSelectedProjectId(null);
    setSelectedIssueKey(null);
    setSearchTerm('');
    setStatusFilter('All');
  }

  function handleUseTicket() {
    const issue = issueQuery.data;
    if (!issue) return;
    onTicketReady({
      title: issue.summary,
      description: issue.description,
      related_issues: issue.links.length > 0 ? issue.links : undefined,
      source_issue_key: issue.key,
      project_id: selectedProjectId,
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
      <Card className="max-w-md p-5">
        <p className="mb-4 text-sm leading-relaxed text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
          Connect your Jira account to import a ticket for review.
        </p>
        <Button onClick={handleConnect}>Connect Jira</Button>
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-sm text-[var(--color-success)]">
          <span className="h-[7px] w-[7px] rounded-full bg-[var(--color-success)]" />
          Jira Connected
        </div>
        <div className="flex items-center gap-2">
          {selectedProjectId && (
            <Button variant="secondary" onClick={handleChangeProject}>
              Change project
            </Button>
          )}
          <Button variant="secondary" onClick={handleConnect}>
            Change connection
          </Button>
        </div>
      </div>

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
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {projectsQuery.data?.map((project) => (
            <Card
              key={project.id}
              className={`cursor-pointer p-4 hover:bg-[color-mix(in_srgb,var(--color-text)_6%,transparent)] ${
                project.id === selectedProjectId ? selectedCardClasses : ''
              }`}
              onClick={() => handleSelectProject(project.id)}
            >
              <div className="text-sm font-medium">{project.name}</div>
              <div className="text-xs text-[color-mix(in_srgb,var(--color-text)_50%,transparent)]">{project.key}</div>
            </Card>
          ))}
        </div>
      </div>

      {selectedProjectId && (
        <div className="grid grid-cols-1 items-start gap-5 lg:grid-cols-[1fr_360px]">
          <div className="flex flex-col gap-3">
            <h2 className="text-base font-medium">Select an Issue</h2>
            {issuesQuery.isLoading && (
              <p className="text-sm text-[color-mix(in_srgb,var(--color-text)_60%,transparent)]">Loading issues…</p>
            )}
            {issuesQuery.isError && <ErrorBanner error={issuesQuery.error} />}
            {issuesQuery.data && issuesQuery.data.length === 0 && (
              <p className="text-sm text-[color-mix(in_srgb,var(--color-text)_40%,transparent)]">
                No issues were found in this project.
              </p>
            )}

            {issuesQuery.data && issuesQuery.data.length > 0 && (
              <>
                <div className="flex flex-col gap-2 sm:flex-row">
                  <input
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    placeholder="Search tickets..."
                    className={`sm:flex-1 ${fieldInputClasses(false)}`}
                  />
                  <select
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                    className={`sm:w-48 ${fieldInputClasses(false)}`}
                  >
                    <option value="All">Jira Status: All</option>
                    {statusOptions.map((status) => (
                      <option key={status} value={status}>
                        {status}
                      </option>
                    ))}
                  </select>
                </div>

                <Card className="overflow-hidden p-0">
                  <div className="grid grid-cols-[1fr_130px] gap-3 border-b border-[var(--color-divider)] px-4 py-2 text-[10.5px] tracking-wide text-[color-mix(in_srgb,var(--color-text)_45%,transparent)] uppercase">
                    <div>Ticket</div>
                    <div>Jira Status</div>
                  </div>
                  {filteredIssues?.map((issue) => (
                    <div
                      key={issue.key}
                      onClick={() => setSelectedIssueKey(issue.key)}
                      className={`grid cursor-pointer grid-cols-[1fr_130px] items-center gap-3 border-b border-[var(--color-divider)] px-4 py-3 last:border-b-0 hover:bg-[color-mix(in_srgb,var(--color-text)_6%,transparent)] ${
                        issue.key === selectedIssueKey ? selectedCardClasses : ''
                      }`}
                    >
                      <div>
                        <div className="text-xs text-[color-mix(in_srgb,var(--color-text)_50%,transparent)]">{issue.key}</div>
                        <div className="text-sm font-medium">{issue.summary}</div>
                      </div>
                      <div>
                        <span className="inline-flex h-[20px] items-center rounded-[var(--radius-sm)] bg-[var(--color-neutral-800)] px-2 text-[11px] text-[color-mix(in_srgb,var(--color-text)_70%,transparent)]">
                          {issue.status}
                        </span>
                      </div>
                    </div>
                  ))}
                  {filteredIssues && filteredIssues.length === 0 && (
                    <div className="px-4 py-8 text-center text-sm text-[color-mix(in_srgb,var(--color-text)_40%,transparent)]">
                      No tickets match your filters.
                    </div>
                  )}
                </Card>
              </>
            )}
          </div>

          <div className="flex flex-col gap-3">
            {selectedIssueKey ? (
              <>
                {issueQuery.isLoading && (
                  <Card className="p-5">
                    <p className="text-sm text-[color-mix(in_srgb,var(--color-text)_60%,transparent)]">Loading issue…</p>
                  </Card>
                )}
                {issueQuery.isError && <ErrorBanner error={issueQuery.error} />}
                {issueQuery.data && (
                  <Card className="p-5">
                    <div className="mb-2 flex items-center gap-2">
                      <span className="text-xs text-[color-mix(in_srgb,var(--color-text)_50%,transparent)]">
                        {issueQuery.data.key}
                      </span>
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
                              <span className="text-[color-mix(in_srgb,var(--color-text)_50%,transparent)]">
                                {link.relationship}:
                              </span>{' '}
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
              </>
            ) : (
              <Card className="p-8 text-center">
                <p className="text-sm text-[color-mix(in_srgb,var(--color-text)_40%,transparent)]">
                  Select a ticket to preview details.
                </p>
              </Card>
            )}

            <KnowledgeContextPanel projectId={selectedProjectId} />
          </div>
        </div>
      )}
    </div>
  );
}
