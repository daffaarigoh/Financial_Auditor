import os
import base64
from pathlib import Path
from config.settings import get_llm_client, MODELS
from config.json_parser import parse_json_response

_VISION_SYSTEM_PROMPT = """You are an expert document forensics agent specializing in visual inspection of financial documents.
Analyze the provided document image and return a JSON object with exactly this schema:
{
  "has_company_stamp": boolean,
  "stamp_quality": "CLEAR_AND_LEGIBLE" | "FAINT" | "PARTIAL" | "NOT_FOUND",
  "has_signature": boolean,
  "signature_status": "VERIFIED" | "UNCLEAR" | "NOT_FOUND",
  "logo_detected": boolean,
  "layout_integrity": "STANDARD_INVOICE_FORMAT" | "UNUSUAL_LAYOUT" | "INCOMPLETE" | "UNRECOGNIZED",
  "visual_notes": string
}
Be strict: only mark has_company_stamp=true if a visible official stamp/seal is clearly present.
Only mark has_signature=true if a handwritten or digital signature is clearly visible.
Return valid JSON only."""

_SIMULATED_RESULT = {
    "has_company_stamp": None,
    "stamp_quality": "NOT_INSPECTED",
    "has_signature": None,
    "signature_status": "NOT_INSPECTED",
    "logo_detected": None,
    "layout_integrity": "NOT_INSPECTED",
    "visual_notes": "Visual inspection not available for this file type (not an image)."
}


class VisionAgent:
    """
    Sub-Agent 2: Visual Inspection Specialist using 'qwen-35b-vision'.
    Sends document images to the vision LLM to detect stamps, signatures,
    logos, and layout integrity. Non-image files are flagged as non-inspectable.
    """

    def __init__(self, model_name: str = MODELS["vision"]):
        self.model_name = model_name
        self.client = get_llm_client()

    def inspect(self, file_path: str) -> dict:
        result = {"model_used": self.model_name, "is_simulated": False}

        if not file_path or not os.path.exists(file_path):
            result.update(_SIMULATED_RESULT)
            result["is_simulated"] = True
            result["visual_notes"] = "File not found — visual inspection skipped."
            return result

        file_ext = Path(file_path).suffix.lower()

        # --- Image files: send to vision LLM ---
        if file_ext in (".png", ".jpg", ".jpeg"):
            return self._inspect_image(file_path, result)

        # --- PDF: render first page as image ---
        if file_ext == ".pdf":
            return self._inspect_pdf(file_path, result)

        # --- Text/JSON files: cannot visually inspect ---
        result.update(_SIMULATED_RESULT)
        result["is_simulated"] = True
        result["visual_notes"] = f"Visual inspection not applicable for {file_ext} files."
        return result

    def _inspect_image(self, file_path: str, result: dict) -> dict:
        try:
            from PIL import Image
            import io
            img = Image.open(file_path)
            max_width = 640
            if img.width > max_width:
                ratio = max_width / img.width
                img = img.resize((max_width, int(img.height * ratio)), Image.LANCZOS)
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="JPEG", quality=85)
            image_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            mime = "image/jpeg"
        except Exception as e:
            result.update(_SIMULATED_RESULT)
            result["is_simulated"] = True
            result["visual_notes"] = f"Failed to read image: {e}"
            return result
        return self._call_vision_llm(image_b64, mime, result)

    def _inspect_pdf(self, file_path: str, result: dict) -> dict:
        try:
            import pymupdf as fitz
            import io
            from PIL import Image
            
            doc = fitz.open(file_path)
            page = doc[0]
            pix = page.get_pixmap(dpi=150)
            doc.close()
            buf = io.BytesIO(pix.tobytes(output="png"))
            
            img = Image.open(buf)
            max_width = 640
            if img.width > max_width:
                ratio = max_width / img.width
                img = img.resize((max_width, int(img.height * ratio)), Image.LANCZOS)
            out_buf = io.BytesIO()
            img.convert("RGB").save(out_buf, format="JPEG", quality=85)
            
            image_b64 = base64.b64encode(out_buf.getvalue()).decode("utf-8")
            return self._call_vision_llm(image_b64, "image/jpeg", result)
        except Exception as e:
            result.update(_SIMULATED_RESULT)
            result["is_simulated"] = True
            result["visual_notes"] = f"PDF rendering unavailable: {e}"
            return result

    def _call_vision_llm(self, image_b64: str, mime_type: str, result: dict) -> dict:
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": _VISION_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime_type};base64,{image_b64}"}
                            },
                            {"type": "text", "text": "Inspect this financial document for stamps, signatures, logo, and layout integrity as JSON."}
                        ]
                    }
                ],
                max_tokens=2500,
                timeout=180
            )
            content = response.choices[0].message.content
            parsed = parse_json_response(content)
            result.update(parsed)
        except Exception as e:
            result.update(_SIMULATED_RESULT)
            result["is_simulated"] = True
            result["visual_notes"] = f"Vision LLM call failed: {e}"
        return result
