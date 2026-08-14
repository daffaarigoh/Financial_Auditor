from agents.ocr_agent import OCRAgent
from agents.vision_agent import VisionAgent
from agents.auditor_agent import AuditorAgent
from agents.reporter_agent import ReporterAgent


class AuditWorkflowPipeline:
    """
    Orchestrator pipeline: OCR → Vision → Auditor → Reporter.
    Each step is isolated with error handling so one failing agent
    does not crash the entire pipeline.
    """

    def __init__(self):
        self.ocr_agent = OCRAgent()
        self.vision_agent = VisionAgent()
        self.auditor_agent = AuditorAgent()
        self.reporter_agent = ReporterAgent()

    def run_pipeline(self, file_name: str, file_path: str, progress_callback=None) -> dict:
        """
        Executes the audit pipeline step-by-step with live progress callbacks.
        Returns all intermediate and final results, plus any pipeline errors.
        """
        pipeline_errors = []

        def _step(step_num: int, total: int, msg: str):
            if progress_callback:
                # Map step to smooth progress: 0 → 20 → 50 → 80 → 100
                progress_map = {1: 20, 2: 50, 3: 80, 4: 100}
                progress_callback(progress_map.get(step_num, step_num * 20), msg)

        # --- Step 1: OCR Extraction ---
        _step(1, 4, "🔍 Sub-Agent 1 (ocr-lighton): Mengekstrak teks & angka dari dokumen...")
        try:
            ocr_result = self.ocr_agent.process(file_path)
        except Exception as e:
            pipeline_errors.append(f"OCR Agent error: {e}")
            ocr_result = {
                "model_used": "ocr-lighton", "is_simulated": True,
                "vendor_name": None, "invoice_number": None, "invoice_date": None,
                "line_items": [], "subtotal": 0.0, "tax_amount": 0.0,
                "total_amount": 0.0, "raw_notes": f"Agent failed: {e}"
            }

        # --- Step 2: Visual Inspection ---
        _step(2, 4, "👁️ Sub-Agent 2 (qwen-35b-vision): Menganalisis visual, stempel, & tanda tangan...")
        try:
            vision_result = self.vision_agent.inspect(file_path)
        except Exception as e:
            pipeline_errors.append(f"Vision Agent error: {e}")
            vision_result = {
                "model_used": "qwen-35b-vision", "is_simulated": True,
                "has_company_stamp": None, "stamp_quality": "NOT_INSPECTED",
                "has_signature": None, "signature_status": "NOT_INSPECTED",
                "logo_detected": None, "layout_integrity": "NOT_INSPECTED",
                "visual_notes": f"Agent failed: {e}"
            }

        # --- Step 3: Financial Audit ---
        _step(3, 4, "⚖️ Sub-Agent 3 (qwen-35b): Memeriksa kalkulasi keuangan & mendeteksi anomali...")
        try:
            audit_result = self.auditor_agent.audit(ocr_result, vision_result)
        except Exception as e:
            pipeline_errors.append(f"Auditor Agent error: {e}")
            audit_result = {
                "model_used": "qwen-35b", "status": "ANOMALY_DETECTED",
                "math_check_passed": False, "expected_total": 0.0, "actual_total": 0.0,
                "anomalies": [f"Audit agent failed: {e}"],
                "risk_level": "HIGH", "risk_reasoning": f"Pipeline error: {e}",
                "tax_rate_percent": None, "tax_rate_valid": False,
                "audit_summary": f"Audit failed due to error: {e}"
            }

        # --- Step 4: Executive Report & DB Save ---
        _step(4, 4, "📝 Sub-Agent 4 (nemotron-35): Menyusun laporan akhir & menyimpan ke database...")
        try:
            final_result = self.reporter_agent.summarize_and_execute(
                file_name=file_name,
                file_path=file_path,
                ocr_data=ocr_result,
                vision_data=vision_result,
                audit_data=audit_result
            )
        except Exception as e:
            pipeline_errors.append(f"Reporter Agent error: {e}")
            final_result = {
                "model_used": "nemotron-35",
                "executive_report": f"⚠️ Laporan tidak dapat dibuat karena error: {e}",
                "audit_record": {},
                "mcp_db_result": {"success": False, "message": f"Pipeline error: {e}"}
            }

        return {
            "ocr_result": ocr_result,
            "vision_result": vision_result,
            "audit_result": audit_result,
            "final_result": final_result,
            "pipeline_errors": pipeline_errors
        }
