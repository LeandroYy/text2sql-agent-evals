import sqlite3

import pytest

from text2sql_agent import db


@pytest.fixture
def sample_db(tmp_path, monkeypatch):
    folder = tmp_path / "shop"
    folder.mkdir()
    conn = sqlite3.connect(folder / "shop.sqlite")
    conn.execute("CREATE TABLE product (id INTEGER, name TEXT)")
    conn.executemany("INSERT INTO product VALUES (?, ?)", [(i, f"item {i}") for i in range(10)])
    conn.commit()
    conn.close()
    monkeypatch.setattr(db, "DATABASES_DIR", tmp_path)
    return "shop"


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM product",
        "  select name from product;  ",
        "WITH x AS (SELECT id FROM product) SELECT COUNT(*) FROM x",
        "SELECT REPLACE(name, 'item', 'x') FROM product",
    ],
)
def test_accepts_read_only_queries(sql):
    assert db.is_read_only_sql(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "",
        "DELETE FROM product",
        "DROP TABLE product",
        "SELECT 1; DROP TABLE product",
        "WITH x AS (SELECT 1) DELETE FROM product",
        "PRAGMA table_info(product)",
        "ATTACH DATABASE 'other.db' AS other",
    ],
)
def test_rejects_writes_and_multiple_statements(sql):
    assert not db.is_read_only_sql(sql)


def test_database_is_opened_read_only(sample_db):
    # Mesmo sem passar pela checagem de texto, o SQLite recusa a escrita.
    with pytest.raises(sqlite3.OperationalError):
        db.run_sql(sample_db, "DELETE FROM product")


def test_limits_rows(sample_db):
    columns, rows, truncated = db.run_sql(sample_db, "SELECT id FROM product", max_rows=3)
    assert columns == ["id"]
    assert len(rows) == 3
    assert truncated


def test_long_query_is_interrupted(sample_db):
    endless = "WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM n) SELECT COUNT(*) FROM n"
    with pytest.raises(sqlite3.OperationalError):
        db.run_sql(sample_db, endless, timeout=0.5)


def test_unknown_database(sample_db):
    with pytest.raises(FileNotFoundError):
        db.run_sql("does_not_exist", "SELECT 1")
