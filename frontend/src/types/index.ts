export interface MaterialItem {
  id: string;
  item_code: string;
  raw_description: string;
  standardized_name?: string;
  category: string;
  unit_of_measure: string;
  source_psu: string;
  status: 'Standardized' | 'Pending Review' | 'Under Approval' | 'Flagged';
  created_at: string;
}

export interface MatchCandidate {
  pair_id: string;
  confidence_score: number;
  classification: 'HIGH_CONFIDENCE_DUPLICATE' | 'AMBIGUOUS_REQUIRES_REVIEW' | 'LOW_SIMILARITY';
  item_incoming: {
    code: string;
    description: string;
    source_entity: string;
    unit: string;
    price_inr: number;
  };
  item_master_candidate: {
    code: string;
    description: string;
    source_entity: string;
    unit: string;
    price_inr: number;
  };
  similarity_breakdown: {
    rapidfuzz_token_set_ratio: number;
    vector_cosine_similarity: number;
    attribute_dimension_match: string;
    material_grade_match: string;
  };
  shap_key_features: Array<{
    feature: string;
    impact: string;
  }>;
  suggested_action: string;
}

export interface ApprovalItem {
  id: string;
  material_code: string;
  proposed_name: string;
  category: string;
  initiator: string;
  tier: string;
  status: string;
  risk_rating: 'LOW' | 'MEDIUM' | 'HIGH';
  estimated_annual_saving_inr: number;
  submission_date: string;
}

export interface AuditLogItem {
  log_id: string;
  timestamp: string;
  actor: string;
  action: string;
  target_entity: string;
  details: string;
  ai_confidence_snapshot: number | null;
  verification_tier: string;
  hash_signature: string;
}

export interface SystemHealth {
  status: string;
  service: string;
  version: string;
  environment: string;
  timestamp: string;
  database_target: string;
  ai_pipeline_status: Record<string, string>;
}

export interface PreviewRowError {
  row_number: number;
  item_code?: string;
  raw_data: Record<string, any>;
  reason: string;
}

export interface PreviewSummary {
  file_name: string;
  total_rows: number;
  valid_records_count: number;
  invalid_records_count: number;
  detected_columns_count: number;
  mapped_columns_count: number;
  source_cpse_detected?: string;
  source_system_detected?: string;
}

export interface PreviewRecord {
  id: string;
  source_cpse: string;
  source_system: string;
  source_material_code: string;
  raw_description: string;
  cleaned_description?: string;
  standard_description?: string;
  category: string;
  sub_category: string;
  material_type?: string;
  material_grade?: string;
  manufacturer?: string;
  part_number?: string;
  model_number?: string;
  uom: string;
  attributes: Record<string, any>;
  normalized_tokens: string[];
  match_status: string;
  approval_status: string;
  created_at: string;
  updated_at: string;
}

export type CanonicalSourceMaterial = PreviewRecord;

export interface CSVPreviewResponseData {
  success: boolean;
  message: string;
  summary: PreviewSummary;
  detected_columns: string[];
  mapped_columns: Record<string, string>;
  valid_records: PreviewRecord[];
  invalid_rows: PreviewRowError[];
}

export interface TextNormalizationResult {
  raw_description: string;
  cleaned_description: string;
  standard_description: string;
  normalized_uom: string;
  normalized_category: string;
  normalized_tokens: string[];
}

export interface AttributeExtractionPayload {
  raw_description: string;
  category?: string;
  uom?: string;
}

export interface AttributeExtractionResult {
  raw_description: string;
  standard_description: string;
  inferred_category: string;
  extracted_attributes: Record<string, any>;
  missing_critical_attributes: string[];
  extraction_confidence: number;
  extraction_notes: string[];
}

export interface MatchingSignal {
  signal_type: string;
  description: string;
  score: number;
  weight: number;
}

export interface ConflictSignal {
  attribute: string;
  value_a: any;
  value_b: any;
  severity: 'CRITICAL' | 'MODERATE' | 'LOW' | string;
  description: string;
}

