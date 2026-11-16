"""Primeira barreira: regras simples, sem custo de LLM."""

from text2sql_agent.config import MAX_QUESTION_CHARS


def check_question(question: str) -> str | None:
    """Devolve o motivo da recusa, ou None se a pergunta pode seguir."""
    text = question.strip()
    if not text:
        return "empty question"
    if len(text) > MAX_QUESTION_CHARS:
        return f"question longer than {MAX_QUESTION_CHARS} characters"
    # Caracteres de controle (exceto quebra de linha e tab) costumam aparecer em tentativas de injeção.
    if any(ord(char) < 32 and char not in "\n\t" for char in text):
        return "control characters in the question"
    return None
