import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Config:
    PROJECT_ROOT = Path(__file__).parent.parent

    # LLM
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.0"))
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "4096"))
    VLM_TIMEOUT_SECONDS: int = int(os.getenv("VLM_TIMEOUT_SECONDS", "60"))

    # Embedding
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
    EMBEDDING_DEVICE: str = os.getenv("EMBEDDING_DEVICE", "cpu")

    # OCR
    TESSERACT_PATH: str = os.getenv("TESSERACT_PATH", "")
    OCR_FALLBACK_ENABLED: bool = os.getenv("OCR_FALLBACK_ENABLED", "true").lower() == "true"

    # Vector DB
    WEAVIATE_URL: str = os.getenv("WEAVIATE_URL", "http://localhost:8081")

    # File limits
    MAX_FILE_SIZE_BYTES: int = int(os.getenv("MAX_FILE_SIZE_MB", "100")) * 1024 * 1024
    SUPPORTED_EXTENSIONS: set = {
        ".pdf", ".docx", ".xlsx", ".png", ".jpg", ".jpeg", ".tiff", ".tif"
    }

    # Extraction
    EXTRACTION_CONFIDENCE_THRESHOLD: float = float(os.getenv("EXTRACTION_CONFIDENCE_THRESHOLD", "0.5"))
    ENTITY_FUZZY_MATCH_THRESHOLD: float = float(os.getenv("ENTITY_FUZZY_MATCH_THRESHOLD", "0.80"))

    # Pipeline
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    PARALLEL_WORKERS: int = int(os.getenv("PARALLEL_WORKERS", "4"))


config = Config()