export interface CandidateScoreBreakdown {
  description_similarity: number;
  attribute_similarity: number;
  token_overlap: number;
  category_compatibility: number;
  uom_compatibility: number;
  mfg_part_compatibility: number;
  final_score: number;
}

export type CandidateClassification =
  | 'HIGH_CONFIDENCE_DUPLICATE'
  | 'POSSIBLE_DUPLICATE'
  | 'LOW_CONFIDENCE_REVIEW'
  | 'NOT_INCLUDED';

export interface CandidateMatchResult {
  pair_id: string;
  source_material_a: PreviewRecord;
  source_material_b: PreviewRecord;
  score: number;
  classification: CandidateClassification;
  score_breakdown: CandidateScoreBreakdown;
  matching_signals: MatchingSignal[];
  conflict_signals: ConflictSignal[];
  recommendation: string;
  semantic_similarity_score?: number;
  semantic_method?: string;
}

export interface CandidateMatchResponse {
  total_records: number;
  compared_pairs: number;
  candidate_count: number;
  candidates: CandidateMatchResult[];
}

export interface EmbeddingMetadata {
  dimensions: number;
  method: string;
  vector_preview_first_8_values: number[];
  l2_normalized: boolean;
  pgvector_ready: boolean;
  model_target: string;
  note: string;
}

export interface EmbeddingResponse {
  input_text: string;
  normalized_embedding_text: string;
  dimensions: number;
  vector_preview_first_8_values: number[];
  metadata: EmbeddingMetadata;
  note: string;
}

export interface SemanticSimilarityResponse {
  material_a_text: string;
  material_b_text: string;
  semantic_similarity_score: number;
  interpretation: string;
  embedding_method: string;
  pgvector_ready: boolean;
  dimensions: number;
  vector_a_preview?: number[];
  vector_b_preview?: number[];
  note: string;
}

export interface SemanticSampleComparisonItem {
  pair_type: 'SIMILAR_PAIR' | 'DISSIMILAR_PAIR' | string;
  category_context: string;
  material_a_code: string;
  material_b_code: string;
  material_a_text: string;
  material_b_text: string;
  semantic_similarity_score: number;
  interpretation: string;
  embedding_method: string;
  vector_a_preview: number[];
  vector_b_preview: number[];
}

export interface SemanticSampleComparisonResponse {
  total_comparisons: number;
  comparisons: SemanticSampleComparisonItem[];
  method: string;
  dimensions: number;
  pgvector_ready: boolean;
  note: string;
}

export type HybridClassification =
  | 'AUTO_MATCH_RECOMMENDED'
  | 'STRONG_REVIEW_CANDIDATE'
  | 'MANUAL_REVIEW_REQUIRED'
  | 'WEAK_MATCH_REVIEW_OPTIONAL'
  | 'REJECTED_BY_SCORING';

export interface MatchFeatureVector {
  description_similarity: number;
  token_similarity: number;
  semantic_similarity_score: number;
  attribute_similarity: number;
  exact_attribute_match_count: number;
  conflicting_attribute_count: number;
  critical_attribute_conflict_count: number;
  missing_critical_attribute_count: number;
  category_compatibility: number;
  uom_compatibility: number;
  manufacturer_match: number;
  part_number_match: number;
  model_number_match: number;
  source_cpse_match: number;
  confidence_gap: number;
  requires_human_review: boolean;
}

export interface HybridScoreBreakdown {
  description_contribution: number;
  attribute_contribution: number;
  semantic_contribution: number;
  token_contribution: number;
  category_contribution: number;
  uom_contribution: number;
  mfg_part_contribution: number;
  completeness_bonus: number;
  raw_composite_score: number;
  conflict_penalty_applied: boolean;
  conflict_penalty_description?: string | null;
  score_cap_applied?: number | null;
  final_hybrid_score: number;
}

