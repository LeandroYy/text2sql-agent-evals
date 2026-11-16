"""Roda o pipeline sobre a amostra e grava uma linha por pergunta.

O arquivo de saída é retomável: perguntas já gravadas são puladas. Se a cota da API acabar,
o script para sem gravar a pergunta com erro; é só rodar de novo depois.

Uso: uv run python -m evals.run_eval --out results/gemini-3.5-flash-lite.jsonl [--limit 10]
"""

import argparse
import json
import sqlite3
import time
from pathlib import Path

from evals.metrics import same_result
from text2sql_agent.config import AGENT_MODEL, GUARDRAIL_MODEL, JUDGE_MODEL, ROOT
from text2sql_agent.db import run_sql
from text2sql_agent.pipeline import ask

GOLD_TIMEOUT_SECONDS = 120  # alguns SQLs esperados do BIRD são pesados
QUOTA_ATTEMPTS = 4  # tentativas por pergunta quando a API recusa por cota
QUOTA_WAIT_SECONDS = 120  # espera entre tentativas (cobre o limite por minuto)


class QuotaExhausted(Exception):
    pass


def execute(db_id: str, sql: str):
    """Executa sem limite de linhas. Devolve (linhas, erro)."""
    if not sql:
        return None, "no sql"
    try:
        _, rows, _ = run_sql(db_id, sql, timeout=GOLD_TIMEOUT_SECONDS)
        return rows, ""
    except sqlite3.Error as error:
        return None, str(error)


def check_quota(state: dict) -> None:
    """Erro de cota não é erro do agente: não pode virar "resposta errada" no resultado."""
    texts = [
        state.get("agent_error", ""),
        (state.get("guardrail") or {}).get("reason", ""),
        " ".join((state.get("judge") or {}).get("issues", [])),
    ]
    joined = " ".join(texts)
    if "RESOURCE_EXHAUSTED" in joined or "429" in joined or "quota" in joined.lower():
        raise QuotaExhausted(joined[:300])


def evaluate(item: dict) -> dict:
    started = time.perf_counter()
    state = ask(item["db_id"], item["question"], item.get("evidence", ""))
    seconds = time.perf_counter() - started
    check_quota(state)

    gold_rows, gold_error = execute(item["db_id"], item["SQL"])
    pred_rows, pred_error = execute(item["db_id"], state.get("sql", ""))
    correct = gold_rows is not None and pred_rows is not None and same_result(pred_rows, gold_rows)

    return {
        "question_id": item["question_id"],
        "db_id": item["db_id"],
        "difficulty": item["difficulty"],
        "question": item["question"],
        "evidence": item.get("evidence", ""),
        "gold_sql": item["SQL"],
        "status": state["status"],
        "sql": state.get("sql", ""),
        "agent_answer": state.get("agent_answer", ""),
        "agent_error": state.get("agent_error", ""),
        "final_answer": state.get("final_answer", ""),
        "guardrail": state.get("guardrail"),
        "judge": state.get("judge"),
        "queries_run": len(state.get("queries", [])),
        "ex_correct": correct,
        "pred_error": pred_error,
        "gold_error": gold_error,
        "usage": state.get("usage", {}),
        "seconds": seconds,
        "models": {"agent": AGENT_MODEL, "guardrail": GUARDRAIL_MODEL, "judge": JUDGE_MODEL},
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", default=str(ROOT / "evals" / "sample.jsonl"))
    parser.add_argument("--out", required=True)
    parser.add_argument("--limit", type=int, default=0, help="roda no máximo N perguntas novas")
    args = parser.parse_args()

    with open(args.sample, encoding="utf-8") as file:
        sample = [json.loads(line) for line in file]

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if out.exists():
        with open(out, encoding="utf-8") as file:
            done = {json.loads(line)["question_id"] for line in file if line.strip()}

    pending = [item for item in sample if item["question_id"] not in done]
    if args.limit:
        pending = pending[: args.limit]
    print(f"{len(done)} já feitas, {len(pending)} para rodar. Agente: {AGENT_MODEL} | Auditor: {JUDGE_MODEL}")

    for number, item in enumerate(pending, start=1):
        # O erro de cota pode ser só o limite por minuto: espera e tenta de novo antes de desistir.
        record = None
        for attempt in range(1, QUOTA_ATTEMPTS + 1):
            try:
                record = evaluate(item)
                break
            except QuotaExhausted as error:
                print(f"  cota atingida (tentativa {attempt}/{QUOTA_ATTEMPTS}): {str(error)[:120]}")
                if attempt < QUOTA_ATTEMPTS:
                    time.sleep(QUOTA_WAIT_SECONDS)
        if record is None:
            print("\nCota da API esgotada. Rode de novo mais tarde para continuar.")
            break
        with open(out, "a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
        mark = "OK " if record["ex_correct"] else "ERR"
        print(
            f"[{number}/{len(pending)}] {mark} {record['status']:<18} {record['seconds']:5.1f}s  "
            f"q{item['question_id']} {item['db_id']}"
        )


if __name__ == "__main__":
    main()
