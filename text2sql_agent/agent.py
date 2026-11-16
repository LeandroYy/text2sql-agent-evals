"""O agente SQL: um loop ReAct (pensa, chama ferramenta, lê o resultado, repete) do LangChain/LangGraph."""

from pathlib import Path

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langgraph.errors import GraphRecursionError
from pydantic import BaseModel, Field

from text2sql_agent.config import AGENT_MAX_STEPS, AGENT_MODEL
from text2sql_agent.llm import add_usage, empty_usage, make_model
from text2sql_agent.tools import make_tools

PROMPT = (Path(__file__).parent / "prompts" / "agent.md").read_text(encoding="utf-8")


class AgentAnswer(BaseModel):
    sql: str = Field(description="The final SQL query, exactly as executed.")
    answer: str = Field(description="Short answer in plain English based on the result.")


def run_agent(db_id: str, question: str, hint: str = "") -> dict:
    """Roda o agente e devolve sql, answer, queries (tudo que ele executou), usage e error."""
    queries: list[dict] = []
    agent = create_agent(
        make_model(AGENT_MODEL),
        make_tools(db_id, queries),
        system_prompt=PROMPT,
        # A resposta final vem como uma "ferramenta" com campos fixos: fica fácil separar SQL e texto.
        response_format=ToolStrategy(AgentAnswer),
    )
    content = question if not hint else f"{question}\n\nHint: {hint}"
    # Cada passo do agente usa 2 nós do grafo (modelo + ferramenta), por isso o limite é o dobro.
    config = {"recursion_limit": AGENT_MAX_STEPS * 2 + 3}

    # stream em vez de invoke: se o agente estourar o limite de passos, ainda temos o último estado.
    state, error = None, ""
    try:
        for snapshot in agent.stream({"messages": [("user", content)]}, config, stream_mode="values"):
            state = snapshot
    except GraphRecursionError:
        error = "step limit reached"
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"[:300]

    usage = empty_usage()
    for message in (state or {}).get("messages", []):
        add_usage(usage, message)

    structured = (state or {}).get("structured_response")
    sql = structured.sql if structured else ""
    answer = structured.answer if structured else ""
    if not sql:
        # Sem resposta estruturada, usamos a última consulta que deu certo.
        successful = [query["sql"] for query in queries if query["ok"]]
        sql = successful[-1] if successful else ""
    if not answer and not error:
        error = "agent returned no final answer"

    return {"sql": sql, "answer": answer, "queries": queries, "usage": usage, "error": error}
