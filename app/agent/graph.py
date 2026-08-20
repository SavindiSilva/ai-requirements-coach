"""LangGraph workflow for Phase 1 single-shot requirement analysis.

START -> retrieve_context -> analyze_requirement -> END

retrieve_context is a Phase 3 addition: a second node, genuinely internal
to this graph invocation (not a separate HTTP round-trip), so it belongs
in the graph rather than as a plain pre-step - see docs/skills.md section 3
for when a step earns a LangGraph node. It always fails safe (see
app/agent/rag_integration.py), so this graph's behaviour with RAG
unavailable is identical to the original single-node graph.

The coaching loop (wait-for-user, re-evaluate, more-gaps branch) is a
separate milestone and is not implemented here - see app/coaching/router.py.
"""

from langgraph.graph import END, StateGraph

from app.agent.llm import run_structured_analysis
from app.agent.prompts import build_system_prompt, build_user_prompt
from app.agent.rag_integration import get_retrieved_context
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


def retrieve_context_node(state: AgentState) -> AgentState:
    ticket = state["ticket"]
    query_text = f"{ticket.title}\n{ticket.description}"
    return {"retrieved_context": get_retrieved_context(query_text)}


def analyze_requirement_node(state: AgentState) -> AgentState:
    ticket = state["ticket"]
    coaching_history = state.get("coaching_history")
    retrieved_context = state.get("retrieved_context")

    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(ticket, coaching_history, retrieved_context)
    content = run_structured_analysis(system_prompt, user_prompt)

    overall_readiness = _compute_overall_readiness(content)
    analysis = AnalysisResult(**content.model_dump(), overall_readiness=overall_readiness)

    return {"ticket": ticket, "analysis": analysis, "coaching_history": coaching_history}


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("retrieve_context", retrieve_context_node)
    graph.add_node("analyze_requirement", analyze_requirement_node)
    graph.set_entry_point("retrieve_context")
    graph.add_edge("retrieve_context", "analyze_requirement")
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
    final_state = graph.invoke(
        {
            "ticket": ticket,
            "analysis": None,
            "coaching_history": coaching_history,
            "retrieved_context": None,
        }
    )
    return final_state["analysis"]
