import logging
import sqlite3


def test_create_database_creates_expected_tables(tmp_path):
    from mockup_db.DB_schema import create_database

    db_file = tmp_path / "created.db"
    schema_file = tmp_path / "schema.sql"
    schema_file.write_text(
        """
        CREATE TABLE Vendor (Agreement_id INTEGER PRIMARY KEY);
        CREATE TABLE Agreement_item (Agreement_id INTEGER, item_nbr INTEGER);
        """,
        encoding="utf-8",
    )

    create_database(db_file=db_file, schema_file=schema_file)

    conn = sqlite3.connect(db_file)
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    finally:
        conn.close()

    assert tables == {"Vendor", "Agreement_item"}


def test_list_tables_logs_existing_tables(tmp_path, caplog):
    from mockup_db.DB_schema import create_database, list_tables

    db_file = tmp_path / "created.db"
    schema_file = tmp_path / "schema.sql"
    schema_file.write_text("CREATE TABLE Sample (id INTEGER);", encoding="utf-8")
    create_database(db_file=db_file, schema_file=schema_file)

    with caplog.at_level(logging.INFO):
        list_tables(db_file=db_file)

    assert "Tables in database:" in caplog.text
    assert "Sample" in caplog.text
