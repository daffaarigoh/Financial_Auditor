import pandas as pd
from datetime import datetime
from config.settings import REPORTS_DIR
from mcp_tools.db_handler import insert_audit_record, get_all_records


def save_audit_record_tool(audit_result: dict) -> dict:
    """
    MCP Tool: Save audited document result to SQLite Database.
    """
    try:
        record_id = insert_audit_record(audit_result)
        return {
            "success": True,
            "record_id": record_id,
            "message": f"Audit record #{record_id} successfully saved to SQLite Database."
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to save audit record to database."
        }


def export_audit_excel_tool() -> dict:
    """
    MCP Tool: Export all audit history to Excel report file (.xlsx).
    Called on-demand from the UI, not automatically after each audit.
    """
    try:
        records = get_all_records()
        if not records:
            return {
                "success": False,
                "message": "No audit records found to export."
            }

        df = pd.DataFrame(records)

        # Select and rename columns for the Excel sheet
        export_columns = {
            "id": "ID",
            "file_name": "Nama File",
            "vendor_name": "Nama Vendor",
            "invoice_number": "Nomor Invoice",
            "invoice_date": "Tanggal Invoice",
            "subtotal": "Subtotal (Rp)",
            "tax_amount": "Pajak (Rp)",
            "total_amount": "Total (Rp)",
            "status": "Status Audit",
            "has_stamp": "Ada Stempel",
            "has_signature": "Ada Tanda Tangan",
            "math_check_passed": "Rumus Matematika Valid",
            "summary": "Ringkasan Audit",
            "created_at": "Waktu Audit"
        }
        available = [c for c in export_columns if c in df.columns]
        df_export = df[available].rename(columns={k: export_columns[k] for k in available})

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_filename = f"Audit_Report_{timestamp}.xlsx"
        report_path = REPORTS_DIR / report_filename

        df_export.to_excel(report_path, index=False, engine="openpyxl")

        return {
            "success": True,
            "file_name": report_filename,
            "file_path": str(report_path),
            "total_records": len(records),
            "message": f"Report berhasil diekspor: {report_filename} ({len(records)} record)"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to export Excel report."
        }
