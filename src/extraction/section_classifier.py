from enum import Enum
from typing import Optional

from src.extraction.layout_analyzer import LayoutBlock


class SectionType(str, Enum):
    ELIGIBILITY = "ELIGIBILITY"
    TECHNICAL = "TECHNICAL"
    SCOPE = "SCOPE"
    INSTRUCTIONS = "INSTRUCTIONS"
    IRRELEVANT = "IRRELEVANT"
    UNKNOWN = "UNKNOWN"


class Section:
    def __init__(
        self,
        section_id: str,
        title: str,
        section_type: SectionType,
        text: str,
        page_start: int,
        page_end: int = 0,
        confidence: float = 1.0,
    ):
        self.section_id = section_id
        self.title = title
        self.section_type = section_type
        self.text = text
        self.page_start = page_start
        self.page_end = page_end or page_start
        self.confidence = confidence


class SectionClassifier:
    _ELIGIBILITY_KEYWORDS: list[str] = [
        "eligibility", "qualification", "minimum criteria", "pre-qualification",
        "mandatory requirement", "essential qualification", "bidder must",
        "tenderer shall possess", "\u092f\u094b\u0917\u094d\u092f\u0924\u093e", "\u0905\u0930\u094d\u0939\u0924\u093e",
    ]
    _TECHNICAL_KEYWORDS: list[str] = [
        "technical specification", "technical bid", "technical evaluation",
        "quality standard", "iso", "testing", "inspection",
    ]
    _SCOPE_KEYWORDS: list[str] = [
        "scope of work", "scope of supply", "deliverables", "work description",
        "services required", "statement of work",
    ]
    _INSTRUCTIONS_KEYWORDS: list[str] = [
        "instruction to bidders", "how to apply", "submission procedure",
        "tender fee", "earnest money", "emd", "bid submission",
        "documents required", "checklist",
    ]

    def classify_sections(self, headers: list[LayoutBlock], full_text: str) -> list[Section]:
        sections: list[Section] = []
        section_counter = 0

        for i, header in enumerate(headers):
            section_type = self._classify_header(header.text)
            if section_type == SectionType.UNKNOWN:
                continue

            section_counter += 1
            section_text = self._extract_section_text(header, headers, i, full_text)
            sections.append(
                Section(
                    section_id=f"SEC-{section_counter:03d}",
                    title=header.text.strip(),
                    section_type=section_type,
                    text=section_text,
                    page_start=header.page_number,
                    confidence=0.8,
                )
            )

        return sections

    def classify_text(self, text: str) -> SectionType:
        text_lower = text.lower()
        scores = {
            SectionType.ELIGIBILITY: self._keyword_count(text_lower, self._ELIGIBILITY_KEYWORDS),
            SectionType.TECHNICAL: self._keyword_count(text_lower, self._TECHNICAL_KEYWORDS),
            SectionType.SCOPE: self._keyword_count(text_lower, self._SCOPE_KEYWORDS),
            SectionType.INSTRUCTIONS: self._keyword_count(text_lower, self._INSTRUCTIONS_KEYWORDS),
        }
        best = max(scores, key=scores.get)  # type: ignore
        return best if scores[best] > 0 else SectionType.UNKNOWN

    def _classify_header(self, header_text: str) -> SectionType:
        return self.classify_text(header_text)

    def _extract_section_text(
        self,
        current: LayoutBlock,
        headers: list[LayoutBlock],
        current_idx: int,
        full_text: str,
    ) -> str:
        if current_idx + 1 < len(headers):
            next_header = headers[current_idx + 1]
            return full_text[:next_header.page_number * 1000][-2000:]
        return full_text

    @staticmethod
    def _keyword_count(text: str, keywords: list[str]) -> int:
        return sum(1 for kw in keywords if kw in text)