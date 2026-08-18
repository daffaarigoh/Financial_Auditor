from unittest.mock import MagicMock
from agents.auditor_agent import AuditorAgent


def test_auditor_deterministic_math_pass(sample_ocr_valid, sample_vision_valid, monkeypatch):
    auditor = AuditorAgent(model_name="mock-auditor")
    # Mock LLM response for layer 2
    mock_llm_result = {
        "llm_anomalies": [],
        "risk_level": "LOW",
        "risk_reasoning": "Semua data konsisten.",
        "tax_rate_percent": 11.0,
        "tax_rate_valid": True
    }
    monkeypatch.setattr(auditor, "_deep_audit_with_llm", lambda ocr, vis: mock_llm_result)

    result = auditor.audit(sample_ocr_valid, sample_vision_valid)
    assert result["math_check_passed"] is True
    assert result["status"] == "VALID"
    assert result["risk_level"] == "LOW"
    assert len(result["anomalies"]) == 0


def test_auditor_math_mismatch(sample_ocr_mismatch, sample_vision_valid, monkeypatch):
    auditor = AuditorAgent(model_name="mock-auditor")
    mock_llm_result = {
        "llm_anomalies": [],
        "risk_level": "LOW",
        "risk_reasoning": "Math discrepancy detected.",
        "tax_rate_percent": 11.0,
        "tax_rate_valid": True
    }
    monkeypatch.setattr(auditor, "_deep_audit_with_llm", lambda ocr, vis: mock_llm_result)

    result = auditor.audit(sample_ocr_mismatch, sample_vision_valid)
    assert result["math_check_passed"] is False
    assert result["status"] == "ANOMALY_DETECTED"
    assert any("Total mismatch" in anom for anom in result["anomalies"])


def test_auditor_missing_stamp_and_signature(sample_ocr_valid, sample_vision_missing_stamp, monkeypatch):
    auditor = AuditorAgent(model_name="mock-auditor")
    mock_llm_result = {
        "llm_anomalies": ["Missing legal stamps."],
        "risk_level": "MEDIUM",
        "risk_reasoning": "No official stamp.",
        "tax_rate_percent": 11.0,
        "tax_rate_valid": True
    }
    monkeypatch.setattr(auditor, "_deep_audit_with_llm", lambda ocr, vis: mock_llm_result)

    result = auditor.audit(sample_ocr_valid, sample_vision_missing_stamp)
    assert result["status"] == "ANOMALY_DETECTED"
    assert any("stempel resmi" in anom for anom in result["anomalies"])
    assert any("tanda tangan" in anom for anom in result["anomalies"])
