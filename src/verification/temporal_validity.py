"""Temporal Validity - Date parsing and expiry validation."""

import re
from typing import Optional, List
from dataclasses import dataclass
from datetime import datetime, date
from enum import Enum


class DateFormat(Enum):
    DD_MM_YYYY = "dd/mm/yyyy"
    DD_MON_YYYY = "dd-mon-yyyy"
    DD_MM_YY = "dd/mm/yy"
    MM_DD_YYYY = "mm/dd/yyyy"
    YYYY_MM_DD = "yyyy-mm-dd"


class TemporalStatus(Enum):
    VALID = "valid"
    EXPIRING_SOON = "expiring_soon"
    EXPIRED = "expired"
    INVALID = "invalid"


@dataclass
class TemporalValidationResult:
    passed: bool
    status: TemporalStatus
    message: str
    parsed_date: Optional[date] = None
    detail: Optional[str] = None


class TemporalValidator:
    """Temporal validity checker.
    
    Handles:
    - Multiple date formats
    - Expiry vs submission deadline comparison
    - Expiring within 30 days flag
    """
    
    DATE_PATTERNS = {
        DateFormat.DD_MM_YYYY: re.compile(r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})"),
        DateFormat.DD_MON_YYYY: re.compile(r"(\d{1,2})[-]([A-Za-z]{3})[-](\d{4})"),
        DateFormat.DD_MM_YY: re.compile(r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{2})"),
        DateFormat.YYYY_MM_DD: re.compile(r"(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})"),
    }
    
    MONTH_MAP = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4,
        "may": 5, "jun": 6, "jul": 7, "aug": 8,
        "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12,
    }
    
    GRACE_PERIOD_DAYS = 30
    
    def parse_date(self, date_str: str) -> Optional[date]:
        """Parse date from various formats.
        
        Supported:
        - 14/01/2026, 14-01-2026
        - 14-Jan-2026, 14-JAN-2026
        - 2026-01-14
        - 14.01.2026
        """
        if not date_str:
            return None
        
        date_clean = date_str.strip().replace(" ", "")
        
        for fmt, pattern in self.DATE_PATTERNS.items():
            match = pattern.match(date_clean)
            if match:
                groups = match.groups()
                
                if fmt == DateFormat.DD_MM_YYYY:
                    day, month, year = int(groups[0]), int(groups[1]), int(groups[2])
                elif fmt == DateFormat.DD_MON_YYYY:
                    day = int(groups[0])
                    month = self.MONTH_MAP.get(groups[1].lower(), 0)
                    year = int(groups[2])
                elif fmt == DateFormat.DD_MM_YY:
                    day, month, year = int(groups[0]), int(groups[1]), int(groups[2])
                    year = 2000 + year if year < 100 else year
                elif fmt == DateFormat.YYYY_MM_DD:
                    year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
                else:
                    continue
                
                if 1 <= day <= 31 and 1 <= month <= 12 and 1900 <= year <= 2100:
                    try:
                        return date(year, month, day)
                    except ValueError:
                        continue
        
        return None
    
    def validate_expiry(
        self,
        expiry_date: date,
        submission_deadline: date
    ) -> TemporalValidationResult:
        """Validate certificate expiry against submission deadline.
        
        Statuses:
        - VALID: expiry_date > submission_deadline + 30 days
        - EXPIRING_SOON: expiry within 30 days of deadline
        - EXPIRED: expiry <= submission_deadline
        """
        if expiry_date is None or submission_deadline is None:
            return TemporalValidationResult(
                passed=False,
                status=TemporalStatus.INVALID,
                message="Date is missing",
                parsed_date=None,
                detail="expiry_date or submission_deadline is None"
            )
        
        days_until_expiry = (expiry_date - submission_deadline).days
        
        if days_until_expiry < 0:
            return TemporalValidationResult(
                passed=False,
                status=TemporalStatus.EXPIRED,
                message=f"Certificate expired {abs(days_until_expiry)} days before submission",
                parsed_date=expiry_date,
                detail=f"Expiry: {expiry_date}, Deadline: {submission_deadline}"
            )
        elif days_until_expiry <= self.GRACE_PERIOD_DAYS:
            return TemporalValidationResult(
                passed=True,
                status=TemporalStatus.EXPIRING_SOON,
                message=f"Certificate expiring in {days_until_expiry} days (within grace period)",
                parsed_date=expiry_date,
                detail=f"Expires: {expiry_date}, Grace: {self.GRACE_PERIOD_DAYS} days"
            )
        else:
            return TemporalValidationResult(
                passed=True,
                status=TemporalStatus.VALID,
                message=f"Certificate valid for {days_until_expiry} days",
                parsed_date=expiry_date,
                detail=f"Expiry: {expiry_date}, Deadline: {submission_deadline}"
            )
    
    def validate_issue_date(
        self,
        issue_date: date,
        submission_deadline: date
    ) -> TemporalValidationResult:
        """Validate certificate issue date is before submission.
        
        Issue date must be before submission deadline.
        """
        if issue_date is None or submission_deadline is None:
            return TemporalValidationResult(
                passed=False,
                status=TemporalStatus.INVALID,
                message="Date is missing",
                parsed_date=None,
                detail="issue_date or submission_deadline is None"
            )
        
        days_since_issue = (submission_deadline - issue_date).days
        
        if days_since_issue < 0:
            return TemporalValidationResult(
                passed=False,
                status=TemporalStatus.INVALID,
                message="Issue date is after submission deadline",
                parsed_date=issue_date,
                detail=f"Issue: {issue_date}, Deadline: {submission_deadline}"
            )
        else:
            return TemporalValidationResult(
                passed=True,
                status=TemporalStatus.VALID,
                message=f"Issued {days_since_issue} days before deadline",
                parsed_date=issue_date,
                detail=f"Issue: {issue_date}, Deadline: {submission_deadline}"
            )
    
    def check_financial_year(
        self,
        document_date: date,
        fy_start_year: int
    ) -> bool:
        """Check if document falls within financial year.
        
        Indian FY: April - March
        FY 2023-24: Apr 2023 - Mar 2024
        """
        fy_start = date(fy_start_year, 4, 1)
        fy_end = date(fy_start_year + 1, 3, 31)
        
        return fy_start <= document_date <= fy_end
    
    def parse_fy_format(self, fy_str: str) -> Optional[tuple]:
        """Parse financial year string.
        
        "FY 2023-24" -> (2023, 2024)
        "FY24" -> (2023, 2024)
        """
        if not fy_str:
            return None
        
        fy_str = fy_str.strip().upper()
        
        match = re.search(r"FY\s*(\d{2,4})[-/]?(\d{2,4})?", fy_str)
        if match:
            start = int(match.group(1))
            end = int(match.group(2)) if match.group(2) else start + 1
            
            if start < 100:
                start += 2000
            if end < 100:
                end = start + 1
                
            return (start, end)
        
        match = re.search(r"FY\s*(\d{2})", fy_str)
        if match:
            year = int(match.group(1))
            year = 2000 + year if year < 100 else year
            return (year, year + 1)
        
        return None
    
    def validate_temporal_scope(
        self,
        document_date: date,
        reference_date: date,
        scope: str
    ) -> TemporalValidationResult:
        """Validate document is within temporal scope.
        
        Args:
            document_date: Date from document
            reference_date: Reference date (usually submission deadline)
            scope: "LAST_5_YEARS", "LAST_3_YEARS", or None
            
        Returns:
            TemporalValidationResult
        """
        if scope is None:
            return TemporalValidationResult(
                passed=True,
                status=TemporalStatus.VALID,
                message="No temporal scope constraint",
                parsed_date=document_date
            )
        
        years_back = 0
        if scope == "LAST_5_YEARS":
            years_back = 5
        elif scope == "LAST_3_YEARS":
            years_back = 3
        else:
            return TemporalValidationResult(
                passed=False,
                status=TemporalStatus.INVALID,
                message=f"Unknown temporal scope: {scope}",
                parsed_date=document_date
            )
        
        from datetime import timedelta
        cutoff_date = reference_date - timedelta(days=years_back * 365)
        
        if document_date >= cutoff_date:
            return TemporalValidationResult(
                passed=True,
                status=TemporalStatus.VALID,
                message=f"Within last {years_back} years",
                parsed_date=document_date,
                detail=f"Document: {document_date}, Cutoff: {cutoff_date}"
            )
        else:
            return TemporalValidationResult(
                passed=False,
                status=TemporalStatus.INVALID,
                message=f"Older than {years_back} years",
                parsed_date=document_date,
                detail=f"Document: {document_date}, Cutoff: {cutoff_date}"
            )


temporal_validator = TemporalValidator()