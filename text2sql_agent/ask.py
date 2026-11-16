"""Faz uma pergunta pela linha de comando.

Uso: uv run python -m text2sql_agent.ask --db superhero "How many superheroes have blue eyes?"
"""

import argparse
import json

from text2sql_agent.pipeline import ask


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, help="nome do banco, ex.: superhero, formula_1")
    parser.add_argument("--hint", default="", help="dica opcional (a 'evidence' do BIRD)")
    parser.add_argument("question")
    args = parser.parse_args()

    state = ask(args.db, args.question, args.hint)
    print(state["final_answer"])
    print(f"\nstatus: {state['status']}")
    if state.get("sql"):
        print(f"sql: {state['sql']}")
    print("usage:", json.dumps(state.get("usage", {}), indent=2))


if __name__ == "__main__":
    main()
