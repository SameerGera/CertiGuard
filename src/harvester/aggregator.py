from dataclasses import dataclass
from typing import Optional
import statistics

from src.models.evidence import ExtractedEntity
from src.models.criterion import AggregationMode


@dataclass
class AggregatedValue:
    canonical_name: str
    value: float
    display_value: str
    method: str
    confidence: float
    source_count: int
    individual_values: list[float]


class Aggregator:
    def aggregate(
        self,
        entities: list[ExtractedEntity],
        criterion_id: str,
        aggregation_mode: AggregationMode = AggregationMode.SINGLE,
        entity_type: str = "numeric",
    ) -> AggregatedValue:
        if not entities:
            return AggregatedValue(
                canonical_name=criterion_id,
                value=0.0,
                display_value="",
                method="none",
                confidence=0.0,
                source_count=0,
                individual_values=[],
            )

        if entity_type in ("turnover", "amount", "net_worth"):
            return self._aggregate_numeric(entities, criterion_id, aggregation_mode)
        elif entity_type in ("certificate", "iso", "experience"):
            return self._aggregate_count(entities, criterion_id, aggregation_mode)
        else:
            return self._aggregate_single(entities, criterion_id)

    def _aggregate_numeric(
        self,
        entities: list[ExtractedEntity],
        criterion_id: str,
        aggregation_mode: AggregationMode,
    ) -> AggregatedValue:
        numeric_values = []
        for entity in entities:
            val = self._parse_numeric(entity.normalized_value or entity.value)
            if val is not None:
                numeric_values.append(val)

        if not numeric_values:
            return AggregatedValue(
                canonical_name=criterion_id,
                value=0.0,
                display_value="",
                method="none",
                confidence=0.0,
                source_count=0,
                individual_values=[],
            )

        method = aggregation_mode.value
        if aggregation_mode == AggregationMode.AVERAGE_LAST_3_FY:
            values = numeric_values[-3:] if len(numeric_values) >= 3 else numeric_values
            value = statistics.mean(values)
            method = "average_last_3"
        elif aggregation_mode == AggregationMode.AVERAGE_LAST_5_FY:
            values = numeric_values[-5:] if len(numeric_values) >= 5 else numeric_values
            value = statistics.mean(values)
            method = "average_last_5"
        elif aggregation_mode == AggregationMode.SUM:
            value = sum(numeric_values)
            method = "sum"
        elif aggregation_mode == AggregationMode.COUNT:
            value = len(numeric_values)
            method = "count"
        else:
            value = max(numeric_values)
            method = "single_max"

        confidence = statistics.mean([e.confidence for e in entities])
        display_value = self._format_inr(value)

        return AggregatedValue(
            canonical_name=criterion_id,
            value=value,
            display_value=display_value,
            method=method,
            confidence=confidence,
            source_count=len(numeric_values),
            individual_values=numeric_values,
        )

    def _aggregate_count(
        self,
        entities: list[ExtractedEntity],
        criterion_id: str,
        aggregation_mode: AggregationMode,
    ) -> AggregatedValue:
        unique_values = list(set(e.value for e in entities if e.value))
        value = len(unique_values)
        confidence = statistics.mean([e.confidence for e in entities])

        return AggregatedValue(
            canonical_name=criterion_id,
            value=float(value),
            display_value=str(value),
            method="count_unique",
            confidence=confidence,
            source_count=len(entities),
            individual_values=[float(v) for v in unique_values],
        )

    def _aggregate_single(
        self,
        entities: list[ExtractedEntity],
        criterion_id: str,
    ) -> AggregatedValue:
        best = max(entities, key=lambda e: e.confidence)
        confidence = best.confidence

        return AggregatedValue(
            canonical_name=criterion_id,
            value=1.0,
            display_value=best.value,
            method="single_best",
            confidence=confidence,
            source_count=len(entities),
            individual_values=[1.0],
        )

    def _parse_numeric(self, value_str: str) -> Optional[float]:
        if not value_str:
            return None

        value_str = str(value_str).replace(",", "").replace(" ", "")
        multipliers = {
            "crore": 10000000,
            "cr": 10000000,
            "lakh": 100000,
            "lac": 100000,
            "million": 1000000,
            "billion": 1000000000,
            "k": 1000,
        }

        import re
        match = re.match(r"([\d.]+)\s*([a-zA-Z]+)?", value_str, re.IGNORECASE)
        if match:
            num = float(match.group(1))
            unit = match.group(2).lower() if match.group(2) else ""
            return num * multipliers.get(unit, 1)

        try:
            return float(value_str)
        except ValueError:
            return None

    def _format_inr(self, value: float) -> str:
        if value >= 10000000:
            return f"₹{value / 10000000:.2f} Crore"
        elif value >= 100000:
            return f"₹{value / 100000:.2f} Lakh"
        elif value >= 1000:
            return f"₹{value / 1000:.2f} Thousand"
        else:
            return f"₹{value:.2f}"

    def compare_threshold(
        self,
        aggregated: AggregatedValue,
        threshold_value: float,
        operator: str = ">=",
    ) -> bool:
        if operator == ">=":
            return aggregated.value >= threshold_value
        elif operator == ">":
            return aggregated.value > threshold_value
        elif operator == "<=":
            return aggregated.value <= threshold_value
        elif operator == "<":
            return aggregated.value < threshold_value
        elif operator == "==":
            return aggregated.value == threshold_value
        return False