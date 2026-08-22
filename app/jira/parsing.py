"""Pure parsing/formatting helpers for Jira Cloud REST API v3 data - both
directions: reading raw Jira responses (adf_to_plain_text,
extract_related_issues), and writing back (format_final_requirement_text,
plain_text_to_adf).

No I/O here - same "pure and side-effect free by design" convention as
app/rag/chunking.py and app/coaching/selection.py, so this can be unit
tested directly against hand-built fixture dicts with no HTTP mocking.
"""

from app.analysis.schemas import RelatedIssue
from app.coaching.schemas import FinalRequirementContent

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


def format_final_requirement_text(final_requirement: FinalRequirementContent) -> str:
    """Format a finalized development-ready requirement as plain text for a Jira description.

    Includes every section - user story, acceptance criteria, scope,
    assumptions, dependencies - per the requirement that the full refined
    requirement (not a partial summary) is written back to Jira. Each
    section's title and body are separated by a blank line so
    plain_text_to_adf() renders the body (a bullet list, or the user story
    paragraph) as its own ADF node distinct from the title.
    """

    def _section(title: str, items: list[str]) -> str:
        body = "\n".join(f"- {item}" for item in items) if items else "(none)"
        return f"{title}:\n\n{body}"

    return "\n\n".join(
        [
            f"User Story:\n\n{final_requirement.user_story}",
            _section("Acceptance Criteria", final_requirement.acceptance_criteria),
            _section("Scope", final_requirement.scope),
            _section("Assumptions", final_requirement.assumptions),
            _section("Dependencies", final_requirement.dependencies),
        ]
    )


def plain_text_to_adf(text: str) -> dict:
    """Convert plain text into a minimal Atlassian Document Format document.

    The inverse of adf_to_plain_text() for the one direction this app
    writes back to Jira. Blocks separated by a blank line become their own
    ADF node: a block whose every line starts with "- " becomes an ADF
    bulletList; any other block becomes one paragraph per line. This is
    intentionally minimal - just enough structure for
    format_final_requirement_text()'s output to render legibly in Jira, not
    a general-purpose Markdown-to-ADF converter.
    """
    content: list[dict] = []

    for block in text.split("\n\n"):
        lines = [line for line in block.split("\n") if line.strip()]
        if not lines:
            continue

        bullet_items = [line[2:] for line in lines if line.startswith("- ")]
        if bullet_items and len(bullet_items) == len(lines):
            content.append(
                {
                    "type": "bulletList",
                    "content": [
                        {
                            "type": "listItem",
                            "content": [
                                {"type": "paragraph", "content": [{"type": "text", "text": item}]}
                            ],
                        }
                        for item in bullet_items
                    ],
                }
            )
        else:
            for line in lines:
                content.append({"type": "paragraph", "content": [{"type": "text", "text": line}]})

    if not content:
        content = [{"type": "paragraph", "content": []}]

    return {"type": "doc", "version": 1, "content": content}
