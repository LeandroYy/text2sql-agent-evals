"""Gera results/REPORT.md e um gráfico por rodada a partir dos arquivos .jsonl.

Uso: uv run python -m evals.report results/gemini-3.5-flash-lite.jsonl [outro.jsonl ...]
"""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # gera PNG sem abrir janela
import matplotlib.pyplot as plt  # noqa: E402

from evals.metrics import compute  # noqa: E402
from text2sql_agent.config import ROOT  # noqa: E402

RESULTS_DIR = ROOT / "results"
# Paleta categórica (slots 1 e 2), texto e grade discretos
BLUE, ORANGE = "#2a78d6", "#eb6834"
TEXT, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"


def pct(value) -> str:
    return "—" if value is None else f"{value * 100:.0f}%"


def load(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def chart(metrics: dict, title: str, out: Path) -> None:
    labels = ["Perguntas respondidas", "Acurácia das respondidas", "Respostas certas mostradas"]
    keys = ["coverage", "accuracy_answered", "correct_shown"]
    without = [(metrics["without_judge"][k] or 0) * 100 for k in keys]
    with_judge = [(metrics["with_judge"][k] or 0) * 100 for k in keys]

    fig, ax = plt.subplots(figsize=(8, 4.2), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    positions = range(len(labels))
    width = 0.34
    gap = 0.02  # pequeno espaço entre as barras do mesmo grupo
    bars_a = ax.bar([p - width / 2 - gap for p in positions], without, width, color=BLUE, label="Sem auditor")
    bars_b = ax.bar([p + width / 2 + gap for p in positions], with_judge, width, color=ORANGE, label="Com auditor")
    for bars in (bars_a, bars_b):
        for bar in bars:
            ax.annotate(
                f"{bar.get_height():.0f}%",
                (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                xytext=(0, 3),
                textcoords="offset points",
                ha="center",
                fontsize=9,
                color=TEXT,
            )

    ax.set_xticks(list(positions), labels, color=TEXT)
    ax.set_ylim(0, 110)
    ax.set_ylabel("% das perguntas", color=MUTED)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(colors=MUTED, length=0)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.set_title(title, color=TEXT, loc="left", fontsize=11)
    ax.legend(frameon=False, labelcolor=TEXT, loc="upper right")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


def section(name: str, records: list[dict], metrics: dict) -> str:
    models = records[0]["models"]
    wo, wj, conf = metrics["without_judge"], metrics["with_judge"], metrics["judge_confusion"]
    lines = [
        f"## {name}",
        "",
        f"Agente: `{models['agent']}` · Guardrail: `{models['guardrail']}` · Auditor: `{models['judge']}` · "
        f"{metrics['n']} perguntas",
        "",
        f"**Execution accuracy (EX) geral: {pct(metrics['ex'])}**",
        "",
        "| Cenário | Respondidas | Acurácia das respondidas | Respostas certas mostradas |",
        "|---|---|---|---|",
        f"| Sem auditor | {pct(wo['coverage'])} | {pct(wo['accuracy_answered'])} | {pct(wo['correct_shown'])} |",
        f"| Com auditor | {pct(wj['coverage'])} | {pct(wj['accuracy_answered'])} | {pct(wj['correct_shown'])} |",
        "",
        "Auditor como classificador (positivo = barrou a resposta):",
        "",
        "| | Resposta errada (EX) | Resposta certa (EX) |",
        "|---|---|---|",
        f"| Barrou | {conf['caught_wrong']} (acerto do auditor) | {conf['blocked_right']} (barrou à toa) |",
        f"| Deixou passar | {conf['passed_wrong']} (erro que passou) | {conf['passed_right']} |",
        "",
        f"Precisão do auditor: {pct(conf['precision'])} · Recall: {pct(conf['recall'])}",
        "",
        "EX por dificuldade: "
        + " · ".join(
            f"{level} {pct(value['ex'])} (n={value['n']})" for level, value in metrics["by_difficulty"].items()
        ),
        "",
        "| Etapa | Chamadas de LLM (média) | Tokens (média) | Segundos (média) |",
        "|---|---|---|---|",
    ]
    for stage, usage in metrics["usage_by_stage"].items():
        lines.append(
            f"| {stage} | {usage['calls_mean']:.1f} | {usage['tokens_mean']:,.0f} | {usage['seconds_mean']:.1f} |"
        )
    lines += [
        "",
        f"Por pergunta: {metrics['tokens_mean']:,.0f} tokens em média · latência p50 "
        f"{metrics['seconds_p50']:.0f}s, p95 {metrics['seconds_p95']:.0f}s",
        "",
        "Status: " + " · ".join(f"{key} {value}" for key, value in sorted(metrics["status_counts"].items())),
        "",
        f"![Com e sem auditor]({name}.png)",
        "",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="+")
    args = parser.parse_args()

    parts = ["# Resultados", ""]
    for file in args.files:
        path = Path(file)
        records = load(path)
        metrics = compute(records)
        chart(metrics, f"{path.stem}: com e sem auditor ({metrics['n']} perguntas)", RESULTS_DIR / f"{path.stem}.png")
        parts.append(section(path.stem, records, metrics))

    report = RESULTS_DIR / "REPORT.md"
    report.write_text("\n".join(parts), encoding="utf-8")
    print(f"Relatório em {report.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
