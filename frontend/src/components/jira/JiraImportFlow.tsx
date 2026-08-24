import { useMemo, useState } from 'react';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { KnowledgeContextPanel } from '../knowledge/KnowledgeContextPanel';
import { fieldInputClasses } from '../../lib/fieldStyles';
import { formatScore } from '../../lib/format';
import { getAiReviewStatus } from '../../lib/aiReviewStatus';
import { useJiraStatus } from '../../hooks/useJiraStatus';
import { useJiraProjects } from '../../hooks/useJiraProjects';
import { useJiraProjectIssues } from '../../hooks/useJiraProjectIssues';
import { useJiraIssue } from '../../hooks/useJiraIssue';
import { useReviewedTickets } from '../../hooks/useReviewedTickets';
import { API_BASE_URL, ApiError } from '../../lib/api/client';
import type { TicketInput } from '../../lib/types/analysis';
import type { ReviewedTicket } from '../../lib/types/reviewedTicket';

// The three states useReviewedTickets()-derived AI Review can be in for a
// Jira issue - matches getAiReviewStatus()'s label vocabulary exactly, so
// this doubles as the filter dropdown's option list.
const AI_REVIEW_OPTIONS = ['Not Reviewed', 'Ready', 'Needs Clarification'] as const;

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
  const [priorityFilter, setPriorityFilter] = useState('All');
  const [aiReviewFilter, setAiReviewFilter] = useState('All');

  const statusQuery = useJiraStatus();
  const connected = statusQuery.data?.connected ?? false;

  // Both queries stay enabled once a project/issue is picked, since the
  // project grid and issue list remain mounted alongside the sidebar
  // instead of being replaced by it.
  const projectsQuery = useJiraProjects(connected);
  const issuesQuery = useJiraProjectIssues(connected && selectedProjectId ? selectedProjectId : null);
  const issueQuery = useJiraIssue(connected && selectedIssueKey ? selectedIssueKey : null);
  // AI Review/Readiness aren't new backend data - they're derived by
  // cross-referencing each issue's key against this same reviewed-ticket
  // history the Dashboard/History already fetch, entirely client-side.
  const reviewedTicketsQuery = useReviewedTickets();

  // Most recent record per issue key. The backend already upserts by
  // issue_key (one row per ticket), so this is a 1:1 lookup, not a
  // "pick the latest of several" reduction.
  const reviewedByIssueKey = useMemo(() => {
    const map = new Map<string, ReviewedTicket>();
    reviewedTicketsQuery.data?.forEach((rt) => {
      if (rt.issueKey) map.set(rt.issueKey, rt);
    });
    return map;
  }, [reviewedTicketsQuery.data]);

  // Derived from whatever statuses/priorities this project's issues
  // actually use, rather than a hardcoded list — both are per-project in
  // Jira (status is a per-project workflow; priority scheme is optional
  // and per-project too).
  const statusOptions = useMemo(() => {
    const statuses = new Set<string>();
    issuesQuery.data?.forEach((issue) => statuses.add(issue.status));
    return Array.from(statuses).sort();
  }, [issuesQuery.data]);

  const priorityOptions = useMemo(() => {
    const priorities = new Set<string>();
    issuesQuery.data?.forEach((issue) => {
      if (issue.priority) priorities.add(issue.priority);
    });
    return Array.from(priorities).sort();
  }, [issuesQuery.data]);

  const filteredIssues = useMemo(() => {
    if (!issuesQuery.data) return undefined;
    const term = searchTerm.trim().toLowerCase();
    return issuesQuery.data.filter((issue) => {
      const matchesTerm =
        !term || issue.key.toLowerCase().includes(term) || issue.summary.toLowerCase().includes(term);
      const matchesStatus = statusFilter === 'All' || issue.status === statusFilter;
      const matchesPriority = priorityFilter === 'All' || issue.priority === priorityFilter;
      const aiReviewLabel = getAiReviewStatus(reviewedByIssueKey.get(issue.key)?.stopReason).label;
      const matchesAiReview = aiReviewFilter === 'All' || aiReviewLabel === aiReviewFilter;
      return matchesTerm && matchesStatus && matchesPriority && matchesAiReview;
    });
  }, [issuesQuery.data, searchTerm, statusFilter, priorityFilter, aiReviewFilter, reviewedByIssueKey]);

  function handleConnect() {
    window.location.href = `${API_BASE_URL}/jira/authorize`;
  }

  function handleSelectProject(projectId: string) {
    setSelectedProjectId(projectId);
    setSelectedIssueKey(null);
    setSearchTerm('');
    setStatusFilter('All');
    setPriorityFilter('All');
    setAiReviewFilter('All');
  }

  function handleChangeProject() {
    setSelectedProjectId(null);
    setSelectedIssueKey(null);
    setSearchTerm('');
    setStatusFilter('All');
    setPriorityFilter('All');
    setAiReviewFilter('All');
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
                  <select
                    value={priorityFilter}
                    onChange={(e) => setPriorityFilter(e.target.value)}
                    className={`sm:w-40 ${fieldInputClasses(false)}`}
                  >
                    <option value="All">Priority: All</option>
                    {priorityOptions.map((priority) => (
                      <option key={priority} value={priority}>
                        {priority}
                      </option>
                    ))}
                  </select>
                  <select
                    value={aiReviewFilter}
                    onChange={(e) => setAiReviewFilter(e.target.value)}
                    className={`sm:w-44 ${fieldInputClasses(false)}`}
                  >
                    <option value="All">AI Review: All</option>
                    {AI_REVIEW_OPTIONS.map((label) => (
                      <option key={label} value={label}>
                        {label}
                      </option>
                    ))}
                  </select>
                </div>

                <Card className="overflow-hidden p-0">
                  <div className="grid grid-cols-[1fr_110px_120px_110px_130px_90px] gap-3 border-b border-[var(--color-divider)] px-4 py-2 text-[10.5px] tracking-wide text-[color-mix(in_srgb,var(--color-text)_45%,transparent)] uppercase">
                    <div>Ticket</div>
                    <div>Jira Status</div>
                    <div>Assignee</div>
                    <div>Priority</div>
                    <div>AI Review</div>
                    <div>Readiness</div>
                  </div>
                  {filteredIssues?.map((issue) => {
                    const reviewedTicket = reviewedByIssueKey.get(issue.key);
                    const aiReview = getAiReviewStatus(reviewedTicket?.stopReason);
                    return (
                      <div
                        key={issue.key}
                        onClick={() => setSelectedIssueKey(issue.key)}
                        className={`grid cursor-pointer grid-cols-[1fr_110px_120px_110px_130px_90px] items-center gap-3 border-b border-[var(--color-divider)] px-4 py-3 last:border-b-0 hover:bg-[color-mix(in_srgb,var(--color-text)_6%,transparent)] ${
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
                        <div className="truncate text-xs text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
                          {issue.assignee ?? 'Unassigned'}
                        </div>
                        <div className="truncate text-xs text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
                          {issue.priority ?? '—'}
                        </div>
                        <div>
                          <span className={`text-xs font-medium whitespace-nowrap ${aiReview.colorClass}`}>{aiReview.label}</span>
                        </div>
                        <div className="text-xs text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
                          {reviewedTicket ? `${formatScore(reviewedTicket.readiness)}/3` : '—'}
                        </div>
                      </div>
                    );
                  })}
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
