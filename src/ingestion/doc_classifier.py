from typing import Optional

from src.models.document import DocumentClassification, DocumentFormat


class DocClassifier:
    _FINANCIAL_KEYWORDS: list[str] = [
        "turnover", "gross revenue", "total income", "profit & loss",
        "balance sheet", "annual report", "audited financial", "p&l",
        "revenue from operations", "net worth", "ebitda",
        "gross receipts", "taxable income", "financial statements",
        "\u091f\u0930\u094d\u0928\u0913\u0935\u0930", "\u0906\u092f",
    ]
    _CERTIFICATE_KEYWORDS: list[str] = [
        "iso 9001", "iso 14001", "iso 27001", "nabcb", "nabet",
        "certificate of incorporation", "registration certificate",
        "quality management", "certified", "accredited",
        "\u092a\u094d\u0930\u092e\u093e\u0923\u092a\u0924\u094d\u0930", "\u092a\u0902\u091c\u0940\u0915\u0943\u0924",
    ]
    _TAX_DOC_KEYWORDS: list[str] = [
        "gst", "pan", "tan", "income tax return", "itr",
        "tax deduction", "tds", "gstin", "permanent account",
        "\u091c\u0940\u090f\u0938\u091f\u0940", "\u092a\u0948\u0928",
    ]
    _WORK_ORDER_KEYWORDS: list[str] = [
        "work order", "purchase order", "contract agreement",
        "completion certificate", "service agreement", "loa",
        "letter of award", "po number", "work completion",
    ]
    _PROFILE_KEYWORDS: list[str] = [
        "company profile", "about us", "board of directors",
        "infrastructure", "workforce", "clientele", "our team",
        "corporate overview", "organization structure",
    ]

    def __init__(self, use_llm: bool = False):
        self.use_llm = use_llm

    def classify(self, text: str, document_format: DocumentFormat) -> DocumentClassification:
        if not text or not text.strip():
            return DocumentClassification.UNKNOWN

        text_lower = text.lower()
        scores = {
            DocumentClassification.FINANCIAL: self._keyword_score(
                text_lower, self._FINANCIAL_KEYWORDS
            ),
            DocumentClassification.CERTIFICATE: self._keyword_score(
                text_lower, self._CERTIFICATE_KEYWORDS
            ),
            DocumentClassification.TAX_DOC: self._keyword_score(
                text_lower, self._TAX_DOC_KEYWORDS
            ),
            DocumentClassification.WORK_ORDER: self._keyword_score(
                text_lower, self._WORK_ORDER_KEYWORDS
            ),
            DocumentClassification.PROFILE: self._keyword_score(
                text_lower, self._PROFILE_KEYWORDS
            ),
        }

        best_class = max(scores, key=scores.get)  # type: ignore
        best_score = scores[best_class]

        if best_score < 2:
            return DocumentClassification.UNKNOWN

        return best_class

    def classify_with_llm(self, text: str) -> Optional[DocumentClassification]:
        if not self.use_llm:
            return None

        try:
            from openai import OpenAI
            from src.config import config

            client = OpenAI(api_key=config.OPENAI_API_KEY)
            prompt = self._build_classification_prompt(text[:4000])

            response = client.chat.completions.create(
                model=config.LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=50,
            )
            result = response.choices[0].message.content.strip().upper()
            return self._parse_llm_result(result)
        except Exception:
            return None

    def _build_classification_prompt(self, text: str) -> str:
        return (
            "Classify the following document into exactly one of these categories:\n"
            "- FINANCIAL: Contains turnover, revenue, balance sheet, profit & loss data\n"
            "- CERTIFICATE: ISO, NABCB, registration, certification document\n"
            "- TAX_DOC: GST, PAN, income tax return, TDS document\n"
            "- WORK_ORDER: Work order, purchase order, contract, completion certificate\n"
            "- PROFILE: Company profile, about us, infrastructure details\n"
            "- UNKNOWN: Cannot determine\n\n"
            "Reply with only the category name.\n\n"
            f"Document text:\n{text[:3000]}\n"
        )

    def _parse_llm_result(self, result: str) -> Optional[DocumentClassification]:
        result = result.strip().upper()
        try:
            return DocumentClassification(result)
        except ValueError:
            return DocumentClassification.UNKNOWN

    @staticmethod
    def _keyword_score(text: str, keywords: list[str]) -> int:
        text_lower = text.lower()
        count = 0
        for kw in keywords:
            if kw in text_lower:
                count += 1
            # Also match with hyphen or underscore replaced
            kw_underscore = kw.replace(" ", "")
            if kw_underscore in text_lower.replace(" ", "").replace("-", ""):
                count += 1
        return count