export interface HybridScoredCandidate {
  pair_id: string;
  source_material_a: PreviewRecord;
  source_material_b: PreviewRecord;
  rapidfuzz_score: number;
  hybrid_score: number;
  hybrid_classification: HybridClassification;
  hybrid_score_breakdown: HybridScoreBreakdown;
  feature_vector: MatchFeatureVector;
  hybrid_recommendation: string;
  matching_signals: MatchingSignal[];
  conflict_signals: ConflictSignal[];
}

export interface HybridScoringResponse {
  total_candidates_scored: number;
  auto_match_count: number;
  strong_review_count: number;
  manual_review_count: number;
  weak_review_count: number;
  rejected_count: number;
  candidates: HybridScoredCandidate[];
  scoring_version: string;
  xgboost_ready: boolean;
}

export interface MLFeatureExportRow {
  pair_id: string;
  source_material_a_code: string;
  source_material_b_code: string;
  source_cpse_a: string;
  source_cpse_b: string;
  description_similarity: number;
  token_similarity: number;
  semantic_similarity_score: number;
  attribute_similarity: number;
  exact_attribute_match_count: number;
  conflicting_attribute_count: number;
  critical_attribute_conflict_count: number;
  missing_critical_attribute_count: number;
  category_compatibility: number;
  uom_compatibility: number;
  manufacturer_match: number;
  part_number_match: number;
  model_number_match: number;
  source_cpse_match: number;
  confidence_gap: number;
  requires_human_review: boolean;
  rule_hybrid_score: number;
  rule_classification: string;
  label?: number | null;
  review_status: string;
}

export interface MLTrainingPlanResponse {
  model_target: string;
  current_status: string;
  feature_count: number;
  feature_names: string[];
  training_sample_requirement: string;
  objective_function: string;
  evaluation_metric: string;
  retraining_trigger: string;
  why_placeholder_for_now: string;
  features_documentation: Record<string, string>;
}

export type ExplanationDirection = 'POSITIVE' | 'NEGATIVE' | 'NEUTRAL';

export interface ExplanationFactor {
  factor_name: string;
  display_label: string;
  contribution_value: number;
  contribution_percentage: number;
  direction: ExplanationDirection;
  explanation: string;
  evidence: string[];
}

export interface AuditExplanation {
  candidate_pair_id: string;
  material_a_summary: string;
  material_b_summary: string;
  hybrid_score: number;
  classification: string;
  top_positive_factors: string[];
  top_negative_risk_factors: string[];
  recommendation: string;
  method_version: string;
  timestamp?: string;
}

export interface ReviewerExplanation {
  pair_id: string;
  source_material_a_code: string;
  source_material_b_code: string;
  source_cpse_a: string;
  source_cpse_b: string;
  hybrid_score: number;
  hybrid_classification: HybridClassification;
  reviewer_summary: string;
  factors: ExplanationFactor[];
  positive_factors: ExplanationFactor[];
  risk_factors: ExplanationFactor[];
  conflict_factors: string[];
  missing_data_warnings: string[];
  audit_explanation: AuditExplanation;
  recommendation: string;
}

export interface ExplainabilityResponse {
  total_explained: number;
  explanations: ReviewerExplanation[];
  version: string;
  model_placeholder: string;
}

export interface ReviewDecisionRequest {
  candidate_id: string;
  decision: 'APPROVE' | 'REJECT' | 'NEEDS_MORE_INFO';
  reviewer_note?: string;
  reviewer_name?: string;
}

export interface ReviewDecisionResponse {
  status: string;
  candidate_id: string;
  decision: string;
  reviewer_note?: string;
  reviewer_name: string;
  message: string;
  persisted: boolean;
  recorded_at: string;
}

export interface ProcurementImpact {
  duplicate_count: number;
  estimated_annual_spend_overlap: number;
  standardization_savings_percent: number;
  estimated_savings_inr: number;
  affected_cpses: string[];
  procurement_risk_level: 'LOW' | 'MEDIUM' | 'HIGH';
  is_demo_estimate: boolean;
}

export interface MappingPreview {
  source_material_codes: string[];
  source_cpses: string[];
  target_national_code: string;
  target_description: string;
  mapping_type: string;
}

