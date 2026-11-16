"""Ferramentas que o agente pode chamar. Cada pergunta ganha um conjunto preso a um banco."""

import csv
import sqlite3

from langchain_core.tools import tool

from text2sql_agent.config import DATABASES_DIR, MAX_ROWS_TO_LLM
from text2sql_agent.db import connect, is_read_only_sql, run_sql

MAX_CELL_CHARS = 100  # corta textos longos para não gastar tokens à toa


def table_names(db_id: str) -> list[str]:
    conn = connect(db_id)
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
    finally:
        conn.close()
    return [row[0] for row in rows]


def column_descriptions(db_id: str, table: str) -> list[str]:
    """Lê as descrições de coluna que o BIRD fornece em CSV (a "camada semântica").

    Faz o mesmo papel dos comentários de tabela e coluna num banco corporativo.
    """
    path = DATABASES_DIR / db_id / "database_description" / f"{table}.csv"
    if not path.exists():
        return []
    lines = []
    with open(path, encoding="utf-8-sig", errors="replace", newline="") as file:
        for row in csv.DictReader(file):
            name = (row.get("original_column_name") or "").strip()
            description = (row.get("column_description") or "").strip()
            values = (row.get("value_description") or "").strip()
            if not name:
                continue
            text = f"- {name}: {description}"
            if values:
                text += f" | values: {values}"
            lines.append(" ".join(text.split()))  # junta quebras de linha do CSV
    return lines


def format_rows(columns: list[str], rows: list[tuple]) -> str:
    def cell(value):
        text = str(value)
        return text if len(text) <= MAX_CELL_CHARS else text[:MAX_CELL_CHARS] + "..."

    lines = [" | ".join(columns)]
    lines += [" | ".join(cell(value) for value in row) for row in rows]
    return "\n".join(lines)


def describe_table(db_id: str, table: str) -> str:
    conn = connect(db_id)
    try:
        create_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
        ).fetchone()[0]
        # O nome já foi conferido contra a lista de tabelas; as aspas protegem nomes com espaço.
        quoted = '"' + table.replace('"', '""') + '"'
        cursor = conn.execute(f"SELECT * FROM {quoted} LIMIT 3")
        columns = [col[0] for col in cursor.description]
        sample = cursor.fetchall()
    finally:
        conn.close()

    parts = [create_sql]
    notes = column_descriptions(db_id, table)
    if notes:
        parts.append("Column notes:\n" + "\n".join(notes))
    parts.append("Sample rows:\n" + format_rows(columns, sample))
    return "\n\n".join(parts)


def make_tools(db_id: str, executed_queries: list[dict]):
    """Cria as ferramentas do agente para um banco.

    `executed_queries` recebe cada SQL rodado; o auditor e o relatório usam essa lista.
    """

    @tool
    def list_tables() -> str:
        """List the tables available in the database."""
        return "\n".join(table_names(db_id))

    @tool
    def get_schema(tables: list[str]) -> str:
        """Return the CREATE statement, column descriptions and 3 sample rows of each table."""
        known = set(table_names(db_id))
        parts = []
        for table in tables:
            if table not in known:
                parts.append(f"Table '{table}' does not exist. Use list_tables.")
            else:
                parts.append(describe_table(db_id, table))
        return "\n\n---\n\n".join(parts)

    @tool
    def run_query(sql: str) -> str:
        """Run one read-only SQLite query (SELECT or WITH) and return the rows."""
        if not is_read_only_sql(sql):
            result = "Error: only a single read-only SELECT/WITH query is allowed."
            executed_queries.append({"sql": sql, "ok": False, "result": result})
            return result
        try:
            columns, rows, truncated = run_sql(db_id, sql, max_rows=MAX_ROWS_TO_LLM)
        except sqlite3.Error as error:
            result = f"Error: {error}"
            executed_queries.append({"sql": sql, "ok": False, "result": result})
            return result

        result = format_rows(columns, rows)
        if not rows:
            result += "\n(no rows)"
        if truncated:
            result += f"\n(showing only the first {MAX_ROWS_TO_LLM} rows)"
        executed_queries.append({"sql": sql, "ok": True, "result": result})
        return result

    return [list_tables, get_schema, run_query]
