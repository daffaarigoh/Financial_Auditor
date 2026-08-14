import os
import re
import json
import base64
from pathlib import Path
from config.settings import get_llm_client, MODELS
from config.json_parser import parse_json_response

_OCR_SYSTEM_PROMPT = """You are an expert OCR and document parsing agent.
Extract structured financial data from the provided document image or text.
You MUST return a valid JSON object with exactly this schema (use null for missing fields):
{
  "vendor_name": string | null,
  "invoice_number": string | null,
  "invoice_date": string | null,
  "line_items": [
    {"description": string, "qty": number, "unit_price": number, "total": number}
  ],
  "subtotal": number,
  "tax_amount": number,
  "total_amount": number,
  "currency": string,
  "raw_notes": string
}
All monetary values must be plain numbers (no currency symbols, no commas). Return valid JSON."""

_EMPTY_RESULT = {
    "vendor_name": None,
    "invoice_number": None,
    "invoice_date": None,
    "line_items": [],
    "subtotal": 0.0,
    "tax_amount": 0.0,
    "total_amount": 0.0,
    "currency": "IDR",
    "raw_notes": ""
}


class OCRAgent:
    """
    Sub-Agent 1: OCR Extraction Specialist using 'ocr-lighton' and 'qwen-35b-vision'.
    - TXT/JSON files: parsed locally (fast, no API call needed).
    - PDF files: rendered to image via PyMuPDF then sent to vision model.
    - Image files (PNG/JPG): base64-encoded and sent as vision message to LLM.
    """

    def __init__(self, model_name: str = MODELS["ocr"]):
        self.model_name = model_name
        self.vision_model = MODELS["vision"]
        self.client = get_llm_client()

    def process(self, file_path: str) -> dict:
        result = dict(_EMPTY_RESULT)
        result["model_used"] = self.model_name
        result["is_simulated"] = False

        if not file_path or not os.path.exists(file_path):
            result["is_simulated"] = True
            result["raw_notes"] = "File not found — no extraction performed."
            return result

        file_ext = Path(file_path).suffix.lower()

        # --- Local parsing for structured text files ---
        if file_ext == ".json":
            return self._parse_json_file(file_path, result)

        if file_ext == ".txt":
            return self._parse_txt_file(file_path, result)

        # --- LLM-based extraction for images and PDF ---
        if file_ext in (".png", ".jpg", ".jpeg"):
            return self._extract_from_image(file_path, result)

        if file_ext == ".pdf":
            return self._extract_from_pdf(file_path, result)

        result["is_simulated"] = True
        result["raw_notes"] = f"Unsupported file type: {file_ext}"
        return result

    def _parse_json_file(self, file_path: str, result: dict) -> dict:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                parsed = json.load(f)
            result.update(parsed)
            result["raw_notes"] = "Parsed from structured JSON file."
        except Exception as e:
            result["is_simulated"] = True
            result["raw_notes"] = f"JSON parse error: {e}"
        return result

    def _parse_txt_file(self, file_path: str, result: dict) -> dict:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            result["raw_notes"] = content

            for line in content.splitlines():
                if ":" not in line:
                    continue
                key, val = line.split(":", 1)
                key = key.strip().upper()
                val = val.strip()

                if "VENDOR" in key:
                    result["vendor_name"] = val
                elif "INVOICE NO" in key or "NOMOR INVOICE" in key:
                    result["invoice_number"] = val
                elif "DATE" in key or "TANGGAL" in key:
                    result["invoice_date"] = val
                elif "SUBTOTAL" in key:
                    result["subtotal"] = float(re.sub(r"[^\d.]", "", val) or 0)
                elif any(k in key for k in ("PAJAK", "PPN", "TAX")):
                    result["tax_amount"] = float(re.sub(r"[^\d.]", "", val) or 0)
                elif "TOTAL" in key and "SUBTOTAL" not in key:
                    result["total_amount"] = float(re.sub(r"[^\d.]", "", val) or 0)
        except Exception as e:
            result["is_simulated"] = True
            result["raw_notes"] = f"TXT parse error: {e}"
        return result

    def _call_llm_with_text(self, text_content: str, result: dict) -> dict:
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": _OCR_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Extract invoice data from this document:\n\n{text_content}"}
                ],
                max_tokens=2500,
                timeout=120
            )
            content = response.choices[0].message.content
            parsed = parse_json_response(content)
            result.update(parsed)
        except Exception as e:
            result["is_simulated"] = True
            result["raw_notes"] = f"LLM call failed: {e}"
        return result

    def _call_llm_with_image(self, image_b64: str, mime_type: str, result: dict) -> dict:
        try:
            response = self.client.chat.completions.create(
                model=self.vision_model,
                messages=[
                    {"role": "system", "content": _OCR_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime_type};base64,{image_b64}"}
                            },
                            {"type": "text", "text": "Extract all invoice data from this document image as JSON."}
                        ]
                    }
                ],
                max_tokens=2500,
                timeout=180
            )
            content = response.choices[0].message.content
            parsed = parse_json_response(content)
            
            # Sanitize numeric fields
            for field in ("subtotal", "tax_amount", "total_amount"):
                v = parsed.get(field)
                if isinstance(v, str):
                    parsed[field] = float(re.sub(r"[^\d.]", "", v) or 0)
            for item in parsed.get("line_items", []):
                for f in ("qty", "quantity", "unit_price", "total", "total_price"):
                    v = item.get(f)
                    if isinstance(v, str):
                        item[f] = float(re.sub(r"[^\d.]", "", v) or 0)
                        
            result.update(parsed)
            result["model_used"] = f"{self.vision_model} (OCR via vision)"
        except Exception as e:
            result["is_simulated"] = True
            result["raw_notes"] = f"Vision OCR call failed: {e}"
        return result

    def _extract_from_image(self, file_path: str, result: dict) -> dict:
        ext = Path(file_path).suffix.lower().lstrip(".")
        mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
        try:
            from PIL import Image
            import io
            img = Image.open(file_path)
            max_width = 640
            if img.width > max_width:
                ratio = max_width / img.width
                new_size = (max_width, int(img.height * ratio))
                img = img.resize(new_size, Image.LANCZOS)
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="JPEG", quality=85)
            image_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            mime = "image/jpeg"
        except Exception as e:
            result["is_simulated"] = True
            result["raw_notes"] = f"Failed to read/resize image file: {e}"
            return result
        return self._call_llm_with_image(image_b64, mime, result)

    def _extract_from_pdf(self, file_path: str, result: dict) -> dict:
        try:
            import pymupdf as fitz
            import io
            doc = fitz.open(file_path)
            page = doc[0]
            pix = page.get_pixmap(dpi=150)
            doc.close()
            buf = io.BytesIO(pix.tobytes(output="png"))
            
            from PIL import Image
            img = Image.open(buf)
            max_width = 640
            if img.width > max_width:
                ratio = max_width / img.width
                img = img.resize((max_width, int(img.height * ratio)), Image.LANCZOS)
            out_buf = io.BytesIO()
            img.convert("RGB").save(out_buf, format="JPEG", quality=85)
            
            image_b64 = base64.b64encode(out_buf.getvalue()).decode("utf-8")
            return self._call_llm_with_image(image_b64, "image/jpeg", result)
        except Exception as e:
            pass

        # Fallback to text extraction if PDF has embedded text
        try:
            from pypdf import PdfReader
            reader = PdfReader(file_path)
            pages_text = "\n".join(
                page.extract_text() or "" for page in reader.pages
            )
            if pages_text.strip():
                return self._call_llm_with_text(pages_text, result)
        except Exception as e:
            pass

        result["is_simulated"] = True
        result["raw_notes"] = "PDF extraction failed."
        return result
