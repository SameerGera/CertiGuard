from src.models.criterion import CriterionNature


class NatureClassifier:
    _MANDATORY_KEYWORDS = [
        "must", "shall", "mandatory", "required", "essential",
        "no bid", "will not be considered", "shall be",
        "must have", "must possess", "should have",
        "\u092e\u093f\u0932\u0915\u0947", "\u0905\u0928\u093f\u0935\u093e\u0930\u094d\u092f",
    ]
    _OPTIONAL_KEYWORDS = [
        "prefer", "preferred", "desirable", "optional",
        "additional", "bonus", "advantage", "may include",
        "\u0908\u091a\u094d\u091b\u0947\u0915", "\u0935\u094b\u0902\u091b\u0940\u0937\u094d\u091f",
    ]
    _DESIRABLE_KEYWORDS = [
        "desirable", "preferred", "would be beneficial",
        "\u092a\u094d\u0930\u0924\u094d\u0938\u0926\u0943\u092a\u094d\u0924",
    ]

    def classify(self, criterion_text: str) -> CriterionNature:
        text_lower = criterion_text.lower()

        mandatory_count = sum(1 for kw in self._MANDATORY_KEYWORDS if kw in text_lower)
        desirable_count = sum(1 for kw in self._DESIRABLE_KEYWORDS if kw in text_lower)
        optional_count = sum(1 for kw in self._OPTIONAL_KEYWORDS if kw in text_lower)

        if mandatory_count > 0:
            return CriterionNature.MANDATORY
        if desirable_count > 0:
            return CriterionNature.DESIRABLE
        if optional_count > 0:
            return CriterionNature.OPTIONAL
        
        return CriterionNature.MANDATORY

    def is_mandatory(self, criterion_text: str) -> bool:
        return self.classify(criterion_text) == CriterionNature.MANDATORY

    def is_optional(self, criterion_text: str) -> bool:
        return self.classify(criterion_text) == CriterionNature.OPTIONAL

    def is_desirable(self, criterion_text: str) -> bool:
        return self.classify(criterion_text) == CriterionNature.DESIRABLE