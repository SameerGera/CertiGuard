export interface CriterionOutput {
  id: string
  label: string
  nature: 'MANDATORY' | 'DESIRABLE' | 'OPTIONAL'
  type: 'FINANCIAL' | 'CERTIFICATION' | 'EXPERIENCE'
  canonical_entities: string[]
  threshold: { value: number; unit: string; operator: string } | null
  aggregation: string
  temporal_scope: string | null
  confidence: number
  raw_text: string
  source_page: number
}

export interface ExtractedEntity {
  entity_type: string
  value: string
  normalized_value: string | null
  bounding_box: number[] | null
  confidence: number
}

export interface EvidenceSegment {
  segment_id: string
  file_name: string
  file_hash: string
  page_number: number
  segment_text: string
  extracted_entities: ExtractedEntity[]
  ocr_confidence: number
  extraction_method: string
}

export interface BidderEvidence {
  bidder_id: string
  bidder_name: string
  documents: { file_name: string; file_hash: string }[]
  evidence_segments: EvidenceSegment[]
}

export interface MLLOutput {
  tender_id: string
  tender_name: string
  submission_deadline: string
  criteria: CriterionOutput[]
  bidder_evidence: BidderEvidence[]
  processing_metadata: Record<string, unknown>
}

export interface VerificationCheck {
  check_name: string
  passed: boolean
  detail: string
  confidence: number | null
}

export interface YellowFlag {
  trigger_type: string
  reason: string
  affected_entity: string
  confidence_delta: number
}

export interface CriterionResult {
  criterion_id: string
  criterion_label: string
  verdict: 'ELIGIBLE' | 'NOT_ELIGIBLE' | 'NEEDS_REVIEW'
  ai_confidence: number
  verification_checks: VerificationCheck[]
  yellow_flags: YellowFlag[] | null
  evidence_refs: string[]
  reason: string
  override?: {
    officer_id: string
    officer_name: string
    rationale: string
    signature: string
    timestamp: string
  }
}

export interface BidderResult {
  bidder_id: string
  bidder_name: string
  criterion_results: CriterionResult[]
  overall_verdict: 'ELIGIBLE' | 'NOT_ELIGIBLE' | 'NEEDS_REVIEW'
  overall_confidence: number
  verdict_reason: string
}

export interface HumanOverride {
  applied: boolean
  officer_id: string
  officer_name: string
  override_verdict: string
  rationale: string
  signature: string
  timestamp: string
}

export interface AuditRecordEntry {
  record_id: string
  timestamp: string
  tender_id: string
  criterion_id: string
  bidder_id: string
  ai_verdict: string
  ai_confidence: number
  verification_checks: VerificationCheck[]
  yellow_flags: YellowFlag[] | null
  human_override: HumanOverride | null
  merkle_hash: string
}

export interface VerdictOutput {
  tender_id: string
  tender_name: string
  bidders: BidderResult[]
  audit_records: AuditRecordEntry[]
  yellow_flag_summary: { total: number; by_type: Record<string, number> }
}

export interface HumanOverrideInput {
  criterion_id: string
  bidder_id: string
  override_verdict: 'ELIGIBLE' | 'NOT_ELIGIBLE'
  officer_id: string
  officer_name: string
  rationale: string
  signature: string
}