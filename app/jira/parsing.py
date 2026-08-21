"""Pure parsing helpers for raw Jira Cloud REST API v3 response data.

No I/O here - same "pure and side-effect free by design" convention as
app/rag/chunking.py and app/coaching/selection.py, so this can be unit
tested directly against hand-built fixture dicts with no HTTP mocking.
"""

from app.analysis.schemas import RelatedIssue

_BLOCK_NODE_TYPES = {"paragraph", "heading", "listItem"}


def adf_to_plain_text(node: dict | None) -> str:
    """Best-effort plain-text extraction from an Atlassian Document Format node.

    Jira Cloud API v3 returns issue `description` as ADF (a rich-content
    JSON tree), not plain text. This walks the tree, joining text nodes and
    inserting a line break after each block-level node, so the result reads
    reasonably as plain text for the analysis prompt. Unknown node types are
    walked into (via `content`) but otherwise ignored, so this degrades
    gracefully rather than raising on ADF constructs it doesn't specially
    handle (tables, panels, etc.).
    """
    if not node:
        return ""

    parts: list[str] = []

    def _walk(n: object) -> None:
        if isinstance(n, dict):
            if n.get("type") == "text":
                parts.append(n.get("text", ""))
            for child in n.get("content") or []:
                _walk(child)
            if n.get("type") in _BLOCK_NODE_TYPES:
                parts.append("\n")
        elif isinstance(n, list):
            for item in n:
                _walk(item)

    _walk(node)
    return "".join(parts).strip()


def extract_related_issues(fields: dict) -> list[RelatedIssue]:
    """Extract only explicit, Jira-confirmed relationships (links, parent, subtasks).

    Never infers a relationship Jira itself doesn't report - this is the
    confirmed counterpart to the LLM-inferred `possible_dependencies` already
    in app/analysis/schemas.py (see CLAUDE.md section 13: "The AI should NOT
    invent dependencies. If Jira provides evidence of a relationship,
    provide it to the agent.").
    """
    related: list[RelatedIssue] = []

    for link in fields.get("issuelinks") or []:
        link_type = link.get("type") or {}
        if "outwardIssue" in link:
            other = link["outwardIssue"]
            relationship = link_type.get("outward", "relates to")
        elif "inwardIssue" in link:
            other = link["inwardIssue"]
            relationship = link_type.get("inward", "relates to")
        else:
            continue
        related.append(
            RelatedIssue(
                key=other["key"],
                relationship=relationship,
                summary=(other.get("fields") or {}).get("summary"),
            )
        )

    parent = fields.get("parent")
    if parent:
        related.append(
            RelatedIssue(
                key=parent["key"],
                relationship="parent",
                summary=(parent.get("fields") or {}).get("summary"),
            )
        )

    for subtask in fields.get("subtasks") or []:
        related.append(
            RelatedIssue(
                key=subtask["key"],
                relationship="subtask",
                summary=(subtask.get("fields") or {}).get("summary"),
            )
        )

    return related
