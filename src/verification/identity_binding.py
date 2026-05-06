"""Identity Binding."""

from typing import Optional, List
from dataclasses import dataclass
from enum import Enum
from difflib import SequenceMatcher
import re


class IdentityMatchResult(Enum):
    EXACT = "exact"
    FUZZY = "fuzzy"
    PARTIAL = "partial"
    NO_MATCH = "no_match"


@dataclass
class IdentityBindingResult:
    matched: bool
    match_type: IdentityMatchResult
    score: float
    message: str
    detail: Optional[str] = None


class IdentityBinder:
    MATCH_THRESHOLD = 0.80

    def normalize_name(self, name: str) -> str:
        if not name:
            return ""
        normalized = name.strip().upper()
        normalized = re.sub(r"[^A-Z0-9\s]", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized)
        for suffix in [" PRIVATE LIMITED", " PVT LTD", " LIMITED", " LTD", " LLP"]:
            normalized = normalized.replace(suffix, "")
        return normalized.strip()

    def fuzzy_match_score(self, name1: str, name2: str) -> float:
        if not name1 or not name2:
            return 0.0
        n1 = self.normalize_name(name1)
        n2 = self.normalize_name(name2)
        if n1 == n2:
            return 1.0
        return SequenceMatcher(None, n1, n2).ratio()

    def token_match_score(self, name1: str, name2: str) -> float:
        if not name1 or not name2:
            return 0.0
        tokens1 = set(self.normalize_name(name1).split())
        tokens2 = set(self.normalize_name(name2).split())
        if not tokens1 or not tokens2:
            return 0.0
        intersection = tokens1 & tokens2
        union = tokens1 | tokens2
        return len(intersection) / len(union) if union else 0.0

    def match_names(self, entity_name: str, bidder_name: str) -> IdentityBindingResult:
        if not entity_name or not bidder_name:
            return IdentityBindingResult(False, IdentityMatchResult.NO_MATCH, 0.0, "Empty name")

        fuzzy_score = self.fuzzy_match_score(entity_name, bidder_name)
        token_score = self.token_match_score(entity_name, bidder_name)
        max_score = max(fuzzy_score, token_score)

        if max_score >= 1.0:
            return IdentityBindingResult(True, IdentityMatchResult.EXACT, max_score, "Exact match", entity_name)
        elif max_score >= self.MATCH_THRESHOLD:
            return IdentityBindingResult(True, IdentityMatchResult.FUZZY, max_score, "Fuzzy match", f"Score: {max_score:.2f}")
        elif token_score >= 0.5:
            return IdentityBindingResult(False, IdentityMatchResult.PARTIAL, token_score, "Partial match", f"Token: {token_score:.2f}")
        else:
            return IdentityBindingResult(False, IdentityMatchResult.NO_MATCH, max_score, "No match", f"Score: {max_score:.2f}")

    def validate_entity_ownership(self, entities: List[dict], bidder_name: str, bidder_pan: Optional[str] = None, bidder_gstin: Optional[str] = None) -> List[IdentityBindingResult]:
        results = []
        for entity in entities:
            entity_type = entity.get("entity_type", "")
            value = entity.get("value", "")
            if entity_type == "company_name":
                results.append(self.match_names(value, bidder_name))
        return results


identity_binder = IdentityBinder()