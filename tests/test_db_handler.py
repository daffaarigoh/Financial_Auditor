from mcp_tools.db_handler import (
    init_db,
    insert_audit_record,
    get_all_records,
    get_record_count,
    clear_all_records,
)


def test_init_db_creates_table(temp_db):
    assert temp_db.exists()


def test_insert_and_get_records():
    record = {
        "file_name": "invoice_001.pdf",
        "file_path": "/uploads/invoice_001.pdf",
        "vendor_name": "PT Jaya Abadi",
        "invoice_number": "INV-001",
        "invoice_date": "2026-08-01",
        "subtotal": 100000.0,
        "tax_amount": 11000.0,
        "total_amount": 111000.0,
        "status": "VALID",
        "has_stamp": True,
        "has_signature": True,
        "math_check_passed": True,
        "anomalies": [],
        "summary": "Dokumen valid dan sesuai.",
    }
    
    row_id = insert_audit_record(record)
    assert row_id is not None
    assert row_id > 0

    records = get_all_records()
    assert len(records) == 1
    saved = records[0]
    assert saved["file_name"] == "invoice_001.pdf"
    assert saved["vendor_name"] == "PT Jaya Abadi"
    assert saved["status"] == "VALID"
    assert isinstance(saved["anomalies"], list)
    assert len(saved["anomalies"]) == 0


def test_record_counts():
    # Insert 1 VALID and 1 ANOMALY
    insert_audit_record({
        "file_name": "valid.pdf",
        "status": "VALID",
        "total_amount": 1000.0,
    })
    insert_audit_record({
        "file_name": "anomaly.pdf",
        "status": "ANOMALY_DETECTED",
        "total_amount": 2000.0,
        "anomalies": ["Total mismatch"],
    })

    counts = get_record_count()
    assert counts["total"] == 2
    assert counts["valid"] == 1
    assert counts["anomaly"] == 1


def test_clear_all_records():
    insert_audit_record({"file_name": "test.pdf", "status": "VALID"})
    assert get_record_count()["total"] == 1

    clear_all_records()
    assert get_record_count()["total"] == 0
    assert len(get_all_records()) == 0
