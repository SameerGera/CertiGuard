import re
from typing import Optional

from src.models.evidence import ExtractedEntity


class EntityExtractor:
    _ENTITY_PATTERNS = {
        "company_name": r"[A-Z][A-Za-z\s]+(?:Pvt|Ltd|Private|Limited|Inc|Corporation)",
        "gst_number": r"[0-9]{2}[A-Z]{1}[0-9]{10}[A-Z]{1}[0-9]{1}",
        "pan_number": r"[A-Z]{5}[0-9]{4}[A-Z]{1}",
        "gstin": r"[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}[0-9]{1}",
        "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "phone": r"(?:\+?91)?[6-9][0-9]{9}",
        "date": r"(?:[0-9]{1,2}[-/][0-9]{1,2}[-/][0-9]{2,4}|[0-9]{4}[-/][0-9]{2}[-/][0-9]{2})",
        "turnover": r"(?:₹|Rs\.?|INR)?\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:Crore?|Lakh?|Lac|Million|Billion)?",
        "amount": r"(?:₹|Rs\.?|INR)?\s*(\d+(?:,\d+)*(?:\.\d+)?)",
    }

    def __init__(self, use_llm: bool = False):
        self.use_llm = use_llm

    def extract_entities(
        self,
        text: str,
        entity_types: list[str],
        criterion_id: str = "",
    ) -> list[ExtractedEntity]:
        entities = []

        for entity_type in entity_types:
            if entity_type in ["turnover", "revenue", "gross", "income"]:
                extracted = self._extract_financial_value(text)
                if extracted:
                    entities.append(extracted)
            elif entity_type in ["company_name", "firm_name", "bidder"]:
                extracted = self._extract_company_name(text)
                if extracted:
                    entities.append(extracted)
            elif entity_type in ["gst_number", "gstin"]:
                extracted = self._extract_by_pattern(text, "gst_number")
                if extracted:
                    extracted.entity_type = "gst_number"
                    entities.append(extracted)
            elif entity_type in ["pan_number", "pan"]:
                extracted = self._extract_by_pattern(text, "pan_number")
                if extracted:
                    entities.append(extracted)
            elif entity_type in ["email", "email_address"]:
                extracted = self._extract_by_pattern(text, "email")
                if extracted:
                    entities.append(extracted)
            elif entity_type in ["phone", "mobile", "contact"]:
                extracted = self._extract_by_pattern(text, "phone")
                if extracted:
                    entities.append(extracted)
            elif entity_type in ["expiry_date", "valid_until", "certificate_expiry"]:
                extracted = self._extract_date(text)
                if extracted:
                    extracted.entity_type = entity_type
                    entities.append(extracted)

        return entities

    def _extract_company_name(self, text: str) -> Optional[ExtractedEntity]:
        pattern = r"([A-Z][A-Za-z\s&]+(?:Pvt\.? Ltd\.? |Private Limited|Limited|Inc\.?|Corporation|Co\.?))"
        matches = re.findall(pattern, text)
        if matches:
            return ExtractedEntity(
                entity_type="company_name",
                value=matches[0].strip(),
                confidence=0.85,
            )
        return None

    def _extract_financial_value(self, text: str) -> Optional[ExtractedEntity]:
        pattern = r"(?:₹|Rs\.?|INR)?\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(Crore?|Lakh?|Lac|Million|Billion)?"
        matches = re.findall(pattern, text, re.IGNORECASE)
        if not matches:
            return None

        value_str, unit = matches[0][0], matches[0][1] if len(matches[0]) > 1 else ""
        try:
            value = float(value_str.replace(",", ""))
            unit = unit.lower().strip() if unit else ""

            if unit in ["crore", "cr"]:
                value *= 10000000
            elif unit in ["lakh", "lac"]:
                value *= 100000
            elif unit == "billion":
                value *= 1000000000
            elif unit == "million":
                value *= 1000000

            normalized = f"{int(value):,}"

            return ExtractedEntity(
                entity_type="turnover",
                value=f"{value_str} {unit}".strip(),
                normalized_value=normalized,
                confidence=0.90,
            )
        except Exception:
            return None

    def _extract_by_pattern(self, text: str, pattern_name: str) -> Optional[ExtractedEntity]:
        pattern = self._ENTITY_PATTERNS.get(pattern_name)
        if not pattern:
            return None

        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            return ExtractedEntity(
                entity_type=pattern_name,
                value=matches[0].strip(),
                confidence=0.85,
            )
        return None

    def _extract_date(self, text: str) -> Optional[ExtractedEntity]:
        pattern = r"([0-9]{1,2}[-/][0-9]{1,2}[-/][0-9]{2,4})"
        matches = re.findall(pattern, text)
        if matches:
            return ExtractedEntity(
                entity_type="date",
                value=matches[0].strip(),
                confidence=0.80,
            )
        return None

    def normalize_value(self, value: str, entity_type: str) -> str:
        if entity_type == "turnover":
            return self._normalize_financial(value)
        elif entity_type in ["gst_number", "pan_number"]:
            return value.upper().strip()
        return value

    def _normalize_financial(self, value: str) -> str:
        import re

        pattern = r"(\d+(?:,\d+)*(?:\.\d+)?)\s*(Crore?|Lakh?|Lac|Million|Billion)?"
        match = re.match(pattern, value, re.IGNORECASE)
        if not match:
            return value

        num_str, unit = match.groups()
        try:
            value = float(num_str.replace(",", ""))
            unit = (unit or "").lower()

            if unit in ["crore", "cr"]:
                value *= 10000000
            elif unit in ["lakh", "lac"]:
                value *= 100000
            elif unit == "billion":
                value *= 1000000000
            elif unit == "million":
                value *= 1000000

            return f"{int(value):,}"
        except Exception:
            return value