import json
from config.settings import get_llm_client, MODELS
from config.json_parser import parse_json_response

_AUDITOR_SYSTEM_PROMPT = """You are an expert financial auditor AI. You will receive structured invoice data and visual inspection results.
Your task is to perform a deep anomaly analysis beyond simple math checks.
Analyze for:
- Suspicious vendor names or invoice numbers (e.g. sequential fraud, duplicate patterns)
- Unrealistic dates (future-dated, weekend-dated invoices for B2B, etc.)
- Unrealistic tax rates (should typically be 10-12% for Indonesian PPN)
- Unusual line item prices compared to descriptions
- Any other red flags that suggest document manipulation or fraud

Return a valid JSON object with this exact schema:
{
  "llm_anomalies": [string],
  "risk_level": "LOW" | "MEDIUM" | "HIGH",
  "risk_reasoning": string,
  "tax_rate_percent": number | null,
  "tax_rate_valid": boolean
}
Return ONLY valid JSON."""


class AuditorAgent:
    """
    Sub-Agent 3: Financial & Math Auditor using 'qwen-35b'.
    Layer 1 (Python): Deterministic math cross-checks — fast and reliable.
    Layer 2 (LLM): Deep qualitative anomaly detection — fraud patterns, date logic, tax rates.
    """

    def __init__(self, model_name: str = MODELS["auditor"]):
        self.model_name = model_name
        self.client = get_llm_client()

    def audit(self, ocr_data: dict, vision_data: dict) -> dict:
        anomalies = []

        subtotal = ocr_data.get("subtotal") or 0.0
        tax = ocr_data.get("tax_amount") or 0.0
        total = ocr_data.get("total_amount") or 0.0

        # --- Layer 1: Deterministic Math Checks ---
        expected_total = subtotal + tax
        math_check_passed = abs(total - expected_total) < 0.01
        if not math_check_passed:
            anomalies.append(
                f"DISCREPANCY: Total mismatch — dokumen menyatakan Rp {total:,.2f}, "
                f"tapi Subtotal ({subtotal:,.2f}) + PPN ({tax:,.2f}) = Rp {expected_total:,.2f}."
            )

        # Line items sum vs subtotal
        line_items = ocr_data.get("line_items") or []
        line_items_sum = sum(item.get("total", item.get("total_price", 0.0)) for item in line_items)
        if line_items_sum > 0 and abs(line_items_sum - subtotal) > 0.01:
            anomalies.append(
                f"DISCREPANCY: Jumlah line items (Rp {line_items_sum:,.2f}) "
                f"tidak sama dengan Subtotal (Rp {subtotal:,.2f})."
            )

        # Visual requirements from vision agent
        if not vision_data.get("is_simulated"):
            if vision_data.get("has_company_stamp") is False:
                anomalies.append("WARNING: Tidak ditemukan stempel resmi perusahaan pada dokumen.")
            if vision_data.get("has_signature") is False:
                anomalies.append("WARNING: Tidak ditemukan tanda tangan yang sah pada dokumen.")

        # --- Layer 2: LLM Deep Analysis ---
        llm_result = self._deep_audit_with_llm(ocr_data, vision_data)
        llm_anomalies = llm_result.get("llm_anomalies", [])
        anomalies.extend(llm_anomalies)

        risk_level = llm_result.get("risk_level", "LOW")
        if not math_check_passed and risk_level == "LOW":
            risk_level = "MEDIUM"

        status = "VALID" if (math_check_passed and len(anomalies) == 0) else "ANOMALY_DETECTED"

        return {
            "model_used": self.model_name,
            "status": status,
            "math_check_passed": math_check_passed,
            "expected_total": expected_total,
            "actual_total": total,
            "anomalies": anomalies,
            "risk_level": risk_level,
            "risk_reasoning": llm_result.get("risk_reasoning", ""),
            "tax_rate_percent": llm_result.get("tax_rate_percent"),
            "tax_rate_valid": llm_result.get("tax_rate_valid", True),
            "audit_summary": (
                f"Status: {status}. Risk: {risk_level}. "
                f"Total anomali: {len(anomalies)}. "
                + ("Semua kalkulasi valid." if math_check_passed else "Ditemukan ketidaksesuaian kalkulasi.")
            )
        }

    def _deep_audit_with_llm(self, ocr_data: dict, vision_data: dict) -> dict:
        context = {
            "vendor_name": ocr_data.get("vendor_name"),
            "invoice_number": ocr_data.get("invoice_number"),
            "invoice_date": ocr_data.get("invoice_date"),
            "subtotal": ocr_data.get("subtotal"),
            "tax_amount": ocr_data.get("tax_amount"),
            "total_amount": ocr_data.get("total_amount"),
            "line_items": ocr_data.get("line_items", []),
            "has_stamp": vision_data.get("has_company_stamp"),
            "has_signature": vision_data.get("has_signature"),
            "layout_integrity": vision_data.get("layout_integrity"),
            "visual_notes": vision_data.get("visual_notes", "")
        }

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": _AUDITOR_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f"Audit this invoice data for anomalies and fraud patterns:\n\n{json.dumps(context, indent=2, ensure_ascii=False)}"
                    }
                ],
                max_tokens=2500,
                timeout=120
            )
            content = response.choices[0].message.content
            return parse_json_response(content)
        except Exception as e:
            return {
                "llm_anomalies": [],
                "risk_level": "LOW",
                "risk_reasoning": f"LLM deep audit unavailable: {e}",
                "tax_rate_percent": None,
                "tax_rate_valid": True
            }
