from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class DocumentChunk:
    chunk_id: str
    text: str
    page_number: int
    start_char: int = 0
    end_char: int = 0
    bbox: Optional[list[int]] = None
    section_title: Optional[str] = None
    word_count: int = 0


class SmartChunker:
    DEFAULT_MAX_CHARS = 3000
    DEFAULT_MIN_CHARS = 500

    def __init__(
        self,
        max_chars: int = DEFAULT_MAX_CHARS,
        min_chars: int = DEFAULT_MIN_CHARS,
    ):
        self.max_chars = max_chars
        self.min_chars = min_chars

    def chunk(self, file_path: str | Path) -> list[DocumentChunk]:
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        ext = file_path.suffix.lower()
        if ext == ".pdf":
            return self._chunk_pdf(file_path)
        if ext == ".docx":
            return self._chunk_docx(file_path)
        if ext in (".txt", ".csv"):
            return self._chunk_text(file_path)
        return []

    def _chunk_pdf(self, file_path: Path) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    text = page.extract_text()
                    if text:
                        page_chunks = self._chunk_text_by_size(text, page_num)
                        chunks.extend(page_chunks)
        except Exception:
            chunks.extend(self._chunk_by_page_fallback(file_path))
        return chunks

    def _chunk_docx(self, file_path: Path) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        try:
            from docx import Document as DocxDocument
            doc = DocxDocument(str(file_path))
            all_text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
            chunks = self._chunk_text_by_size(all_text, page_number=1)
        except Exception:
            pass
        return chunks

    def _chunk_text(self, file_path: Path) -> list[DocumentChunk]:
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        return self._chunk_text_by_size(text, page_number=1)

    def _chunk_text_by_size(self, text: str, page_number: int) -> list[DocumentChunk]:
        if len(text) <= self.max_chars:
            return [
                DocumentChunk(
                    chunk_id=f"chunk-{page_number}-1",
                    text=text.strip(),
                    page_number=page_number,
                    start_char=0,
                    end_char=len(text),
                    word_count=len(text.split()),
                )
            ]

        chunks: list[DocumentChunk] = []
        paragraphs = text.split("\n\n")
        current_chunk = ""
        chunk_idx = 1

        for para in paragraphs:
            if not para.strip():
                continue
            if len(current_chunk) + len(para) > self.max_chars and current_chunk:
                chunks.append(
                    DocumentChunk(
                        chunk_id=f"chunk-{page_number}-{chunk_idx}",
                        text=current_chunk.strip(),
                        page_number=page_number,
                        word_count=len(current_chunk.split()),
                    )
                )
                chunk_idx += 1
                current_chunk = para
            else:
                current_chunk += "\n\n" + para if current_chunk else para

        if current_chunk.strip():
            chunks.append(
                DocumentChunk(
                    chunk_id=f"chunk-{page_number}-{chunk_idx}",
                    text=current_chunk.strip(),
                    page_number=page_number,
                    word_count=len(current_chunk.split()),
                )
            )

        return chunks

    def _chunk_by_page_fallback(self, file_path: Path) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        try:
            import PyPDF2
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page_num, page in enumerate(reader.pages, 1):
                    text = page.extract_text() or ""
                    if text.strip():
                        chunks.extend(self._chunk_text_by_size(text, page_num))
        except Exception:
            pass
        return chunks

    def chunk_by_section(
        self, text: str, section_headers: list[str], page_number: int = 1
    ) -> list[DocumentChunk]:
        if not section_headers:
            return self._chunk_text_by_size(text, page_number)

        chunks: list[DocumentChunk] = []
        text_lower = text.lower()

        for i, header in enumerate(section_headers):
            header_lower = header.lower()
            start = text_lower.find(header_lower)
            if start == -1:
                continue

            end = len(text)
            if i + 1 < len(section_headers):
                next_header_lower = section_headers[i + 1].lower()
                end = text_lower.find(next_header_lower, start)
                if end == -1:
                    end = len(text)

            section_text = text[start:end].strip()
            chunks.append(
                DocumentChunk(
                    chunk_id=f"chunk-{page_number}-{i + 1}",
                    text=section_text,
                    page_number=page_number,
                    section_title=header,
                    word_count=len(section_text.split()),
                )
            )

        return chunks