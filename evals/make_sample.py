"""Sorteia a amostra do eval: N perguntas, proporcional ao número de perguntas de cada banco.

A semente fixa faz qualquer pessoa sortear exatamente as mesmas perguntas.

Uso: uv run python -m evals.make_sample --size 100
"""

import argparse
import json
import random

from text2sql_agent.config import ROOT

QUESTIONS = ROOT / "data" / "mini_dev_sqlite.jsonl"
OUTPUT = ROOT / "evals" / "sample.jsonl"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    with open(QUESTIONS, encoding="utf-8") as file:
        questions = [json.loads(line) for line in file]

    by_db: dict[str, list[dict]] = {}
    for question in questions:
        by_db.setdefault(question["db_id"], []).append(question)

    rng = random.Random(args.seed)
    sample = []
    for db_id in sorted(by_db):
        group = by_db[db_id]
        count = round(len(group) * args.size / len(questions))
        sample += rng.sample(group, count)

    # O arredondamento por banco pode deixar a amostra com uma ou duas perguntas a menos ou a mais.
    if len(sample) < args.size:
        chosen = {question["question_id"] for question in sample}
        rest = [question for question in questions if question["question_id"] not in chosen]
        sample += rng.sample(rest, args.size - len(sample))
    sample = sorted(sample, key=lambda question: question["question_id"])[: args.size]

    with open(OUTPUT, "w", encoding="utf-8") as file:
        for question in sample:
            file.write(json.dumps(question, ensure_ascii=False) + "\n")
    print(f"{len(sample)} perguntas salvas em {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
