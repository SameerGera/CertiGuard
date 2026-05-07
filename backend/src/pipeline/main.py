"""Pipeline orchestration - actual processing."""

import os
import re
import json
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.verification.rule_engine import RuleEngine, ValidationResult
from src.verification.identity_binding import IdentityBinder
from src.verification.temporal_validity import TemporalValidator
from src.verdict.yellow_flag import YellowFlagGenerator
from src.extraction.entity_extractor import EntityExtractor as EnhancedEntityExtractor


@dataclass
class PipelineConfig:
    tender_id: str
    tender_path: str
    bidders_dir: str
    output_dir: str
    max_file_size_mb: int = 100
    vlm_timeout: int = 60


@dataclass
class ExtractedEntity:
    entity_type: str
    value: str
    normalized_value: Optional[str]
    confidence: float


@dataclass
class BidderDocument:
    bidder_id: str
    bidder_name: str
    files: List[str]
    extracted_entities: List[ExtractedEntity]
    ocr_text: str


class OCRProcessor:
    """OCR using pdfplumber - text-based extraction with scanned doc detection."""

    def extract_text(self, file_path: str) -> str:
        """Extract text from PDF using pdfplumber."""
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                text = ""
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += "\n" + page_text
                return text.strip()
        except Exception as e:
            print(f"[OCR] Failed to extract {file_path}: {e}")
            return ""

    def is_scanned_document(self, file_path: str) -> bool:
        """Detect if PDF is a scanned document (no extractable text)."""
        text = self.extract_text(file_path)
        if not text or len(text.strip()) < 10:
            return True
        return False


class EntityExtractor:
    """Extract entities from OCR text using regex patterns."""

    GSTIN_PATTERN = re.compile(r'[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[0-9]{1}[A-Z]{1}', re.IGNORECASE)
    PAN_PATTERN = re.compile(r'[A-Z]{5}[0-9]{4}[A-Z]{1}', re.IGNORECASE)
    AMOUNT_PATTERN = re.compile(r'Rs\.?\s*([\d,]+(?:\.\d+)?)\s*(Lakhs?|L|l|Cr|cr|Million|M)?', re.IGNORECASE)
    DATE_PATTERN = re.compile(r'(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})')
    YEARS_PATTERN = re.compile(r'(\d+)\s+(?:years?|yrs?|years\s+of)', re.IGNORECASE)

    def extract(self, text: str) -> List[ExtractedEntity]:
        entities = []

        # Extract GSTIN
        for match in self.GSTIN_PATTERN.findall(text):
            entities.append(ExtractedEntity(
                entity_type="gstin",
                value=match.upper(),
                normalized_value=match.upper(),
                confidence=0.9
            ))

        # Extract PAN
        for match in self.PAN_PATTERN.findall(text):
            entities.append(ExtractedEntity(
                entity_type="pan",
                value=match.upper(),
                normalized_value=match.upper(),
                confidence=0.9
            ))

        # Extract amounts (turnover)
        for match in self.AMOUNT_PATTERN.findall(text):
            amount_str = match[0].replace(',', '')
            multiplier = 1
            if match[1].lower() in ['lakh', 'lac', 'l']:
                multiplier = 100000
            elif match[1].lower() in ['crore', 'cr', 'c']:
                multiplier = 10000000
            elif match[1].lower() in ['million', 'm']:
                multiplier = 1000000
            try:
                value = int(float(amount_str) * multiplier)
                entities.append(ExtractedEntity(
                    entity_type="turnover",
                    value=f"Rs. {match[0]} {match[1]}",
                    normalized_value=str(value),
                    confidence=0.85
                ))
            except (ValueError, TypeError) as e:
                print(f"[EntityExtractor] Failed to parse amount '{match}': {e}")

        # Extract years of experience
        for match in self.YEARS_PATTERN.findall(text):
            entities.append(ExtractedEntity(
                entity_type="experience_years",
                value=f"{match} years",
                normalized_value=match,
                confidence=0.8
            ))

        return entities


