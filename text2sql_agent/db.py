"""Acesso aos bancos SQLite, sempre em modo somente leitura e com tempo máximo por consulta."""

import sqlite3
import time

from text2sql_agent.config import DATABASES_DIR, QUERY_TIMEOUT_SECONDS

# Palavras que não podem aparecer numa consulta do agente. É uma segunda barreira:
# a primeira é abrir o banco em modo somente leitura, que já impede qualquer escrita.
FORBIDDEN_WORDS = {
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "create",
    "attach",
    "detach",
    "pragma",
    "vacuum",
    "reindex",
}


def database_path(db_id: str):
    path = DATABASES_DIR / db_id / f"{db_id}.sqlite"
    if not path.exists():
        raise FileNotFoundError(f"Banco não encontrado: {db_id}")
    return path


def connect(db_id: str) -> sqlite3.Connection:
    # "mode=ro" abre o arquivo só para leitura: um INSERT ou DROP falha no próprio SQLite.
    uri = database_path(db_id).as_uri() + "?mode=ro"
    return sqlite3.connect(uri, uri=True)


def is_read_only_sql(sql: str) -> bool:
    """Aceita só uma instrução, começando com SELECT ou WITH, sem palavras de escrita."""
    text = sql.strip().rstrip(";").strip()
    if not text or ";" in text:
        return False
    words = text.lower().replace("(", " ").replace(")", " ").replace(",", " ").split()
    if words[0] not in ("select", "with"):
        return False
    return not FORBIDDEN_WORDS.intersection(words)


def run_sql(db_id: str, sql: str, max_rows: int | None = None, timeout: float = QUERY_TIMEOUT_SECONDS):
    """Executa a consulta e devolve (colunas, linhas, cortou_linhas).

    Se a consulta passar do tempo, o SQLite interrompe e levanta sqlite3.OperationalError.
    """
    conn = connect(db_id)
    deadline = time.monotonic() + timeout
    # O SQLite chama essa função a cada N instruções internas; devolver 1 interrompe a consulta.
    conn.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10_000)
    try:
        cursor = conn.execute(sql)
        columns = [col[0] for col in cursor.description or []]
        if max_rows is None:
            rows = cursor.fetchall()
        else:
            rows = cursor.fetchmany(max_rows + 1)
    finally:
        conn.close()

    truncated = max_rows is not None and len(rows) > max_rows
    if truncated:
        rows = rows[:max_rows]
    return columns, rows, truncated
