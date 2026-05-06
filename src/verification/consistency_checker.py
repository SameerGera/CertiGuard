"""Consistency Checker - Cross-document entity consistency."""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum


class ConsistencyStatus(Enum):
    CONSISTENT = "consistent"
    INCONSISTENT = "inconsistent"
    MISSING = "missing"
    UNCHECKED = "unchecked"


@dataclass
class ConsistencyResult:
    passed: bool
    status: ConsistencyStatus
    message: str
    detail: Optional[str] = None


class ConsistencyChecker:
    """Cross-document consistency checker.
    
    Validates that entities are consistent across all bidder documents:
    - GSTIN must match across all documents
    - PAN must match across all documents
    - Company name must be consistent
    """
    
    def compare_values(
        self,
        value1: Optional[str],
        value2: Optional[str]
    ) -> bool:
        """Compare two values (case-insensitive, ignoring special chars)."""
        if not value1 and not value2:
            return True
        
        if not value1 or not value2:
            return False
        
        v1 = value1.strip().upper().replace(" ", "").replace("-", "").replace("_", "")
        v2 = value2.strip().upper().replace(" ", "").replace("-", "").replace("_", "")
        
        return v1 == v2
    
    def check_entity_consistency(
        self,
        entity_type: str,
        values: List[str]
    ) -> ConsistencyResult:
        """Check if entity values are consistent across documents.
        
        Args:
            entity_type: Type of entity (gstin, pan, company_name)
            values: List of values from different documents
            
        Returns:
            ConsistencyResult
        """
        if not values:
            return ConsistencyResult(
                passed=False,
                status=ConsistencyStatus.MISSING,
                message=f"No {entity_type} values found",
                detail="Cannot verify consistency - no values"
            )
        
        unique_values = set(values)
        
        if len(unique_values) == 1:
            return ConsistencyResult(
                passed=True,
                status=ConsistencyStatus.CONSISTENT,
                message=f"{entity_type.upper()} is consistent across all documents",
                detail=list(unique_values)[0]
            )
        else:
            return ConsistencyResult(
                passed=False,
                status=ConsistencyStatus.INCONSISTENT,
                message=f"{entity_type.upper()} has conflicting values",
                detail=f"Unique values: {list(unique_values)}"
            )
    
    def check_gstin_consistency(
        self,
        gstin_list: List[str]
    ) -> ConsistencyResult:
        """Check GSTIN consistency across documents.
        
        Args:
            gstin_list: List of GSTINs from different documents
            
        Returns:
            ConsistencyResult
        """
        return self.check_entity_consistency("gstin", gstin_list)
    
    def check_pan_consistency(
        self,
        pan_list: List[str]
    ) -> ConsistencyResult:
        """Check PAN consistency across documents.
        
        Args:
            pan_list: List of PANs from different documents
            
        Returns:
            ConsistencyResult
        """
        return self.check_entity_consistency("pan", pan_list)
    
    def check_name_consistency(
        self,
        name_list: List[str]
    ) -> ConsistencyResult:
        """Check company name consistency across documents.
        
        Args:
            name_list: List of company names from different documents
            
        Returns:
            ConsistencyResult
        """
        normalized_names = []
        
        for name in name_list:
            if name:
                normalized = name.strip().upper()
                for suffix in [" PRIVATE LIMITED", " PVT LTD", " LIMITED", " LTD"]:
                    normalized = normalized.replace(suffix, "")
                normalized_names.append(normalized)
        
        unique_names = set(normalized_names)
        
        if len(unique_names) == 1:
            return ConsistencyResult(
                passed=True,
                status=ConsistencyStatus.CONSISTENT,
                message="Company name is consistent",
                detail=name_list[0] if name_list else None
            )
        elif len(unique_names) <= 2:
            return ConsistencyResult(
                passed=True,
                status=ConsistencyStatus.CONSISTENT,
                message="Company name is mostly consistent",
                detail=f"Variations: {list(unique_names)}"
            )
        else:
            return ConsistencyResult(
                passed=False,
                status=ConsistencyStatus.INCONSISTENT,
                message="Company name has multiple variations",
                detail=f"Unique names: {list(unique_names)}"
            )
    
    def check_value_conflicts(
        self,
        entity_key: str,
        documents: List[Dict]
    ) -> ConsistencyResult:
        """Check for conflicts in any entity across documents.
        
        Args:
            entity_key: Key to extract from each document
            documents: List of document entity dictionaries
            
        Returns:
            ConsistencyResult
        """
        values = []
        
        for doc in documents:
            if entity_key in doc and doc[entity_key]:
                values.append(doc[entity_key])
        
        if not values:
            return ConsistencyResult(
                passed=True,
                status=ConsistencyStatus.MISSING,
                message=f"No {entity_key} found in documents",
                detail="Cannot verify - entity not present"
            )
        
        return self.check_entity_consistency(entity_key, values)
    
    def check_all_documents(
        self,
        all_entities: Dict[str, List[Any]]
    ) -> List[ConsistencyResult]:
        """Check consistency for all entity types.
        
        Args:
            all_entities: Dict of {entity_type: [values]}
            
        Returns:
            List of ConsistencyResult for each entity type
        """
        results = []
        
        if "gstin" in all_entities:
            results.append(
                self.check_gstin_consistency(all_entities["gstin"])
            )
        
        if "pan" in all_entities:
            results.append(
                self.check_pan_consistency(all_entities["pan"])
            )
        
        if "company_name" in all_entities:
            results.append(
                self.check_name_consistency(all_entities["company_name"])
            )
        
        return results
    
    def find_conflicts(
        self,
        all_entities: Dict[str, List[Any]]
    ) -> List[Dict[str, Any]]:
        """Find all conflicting entities.
        
        Args:
            all_entities: Dict of {entity_type: [values]}
            
        Returns:
            List of conflict details
        """
        conflicts = []
        
        results = self.check_all_documents(all_entities)
        
        for result in results:
            if result.status == ConsistencyStatus.INCONSISTENT:
                conflicts.append({
                    "type": "inconsistency",
                    "message": result.message,
                    "detail": result.detail
                })
        
        return conflicts


consistency_checker = ConsistencyChecker()