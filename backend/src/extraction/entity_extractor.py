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

    _CERTIFICATION_PATTERNS = {
        "iso_9001": r"ISO\s*9001[:\-]?\s*(\d{4})?",
        "iso_14001": r"ISO\s*14001[:\-]?\s*(\d{4})?",
        "iso_45001": r"ISO\s*45001[:\-]?\s*(\d{4})?",
        "iso_27001": r"ISO\s*27001[:\-]?\s*(\d{4})?",
        "iso_certification": r"(?:ISO\s*\d{4,5}|International\s*Organization\s*for\s*Standardization)",
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
            elif entity_type in ["experience_years", "years_of_experience", "experience"]:
                extracted = self._extract_experience_years(text)
                if extracted:
                    entities.append(extracted)
            elif entity_type in ["certification", "iso_cert", "iso_certificate", "quality_cert"]:
                extracted = self._extract_certifications(text)
                if extracted:
                    entities.extend(extracted)
            elif entity_type in ["address", "registered_address"]:
                extracted = self._extract_address(text)
                if extracted:
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

    def _extract_experience_years(self, text: str) -> Optional[ExtractedEntity]:
        patterns = [
            r"(\d+)\s*(?:\+\s*)?years?\s*(?:of\s*)?(?:experience|exp)",
            r"experience\s*[:\-]?\s*(\d+)\s*years?",
            r"(\d+)\s*yrs?\s*(?:of\s*)?(?:experience|exp)",
            r"since\s*(\d{4})\s*-\s*(?:present|current)",
            r"working\s*(?:since|from)\s*(\d{4})",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    if match.lastindex == 1:
                        years = int(match.group(1))
                        if years > 50:
                            current_year = 2026
                            years = current_year - years
                        return ExtractedEntity(
                            entity_type="experience_years",
                            value=f"{years} years",
                            normalized_value=str(years),
                            confidence=0.85
                        )
                except (ValueError, AttributeError):
                    pass
        return None

    def _extract_certifications(self, text: str) -> list[ExtractedEntity]:
        entities = []
        
        for cert_type, pattern in self._CERTIFICATION_PATTERNS.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                year = matches[0] if matches[0] else "Valid"
                entities.append(ExtractedEntity(
                    entity_type="certification",
                    value=f"{cert_type.replace('_', ' ').upper()} - {year}",
                    normalized_value=year if year != "Valid" else "Active",
                    confidence=0.90
                ))
        
        if not entities:
            iso_matches = re.findall(r"ISO\s*\d+", text, re.IGNORECASE)
            if iso_matches:
                entities.append(ExtractedEntity(
                    entity_type="certification",
                    value="ISO Certification Found",
                    normalized_value="Active",
                    confidence=0.80
                ))
        
        return entities

    def _extract_address(self, text: str) -> Optional[ExtractedEntity]:
        patterns = [
            r"[A-Z][a-zA-Z\s]+,\s*[A-Z]{2}\s*\d{6}",
            r"(?:address|registered\s*office)[:\s]*([^,\n]+(?:,\s*[^,\n]+){0,3})",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return ExtractedEntity(
                    entity_type="address",
                    value=match.group(0).strip(),
                    confidence=0.75
                )
        return None

    def validate_entity(self, entity: ExtractedEntity) -> tuple[bool, str]:
        if entity.entity_type == "gst_number":
            if len(entity.value) == 15:
                return True, "Valid GST format"
            return False, "Invalid GST format"
        
        if entity.entity_type == "pan_number":
            if len(entity.value) == 10 and entity.value[:5].isupper() and entity.value[5:9].isdigit():
                return True, "Valid PAN format"
            return False, "Invalid PAN format"
        
        if entity.entity_type == "email":
            if re.match(r"[^@]+@[^@]+\.[^@]+", entity.value):
                return True, "Valid email format"
            return False, "Invalid email format"
        
        if entity.entity_type == "phone":
            if len(re.sub(r"\D", "", entity.value)) >= 10:
                return True, "Valid phone format"
            return False, "Invalid phone format"
        
        if entity.entity_type == "experience_years":
            try:
                years = int(entity.normalized_value)
                if 0 < years <= 50:
                    return True, f"Valid: {years} years"
                return False, f"Years out of reasonable range"
            except (ValueError, TypeError):
                return False, "Invalid experience value"
        
        if entity.entity_type == "turnover":
            try:
                amount = int(entity.normalized_value.replace(",", ""))
                if amount > 0:
                    return True, f"Valid: Rs. {amount:,}"
                return False, "Turnover must be positive"
            except (ValueError, TypeError):
                return False, "Invalid turnover value"
        
        return True, "Valid"