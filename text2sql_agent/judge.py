"""Auditor (LLM-as-judge): um segundo modelo confere se a resposta do agente é sustentada pelos dados."""

from pathlib import Path

from pydantic import BaseModel, Field

from text2sql_agent.config import JUDGE_MODEL
from text2sql_agent.llm import add_usage, empty_usage, make_model

PROMPT = (Path(__file__).parent / "prompts" / "judge.md").read_text(encoding="utf-8")
MAX_RESULT_CHARS = 1500  # por consulta, para o contexto do auditor não crescer demais
LAST_QUERIES = 5  # o auditor vê só as últimas consultas; as primeiras costumam ser exploração


class JudgeVerdict(BaseModel):
    consistent: bool
    issues: list[str] = Field(default_factory=list)
    explanation: str = Field(description="How the result was obtained, for a non-technical user.")


def build_report(question: str, hint: str, queries: list[dict], sql: str, answer: str) -> str:
    """Monta o texto que o auditor lê: pergunta, consultas executadas com resultado e resposta."""
    parts = [f"## Question\n{question}"]
    if hint:
        parts.append(f"## Hint\n{hint}")
    for number, query in enumerate(queries[-LAST_QUERIES:], start=1):
        result = query["result"]
        if len(result) > MAX_RESULT_CHARS:
            result = result[:MAX_RESULT_CHARS] + "\n(...cut)"
        parts.append(f"## Query {number}\n```sql\n{query['sql']}\n```\nResult:\n{result}")
    parts.append(f"## Final SQL\n```sql\n{sql}\n```")
    parts.append(f"## Final answer\n{answer}")
    return "\n\n".join(parts)


def judge(question: str, hint: str, queries: list[dict], sql: str, answer: str) -> tuple[dict, dict]:
    """Devolve (veredito, uso de tokens). Em caso de erro, a resposta é tratada como não confiável."""
    usage = empty_usage()
    model = make_model(JUDGE_MODEL).with_structured_output(JudgeVerdict, include_raw=True)
    report = build_report(question, hint, queries, sql, answer)
    try:
        result = model.invoke([("system", PROMPT), ("human", report)])
        add_usage(usage, result["raw"])
        verdict = result["parsed"]
        if verdict is None:
            raise ValueError("judge returned an invalid response")
        return verdict.model_dump(), usage
    except Exception as error:
        issue = f"judge error: {type(error).__name__}: {error}"[:300]
        return {"consistent": False, "issues": [issue], "explanation": ""}, usage
