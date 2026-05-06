import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.models.document import DocumentMetadata, DocumentFormat, DocumentClassification


class FileCrawler:
    _SUPPORTED_EXTENSIONS: set = {
        ".pdf", ".docx", ".xlsx",
        ".png", ".jpg", ".jpeg", ".tiff", ".tif"
    }
    _MAX_FILE_SIZE = 100 * 1024 * 1024

    def __init__(self, supported_extensions: Optional[set[str]] = None, max_file_size: int = 100):
        self.supported_extensions = supported_extensions or self._SUPPORTED_EXTENSIONS
        self.max_file_size = max_file_size * 1024 * 1024

    def crawl(self, directory: str | Path) -> list[DocumentMetadata]:
        directory = Path(directory).resolve()
        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")
        if not directory.is_dir():
            raise NotADirectoryError(f"Not a directory: {directory}")

        documents = []
        for root, _, files in os.walk(directory):
            for filename in sorted(files):
                file_path = Path(root) / filename
                if file_path.suffix.lower() not in self.supported_extensions:
                    continue

                file_stat = file_path.stat()
                if file_stat.st_size > self.max_file_size:
                    continue

                try:
                    metadata = self._build_metadata(file_path)
                    documents.append(metadata)
                except Exception:
                    continue

        return documents

    def _build_metadata(self, file_path: Path) -> DocumentMetadata:
        file_stat = file_path.stat()
        file_hash = self._compute_sha256(file_path)

        return DocumentMetadata(
            file_path=str(file_path.resolve()),
            file_name=file_path.name,
            file_hash=file_hash,
            file_size_bytes=file_stat.st_size,
            format=self._detect_format(file_path),
            modified_at=datetime.fromtimestamp(file_stat.st_mtime),
        )

    def _detect_format(self, file_path: Path) -> DocumentFormat:
        ext = file_path.suffix.lower()
        if ext == ".pdf":
            return self._detect_pdf_type(file_path)
        if ext == ".docx":
            return DocumentFormat.DOCX
        if ext == ".xlsx":
            return DocumentFormat.XLSX
        return DocumentFormat.IMAGE

    def _detect_pdf_type(self, file_path: Path) -> DocumentFormat:
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                text = ""
                for page in pdf.pages[:3]:
                    t = page.extract_text()
                    if t:
                        text += t
                if len(text.strip()) > 50:
                    return DocumentFormat.PDF_DIGITAL
        except Exception:
            pass
        return DocumentFormat.PDF_SCANNED

    @staticmethod
    def _compute_sha256(file_path: Path) -> str:
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
        return f"sha256:{sha256.hexdigest()}"