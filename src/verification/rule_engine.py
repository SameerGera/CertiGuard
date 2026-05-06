"""Rule Engine - Deterministic validation."""

import re
from typing import Optional
from dataclasses import dataclass
from enum import Enum


class ValidationResult(Enum):
    VALID = "valid"
    INVALID = "invalid"
    WARNING = "warning"


@dataclass
class RuleValidationResult:
    passed: bool
    result: ValidationResult
    message: str
    detail: Optional[str] = None


class RuleEngine:
    GSTIN_PATTERN = re.compile(
        r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[0-9]{1}[A-Z]{1}$"
    )
    PAN_PATTERN = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$")

    UNIT_MULTIPLIERS = {
        "rs": 1, "inr": 1, "rupees": 1, "₹": 1,
        "lakh": 100000, "lac": 100000, "l": 100000,
        "crore": 10000000, "cr": 10000000, "c": 10000000,
        "million": 1000000, "m": 1000000,
        "billion": 1000000000, "b": 1000000000,
    }

    def validate_gstin(self, gstin: str) -> RuleValidationResult:
        if not gstin:
            return RuleValidationResult(False, ValidationResult.INVALID, "GSTIN empty")

        gstin_clean = gstin.strip().upper().replace(" ", "").replace("-", "")

        if len(gstin_clean) != 15:
            return RuleValidationResult(False, ValidationResult.INVALID, f"GSTIN must be 15 chars", gstin_clean)

        if gstin_clean[0:2].isdigit() and gstin_clean[-1:].isalpha():
            return RuleValidationResult(True, ValidationResult.VALID, "Valid", gstin_clean)

        return RuleValidationResult(False, ValidationResult.INVALID, "Invalid GSTIN format", gstin_clean)

    def validate_pan(self, pan: str) -> RuleValidationResult:
        if not pan:
            return RuleValidationResult(False, ValidationResult.INVALID, "PAN empty")

        pan_clean = pan.strip().upper().replace(" ", "").replace("-", "")

        if len(pan_clean) != 10:
            return RuleValidationResult(False, ValidationResult.INVALID, f"PAN must be 10 chars, got {len(pan_clean)}", pan_clean)

        if not self.PAN_PATTERN.match(pan_clean):
            return RuleValidationResult(False, ValidationResult.INVALID, "Invalid PAN format", pan_clean)

        return RuleValidationResult(True, ValidationResult.VALID, "Valid", pan_clean)

    def normalize_unit(self, value_str: str) -> Optional[int]:
        # Convert Crore/Lakh/Million to INR base
        if not value_str:
            return None

        value_clean = value_str.strip().replace(",", "").replace(" ", "")
        multiplier = 1

        for unit, mult in self.UNIT_MULTIPLIERS.items():
            if unit in value_clean.lower():
                multiplier = mult
                value_clean = value_clean.lower().replace(unit, "").strip()
                break

        try:
            return int(float(value_clean) * multiplier)
        except ValueError:
            return None

    def compare_threshold(self, actual: int, threshold: int, operator: str) -> RuleValidationResult:
        ops = {">=": lambda a, t: a >= t, ">": lambda a, t: a > t, "<=": lambda a, t: a <= t, "<": lambda a, t: a < t}

        if operator not in ops:
            return RuleValidationResult(False, ValidationResult.INVALID, f"Unknown operator: {operator}")

        passed = ops[operator](actual, threshold)
        return RuleValidationResult(passed, ValidationResult.VALID if passed else ValidationResult.INVALID,
                              f"{actual:,} {operator} {threshold:,}", f"Actual: {actual:,}, Threshold: {threshold:,}")

    def validate_amount_range(self, value: int, min_val: Optional[int] = None, max_val: Optional[int] = None) -> RuleValidationResult:
        if min_val and max_val:
            passed = min_val <= value <= max_val
            return RuleValidationResult(passed, ValidationResult.VALID if passed else ValidationResult.INVALID,
                                  f"Range: {min_val:,}-{max_val:,}", f"Value: {value:,}")
        elif min_val:
            passed = value >= min_val
            return RuleValidationResult(passed, ValidationResult.VALID if passed else ValidationResult.INVALID,
                                  f"Min: {min_val:,}", f"Value: {value:,}")
        elif max_val:
            passed = value <= max_val
            return RuleValidationResult(passed, ValidationResult.VALID if passed else ValidationResult.INVALID,
                                  f"Max: {max_val:,}", f"Value: {value:,}")

        return RuleValidationResult(True, ValidationResult.VALID, "No constraint")


rule_engine = RuleEngine()