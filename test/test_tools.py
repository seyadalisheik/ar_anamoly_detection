from datetime import date


def test_allowance_tools_return_expected_totals_and_details(monkeypatch, seeded_db):
    from src.tools import allownce_history

    monkeypatch.setattr(allownce_history, "DB_FILE", seeded_db)

    assert allownce_history.get_total_allowance_amount.func(1001) == 18.0
    assert allownce_history.calculate_allowance_amount.func(1001, 10.0, 180.0) == 18.0

    details = allownce_history.get_agreement_details.func(1001)
    assert details == {
        "agreement_start_date": "2026-01-01",
        "agreement_end_date": "2026-12-31",
        "agreement_type": "SALE",
        "allowance_percent": 10,
        "item_list": [111, 222],
    }

    item_summary = allownce_history.get_item_level_allowance_summary.func(1001)
    assert item_summary == [
        {"item": 111, "total_allowance_amt": 13.0, "date": "2026-02-01"},
        {"item": 222, "total_allowance_amt": 5.0, "date": "2026-02-02"},
    ]


def test_allowance_tools_handle_missing_agreement(monkeypatch, seeded_db):
    from src.tools import allownce_history

    monkeypatch.setattr(allownce_history, "DB_FILE", seeded_db)

    assert allownce_history.get_agreement_details.func(9999) == {}
    assert allownce_history.get_total_allowance_amount.func(9999) == 0.0
    assert allownce_history.get_item_level_allowance_summary.func(9999) == []


def test_sales_tools_aggregate_by_date_and_ignore_empty_items(monkeypatch, seeded_db):
    from src.tools import sales_history

    monkeypatch.setattr(sales_history, "DB_FILE", seeded_db)

    assert sales_history.get_total_sales_cost.func(
        [111, 222], date(2026, 1, 1), date(2026, 12, 31)
    ) == 180.0
    assert sales_history.get_total_sales_cost.func([], date(2026, 1, 1), date(2026, 12, 31)) == 0.0

    item_summary = sales_history.get_item_level_sales_summary.func(
        [111, 222], date(2026, 1, 1), date(2026, 12, 31), 10.0
    )
    assert item_summary == [
        {
            "item": 111,
            "sales_date": "2026-02-01",
            "total_sales_qty": 6,
            "total_sales_cost": 130.0,
            "allowance_amount": 13.0,
        },
        {
            "item": 222,
            "sales_date": "2026-02-02",
            "total_sales_qty": 5,
            "total_sales_cost": 50.0,
            "allowance_amount": 5.0,
        },
    ]
    assert sales_history.get_item_level_sales_summary.func(
        [], date(2026, 1, 1), date(2026, 12, 31), 10.0
    ) == []


def test_bill_tools_return_bill_and_sap_totals_by_date(monkeypatch, seeded_db):
    from src.tools import bill_history

    monkeypatch.setattr(bill_history, "DB_FILE", seeded_db)

    assert bill_history.get_bill_amount_by_date.func(1001) == [
        {"Bill_amount": 13.0, "Bill_date": "2026-02-05"},
        {"Bill_amount": 5.0, "Bill_date": "2026-02-06"},
    ]
    assert bill_history.get_sap_bill_amount_by_date.func(1001) == [
        {"SAP_Bill_amount": 13.0, "SAP_Bill_date": "2026-02-05"},
        {"SAP_Bill_amount": 4.5, "SAP_Bill_date": "2026-02-06"},
    ]
    assert bill_history.get_bill_amount_by_date.func(9999) == []
    assert bill_history.get_sap_bill_amount_by_date.func(9999) == []
