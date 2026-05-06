from enum import Enum
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class DocumentFormat(str, Enum):
    PDF_DIGITAL = "pdf_digital"
    PDF_SCANNED = "pdf_scanned"
    DOCX = "docx"
    XLSX = "xlsx"
    IMAGE = "image"


class DocumentClassification(str, Enum):
    FINANCIAL = "FINANCIAL"
    CERTIFICATE = "CERTIFICATE"
    TAX_DOC = "TAX_DOC"
    WORK_ORDER = "WORK_ORDER"
    PROFILE = "PROFILE"
    UNKNOWN = "UNKNOWN"


class DocumentMetadata(BaseModel):
    file_path: str
    file_name: str
    file_hash: str
    file_size_bytes: int
    format: DocumentFormat
    classification: DocumentClassification = DocumentClassification.UNKNOWN
    created_at: datetime = Field(default_factory=datetime.now)
    modified_at: Optional[datetime] = None
    page_count: Optional[int] = None
    ocr_text: Optional[str] = None


class Document(BaseModel):
    metadata: DocumentMetadata
    raw_text: str = ""
    pages: list[dict] = Field(default_factory=list)