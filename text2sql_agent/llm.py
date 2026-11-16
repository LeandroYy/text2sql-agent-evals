"""Criação dos modelos e contagem de tokens."""

from langchain.chat_models import init_chat_model
from langchain_core.rate_limiters import InMemoryRateLimiter

from text2sql_agent.config import REQUESTS_PER_MINUTE

# Um limitador só para todas as chamadas: a cota gratuita é contada por chave de API.
rate_limiter = InMemoryRateLimiter(
    requests_per_second=REQUESTS_PER_MINUTE / 60,
    check_every_n_seconds=0.2,
    max_bucket_size=1,
)


def make_model(name: str):
    """`name` no formato "provedor:modelo", ex.: "google_genai:gemini-3.5-flash"."""
    return init_chat_model(name, temperature=0, max_retries=6, timeout=120, rate_limiter=rate_limiter)


def empty_usage() -> dict:
    return {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cached_tokens": 0, "reasoning_tokens": 0}


def add_usage(total: dict, message) -> None:
    """Soma no `total` os tokens informados pelo provedor numa resposta do modelo."""
    meta = getattr(message, "usage_metadata", None)
    if not meta:
        return
    total["calls"] += 1
    total["input_tokens"] += meta.get("input_tokens", 0)
    total["output_tokens"] += meta.get("output_tokens", 0)
    total["cached_tokens"] += (meta.get("input_token_details") or {}).get("cache_read", 0)
    total["reasoning_tokens"] += (meta.get("output_token_details") or {}).get("reasoning", 0)
