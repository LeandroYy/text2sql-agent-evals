"""Liga as etapas num grafo do LangGraph:

pré-filtro → guardrail → agente → auditor → sanitização

Qualquer etapa pode encerrar o fluxo com uma recusa. O campo `status` diz onde parou.
"""

import time
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from text2sql_agent.agent import run_agent
from text2sql_agent.guardrail import check_with_llm
from text2sql_agent.judge import judge
from text2sql_agent.prefilter import check_question
from text2sql_agent.sanitizer import sanitize

BLOCKED_MESSAGE = "I can't help with that request. I can only answer questions about the data."
FAILED_MESSAGE = "I couldn't answer this question. Try rephrasing it."
NOT_CONFIDENT_MESSAGE = "I found an answer, but I couldn't confirm it against the data, so I won't show it."


def merge(old: dict, new: dict) -> dict:
    return {**old, **new}


class State(TypedDict, total=False):
    db_id: str
    question: str
    hint: str
    # answered | blocked_prefilter | blocked_guardrail | agent_error | rejected_by_judge
    status: str
    prefilter_reason: str
    guardrail: dict
    sql: str
    agent_answer: str
    agent_error: str
    queries: list[dict]
    judge: dict
    final_answer: str
    # tokens e segundos por etapa; `merge` junta o que cada nó devolve
    usage: Annotated[dict, merge]


def prefilter_node(state: State) -> dict:
    reason = check_question(state["question"])
    if reason:
        return {"status": "blocked_prefilter", "prefilter_reason": reason, "final_answer": BLOCKED_MESSAGE}
    return {}


def guardrail_node(state: State) -> dict:
    start = time.perf_counter()
    verdict, usage = check_with_llm(state["question"])
    update = {"guardrail": verdict, "usage": {"guardrail": {**usage, "seconds": time.perf_counter() - start}}}
    if not verdict["allowed"]:
        update.update(status="blocked_guardrail", final_answer=BLOCKED_MESSAGE)
    return update


def agent_node(state: State) -> dict:
    start = time.perf_counter()
    result = run_agent(state["db_id"], state["question"], state.get("hint", ""))
    update = {
        "sql": result["sql"],
        "agent_answer": result["answer"],
        "agent_error": result["error"],
        "queries": result["queries"],
        "usage": {"agent": {**result["usage"], "seconds": time.perf_counter() - start}},
    }
    if result["error"]:
        update.update(status="agent_error", final_answer=FAILED_MESSAGE)
    return update


def judge_node(state: State) -> dict:
    start = time.perf_counter()
    verdict, usage = judge(
        state["question"], state.get("hint", ""), state["queries"], state["sql"], state["agent_answer"]
    )
    update = {"judge": verdict, "usage": {"judge": {**usage, "seconds": time.perf_counter() - start}}}
    if verdict["consistent"]:
        answer = state["agent_answer"]
        if verdict["explanation"]:
            answer += "\n\nHow I got this: " + verdict["explanation"]
        update.update(status="answered", final_answer=answer)
    else:
        update.update(status="rejected_by_judge", final_answer=NOT_CONFIDENT_MESSAGE)
    return update


def sanitize_node(state: State) -> dict:
    return {"final_answer": sanitize(state["final_answer"])}


def stop_if_finished(next_node: str):
    """Depois de cada etapa: se alguma recusa já definiu o status, encerra; senão segue."""
    return lambda state: END if state.get("status") else next_node


def build_pipeline():
    graph = StateGraph(State)
    graph.add_node("prefilter", prefilter_node)
    graph.add_node("guardrail", guardrail_node)
    graph.add_node("agent", agent_node)
    graph.add_node("judge", judge_node)
    graph.add_node("sanitize", sanitize_node)

    graph.add_edge(START, "prefilter")
    # A lista no fim diz ao LangGraph os destinos possíveis (serve também para desenhar o grafo).
    graph.add_conditional_edges("prefilter", stop_if_finished("guardrail"), ["guardrail", END])
    graph.add_conditional_edges("guardrail", stop_if_finished("agent"), ["agent", END])
    graph.add_conditional_edges("agent", stop_if_finished("judge"), ["judge", END])
    graph.add_edge("judge", "sanitize")
    graph.add_edge("sanitize", END)
    return graph.compile()


pipeline = build_pipeline()


def ask(db_id: str, question: str, hint: str = "") -> dict:
    return pipeline.invoke({"db_id": db_id, "question": question, "hint": hint, "usage": {}})
