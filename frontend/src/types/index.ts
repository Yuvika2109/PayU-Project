// ─── Enums ────────────────────────────────────────────────────────────────────

export type SchemaType = 'emvco' | 'emvco_3ds';
export type RuleSeverity = 'high' | 'medium' | 'low';
export type RuleCategory = 'velocity' | 'amount' | 'device' | 'geography' | 'authentication' | 'behavioral' | 'account' | 'merchant';
export type OperatorType = 'gt' | 'gte' | 'lt' | 'lte' | 'eq' | 'neq' | 'in' | 'not_in' | 'contains';
export type RuleMode = 'normal' | 'assisted';

// ─── Rule Models ──────────────────────────────────────────────────────────────

export interface RuleCondition {
  field: string;
  operator: OperatorType;
  value: string | number | string[];
  description: string;
}

export interface FraudRule {
  id: string;
  name: string;
  description: string;
  category: RuleCategory;
  severity: RuleSeverity;
  logic_expression: string;
  conditions: RuleCondition[];
  match_any: boolean;
  tags: string[];
}

// ─── Request Models ───────────────────────────────────────────────────────────

export interface GenerateRulesRequest {
  scenario: string;
  mode: RuleMode;
  schema_type?: SchemaType;
  available_columns?: string[];
  num_rules: number;
  session_id?: string;
}

export interface EvaluateRequest {
  rules: FraudRule[];
  selected_rule_ids?: string[];
}

// ─── Response Models ──────────────────────────────────────────────────────────

export interface DatasetSummary {
  total_rows: number;
  fraud_rows: number;
  non_fraud_rows: number;
  fraud_rate: number;
  schema_type: SchemaType;
  columns: string[];
  missing_value_counts: Record<string, number>;
}

export interface UploadResponse {
  session_id: string;
  filename: string;
  rows: number;
  schema_type: SchemaType;
  columns: string[];
  dataset_summary: DatasetSummary;
}

export interface GenerateRulesResponse {
  scenario_summary: string;
  schema_type: SchemaType;
  rules: FraudRule[];
  model_used: string;
}

export interface RuleResult {
  rule_id: string;
  rule_name: string;
  severity: RuleSeverity;
  category: RuleCategory;
  flagged_count: number;
  flag_rate: number;
  true_positive_count: number;
  false_positive_count: number;
  precision: number;
  recall: number;
  f1: number;
  logic_expression: string;
  sample_flagged_ids: string[];
}

export interface EvaluationMetrics {
  total_records: number;
  total_flagged: number;
  overall_flag_rate: number;
  fraud_captured: number;
  overall_precision: number;
  overall_recall: number;
  overall_f1: number;
  rule_results: RuleResult[];
  dataset_summary: DatasetSummary;
  flagged_sample: Record<string, unknown>[];
}

// ─── App State ────────────────────────────────────────────────────────────────

export type AppStep = 1 | 2 | 3 | 4;

export interface AppState {
  step: AppStep;
  // Step 1 – Upload
  uploadResponse: UploadResponse | null;
  // Step 2 – Generate
  scenario: string;
  numRules: number;
  generateResponse: GenerateRulesResponse | null;
  // Step 3 – Select
  selectedRuleIds: Set<string>;
  // Step 4 – Evaluate
  evaluationMetrics: EvaluationMetrics | null;
}
