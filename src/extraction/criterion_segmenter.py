from typing import Optional
from src.models.criterion import (
    Criterion,
    CriterionNature,
    CriterionType,
    CriterionThreshold,
    AggregationMode,
)


class CriterionSegmenter:
    def __init__(self, use_llm: bool = True):
        self.use_llm = use_llm

    def extract_criteria(self, tender_text: str, tender_id: str = "") -> list[Criterion]:
        if self.use_llm:
            return self._extract_with_llm(tender_text, tender_id)
        return self._extract_with_heuristics(tender_text, tender_id)

    def _extract_with_llm(self, tender_text: str, tender_id: str) -> list[Criterion]:
        try:
            from openai import OpenAI
            from src.config import config

            client = OpenAI(api_key=config.OPENAI_API_KEY)
            prompt = self._build_criterion_prompt(tender_text[:8000])

            response = client.chat.completions.create(
                model=config.LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=4000,
            )
            result = response.choices[0].message.content
            return self._parse_llm_criteria(result, tender_id)
        except Exception as e:
            return self._extract_with_heuristics(tender_text, tender_id)

    def _extract_with_heuristics(self, tender_text: str, tender_id: str) -> list[Criterion]:
        criteria = []
        text_lower = tender_text.lower()

        # Financial criteria (turnover, revenue, net worth)
        if "turnover" in text_lower or "revenue" in text_lower:
            threshold = self._extract_threshold(tender_text, ["turnover", "revenue", "gross", "annual"])
            criteria.append(Criterion(
                id=f"{tender_id}-C001",
                label="Minimum Annual Turnover",
                nature=CriterionNature.MANDATORY,
                type=CriterionType.FINANCIAL,
                canonical_entities=["turnover", "gross revenue", "total income"],
                threshold=threshold,
                aggregation=AggregationMode.AVERAGE_LAST_3_FY,
                raw_text=self._extract_raw_text(tender_text, ["turnover", "revenue"]),
                confidence=0.85,
            ))

        # ISO Certification
        if "iso" in text_lower or "certificate" in text_lower:
            criteria.append(Criterion(
                id=f"{tender_id}-C002",
                label="ISO Certification",
                nature=CriterionNature.MANDATORY,
                type=CriterionType.CERTIFICATION,
                canonical_entities=["iso 9001", "iso 14001", "iso 27001", "nabcb"],
                aggregation=AggregationMode.COUNT,
                raw_text=self._extract_raw_text(tender_text, ["iso", "certificate"]),
                confidence=0.90,
            ))

        # Experience
        if "experience" in text_lower or "years" in text_lower:
            threshold = self._extract_threshold(tender_text, ["years", "experience"])
            if threshold:
                criteria.append(Criterion(
                    id=f"{tender_id}-C003",
                    label="Minimum Experience",
                    nature=CriterionNature.MANDATORY,
                    type=CriterionType.EXPERIENCE,
                    canonical_entities=["experience", "years"],
                    threshold=threshold,
                    aggregation=AggregationMode.SINGLE,
                    temporal_scope="LAST_5_YEARS",
                    raw_text=self._extract_raw_text(tender_text, ["experience", "years"]),
                    confidence=0.80,
                ))

        # GST registration
        if "gst" in text_lower or "gstin" in text_lower:
            criteria.append(Criterion(
                id=f"{tender_id}-C004",
                label="GST Registration",
                nature=CriterionNature.MANDATORY,
                type=CriterionType.LEGAL,
                canonical_entities=["gst", "gstin", "registration"],
                aggregation=AggregationMode.SINGLE,
                raw_text=self._extract_raw_text(tender_text, ["gst", "gstin"]),
                confidence=0.95,
            ))

        # PAN
        if "pan" in text_lower:
            criteria.append(Criterion(
                id=f"{tender_id}-C005",
                label="PAN Registration",
                nature=CriterionNature.MANDATORY,
                type=CriterionType.LEGAL,
                canonical_entities=["pan", "permanent account"],
                aggregation=AggregationMode.SINGLE,
                raw_text=self._extract_raw_text(tender_text, ["pan"]),
                confidence=0.95,
            ))

        return criteria[:10]

    def _build_criterion_prompt(self, text: str) -> str:
        return (
            "Extract all eligibility criteria from this tender document.\n"
            "For each criterion, identify:\n"
            "- id: unique ID like C-001, C-002\n"
            "- label: human-readable name\n"
            "- nature: MANDATORY or OPTIONAL\n"
            "- type: FINANCIAL, CERTIFICATION, EXPERIENCE, LEGAL, TECHNICAL\n"
            "- threshold: numeric value and unit (e.g., 50000000 INR) if applicable\n"
            "- aggregation: AVERAGE_LAST_3_FY, SINGLE, COUNT, SUM\n"
            "- canonical_entities: alternative names (e.g., turnover/gross revenue)\n\n"
            "Output as JSON array with these fields.\n\n"
            f"Document:\n{text}\n"
        )

    def _parse_llm_criteria(self, llm_output: str, tender_id: str) -> list[Criterion]:
        import json

        try:
            data = json.loads(llm_output)
            criteria = []
            for i, item in enumerate(data):
                threshold = None
                if item.get("threshold"):
                    t = item["threshold"]
                    threshold = CriterionThreshold(
                        value=float(t.get("value", 0)),
                        unit=t.get("unit", "INR"),
                        operator=t.get("operator", ">="),
                    )
                try:
                    nature = CriterionNature(item.get("nature", "MANDATORY"))
                except ValueError:
                    nature = CriterionNature.MANDATORY
                try:
                    ctype = CriterionType(item.get("type", "FINANCIAL"))
                except ValueError:
                    ctype = CriterionType.FINANCIAL
                try:
                    agg = AggregationMode(item.get("aggregation", "SINGLE"))
                except ValueError:
                    agg = AggregationMode.SINGLE
                criteria.append(Criterion(
                    id=item.get("id", f"{tender_id}-C{i+1:03d}"),
                    label=item.get("label", ""),
                    nature=nature,
                    type=ctype,
                    canonical_entities=item.get("canonical_entities", []),
                    threshold=threshold,
                    aggregation=agg,
                    temporal_scope=item.get("temporal_scope"),
                    raw_text=item.get("raw_text", ""),
                    confidence=float(item.get("confidence", 0.8)),
                ))
            return criteria
        except Exception:
            return []

    def _extract_threshold(self, text: str, keywords: list[str]) -> Optional[CriterionThreshold]:
        import re

        text_lower = text.lower()
        for kw in keywords:
            if kw in text_lower:
                pattern = rf"(\d+(?:,\d+)*(?:(?:\.\d+)?)\s*(?:crore|lakh| lakh |million|billion|lac|rs|inr|₹)?)"
                matches = re.findall(pattern, text_lower)
                if matches:
                    value_str = matches[0].replace(",", "").strip()
                    try:
                        value = float(value_str.replace(" ", ""))
                        if "crore" in value_str.lower() or "cr" in value_str.lower():
                            value *= 10000000
                        elif "lakh" in value_str.lower() or "lac" in value_str.lower():
                            value *= 100000
                        elif "billion" in value_str.lower():
                            value *= 1000000000
                        elif "million" in value_str.lower():
                            value *= 1000000
                        return CriterionThreshold(value=value, unit="INR", operator=">=")
                    except Exception:
                        pass
        return None

    def _extract_raw_text(self, text: str, keywords: list[str]) -> str:
        lines = text.split("\n")
        for line in lines:
            if any(kw in line.lower() for kw in keywords):
                return line.strip()[:500]
        return ""