class CertiGuardPipeline:
    """Main pipeline orchestrator."""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.ocr = OCRProcessor()
        self.entity_extractor = EnhancedEntityExtractor()
        self.rule_engine = RuleEngine()
        self.identity_binder = IdentityBinder()
        self.temporal_validator = TemporalValidator()

        os.makedirs(config.output_dir, exist_ok=True)

    def run(self) -> Dict[str, Any]:
        """Run the full pipeline."""
        print(f"[Pipeline] Starting for tender: {self.config.tender_id}")

        # Load tender criteria
        tender_criteria = self._load_tender_criteria()

        # Process each bidder - handle both folder and flat file structures
        bidders_results = []
        all_entities = {}

        # Check if bidders are in subfolders or flat files with prefix
        bidder_dirs = [d for d in Path(self.config.bidders_dir).iterdir() if d.is_dir()]

        if not bidder_dirs:
            # Flat files - group by bidder ID prefix (e.g., B001_gst.pdf, B001_pan.pdf)
            files = list(Path(self.config.bidders_dir).glob("*.pdf"))
            bidder_ids = sorted(set(f.stem.split('_')[0] for f in files))

            for bidder_id in bidder_ids:
                print(f"[Pipeline] Processing bidder: {bidder_id}")

                # Get all files for this bidder
                bidder_files = [f for f in files if f.stem.startswith(bidder_id)]
                bidder_name = self._extract_bidder_name_from_files(bidder_files)

                extracted_entities = []
                all_text = ""

                entity_types = ['gstin', 'gst_number', 'pan', 'pan_number', 'turnover', 
                               'experience_years', 'years_of_experience', 'certification', 
                               'company_name', 'email', 'phone']

                for pdf_file in bidder_files:
                    text = self.ocr.extract_text(str(pdf_file))
                    entities = self.entity_extractor.extract_entities(text, entity_types)
                    extracted_entities.extend(entities)
                    all_text += "\n" + text

                # Debug: print extracted entities
                print(f"[Debug] Bidder {bidder_id} entities: {[(e.entity_type, e.value) for e in extracted_entities]}")

                # Verify and generate verdict
                criterion_results = self._verify_bidder(
                    bidder_id, extracted_entities, tender_criteria, all_text
                )

                verdicts = [r['verdict'] for r in criterion_results]
                if 'NOT_ELIGIBLE' in verdicts:
                    overall = 'NOT_ELIGIBLE'
                elif 'NEEDS_REVIEW' in verdicts:
                    overall = 'NEEDS_REVIEW'
                else:
                    overall = 'ELIGIBLE'

                avg_conf = sum((r['ai_confidence'] for r in criterion_results), 0) / len(criterion_results) if criterion_results else 0

                bidders_results.append({
                    'bidder_id': bidder_id,
                    'bidder_name': bidder_name,
                    'criterion_results': criterion_results,
                    'overall_verdict': overall,
                    'overall_confidence': round(avg_conf, 2),
                    'verdict_reason': f"Reviewed {len(criterion_results)} criteria"
                })
        else:
            # Subfolder structure
            for bidder_dir in bidder_dirs:
                bidder_id = bidder_dir.name
                print(f"[Pipeline] Processing bidder: {bidder_id}")

                bidder_name = self._extract_bidder_name(bidder_dir)

                extracted_entities = []
                all_text = ""

                for pdf_file in bidder_dir.glob("*.pdf"):
                    text = self.ocr.extract_text(str(pdf_file))
                    entities = self.entity_extractor.extract_entities(text, [])
                    extracted_entities.extend(entities)
                    all_text += "\n" + text

                all_entities[bidder_id] = extracted_entities

                # Verify and generate verdict
                criterion_results = self._verify_bidder(
                    bidder_id, extracted_entities, tender_criteria, all_text
                )

                # Determine overall verdict
                verdicts = [r['verdict'] for r in criterion_results]
                if 'NOT_ELIGIBLE' in verdicts:
                    overall = 'NOT_ELIGIBLE'
                elif 'NEEDS_REVIEW' in verdicts:
                    overall = 'NEEDS_REVIEW'
                else:
                    overall = 'ELIGIBLE'

                avg_conf = sum((r['ai_confidence'] for r in criterion_results), 0) / len(criterion_results) if criterion_results else 0

                bidders_results.append({
                    'bidder_id': bidder_id,
                    'bidder_name': bidder_name,
                    'criterion_results': criterion_results,
                    'overall_verdict': overall,
                    'overall_confidence': round(avg_conf, 2),
                    'verdict_reason': f"Reviewed {len(criterion_results)} criteria"
                })

        # Generate yellow flag summary
        yellow_flags = []
        for br in bidders_results:
            for cr in br['criterion_results']:
                if cr.get('yellow_flags'):
                    yellow_flags.extend(cr['yellow_flags'])

        summary = {
            'total': len(yellow_flags),
            'by_type': {}
        }
        for yf in yellow_flags:
            t = yf.get('trigger_type', 'unknown')
            summary['by_type'][t] = summary['by_type'].get(t, 0) + 1

        # Save results
        result = {
            'tender_id': self.config.tender_id,
            'tender_name': tender_criteria.get('name', 'Unknown'),
            'submission_deadline': tender_criteria.get('deadline', ''),
            'criteria': tender_criteria.get('criteria', []),
            'criteria_approved': False,
            'sign_off': None,
            'bidders': bidders_results,
            'audit_records': [],
            'yellow_flag_summary': summary,
            'processed_at': datetime.now().isoformat()
        }

        output_file = os.path.join(self.config.output_dir, f"{self.config.tender_id}_results.json")
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)

        print(f"[Pipeline] Results saved to: {output_file}")
        return result

    def _load_tender_criteria(self) -> Dict[str, Any]:
        """Load tender criteria - either from file or use defaults."""
        tender_file = os.path.join(self.config.tender_path)
        
        # Check if we have a real tender PDF to parse
        if os.path.exists(tender_file):
            try:
                text = self.ocr.extract_text(tender_file)
                if text:
                    parsed_criteria = self._parse_tender_criteria(text)
                    if parsed_criteria:
                        return parsed_criteria
            except Exception as e:
                print(f"[TenderParser] Failed to parse tender: {e}")
        
        # Fallback to defaults
        tender_name_map = {
            'T001': 'CRPF Uniform Supply 2026',
            'T002': 'CRPF Security Services 2026',
            'T003': 'CRPF IT Equipment 2026',
        }
        return {
            'name': tender_name_map.get(self.config.tender_id, f'Tender {self.config.tender_id}'),
            'deadline': '2026-12-31',
            'criteria': [
                {'id': 'C001', 'label': 'Valid GST Registration', 'type': 'compliance', 'nature': 'MANDATORY'},
                {'id': 'C002', 'label': 'Minimum Experience', 'type': 'technical', 'nature': 'MANDATORY'},
                {'id': 'C003', 'label': 'Annual Turnover', 'type': 'financial', 'nature': 'DESIRABLE'},
                {'id': 'C004', 'label': 'Quality Certification', 'type': 'compliance', 'nature': 'DESIRABLE'},
            ]
        }

    def _parse_tender_criteria(self, text: str) -> Dict[str, Any]:
        """Parse eligibility criteria from tender document text."""
        criteria = []
        criterion_id = 1
        
        # Extract tender name
        name_match = re.search(r'Tender[:\s]+(.+?)(?:\n|$)', text, re.IGNORECASE)
        name = name_match.group(1).strip() if name_match else "Tender Document"
        
        # Extract deadline
        deadline_match = re.search(r'(?:submission\s+)?deadline[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', text, re.IGNORECASE)
        deadline = deadline_match.group(1) if deadline_match else ""
        
        # Patterns for different criteria types
        patterns = {
            'FINANCIAL': [
                (r'turnover[:\s]+(?:₹|Rs\.?)\s*(\d+(?:\.\d+)?)\s*(Lakh|Lakhs?|L|l|Crore|Cr|cr|Million|M)', 'Annual Turnover', 'MANDATORY'),
                (r'minimum\s+turnover[:\s]+(?:₹|Rs\.?)\s*(\d+(?:\.\d+)?)\s*(Lakh|Lakhs?|L|l|Crore|Cr|cr)', 'Minimum Turnover', 'MANDATORY'),
                (r'annual\s+turnover[:\s]+(?:₹|Rs\.?)\s*(\d+(?:\.\d+)?)\s*(Lakh|Lakhs?|L|l|Crore|Cr|cr)', 'Annual Turnover', 'DESIRABLE'),
            ],
            'EXPERIENCE': [
                (r'(\d+)\s+(?:years?|yrs?)\s+(?:of\s+)?experience', 'Years of Experience', 'MANDATORY'),
                (r'minimum\s+(\d+)\s+(?:years?|yrs?)\s+(?:of\s+)?experience', 'Minimum Experience', 'MANDATORY'),
                (r'experience[:\s]+(\d+)\s+(?:years?|yrs?)', 'Experience', 'MANDATORY'),
            ],
            'CERTIFICATION': [
                (r'GST(?:IN)?\s+registration', 'Valid GST Registration', 'MANDATORY'),
                (r'GST\s+Certificate', 'GST Certificate', 'MANDATORY'),
                (r'ISO\s+(\d+)(?::\d+)?', 'ISO Certification', 'MANDATORY'),
                (r'PAN\s+(?:Card)?', 'Valid PAN', 'MANDATORY'),
            ]
        }
        
        # Find financial criteria
        for pattern, label, nature in patterns['FINANCIAL']:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                value = match.group(1) if match.lastindex >= 1 else ""
                unit = match.group(2) if match.lastindex >= 2 else ""
                criteria.append({
                    'id': f'C{str(criterion_id).zfill(3)}',
                    'label': f'{label} above {value} {unit}' if value else label,
                    'type': 'FINANCIAL',
                    'nature': nature,
                    'threshold': value,
                    'unit': unit
                })
                criterion_id += 1
        
        # Find experience criteria
        for pattern, label, nature in patterns['EXPERIENCE']:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                years = match.group(1) if match.lastindex >= 1 else ""
                criteria.append({
                    'id': f'C{str(criterion_id).zfill(3)}',
                    'label': f'Minimum {years} Years Experience',
                    'type': 'EXPERIENCE',
                    'nature': nature,
                    'threshold': int(years) if years else 0
                })
                criterion_id += 1
        
        # Find certification criteria
        for pattern, label, nature in patterns['CERTIFICATION']:
            if re.search(pattern, text, re.IGNORECASE):
                criteria.append({
                    'id': f'C{str(criterion_id).zfill(3)}',
                    'label': label,
                    'type': 'CERTIFICATION',
                    'nature': nature
                })
                criterion_id += 1
        
        if not criteria:
            return None
        
        return {
            'name': name,
            'deadline': deadline,
            'criteria': criteria
        }

    def _extract_bidder_name(self, bidder_dir: Path) -> str:
        """Extract bidder name from folder or files."""
        # Try to find name in filenames
        for f in bidder_dir.glob("*_gst.pdf"):
            text = self.ocr.extract_text(str(f))
            # Look for company name pattern
            match = re.search(r'Company Name:\s*(.+)', text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return f"Bidder {bidder_dir.name}"

    def _extract_bidder_name_from_files(self, bidder_files: List[Path]) -> str:
        """Extract bidder name from flat file list."""
        for f in bidder_files:
            if '_gst' in f.stem:
                text = self.ocr.extract_text(str(f))
                match = re.search(r'Company Name:\s*(.+)', text, re.IGNORECASE)
                if match:
                    return match.group(1).strip()
        return "Unknown Bidder"

    def _validate_all_entities(self, entities: List[ExtractedEntity]) -> Dict[str, Dict]:
        """Validate all extracted entities."""
        validations = {}
        
        for entity in entities:
            is_valid, message = self.entity_extractor.validate_entity(entity)
            validations[entity.entity_type] = {
                'is_valid': is_valid,
                'message': message,
                'value': entity.value
            }
        
        return validations

    def _verify_bidder(self, bidder_id: str, entities: List[ExtractedEntity],
                       tender_criteria: Dict, ocr_text: str) -> List[Dict]:
        """Verify bidder against criteria."""
        
        entity_validations = self._validate_all_entities(entities)
        
        results = []

        for criterion in tender_criteria.get('criteria', []):
            criterion_id = criterion['id']
            criterion_label = criterion['label']
            criterion_type = criterion['type']
            criterion_nature = criterion['nature']

            checks = []
            yellow_flags = None
            verdict = 'ELIGIBLE'
            confidence = 0.95
            reason = ''

            if criterion_id == 'C001':  # GST Registration
                gst_entities = [e for e in entities if e.entity_type in ['gstin', 'gst_number']]
                if not gst_entities:
                    verdict = 'NOT_ELIGIBLE'
                    confidence = 0.9
                    reason = 'No GSTIN found in documents'
                else:
                    gst = gst_entities[0]
                    result = self.rule_engine.validate_gstin(gst.value)
                    checks.append({
                        'check_name': 'GSTIN Format',
                        'passed': result.passed,
                        'detail': result.message,
                        'confidence': result.confidence if hasattr(result, 'confidence') else 0.9
                    })
                    
                    gst_validation = entity_validations.get('gstin', {})
                    if gst_validation:
                        checks.append({
                            'check_name': 'Entity Validation',
                            'passed': gst_validation.get('is_valid', True),
                            'detail': gst_validation.get('message', 'Valid'),
                            'confidence': 0.9
                        })
                    
                    if not result.passed:
                        verdict = 'NOT_ELIGIBLE'
                        confidence = 0.9
                        reason = result.message

                    if 'expired' in ocr_text.lower() or 'expired' in gst.value.lower():
                        verdict = 'NOT_ELIGIBLE'
                        confidence = 0.95
                        reason = 'GST registration expired'
                        checks[0]['passed'] = False
                        checks[0]['detail'] = 'GST registration expired'

            elif criterion_id == 'C002':  # Experience
                exp_entities = [e for e in entities if e.entity_type == 'experience_years']
                if not exp_entities:
                    verdict = 'NEEDS_REVIEW'
                    confidence = 0.5
                    reason = 'No experience information found'
                    yellow_flags = [{
                        'trigger_type': 'INCOMPLETE_EVIDENCE',
                        'reason': 'Experience certificate not found or unclear',
                        'affected_entity': 'experience_years',
                        'confidence_delta': -0.3
                    }]
                else:
                    years = int(exp_entities[0].normalized_value or 0)
                    if years >= 3:
                        reason = f'Experience verified: {years} years'
                        confidence = 0.85
                        if years == 3:
                            confidence = 0.7
                            verdict = 'NEEDS_REVIEW'
                            yellow_flags = [{
                                'trigger_type': 'AMBIGUOUS_VALUE',
                                'reason': 'Exactly 3 years - borderline case',
                                'affected_entity': 'experience_years',
                                'confidence_delta': -0.2
                            }]
                    else:
                        verdict = 'NOT_ELIGIBLE'
                        confidence = 0.9
                        reason = f'Only {years} years, need minimum 3'

                    checks.append({
                        'check_name': 'Experience Years',
                        'passed': verdict != 'NOT_ELIGIBLE',
                        'detail': f'{years} years verified',
                        'confidence': confidence
                    })
                    
                    exp_validation = entity_validations.get('experience_years')
                    if exp_validation:
                        checks.append({
                            'check_name': 'Entity Validation',
                            'passed': exp_validation.get('is_valid', True),
                            'detail': exp_validation.get('message', 'Valid'),
                            'confidence': 0.85
                        })

            if criterion_id == 'C003':  # Turnover
                turnover_entities = [e for e in entities if e.entity_type == 'turnover']
                is_mandatory = criterion_nature == 'MANDATORY'
                
                if not turnover_entities:
                    if is_mandatory:
                        verdict = 'NEEDS_REVIEW'
                        confidence = 0.5
                        reason = 'No turnover documents found - mandatory criterion requires verification'
                        yellow_flags = [{
                            'trigger_type': 'MISSING_MANDATORY_FIELD',
                            'reason': 'Turnover documents not found or unclear',
                            'affected_entity': 'turnover',
                            'confidence_delta': -0.3
                        }]
                    else:
                        verdict = 'ELIGIBLE'
                        confidence = 0.6
                        reason = 'No turnover documents found - optional criterion'
                    checks.append({
                        'check_name': 'Turnover Validation',
                        'passed': not is_mandatory,
                        'detail': 'Not provided' + (' (mandatory)' if is_mandatory else ' (optional)'),
                        'confidence': 0.5 if is_mandatory else 0.6
                    })
                else:
                    # Pick the turnover with highest value
                    valid_turnovers = []
                    for te in turnover_entities:
                        try:
                            val = int(te.normalized_value.replace(",", "") or 0)
                            if val > 1000:
                                valid_turnovers.append((val, te))
                        except (ValueError, TypeError, AttributeError) as e:
                            print(f"[Pipeline] Failed to parse turnover value: {e}")
                    
                    if not valid_turnovers:
                        verdict = 'NEEDS_REVIEW'
                        confidence = 0.5
                        reason = 'Turnover value not properly extracted'
                        checks.append({
                            'check_name': 'Turnover Validation',
                            'passed': False,
                            'detail': 'Extraction failed - requires manual review',
                            'confidence': 0.5
                        })
                    else:
                        valid_turnovers.sort(key=lambda x: x[0], reverse=True)
                        amount = valid_turnovers[0][0]
                        
                        threshold = 50 * 100000
                        if amount >= threshold:
                            reason = f'Turnover verified: Rs. {amount/100000:.1f} Lakhs'
                            confidence = 0.85
                            checks.append({
                                'check_name': 'Turnover Validation',
                                'passed': True,
                                'detail': reason,
                                'confidence': confidence
                            })
                        else:
                            verdict = 'NEEDS_REVIEW'
                            confidence = 0.6
                            reason = f'Turnover Rs. {amount/100000:.1f}L below 50L threshold'
                            yellow_flags = [{
                                'trigger_type': 'BELOW_THRESHOLD',
                                'reason': f'Turnover Rs. {amount/100000:.1f}L below 50L threshold',
                                'affected_entity': 'turnover',
                                'confidence_delta': -0.25
                            }]
                            checks.append({
                                'check_name': 'Turnover Validation',
                                'passed': False,
                                'detail': reason,
                                'confidence': confidence
                            })
                    
                    if turnover_entities:
                        turnover_validation = entity_validations.get('turnover')
                        if turnover_validation:
                            checks.append({
                                'check_name': 'Entity Validation',
                                'passed': turnover_validation.get('is_valid', True),
                                'detail': turnover_validation.get('message', 'Valid'),
                                'confidence': 0.85
                            })

            # Default verdict for missing critical info
            if verdict == 'ELIGIBLE' and not checks:
                verdict = 'NEEDS_REVIEW'
                confidence = 0.5
                reason = 'Unable to verify - requires manual review'

            results.append({
                'criterion_id': criterion_id,
                'criterion_label': criterion_label,
                'verdict': verdict,
                'ai_confidence': confidence,
                'verification_checks': checks,
                'yellow_flags': yellow_flags,
                'evidence_refs': [e.entity_type for e in entities],
                'reason': reason
            })

        return results


def run_pipeline(tender_id: str, tender_path: str, bidders_dir: str, output_dir: str):
    """Run the pipeline."""
    config = PipelineConfig(
        tender_id=tender_id,
        tender_path=tender_path,
        bidders_dir=bidders_dir,
        output_dir=output_dir
    )
    pipeline = CertiGuardPipeline(config)
    return pipeline.run()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CertiGuard Pipeline")
    parser.add_argument("--tender-id", required=True, help="Tender ID")
    parser.add_argument("--tender-path", required=True, help="Path to tender PDF")
    parser.add_argument("--bidders-dir", required=True, help="Path to bidders folder")
    parser.add_argument("--output-dir", required=True, help="Output directory")

    args = parser.parse_args()

    result = run_pipeline(args.tender_id, args.tender_path, args.bidders_dir, args.output_dir)
    print("\n=== RESULT ===")
    print(json.dumps(result, indent=2))