export type ApprovalStage = 'PENDING_L1' | 'PENDING_L2' | 'COMPLETED' | 'REJECTED' | 'NEEDS_INFO';
export type ApprovalWorkflowStatus = 'PENDING' | 'APPROVED_AS_MASTER_ALIAS' | 'APPROVED_AS_UNIFIED_SKU' | 'REJECTED_DISTINCT' | 'NEEDS_MORE_INFO';

export interface ApprovalCase {
  approval_case_id: string;
  candidate_pair_id: string;
  source_material_a: CanonicalSourceMaterial;
  source_material_b: CanonicalSourceMaterial;
  proposed_national_material_code: string;
  proposed_standard_description: string;
  hybrid_score: number;
  hybrid_classification: HybridClassification;
  explanation_summary: string;
  required_approval_level: 'L1_ONLY' | 'L1_AND_L2' | 'L2_SPECIALIST' | 'REJECTED_ONLY' | string;
  current_stage: ApprovalStage;
  approval_status: ApprovalWorkflowStatus;
  l1_reviewer?: string | null;
  l1_decision?: string | null;
  l1_reviewed_at?: string | null;
  l1_notes?: string | null;
  l2_reviewer?: string | null;
  l2_decision?: string | null;
  l2_reviewed_at?: string | null;
  l2_notes?: string | null;
  procurement_impact: ProcurementImpact;
  mapping_preview: MappingPreview;
  created_at: string;
}

export interface ApprovalQueueResponse {
  total_cases: number;
  pending_l1_count: number;
  pending_l2_count: number;
  completed_count: number;
  cases: ApprovalCase[];
  version: string;
  note: string;
}

export interface ApprovalActionPayload {
  approval_case_id: string;
  decision: 'APPROVE' | 'REJECT' | 'NEEDS_MORE_INFO';
  reviewer_name?: string;
  reviewer_role?: 'NODAL_OFFICER' | 'MINISTRY_AUTHORITY';
  reviewer_note?: string;
  stage?: 'L1_REVIEW' | 'L2_REVIEW';
}

export interface ApprovalActionResponse {
  status: string;
  approval_case_id: string;
  decision: string;
  updated_case: ApprovalCase;
  generated_audit_event: Record<string, any>;
  message: string;
  persisted: boolean;
}

export interface AuditTrailEvent {
  audit_id: string;
  timestamp: string;
  actor: string;
  actor_role: string;
  action: string;
  entity_type: string;
  entity_id: string;
  old_value?: Record<string, any> | null;
  new_value?: Record<string, any> | null;
  reason?: string | null;
  method_version: string;
  previous_hash: string;
  hash_signature: string;
  verification_status: 'VERIFIED' | 'CORRUPTED' | 'GENESIS';
}

export interface AuditTrailResponse {
  total_events: number;
  chain_verified: boolean;
  genesis_hash: string;
  latest_hash: string;
  events: AuditTrailEvent[];
  tamper_evident: boolean;
  note: string;
}

export interface AuditChainVerificationResponse {
  chain_status: 'CHAIN_INTACT' | 'CHAIN_BROKEN';
  verified_event_count: number;
  genesis_hash: string;
  latest_hash: string;
  is_valid: boolean;
  verification_timestamp: string;
  message: string;
}

export interface ModuleStatus {
  name: string;
  key: string;
  status: 'READY' | 'DEMO_READY' | 'VERIFIED' | 'PLANNED' | string;
  description: string;
  implementation: string;
}

export interface DemoSummaryResponse {
  service_status: string;
  service_name: string;
  version: string;
  timestamp: string;
  sample_material_count: number;
  candidate_count: number;
  high_confidence_match_count: number;
  approval_case_count: number;
  pending_l1_count: number;
  pending_l2_count: number;
  audit_event_count: number;
  audit_chain_status: string;
  total_estimated_savings_inr: number;
  modules: ModuleStatus[];
  persistence_status: string;
  is_database_connected: boolean;
  planned_production_integrations: string[];
  notes: string;
}
