import os
import sqlite3
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("GROQ_API_KEY", "unit-test-groq-key")
os.environ.setdefault("CLAUDE_API_KEY", "unit-test-claude-key")
os.environ.setdefault("OPENAI_API_KEY", "unit-test-openai-key")
os.environ.setdefault("DEFAULT_LLM_PROVIDER", "groq")


@pytest.fixture()
def sqlite_db(tmp_path):
    db_file = tmp_path / "vendor_agreement.db"
    schema_file = PROJECT_ROOT / "mockup_db" / "vendor_agreement_schema.sql"

    conn = sqlite3.connect(db_file)
    try:
        conn.executescript(schema_file.read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()

    return db_file


@pytest.fixture()
def seeded_db(sqlite_db):
    conn = sqlite3.connect(sqlite_db)
    try:
        conn.execute(
            """
            INSERT INTO Vendor (
                Agreement_id, Vendor_id, Agreement_type, Vendor_Name,
                Agreement_start_date, Agreement_end_date, Agreement_status,
                agreement_division, Agreement_allowance_type,
                Agreement_allowance_percent, Bill_frequency,
                Store_alloc_frequency, Last_updated_timestamp,
                Last_change_userid
            ) VALUES (
                1001, 501, 'SALE', 'Acme Supplies', '2026-01-01',
                '2026-12-31', 1, 10, 'OI', 10.0, 'M', 'M',
                '2026-01-01 00:00:00', 'TEST'
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO Agreement_item (Agreement_id, Vendor_id, item_nbr, item_desc)
            VALUES (1001, 501, ?, ?)
            """,
            [(111, "Item 111"), (222, "Item 222")],
        )
        conn.executemany(
            """
            INSERT INTO Agreement_allowance_history (
                Agreement_id, Vendor_id, purchase_order_id, sales_date,
                item_nbr, store_nbr, process_date, seq_nbr, item_cost,
                Agreement_allowance_type, dept_nbr, quantity, canculated_amt,
                allowance_amount, bill_nbr, Bill_date, Store_Alloc_ind,
                Store_Alloc_date, Last_change_user_id, Last_change_timestamp
            ) VALUES (
                1001, 501, ?, ?, ?, 1, ?, ?, ?, 'OI', 10, ?, ?, ?,
                NULL, NULL, 'Y', ?, 'TEST', '2026-01-01 00:00:00'
            )
            """,
            [
                (9001, "2026-02-01", 111, "2026-02-01", 1, 25.0, 4, 100.0, 10.0, "2026-02-01"),
                (9002, "2026-02-01", 111, "2026-02-01", 2, 15.0, 2, 30.0, 3.0, "2026-02-01"),
                (9003, "2026-02-02", 222, "2026-02-02", 1, 10.0, 5, 50.0, 5.0, "2026-02-02"),
            ],
        )
        conn.executemany(
            """
            INSERT INTO Sales_item_store_history (
                sale_unique_id, item_nbr, item_vendor, item_department,
                store_nbr, sales_date, sequence_nbr, item_category,
                sales_qty, item_cost
            ) VALUES (?, ?, '501', '10', 1, ?, ?, NULL, ?, ?)
            """,
            [
                ("sale-1", 111, "2026-02-01", 1, 4, 25.0),
                ("sale-2", 111, "2026-02-01", 2, 2, 15.0),
                ("sale-3", 222, "2026-02-02", 1, 5, 10.0),
                ("outside-range", 111, "2027-01-01", 1, 1, 999.0),
            ],
        )
        conn.executemany(
            """
            INSERT INTO Agreement_bill_history (
                Agreement_id, Vendor_id, Bill_nbr, Bill_date, transacion_id,
                Bill_amount, Bill_credit_account, Bill_debit_account,
                sap_doc_nbr, posting_response_code, posting_timestamp,
                last_changed_user_id
            ) VALUES (1001, 501, ?, ?, ?, ?, 100, 200, ?, 0, ?, 'TEST')
            """,
            [
                (7001, "2026-02-05", "txn-1", 13.0, "sap-1", "2026-02-05 00:00:00"),
                (7002, "2026-02-06", "txn-2", 5.0, "sap-2", "2026-02-06 00:00:00"),
            ],
        )
        conn.executemany(
            """
            INSERT INTO SAP_Invoice_history (
                Agreement_id, SAP_Bill_nbr, SAP_Bill_document_nbr,
                SAP_Bill_date, Transaction_Date, sequence_nbr,
                SAP_Bill_amount, SAP_Bill_credit_amt, SAP_Bill_debit_amt,
                SAP_Bill_customer_account, SAP_Bill_company_amount,
                Transaction_Timestamp
            ) VALUES (1001, ?, ?, ?, ?, 1, ?, ?, ?, 100, 200, ?)
            """,
            [
                (7001, "sap-1", "2026-02-05", "2026-02-05", 13.0, 13.0, 13.0, "2026-02-05 00:00:00"),
                (7002, "sap-2", "2026-02-06", "2026-02-06", 4.5, 4.5, 4.5, "2026-02-06 00:00:00"),
            ],
        )
        conn.commit()
    finally:
        conn.close()

    return sqlite_db
