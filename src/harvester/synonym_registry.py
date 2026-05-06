from typing import Optional


class SynonymRegistry:
    _SYNONYMS = {
        "turnover": [
            "turnover",
            "gross revenue",
            "total income",
            "gross receipts",
            "revenue from operations",
            "total sales",
            "net sales",
            "income from operations",
            "\u091f\u0930\u094d\u0928\u0913\u0935\u0930",
            "\u0906\u092f",
            "\u0938\u0902\u092a\u0923 \u0906\u092e\u0926",
        ],
        "net_worth": [
            "net worth",
            "capital",
            "paid up capital",
            "equity capital",
            "share capital",
            "owned funds",
            "\u0928\u0947\u091f \u0932\u094b\u0928",
            "\u092a\u0941\u0928\u0940 \u0915\u092a\u093f\u0924\u0932",
        ],
        "experience": [
            "experience",
            "years in business",
            "years of operation",
            "operational experience",
            "track record",
            "\u0905\u0928\u0941\u092d\u093e\u0917",
            "\u0915\u093e\u0930\u094d\u092f\u0915\u093e\u0932 \u0905\u0928\u0941\u092d\u093e",
        ],
        "certificate": [
            "certificate",
            "certification",
            "iso",
            "nabcb",
            "nabet",
            "certified",
            "accredited",
            "\u092a\u094d\u0930\u092e\u093e\u0923\u092a\u0924\u094d\u0930",
            "\u092a\u0902\u091c\u0940\u0915\u0943\u0924",
        ],
        "gst_registration": [
            "gst registration",
            "gstin",
            "goods and services tax",
            "\u091c\u0940\u090f\u0938\u091f \u0930\u0947\u091c\u093f\u0938\u094d\u091f\u094d\u0930\u0947\u0936\u0928",
        ],
        "pan": [
            "pan",
            "permanent account number",
            "\u092a\u0948\u0928",
            "\u092a\u0930\u092e\u093e\u0928\u0947\u0902\u091f \u090f\u0915\u093e\u0907\u0902\u091f \u0928\u0902\u092c\u0930",
        ],
        "employee": [
            "employee",
            "staff",
            "workforce",
            "manpower",
            "personnel",
            "labor",
            "\u0915\u0930\u094d\u092e\u091a\u093e\u0930\u0940",
            "\u0938\u0928\u093e\u092f\u0942\u0917\u0924",
        ],
        "infrastructure": [
            "infrastructure",
            "equipment",
            "machinery",
            "plant",
            "facility",
            "\u090a\u0930\u0928\u093e\u0938\u094d\u0925\u093e\u0928",
            "\u0938\u0902\u092f\u0902\u091c\u0928",
        ],
        "iso_9001": [
            "iso 9001",
            "iso 9001:2015",
            "iso 9001:2015",
            "quality management system",
            "qms",
        ],
        "iso_14001": [
            "iso 14001",
            "iso 14001:2015",
            "environment management system",
            "ems",
        ],
    }

    def __init__(self):
        self._reverse_index: dict[str, list[str]] = {}
        self._build_index()

    def _build_index(self):
        for canonical, synonyms in self._SYNONYMS.items():
            for syn in synonyms:
                key = syn.lower().replace(" ", "")
                if key not in self._reverse_index:
                    self._reverse_index[key] = []
                self._reverse_index[key].append(canonical)

    def lookup(self, term: str) -> list[str]:
        term_lower = term.lower().strip()
        if term_lower in self._SYNONYMS:
            return self._SYNONYMS[term_lower]
        key = term_lower.replace(" ", "")
        if key in self._reverse_index:
            canonical = self._reverse_index[key][0]
            return self._SYNONYMS.get(canonical, [term])
        return [term]

    def get_canonical(self, term: str) -> Optional[str]:
        term_lower = term.lower().strip()
        if term_lower in self._SYNONYMS:
            return term_lower
        key = term_lower.replace(" ", "")
        if key in self._reverse_index:
            return self._reverse_index[key][0]
        return None

    def is_synonym(self, term1: str, term2: str) -> bool:
        syns1 = self.lookup(term1)
        syns2 = self.lookup(term2)
        return any(s in syns2 for s in syns1)

    def match_in_text(self, text: str) -> dict[str, list[str]]:
        text_lower = text.lower()
        matches = {}
        for canonical, synonyms in self._SYNONYMS.items():
            found = [syn for syn in synonyms if syn in text_lower]
            if found:
                matches[canonical] = found
        return matches

    def get_all_canonical(self) -> list[str]:
        return list(self._SYNONYMS.keys())