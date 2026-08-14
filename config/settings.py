import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

# Load .env file from project root (if it exists)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Base Directory Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
REPORTS_DIR = DATA_DIR / "reports"
DB_PATH = DATA_DIR / "audit_database.db"

# Ensure required directories exist
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# AI Models Assignment
MODELS = {
    "ocr": "ocr-lighton",
    "vision": "qwen-35b-vision",
    "auditor": "qwen-35b",
    "reporter": "nemotron-35"
}

# API Configuration
LLM_API_BASE = os.getenv("LLM_API_BASE", "http://localhost:11434/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "dummy-key")


def get_llm_client() -> OpenAI:
    """Returns a configured OpenAI-compatible client using env credentials."""
    return OpenAI(
        base_url=LLM_API_BASE,
        api_key=LLM_API_KEY,
    )
