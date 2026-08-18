import os
import tempfile
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

# Use temp database for testing
@pytest.fixture(autouse=True)
def temp_db(monkeypatch, tmp_path):
    test_db = tmp_path / "test_audit_database.db"
    monkeypatch.setattr("config.settings.DB_PATH", test_db)
    monkeypatch.setattr("mcp_tools.db_handler.DB_PATH", test_db)
    
    from mcp_tools.db_handler import init_db
    init_db()
    yield test_db


@pytest.fixture
def client():
    from server import app
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_ocr_valid():
    return {
        "vendor_name": "PT Sumber Rejeki Abadi",
        "invoice_number": "INV/2026/08/001",
        "invoice_date": "2026-08-15",
        "subtotal": 1000000.0,
        "tax_amount": 110000.0,
        "total_amount": 1110000.0,
        "line_items": [
            {"description": "Konsultasi IT", "quantity": 1, "unit_price": 1000000.0, "total": 1000000.0}
        ]
    }


@pytest.fixture
def sample_ocr_mismatch():
    return {
        "vendor_name": "Toko Fiktif",
        "invoice_number": "INV/ERR/999",
        "invoice_date": "2026-08-15",
        "subtotal": 1000000.0,
        "tax_amount": 110000.0,
        "total_amount": 1500000.0,  # Intentional discrepancy (expected 1,110,000)
        "line_items": [
            {"description": "Barang A", "quantity": 1, "unit_price": 500000.0, "total": 500000.0}
        ]
    }


@pytest.fixture
def sample_vision_valid():
    return {
        "has_company_stamp": True,
        "has_signature": True,
        "layout_integrity": "ORIGINAL_STRUCTURE",
        "visual_notes": "Stempel dan tanda tangan lengkap.",
        "is_simulated": False
    }


@pytest.fixture
def sample_vision_missing_stamp():
    return {
        "has_company_stamp": False,
        "has_signature": False,
        "layout_integrity": "SUSPICIOUS_ALIGNED",
        "visual_notes": "Tidak ditemukan stempel dan tanda tangan.",
        "is_simulated": False
    }
