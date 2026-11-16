"""Métricas calculadas a partir do arquivo de resultados do run_eval."""

import statistics

# Status em que o agente chegou a produzir uma resposta (o auditor aprovando ou não).
AGENT_ANSWERED = ("answered", "rejected_by_judge")
STAGES = ("guardrail", "agent", "judge")


def same_result(predicted: list[tuple], gold: list[tuple]) -> bool:
    """Execution accuracy do BIRD: os dois SQLs devolvem o mesmo conjunto de linhas.

    Comparação como conjunto: ordem e linhas repetidas não contam.
    """
    return set(predicted) == set(gold)


def rate(part: int, total: int) -> float | None:
    return part / total if total else None


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, round(fraction * (len(ordered) - 1)))
    return ordered[index]


def compute(records: list[dict]) -> dict:
    total = len(records)
    attempted = [r for r in records if r["status"] in AGENT_ANSWERED]
    kept = [r for r in records if r["status"] == "answered"]

    # O auditor visto como classificador: "positivo" = ele barrou a resposta.
    caught_wrong = sum(1 for r in attempted if r["status"] == "rejected_by_judge" and not r["ex_correct"])
    blocked_right = sum(1 for r in attempted if r["status"] == "rejected_by_judge" and r["ex_correct"])
    passed_wrong = sum(1 for r in attempted if r["status"] == "answered" and not r["ex_correct"])
    passed_right = sum(1 for r in attempted if r["status"] == "answered" and r["ex_correct"])

    status_counts: dict[str, int] = {}
    for r in records:
        status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1

    by_difficulty = {}
    for level in ("simple", "moderate", "challenging"):
        group = [r for r in records if r["difficulty"] == level]
        if group:
            by_difficulty[level] = {"n": len(group), "ex": rate(sum(r["ex_correct"] for r in group), len(group))}

    usage = {}
    for stage in STAGES:
        stage_usage = [r["usage"][stage] for r in records if stage in (r.get("usage") or {})]
        if stage_usage:
            usage[stage] = {
                "tokens_mean": statistics.mean(u["input_tokens"] + u["output_tokens"] for u in stage_usage),
                "calls_mean": statistics.mean(u["calls"] for u in stage_usage),
                "seconds_mean": statistics.mean(u["seconds"] for u in stage_usage),
            }

    seconds = [r["seconds"] for r in records]
    tokens = [sum(u["input_tokens"] + u["output_tokens"] for u in (r.get("usage") or {}).values()) for r in records]

    return {
        "n": total,
        "status_counts": status_counts,
        # EX geral: acertos sobre todas as perguntas, como no benchmark
        "ex": rate(sum(r["ex_correct"] for r in records), total),
        "without_judge": {
            "coverage": rate(len(attempted), total),
            "accuracy_answered": rate(sum(r["ex_correct"] for r in attempted), len(attempted)),
            "correct_shown": rate(sum(r["ex_correct"] for r in attempted), total),
        },
        "with_judge": {
            "coverage": rate(len(kept), total),
            "accuracy_answered": rate(sum(r["ex_correct"] for r in kept), len(kept)),
            "correct_shown": rate(passed_right, total),
        },
        "judge_confusion": {
            "caught_wrong": caught_wrong,
            "blocked_right": blocked_right,
            "passed_wrong": passed_wrong,
            "passed_right": passed_right,
            "precision": rate(caught_wrong, caught_wrong + blocked_right),
            "recall": rate(caught_wrong, caught_wrong + passed_wrong),
        },
        "by_difficulty": by_difficulty,
        "usage_by_stage": usage,
        "seconds_p50": percentile(seconds, 0.5),
        "seconds_p95": percentile(seconds, 0.95),
        "tokens_mean": statistics.mean(tokens) if tokens else None,
    }
