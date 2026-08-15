"""LangGraph workflow for Phase 1 single-shot requirement analysis.

START -> analyze_requirement -> END

This is intentionally a single-node graph for Phase 1 (mock ticket -> Claude
-> structured analysis). The coaching loop (wait-for-user, re-evaluate,
more-gaps branch) is a later milestone and is not implemented here.
"""

from langgraph.graph import END, StateGraph

from app.agent.llm import run_structured_analysis
from app.agent.prompts import build_system_prompt, build_user_prompt
from app.agent.state import AgentState
from app.analysis.schemas import AnalysisContent, AnalysisResult, TicketInput


def _compute_overall_readiness(content: AnalysisContent) -> float:
    scores = [
        content.requirement_clarity.score,
        content.acceptance_criteria.score,
        content.open_questions.score,
        content.scope_definition.score,
    ]
    return round(sum(scores) / len(scores), 2)


def analyze_requirement_node(state: AgentState) -> AgentState:
    ticket = state["ticket"]
    coaching_history = state.get("coaching_history")

    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(ticket, coaching_history)
    content = run_structured_analysis(system_prompt, user_prompt)

    overall_readiness = _compute_overall_readiness(content)
    analysis = AnalysisResult(**content.model_dump(), overall_readiness=overall_readiness)

    return {"ticket": ticket, "analysis": analysis, "coaching_history": coaching_history}


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("analyze_requirement", analyze_requirement_node)
    graph.set_entry_point("analyze_requirement")
    graph.add_edge("analyze_requirement", END)
    return graph.compile()


_compiled_graph = None


def get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph


def analyze_ticket(
    ticket: TicketInput,
    coaching_history: list[tuple[str, str]] | None = None,
) -> AnalysisResult:
    graph = get_graph()
    final_state = graph.invoke({"ticket": ticket, "analysis": None, "coaching_history": coaching_history})
    return final_state["analysis"]
