import json
from config.settings import get_llm_client, MODELS
from mcp_tools.server import save_audit_record_tool

_REPORTER_SYSTEM_PROMPT = """Anda adalah agen pelaporan keuangan profesional.
Tulis laporan audit dokumen keuangan dalam Bahasa Indonesia yang formal dan mudah dipahami.
Laporan harus mencakup:
1. Ringkasan eksekutif status dokumen (VALID atau ANOMALI)
2. Detail data yang diekstrak (vendor, nomor invoice, tanggal, nominal)
3. Hasil pemeriksaan visual (stempel, tanda tangan)
4. Hasil audit matematis dan analisis risiko
5. Daftar anomali yang ditemukan (jika ada)
6. Rekomendasi tindakan yang harus diambil

Gunakan format Markdown dengan emoji yang relevan untuk keterbacaan.
Tulis langsung laporan tanpa penjelasan tambahan."""


class ReporterAgent:
    """
    Sub-Agent 4: Reporter & MCP Tool Execution Specialist using 'nemotron-35'.
    Uses LLM to synthesize all agent findings into a professional executive report
    in Bahasa Indonesia, then triggers MCP tool to persist the record to the database.
    """

    def __init__(self, model_name: str = MODELS["reporter"]):
        self.model_name = model_name
        self.client = get_llm_client()

    def summarize_and_execute(
        self,
        file_name: str,
        file_path: str,
        ocr_data: dict,
        vision_data: dict,
        audit_data: dict
    ) -> dict:
        """
        Synthesizes all agent outputs into an executive report and persists to DB.
        Excel export is now on-demand from the UI — NOT called here automatically.
        """
        audit_record = {
            "file_name": file_name,
            "file_path": file_path,
            "vendor_name": ocr_data.get("vendor_name") or "-",
            "invoice_number": ocr_data.get("invoice_number") or "-",
            "invoice_date": ocr_data.get("invoice_date") or "-",
            "subtotal": ocr_data.get("subtotal") or 0.0,
            "tax_amount": ocr_data.get("tax_amount") or 0.0,
            "total_amount": ocr_data.get("total_amount") or 0.0,
            "status": audit_data.get("status", "ANOMALY_DETECTED"),
            "has_stamp": vision_data.get("has_company_stamp"),
            "has_signature": vision_data.get("has_signature"),
            "math_check_passed": audit_data.get("math_check_passed", False),
            "anomalies": audit_data.get("anomalies", []),
            "summary": audit_data.get("audit_summary", "")
        }

        # Generate executive report via LLM
        executive_report = self._generate_report_with_llm(
            audit_record, ocr_data, vision_data, audit_data
        )

        # MCP Tool: Save record to SQLite database
        mcp_db_result = save_audit_record_tool(audit_record)

        return {
            "model_used": self.model_name,
            "executive_report": executive_report,
            "audit_record": audit_record,
            "mcp_db_result": mcp_db_result,
            # mcp_excel_result removed — Excel export is now on-demand from the UI
        }

    def _generate_report_with_llm(
        self,
        audit_record: dict,
        ocr_data: dict,
        vision_data: dict,
        audit_data: dict
    ) -> str:
        """Calls nemotron-35 to generate a comprehensive Bahasa Indonesia audit report."""
        context = {
            "file_name": audit_record["file_name"],
            "status": audit_record["status"],
            "risk_level": audit_data.get("risk_level", "LOW"),
            "risk_reasoning": audit_data.get("risk_reasoning", ""),
            "vendor_name": audit_record["vendor_name"],
            "invoice_number": audit_record["invoice_number"],
            "invoice_date": audit_record["invoice_date"],
            "subtotal_rp": audit_record["subtotal"],
            "tax_rp": audit_record["tax_amount"],
            "total_rp": audit_record["total_amount"],
            "tax_rate_percent": audit_data.get("tax_rate_percent"),
            "line_items": ocr_data.get("line_items", []),
            "has_stamp": vision_data.get("has_company_stamp"),
            "stamp_quality": vision_data.get("stamp_quality"),
            "has_signature": vision_data.get("has_signature"),
            "signature_status": vision_data.get("signature_status"),
            "layout_integrity": vision_data.get("layout_integrity"),
            "visual_notes": vision_data.get("visual_notes", ""),
            "math_check_passed": audit_record["math_check_passed"],
            "anomalies": audit_record["anomalies"],
            "ocr_simulated": ocr_data.get("is_simulated", False),
            "vision_simulated": vision_data.get("is_simulated", False)
        }

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": _REPORTER_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f"Buat laporan audit untuk data berikut:\n\n{json.dumps(context, indent=2, ensure_ascii=False)}"
                    }
                ],
                max_tokens=2500,
                timeout=180
            )
            return response.choices[0].message.content
        except Exception as e:
            # Fallback to template report if LLM unavailable
            return self._fallback_report(audit_record, audit_data, vision_data, str(e))

    def _fallback_report(
        self,
        audit_record: dict,
        audit_data: dict,
        vision_data: dict,
        error_msg: str
    ) -> str:
        """Template report used when nemotron-35 API is unavailable."""
        status_icon = "✅" if audit_record["status"] == "VALID" else "⚠️"
        status_label = "LULUS AUDIT (VALID)" if audit_record["status"] == "VALID" else "ANOMALI DITEMUKAN"

        anomaly_lines = "\n".join(f"- {a}" for a in audit_record["anomalies"]) or "- Tidak ditemukan anomali."
        stamp_txt = "Ada" if audit_record.get("has_stamp") else ("Tidak Ada" if audit_record.get("has_stamp") is False else "Tidak Diperiksa")
        sig_txt = "Ada" if audit_record.get("has_signature") else ("Tidak Ada" if audit_record.get("has_signature") is False else "Tidak Diperiksa")

        return f"""### 📊 LAPORAN HASIL AUDIT DOKUMEN
> ⚠️ *Laporan ini digenerate dalam mode fallback karena LLM Reporter tidak tersedia: {error_msg}*

**Status Dokumen**: {status_icon} **{status_label}**
**Tingkat Risiko**: {audit_data.get("risk_level", "LOW")}

---

**Detail Dokumen**:
- **Nama File**: `{audit_record["file_name"]}`
- **Vendor**: {audit_record["vendor_name"]}
- **Nomor Invoice**: {audit_record["invoice_number"]}
- **Tanggal**: {audit_record["invoice_date"]}
- **Subtotal**: Rp {audit_record["subtotal"]:,.2f}
- **PPN**: Rp {audit_record["tax_amount"]:,.2f}
- **Total**: Rp {audit_record["total_amount"]:,.2f}

**Hasil Inspeksi Visual**:
- Stempel Perusahaan: {stamp_txt}
- Tanda Tangan: {sig_txt}

**Audit Matematika**: {"✅ Sesuai" if audit_record["math_check_passed"] else "❌ Tidak Sesuai"}

**Catatan Anomali**:
{anomaly_lines}
"""
