from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class LayoutBlock:
    block_id: str
    block_type: str  # "text", "table", "header", "image", "title"
    text: str
    page_number: int
    bbox: list[int]  # [x1, y1, x2, y2]
    confidence: float = 1.0


@dataclass
class DocumentLayout:
    file_path: str
    page_count: int
    blocks: list[LayoutBlock] = field(default_factory=list)
    tables: list[dict] = field(default_factory=list)
    headers: list[str] = field(default_factory=list)
    toc_entries: list[dict] = field(default_factory=list)


class LayoutAnalyzer:

    def analyze(self, file_path: str | Path) -> DocumentLayout:
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        ext = file_path.suffix.lower()
        if ext == ".pdf":
            return self._analyze_pdf(file_path)
        if ext == ".docx":
            return self._analyze_docx(file_path)
        if ext in (".png", ".jpg", ".jpeg", ".tiff", ".tif"):
            return self._analyze_image(file_path)
        return DocumentLayout(file_path=str(file_path), page_count=0)

    def _analyze_pdf(self, file_path: Path) -> DocumentLayout:
        blocks: list[LayoutBlock] = []
        tables: list[dict] = []
        page_count = 0

        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                page_count = len(pdf.pages)
                for page_num, page in enumerate(pdf.pages, 1):
                    page_blocks = self._extract_page_blocks(page, page_num)
                    blocks.extend(page_blocks)
                    page_tables = self._extract_tables(page, page_num)
                    tables.extend(page_tables)
        except Exception:
            pass

        headers = self._detect_headers(blocks)
        toc_entries = self._detect_toc(blocks)

        return DocumentLayout(
            file_path=str(file_path),
            page_count=page_count,
            blocks=blocks,
            tables=tables,
            headers=headers,
            toc_entries=toc_entries,
        )

    def _analyze_docx(self, file_path: Path) -> DocumentLayout:
        blocks: list[LayoutBlock] = []
        try:
            from docx import Document as DocxDocument
            doc = DocxDocument(str(file_path))
            for i, para in enumerate(doc.paragraphs):
                if para.text.strip():
                    block_type = (
                        "header" if para.style.name.startswith("Heading")
                        else "text"
                    )
                    blocks.append(
                        LayoutBlock(
                            block_id=f"block-{i + 1}",
                            block_type=block_type,
                            text=para.text,
                            page_number=1,
                            bbox=[0, 0, 0, 0],
                        )
                    )
        except Exception:
            pass

        return DocumentLayout(
            file_path=str(file_path),
            page_count=1,
            blocks=blocks,
        )

    def _analyze_image(self, file_path: Path) -> DocumentLayout:
        return DocumentLayout(
            file_path=str(file_path),
            page_count=1,
            blocks=[
                LayoutBlock(
                    block_id="img-1",
                    block_type="image",
                    text="",
                    page_number=1,
                    bbox=[0, 0, 0, 0],
                )
            ],
        )

    def _extract_page_blocks(self, page, page_number: int) -> list[LayoutBlock]:
        blocks: list[LayoutBlock] = []
        try:
            words = page.extract_words()
            if words:
                for i, word in enumerate(words):
                    blocks.append(
                        LayoutBlock(
                            block_id=f"p{page_number}-w{i}",
                            block_type="text",
                            text=word.get("text", ""),
                            page_number=page_number,
                            bbox=[
                                int(word.get("x0", 0)),
                                int(word.get("top", 0)),
                                int(word.get("x1", 0)),
                                int(word.get("bottom", 0)),
                            ],
                        )
                    )
        except Exception:
            pass

        if not blocks:
            text = page.extract_text() or ""
            if text.strip():
                blocks.append(
                    LayoutBlock(
                        block_id=f"p{page_number}",
                        block_type="text",
                        text=text,
                        page_number=page_number,
                        bbox=[0, 0, 0, 0],
                    )
                )

        return blocks

    def _extract_tables(self, page, page_number: int) -> list[dict]:
        tables: list[dict] = []
        try:
            page_tables = page.extract_tables()
            for i, table in enumerate(page_tables):
                tables.append({
                    "table_id": f"table-p{page_number}-{i}",
                    "page": page_number,
                    "rows": table,
                    "row_count": len(table),
                    "col_count": len(table[0]) if table else 0,
                })
        except Exception:
            pass
        return tables

    def _detect_headers(self, blocks: list[LayoutBlock]) -> list[str]:
        headers: list[str] = []
        for block in blocks:
            if block.block_type == "header":
                headers.append(block.text)
            elif block.text.strip().isupper() and len(block.text.strip()) < 100:
                headers.append(block.text.strip())
            elif block.text.strip() and (
                block.text.strip().upper().startswith((
                    "SECTION", "CHAPTER", "CLAUSE", "PART", "ANNEXURE",
                    "SCHEDULE", "ELIGIBILITY", "TERMS", "CONDITIONS",
                    "SCOPE OF WORK", "TECHNICAL", "GENERAL", "SPECIAL",
                    "\u0927\u093e\u0930\u093e", "\u0905\u0928\u0941\u092d\u093e\u0917",
                ))
            ):
                headers.append(block.text.strip())

        return headers

    def _detect_toc(self, blocks: list[LayoutBlock]) -> list[dict]:
        toc_entries: list[dict] = []
        for block in blocks:
            text = block.text.strip()
            if text and ("....." in text or "…" in text or "Table of Contents" in text):
                toc_entries.append({
                    "page": block.page_number,
                    "text": text,
                })
        return toc_entries[:5]