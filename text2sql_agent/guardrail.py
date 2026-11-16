"""Segunda barreira: um LLM classifica a pergunta antes do agente."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from text2sql_agent.config import GUARDRAIL_MODEL
from text2sql_agent.llm import add_usage, empty_usage, make_model

PROMPT = (Path(__file__).parent / "prompts" / "guardrail.md").read_text(encoding="utf-8")


class GuardrailVerdict(BaseModel):
    allowed: bool
    category: Literal["ok", "prompt_injection", "write_request", "system_extraction", "off_topic"]
    reason: str = Field(description="One sentence explaining the decision.")


def check_with_llm(question: str) -> tuple[dict, dict]:
    """Devolve (veredito, uso de tokens).

    Fail-closed: se o classificador der erro ou timeout, a pergunta é bloqueada.
    Deixar passar quando o filtro falha abriria uma porta justamente quando ninguém está olhando.
    """
    usage = empty_usage()
    model = make_model(GUARDRAIL_MODEL).with_structured_output(GuardrailVerdict, include_raw=True)
    try:
        result = model.invoke([("system", PROMPT), ("human", question)])
        add_usage(usage, result["raw"])
        verdict = result["parsed"]
        if verdict is None:
            raise ValueError("guardrail returned an invalid response")
        return verdict.model_dump(), usage
    except Exception as error:
        reason = f"{type(error).__name__}: {error}"[:300]
        return {"allowed": False, "category": "guardrail_error", "reason": reason}, usage
