import base64
from pathlib import Path
from typing import Optional
import json

from src.models.evidence import ExtractedEntity


class VLMExtractor:
    def __init__(
        self,
        provider: str = "openai",  # "openai", "anthropic", "donut"
        model: str = "gpt-4o-mini",
    ):
        self.provider = provider
        self.model = model
        self._client = None

    def _get_client(self):
        if self.provider == "openai" and not self._client:
            from openai import OpenAI
            from src.config import config
            self._client = OpenAI(api_key=config.OPENAI_API_KEY)
        elif self.provider == "anthropic" and not self._client:
            import anthropic
            from src.config import config
            self._client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        return self._client

    def extract(
        self,
        image_path: str | Path,
        entity_types: list[str],
        criterion_context: str = "",
    ) -> list[ExtractedEntity]:
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        if self.provider in ("openai", "anthropic"):
            return self._extract_with_llm(image_path, entity_types, criterion_context)
        return self._extract_with_donut(image_path, entity_types)

    def _extract_with_llm(
        self,
        image_path: Path,
        entity_types: list[str],
        criterion_context: str,
    ) -> list[ExtractedEntity]:
        image_base64 = self._encode_image(image_path)

        if self.provider == "openai":
            return self._extract_openai(image_base64, entity_types, criterion_context)
        elif self.provider == "anthropic":
            return self._extract_anthropic(image_base64, entity_types, criterion_context)
        return []

    def _extract_openai(
        self,
        image_base64: str,
        entity_types: list[str],
        criterion_context: str,
    ) -> list[ExtractedEntity]:
        client = self._get_client()
        if not client:
            return []

        entity_types_str = ", ".join(entity_types)
        prompt = (
            f"Extract the following entity types from this document: {entity_types_str}.\n"
            f"Context: {criterion_context}\n"
            "Return JSON with fields: entity_type, value, confidence."
        )

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{image_base64}"},
                            },
                        ],
                    }
                ],
                max_tokens=1000,
                temperature=0,
            )
            result = response.choices[0].message.content
            return self._parse_llm_result(result)
        except Exception as e:
            print(f"[WARN] OpenAI extraction failed: {e}")
            return []

    def _extract_anthropic(
        self,
        image_base64: str,
        entity_types: list[str],
        criterion_context: str,
    ) -> list[ExtractedEntity]:
        client = self._get_client()
        if not client:
            return []

        entity_types_str = ", ".join(entity_types)
        prompt = (
            f"Extract the following entity types from this document: {entity_types_str}.\n"
            f"Context: {criterion_context}\n"
            "Return JSON with fields: entity_type, value, confidence. Do not include markdown."
        )

        try:
            response = client.messages.create(
                model=self.model,
                max_tokens=1000,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": image_base64,
                                },
                            },
                        ],
                    }
                ],
            )
            result = response.content[0].text
            return self._parse_llm_result(result)
        except Exception as e:
            print(f"[WARN] Anthropic extraction failed: {e}")
            return []

    def _extract_with_donut(
        self,
        image_path: Path,
        entity_types: list[str],
    ) -> list[ExtractedEntity]:
        try:
            from donut import DonutModel
            model = DonutModel.from_pretrained("naver-clova-ix/donut-base")
            result = model.inference(image_path)
            return [ExtractedEntity(entity_type="text", value=result, confidence=0.8)]
        except Exception as e:
            print(f"[WARN] Donut extraction failed: {e}")
            return []

    def _encode_image(self, image_path: Path) -> str:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def _parse_llm_result(self, result: str) -> list[ExtractedEntity]:
        entities = []
        result = result.strip()
        if result.startswith("```"):
            result = result[result.find("```") + 3:]
            if result.find("```") > 0:
                result = result[:result.find("```")]
        if result.startswith("json"):
            result = result[4:]
        result = result.strip()

        try:
            data = json.loads(result)
            if isinstance(data, list):
                for item in data:
                    entities.append(
                        ExtractedEntity(
                            entity_type=item.get("entity_type", "unknown"),
                            value=str(item.get("value", "")),
                            confidence=float(item.get("confidence", 0.8)),
                        )
                    )
            elif isinstance(data, dict):
                entities.append(
                    ExtractedEntity(
                        entity_type=data.get("entity_type", "unknown"),
                        value=str(data.get("value", "")),
                        confidence=float(data.get("confidence", 0.8)),
                    )
                )
        except json.JSONDecodeError:
            pass
        return entities

    def is_available(self) -> bool:
        try:
            client = self._get_client()
            return client is not None
        except Exception:
            return False