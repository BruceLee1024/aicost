const BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000/api";

async function request<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

async function upload<T>(path: string, formData: FormData): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: "POST", body: formData });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

// ─── Types ───────────────────────────────────────────────────────

export interface Project {
  id: number; name: string; description: string | null; region: string;
  project_type: string; status: string; budget: number | null;
  start_date: string | null; end_date: string | null; owner: string | null;
  standard_type: string; language: string; currency: string;
  created_at: string | null; updated_at: string | null;
}

export interface ProjectListResponse {
  items: Project[]; total: number; page: number;
  page_size: number; total_pages: number;
}

export interface ProjectListParams {
  q?: string; status?: string; project_type?: string;
  region?: string; sort_by?: string; sort_order?: string;
  page?: number; page_size?: number;
}

export interface ProjectCreateData {
  name: string; region: string; description?: string;
  project_type?: string; budget?: number; start_date?: string;
  end_date?: string; owner?: string; standard_type?: string;
  language?: string; currency?: string;
}

export interface ProjectUpdateData {
  name?: string; description?: string; region?: string;
  project_type?: string; budget?: number; start_date?: string;
  end_date?: string; owner?: string; standard_type?: string;
  language?: string; currency?: string;
}

export interface BoqItem {
  id: number; project_id: number; code: string; name: string;
  characteristics: string; unit: string; quantity: number; division: string;
  sort_order: number; item_ref: string; trade_section: string;
  description_en: string; rate: number; amount: number; remark: string;
}
export interface BoqItemCreate {
  code: string; name: string; characteristics?: string; unit: string; quantity: number;
  division?: string; sort_order?: number; item_ref?: string; trade_section?: string;
  description_en?: string; rate?: number; remark?: string;
}
export interface BoqItemUpdate {
  name?: string; characteristics?: string; unit?: string; quantity?: number;
  division?: string; sort_order?: number; item_ref?: string; trade_section?: string;
  description_en?: string; rate?: number; remark?: string;
}

export interface ImportResult { imported: number; skipped: number; items: unknown[] }

export interface MatchCandidate {
  quota_item_id: number; quota_code: string; quota_name: string;
  unit: string; confidence: number; reasons: string[];
  is_enterprise?: boolean; source_type?: "public" | "enterprise";
}

export interface Binding { id: number; boq_item_id: number; quota_item_id: number; coefficient: number }

export interface BindingWithQuota {
  binding_id: number;
  boq_item_id: number;
  quota_item_id: number;
  coefficient: number;
  quota_code: string;
  quota_name: string;
  quota_unit: string;
  labor_qty: number;
  material_qty: number;
  machine_qty: number;
}

export interface LineCalcResult {
  boq_item_id: number; boq_code: string; boq_name: string;
  direct_cost: number; management_fee: number; profit: number;
  regulatory_fee: number; pre_tax_total: number; tax: number; total: number;
}
export interface CalcSummary {
  total_direct: number; total_management: number; total_profit: number;
  total_regulatory: number; total_pre_tax: number; total_tax: number;
  total_measures: number; grand_total: number; line_results: LineCalcResult[];
}

export interface QuotaRef {
  quota_code: string; quota_name: string; unit: string;
  labor_qty: number; material_qty: number; machine_qty: number;
}
export interface BindingRef { binding_id: number; coefficient: number; direct_cost: number | null; quota: QuotaRef }
export interface PriceSnapshot {
  labor_price: number;
  material_price: number;
  machine_price: number;
}
export interface CalcBreakdown {
  direct_cost: number;
  management_fee: number;
  profit: number;
  regulatory_fee: number;
  pre_tax_total: number;
  tax: number;
  total: number;
}
export interface CalcProvenance {
  boq_item_id: number; boq_code: string; boq_name: string;
  boq_unit: string; boq_quantity: number; bindings: BindingRef[];
  price_snapshot: PriceSnapshot;
  calc_breakdown: CalcBreakdown | null;
  unit_price: number | null;
  calc_total: number | null; fee_config_snapshot: Record<string, number>;
  explanation: string;
}

export interface ValidationIssue {
  code: string; severity: string; boq_item_id: number | null;
  message: string; suggestion: string;
}
export interface ValidationReport {
  project_id: number; total_issues: number; errors: number;
  warnings: number; issues: ValidationIssue[];
}

export interface Snapshot {
  id: number; project_id: number; label: string;
  created_at: string; grand_total: number;
}
export interface LineDiff {
  boq_code: string; boq_name: string; change_type: string;
  old_total: number | null; new_total: number | null; delta: number;
}
export interface DiffReport {
  snapshot_a_id: number; snapshot_b_id: number;
  old_grand_total: number; new_grand_total: number; grand_total_delta: number;
  lines: LineDiff[]; explanation: string;
}

export interface RulePackage {
  id: number; name: string; region: string;
  management_rate: number; profit_rate: number; regulatory_rate: number;
  tax_rate: number; rounding_rule: string; version: string;
}
export interface RulePackageCreate {
  name: string; region?: string; management_rate?: number;
  profit_rate?: number; regulatory_rate?: number; tax_rate?: number;
}

export interface MaterialPrice {
  id: number; code: string; name: string; spec: string;
  unit: string; unit_price: number; source: string;
  region: string; effective_date: string;
}
export interface MaterialPriceCreate {
  code: string; name: string; spec?: string;
  unit: string; unit_price: number; source?: string;
  region?: string; effective_date?: string;
}

export interface MaterialPriceQuery {
  region?: string;
  name?: string;
  as_of_date?: string;
  latest_only?: boolean;
}

export interface MeasureItem {
  id: number; project_id: number; name: string;
  calc_base: string; rate: number; amount: number; is_fixed: boolean;
}
export interface MeasureItemCreate {
  name: string; calc_base?: string; rate?: number;
  amount?: number; is_fixed?: boolean;
}

export interface Member { id: number; project_id: number; user_name: string; role: string }
export interface CommentItem {
  id: number; project_id: number; boq_item_id: number | null;
  author: string; content: string; created_at: string;
}

export interface AuditLog {
  id: number; project_id: number; actor: string; action: string;
  resource_type: string; resource_id: number | null;
  before_json: string | null; after_json: string | null; timestamp: string;
}

export interface QueryHit {
  boq_item_id: number; code: string; name: string;
  unit: string; quantity: number; reason: string;
}
export interface QueryResponse { query: string; total_hits: number; hits: QueryHit[] }

export interface DivisionStat {
  division: string;
  count: number;
  cost: number;
}

export interface HealthScoreDimension {
  name: string;
  score: number;
  weight: number;
  detail: string;
}

export interface HealthScore {
  project_id: number;
  overall_score: number;
  grade: string;
  dimensions: HealthScoreDimension[];
  suggestions: string[];
}

export interface DashboardSummary {
  project_id: number;
  boq_count: number;
  unbound_count: number;
  dirty_count: number;
  validation_total: number;
  validation_errors: number;
  validation_warnings: number;
  recent_audit_count: number;
  recent_comment_count: number;
  calc_total: number;
  binding_rate: string;
  budget: number | null;
  top_divisions: DivisionStat[];
}

export interface ValuationStandardConfig {
  project_id: number;
  standard_code: string;
  standard_name: string;
  effective_date: string;
  locked: boolean;
  locked_at: string | null;
}

export interface ValuationStage {
  key: string;
  label: string;
  status: string;
  detail: string;
}

export interface ValuationOverview {
  project_id: number;
  standard: ValuationStandardConfig;
  stages: ValuationStage[];
  boq_count: number;
  measurement_count: number;
  adjustment_count: number;
  payment_count: number;
  adjustment_total: number;
  payment_net_total: number;
}

export interface ValuationStandardConfigUpdate {
  standard_code: string;
  standard_name: string;
  effective_date: string;
  lock_standard: boolean;
}

export interface ContractMeasurement {
  id: number;
  project_id: number;
  boq_item_id: number;
  boq_code: string;
  boq_name: string;
  boq_unit: string;
  period_label: string;
  measured_qty: number;
  cumulative_qty: number;
  status: string;
  approved_by: string;
  approved_at: string;
  note: string;
  created_at: string;
}

export interface ContractMeasurementCreate {
  boq_item_id: number;
  period_label: string;
  measured_qty: number;
  note?: string;
}

export interface PriceAdjustment {
  id: number;
  project_id: number;
  boq_item_id: number | null;
  boq_code: string;
  boq_name: string;
  adjustment_type: string;
  amount: number;
  status: string;
  reason: string;
  created_at: string;
}

export interface PriceAdjustmentCreate {
  adjustment_type: string;
  boq_item_id?: number | null;
  amount: number;
  reason?: string;
  status?: string;
}

export interface PaymentCertificate {
  id: number;
  project_id: number;
  period_label: string;
  gross_amount: number;
  prepayment_deduction: number;
  retention: number;
  net_payable: number;
  paid_amount: number;
  status: string;
  issued_at: string;
}

export interface PaymentCertificateCreate {
  period_label: string;
  gross_amount: number;
  prepayment_deduction?: number;
  retention?: number;
  paid_amount?: number;
  status?: string;
}

export interface BoqSuggestion {
  code: string; name: string; characteristics: string; unit: string;
  quantity: number; division: string; reason: string;
}
export interface GenerateBoqResponse {
  description: string; floors_detected: number;
  total_items: number; suggestions: BoqSuggestion[];
}

export interface AutoValuateMatchDetail {
  boq_item_id: number; boq_code: string; boq_name: string;
  quota_item_id: number | null; quota_code: string; quota_name: string;
  confidence: number; status: string;
}
export interface AutoValuateResponse {
  total_items: number; already_bound: number;
  newly_matched: number; skipped: number;
  match_details: AutoValuateMatchDetail[];
  calc_summary: CalcSummary | null;
}

export interface AIProviderConfig {
  api_key: string; base_url: string; model: string;
}
export interface AIProvidersConfig {
  deepseek: AIProviderConfig; qwen: AIProviderConfig;
  kimi: AIProviderConfig; glm: AIProviderConfig; openai: AIProviderConfig;
}
export interface AISettingsPayload {
  provider: string; timeout_seconds: number; enable_audit_logs: boolean;
  providers: AIProvidersConfig;
}

export interface AITestConnectionResponse {
  success: boolean;
  latency_ms: number;
  reply: string;
  error: string;
}

export interface AIAnalyzeResponse {
  insight: string | null;
  ai_available: boolean;
}

export interface AIChatResponse {
  reply: string | null;
  ai_available: boolean;
}

// Batch Review types
export interface ReviewIssue {
  boq_item_id: number; boq_code: string; boq_name: string;
  severity: string; issue_type: string; message: string; suggestion: string;
}
export interface BatchReviewResponse {
  project_id: number; total_items: number; bound_count: number; unbound_count: number;
  issues: ReviewIssue[]; ai_summary: string | null; error: string | null;
}

// Coefficient Suggestion types
export interface CoeffSuggestionItem {
  binding_id: number | null; quota_code: string; quota_name: string;
  current_coefficient: number; suggested_coefficient: number; reasoning: string;
}
export interface CoeffSuggestResponse {
  boq_item_id: number; suggestions: CoeffSuggestionItem[];
}

// Rate Suggestion types
export interface RateSuggestionResponse {
  boq_item_id: number; suggested_rate: number; rate_low: number; rate_high: number;
  currency: string; reasoning: string; confidence: number;
}

// Agent valuation types
export interface AgentStep {
  type: "thinking" | "tool_call" | "tool_result" | "answer" | "done";
  content: string;
  tool_name: string;
  tool_args: Record<string, unknown>;
  tool_result: string;
  // done-specific fields
  answer?: string;
  bindings_changed?: boolean;
  error?: string | null;
  /** Phase H7: set on the orchestrate stream 'done' event. */
  auto_saved_memories?: string[];
}

export interface AgentValuateResponse {
  answer: string;
  steps: AgentStep[];
  bindings_changed: boolean;
  error: string | null;
}

// ─── Orchestrator & Pipeline Types ────────────────────────────────

export interface OrchestrateResponse {
  answer: string;
  tool_calls_made: number;
  error: string | null;
  /** Phase H7: keys of memories auto-saved during this run. */
  auto_saved_memories?: string[];
}

export interface ConversationTurn {
  role: "user" | "assistant";
  content: string;
}

export interface OrchestrateRequestExtras {
  /** Phase H8: associate with a user for user-scoped memory. */
  user_id?: number;
  /** Phase H7: override AI_AUTO_SAVE_MEMORY env default for this call. */
  auto_save_memory?: boolean;
  /** Prior conversation turns, for multi-turn chat. */
  conversation_history?: ConversationTurn[];
}

// ─── Memory Types (Phase H3–H5, H9) ───────────────────────────────

export type MemoryScope = "global" | "user" | "project";

export interface AgentMemoryDTO {
  id: number | null;
  scope: MemoryScope;
  scope_id: number | null;
  key: string;
  content: string;
  tags: string[];
  importance: number;
  created_by_agent: string;
  created_at: string;
  updated_at: string;
  accessed_count: number;
}

export interface AgentMemoryWithScore extends AgentMemoryDTO {
  score: number;
}

export interface ListMemoriesResponse {
  memories: AgentMemoryDTO[];
  total: number;
}

export interface SearchMemoriesResponse {
  matches: AgentMemoryDTO[];
  total: number;
}

export interface SemanticMemoriesResponse {
  matches: AgentMemoryWithScore[];
  total: number;
}

export interface UpsertMemoryRequest {
  scope: MemoryScope;
  scope_id?: number | null;
  key: string;
  content: string;
  importance?: number;
  tags?: string[];
  created_by_agent?: string;
}

// ─── Skill Types (Phase H4–H5, H9) ────────────────────────────────

export interface SkillSummary {
  name: string;
  title: string;
  description: string;
  triggers: string[];
  tags: string[];
  version: string;
}

export interface SkillDetail extends SkillSummary {
  body: string;
}

export interface SkillMatch extends SkillSummary {
  score: number;
}

export interface ListSkillsResponse {
  skills: SkillSummary[];
  total: number;
}

export interface SearchSkillsResponse {
  matches: SkillSummary[];
  total: number;
}

export interface SemanticSkillsResponse {
  matches: SkillMatch[];
  total: number;
}

export interface QuotaItemDTO {
  id: number;
  quota_code: string;
  name: string;
  unit: string;
  chapter: string;
  labor_qty: number;
  material_qty: number;
  machine_qty: number;
  labor_fee?: number;
  material_fee?: number;
  machine_fee?: number;
  base_price?: number;
  version?: string;
}

export type OtherItemCategory = "provisional_sum" | "provisional_price" | "daywork" | "gc_service";

export const OTHER_ITEM_CATEGORY_ZH: Record<OtherItemCategory, string> = {
  provisional_sum: "暂列金额",
  provisional_price: "暂估价",
  daywork: "计日工",
  gc_service: "总承包服务费",
};

export interface OtherItem {
  id: number;
  project_id: number;
  category: OtherItemCategory;
  name: string;
  unit?: string;
  quantity: number;
  unit_price: number;
  amount: number;
  is_fixed: number;
  tax_mode?: string;
  note?: string;
  sort_order: number;
}

export interface OtherItemCreate {
  category: OtherItemCategory;
  name: string;
  unit?: string;
  quantity?: number;
  unit_price?: number;
  amount?: number;
  is_fixed?: number;
  tax_mode?: string;
  note?: string;
  sort_order?: number;
}

export interface OtherItemUpdate extends Partial<OtherItemCreate> {}

export interface OtherItemCategorySummary {
  category: OtherItemCategory;
  category_zh: string;
  total: number;
  count: number;
}

export interface OtherItemSummary {
  grand_total: number;
  categories: OtherItemCategorySummary[];
}

export interface RegulatoryFees {
  project_id: number;
  labor_base: number;
  social_insurance_rate: number;
  housing_fund_rate: number;
  social_insurance_fee: number;
  housing_fund_fee: number;
  regulatory_fee_total: number;
  breakdown?: { name: string; rate: number; base: number; amount: number }[];
  provenance?: { formula: string; standard: string };
}

export interface QuotaListResponse {
  total: number;
  items: QuotaItemDTO[];
}

export interface QuotaChapterStat {
  chapter: string;
  count: number;
}

export interface QuotaStatsResponse {
  total: number;
  chapters: QuotaChapterStat[];
}

export interface PipelineStageOut {
  index: number;
  agent: string;
  success: boolean;
  duration_s: number;
  tool_calls: number;
  answer: string;
}

export interface PipelineResponse {
  pipeline: string;
  stages: PipelineStageOut[];
  final_answer: string;
  success: boolean;
  total_duration_s: number;
  error: string | null;
}

// ─── Traces & Cost Dashboard Types ───────────────────────────────

export interface TraceOut {
  id: number;
  project_id: number | null;
  agent_name: string;
  parent_trace_id: number | null;
  model: string | null;
  provider: string | null;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  estimated_cost_cents: number;
  turns_used: number;
  tool_calls_made: number;
  duration_ms: number;
  success: boolean;
  error: string | null;
  answer_preview: string | null;
  started_at: string;
  finished_at: string | null;
}

export interface TraceListResponse {
  total: number;
  traces: TraceOut[];
}

export interface AgentCostStats {
  agent_name: string;
  trace_count: number;
  total_tokens: number;
  total_cost_cents: number;
  avg_duration_ms: number;
  success_rate: number;
}

export interface DayCostStats {
  date: string;
  trace_count: number;
  total_tokens: number;
  total_cost_cents: number;
}

export interface CostStatsResponse {
  period: string;
  total_traces: number;
  successful_traces: number;
  failed_traces: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  total_cost_cents: number;
  total_tool_calls: number;
  avg_duration_ms: number;
  by_agent: AgentCostStats[];
  by_day: DayCostStats[];
}

// ─── Knowledge Graph Types ────────────────────────────────────────

export interface TagOut {
  id: number; name: string; color: string; category: string; created_at: string;
}
export interface TagCreate { name: string; color?: string; category?: string }

export interface EntityTagOut {
  id: number; tag_id: number; tag_name: string; tag_color: string;
  entity_type: string; entity_id: number;
}
export interface EntityTagCreate { tag_id: number; entity_type: string; entity_id: number }

export interface KnowledgeLinkOut {
  id: number; source_type: string; source_id: number;
  target_type: string; target_id: number;
  link_type: string; label: string; note: string; created_at: string;
}
export interface KnowledgeLinkCreate {
  source_type: string; source_id: number;
  target_type: string; target_id: number;
  link_type?: string; label?: string; note?: string;
}
export interface KnowledgeLinkUpdate {
  link_type?: string; label?: string; note?: string;
}

export interface KnowledgeNoteOut {
  id: number; entity_type: string; entity_id: number;
  title: string; content: string; created_at: string; updated_at: string;
}
export interface KnowledgeNoteCreate {
  entity_type: string; entity_id: number; title?: string; content?: string;
}
export interface KnowledgeNoteUpdate { title?: string; content?: string }

export interface GraphNode {
  id: string; type: string; label: string;
  properties: Record<string, unknown>; tags: string[];
}
export interface GraphEdge {
  source: string; target: string; type: string; label: string;
}
export interface GraphDataOut { nodes: GraphNode[]; edges: GraphEdge[] }

// ─── API ─────────────────────────────────────────────────────────

export const api = {
  // Projects
  listProjects: (params?: ProjectListParams) => {
    const qs = new URLSearchParams();
    if (params?.q) qs.set("q", params.q);
    if (params?.status) qs.set("status", params.status);
    if (params?.project_type) qs.set("project_type", params.project_type);
    if (params?.region) qs.set("region", params.region);
    if (params?.sort_by) qs.set("sort_by", params.sort_by);
    if (params?.sort_order) qs.set("sort_order", params.sort_order);
    if (params?.page != null) qs.set("page", String(params.page));
    if (params?.page_size != null) qs.set("page_size", String(params.page_size));
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return request<ProjectListResponse>(`/projects${suffix}`);
  },
  getProject: (pid: number) => request<Project>(`/projects/${pid}`),
  createProject: (data: ProjectCreateData) =>
    request<Project>("/projects", { method: "POST", body: JSON.stringify(data) }),
  updateProject: (pid: number, data: ProjectUpdateData) =>
    request<Project>(`/projects/${pid}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteProject: (pid: number) =>
    request<{ ok: boolean; deleted_id: number }>(`/projects/${pid}`, { method: "DELETE" }),
  archiveProject: (pid: number) =>
    request<Project>(`/projects/${pid}:archive`, { method: "POST" }),
  duplicateProject: (pid: number) =>
    request<Project>(`/projects/${pid}:duplicate`, { method: "POST" }),
  changeProjectStatus: (pid: number, status: string) =>
    request<Project>(`/projects/${pid}/status`, { method: "PATCH", body: JSON.stringify({ status }) }),
  batchDeleteProjects: (ids: number[]) =>
    request<{ ok: boolean; deleted: number }>("/projects:batch-delete", { method: "POST", body: JSON.stringify(ids) }),
  batchArchiveProjects: (ids: number[]) =>
    request<{ ok: boolean; archived: number }>("/projects:batch-archive", { method: "POST", body: JSON.stringify(ids) }),

  // BOQ CRUD
  listBoqItems: (pid: number) => request<BoqItem[]>(`/projects/${pid}/boq-items`),
  createBoqItem: (pid: number, data: BoqItemCreate) =>
    request<BoqItem>(`/projects/${pid}/boq-items`, { method: "POST", body: JSON.stringify(data) }),
  updateBoqItem: (pid: number, itemId: number, data: BoqItemUpdate) =>
    request<BoqItem>(`/projects/${pid}/boq-items/${itemId}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteBoqItem: (pid: number, itemId: number) =>
    request<{ ok: boolean }>(`/projects/${pid}/boq-items/${itemId}`, { method: "DELETE" }),

  // Import
  importBoq: (pid: number, file: File) => {
    const fd = new FormData(); fd.append("file", file);
    return upload<ImportResult>(`/imports/boq?project_id=${pid}`, fd);
  },
  importQuota: (file: File) => {
    const fd = new FormData(); fd.append("file", file);
    return upload<ImportResult>("/imports/quota", fd);
  },

  // AI Match
  getQuotaCandidates: (boqItemId: number, topN = 5) =>
    request<MatchCandidate[]>(`/boq-items/${boqItemId}/quota-candidates?top_n=${topN}`, { method: "POST" }),

  // Bindings
  confirmBinding: (boqItemId: number, quotaItemId: number) =>
    request<Binding>(`/boq-items/${boqItemId}/quota-binding:confirm`, {
      method: "POST", body: JSON.stringify({ quota_item_id: quotaItemId, coefficient: 1 }),
    }),
  confirmBindingWithCoefficient: (boqItemId: number, quotaItemId: number, coefficient: number) =>
    request<Binding>(`/boq-items/${boqItemId}/quota-binding:confirm`, {
      method: "POST", body: JSON.stringify({ quota_item_id: quotaItemId, coefficient }),
    }),
  replaceBinding: (boqItemId: number, quotaItemId: number) =>
    request<Binding>(`/boq-items/${boqItemId}/quota-binding:replace`, {
      method: "POST", body: JSON.stringify({ quota_item_id: quotaItemId, coefficient: 1 }),
    }),
  replaceBindingWithCoefficient: (boqItemId: number, quotaItemId: number, coefficient: number) =>
    request<Binding>(`/boq-items/${boqItemId}/quota-binding:replace`, {
      method: "POST", body: JSON.stringify({ quota_item_id: quotaItemId, coefficient }),
    }),
  batchConfirmBindings: (bindings: Array<{ boq_item_id: number; quota_item_id: number; coefficient?: number }>) =>
    request<Binding[]>("/boq-items/quota-binding:batch-confirm", {
      method: "POST", body: JSON.stringify({ bindings }),
    }),
  batchReplaceBindings: (bindings: Array<{ boq_item_id: number; quota_item_id: number; coefficient?: number }>) =>
    request<Binding[]>("/boq-items/quota-binding:batch-replace", {
      method: "POST", body: JSON.stringify({ bindings }),
    }),
  listBindings: (boqItemId: number) => request<Binding[]>(`/boq-items/${boqItemId}/quota-bindings`),
  listProjectBindings: (projectId: number) =>
    request<BindingWithQuota[]>(`/projects/${projectId}/bindings-with-quota`),
  deleteBinding: (boqItemId: number, bindingId: number) =>
    request<{ boq_item_id: number; removed: number }>(`/boq-items/${boqItemId}/quota-bindings/${bindingId}`, {
      method: "DELETE",
    }),
  clearBindings: (boqItemId: number) =>
    request<{ boq_item_id: number; removed: number }>(`/boq-items/${boqItemId}/quota-bindings:clear`, {
      method: "DELETE",
    }),

  // Calculate
  calculate: (pid: number) => request<CalcSummary>(`/projects/${pid}/calculate`, { method: "POST" }),
  getCalcSummary: (pid: number) => request<CalcSummary>(`/projects/${pid}/calc-summary`),

  // Provenance
  getProvenance: (boqItemId: number) => request<CalcProvenance>(`/calc-results/${boqItemId}/provenance`),

  // Validation
  validate: (pid: number) => request<ValidationReport>(`/projects/${pid}/validation-issues`),

  // Snapshots
  listSnapshots: (pid: number) => request<Snapshot[]>(`/projects/${pid}/snapshots`),
  createSnapshot: (pid: number, label: string) =>
    request<Snapshot>(`/projects/${pid}/snapshots`, { method: "POST", body: JSON.stringify({ label }) }),
  diffSnapshots: (pid: number, aId: number, bId: number) =>
    request<DiffReport>(`/projects/${pid}/diff`, {
      method: "POST", body: JSON.stringify({ snapshot_a_id: aId, snapshot_b_id: bId }),
    }),

  // Export (POST endpoints — trigger download via form submission)
  exportValuationUrl: (pid: number) => `${BASE}/exports/valuation-report?project_id=${pid}`,
  exportDiffUrl: (aId: number, bId: number) =>
    `${BASE}/exports/diff-report?snapshot_a_id=${aId}&snapshot_b_id=${bId}`,

  // Rule Packages
  listRulePackages: () => request<RulePackage[]>("/rule-packages"),
  createRulePackage: (data: RulePackageCreate) =>
    request<RulePackage>("/rule-packages", { method: "POST", body: JSON.stringify(data) }),
  bindRulePackage: (pid: number, rpId: number) =>
    request<Project>(`/projects/${pid}/rule-package:bind`, {
      method: "POST", body: JSON.stringify({ rule_package_id: rpId }),
    }),

  // Material Prices
  listMaterialPrices: (query?: MaterialPriceQuery) => {
    const qs = new URLSearchParams();
    if (query?.region) qs.set("region", query.region);
    if (query?.name) qs.set("name", query.name);
    if (query?.as_of_date) qs.set("as_of_date", query.as_of_date);
    if (query?.latest_only) qs.set("latest_only", "true");
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return request<MaterialPrice[]>(`/material-prices${suffix}`);
  },
  createMaterialPrice: (data: MaterialPriceCreate) =>
    request<MaterialPrice>("/material-prices", { method: "POST", body: JSON.stringify(data) }),

  // Measures
  listMeasures: (pid: number) => request<MeasureItem[]>(`/projects/${pid}/measures`),
  createMeasure: (pid: number, data: MeasureItemCreate) =>
    request<MeasureItem>(`/projects/${pid}/measures`, { method: "POST", body: JSON.stringify(data) }),
  deleteMeasure: (pid: number, mId: number) =>
    request<{ ok: boolean }>(`/projects/${pid}/measures/${mId}`, { method: "DELETE" }),

  // Collaboration
  listMembers: (pid: number) => request<Member[]>(`/projects/${pid}/members`),
  addMember: (pid: number, userName: string, role = "viewer") =>
    request<Member>(`/projects/${pid}/members`, { method: "POST", body: JSON.stringify({ user_name: userName, role }) }),
  listComments: (pid: number) => request<CommentItem[]>(`/projects/${pid}/comments`),
  addComment: (pid: number, author: string, content: string, boqItemId?: number) =>
    request<CommentItem>(`/projects/${pid}/comments`, {
      method: "POST", body: JSON.stringify({ author, content, boq_item_id: boqItemId ?? null }),
    }),

  // Audit Logs
  listAuditLogs: (pid: number) => request<AuditLog[]>(`/projects/${pid}/audit-logs`),
  getDashboardSummary: (pid: number) =>
    request<DashboardSummary>(`/projects/${pid}/dashboard-summary`),
  getHealthScore: (pid: number) =>
    request<HealthScore>(`/projects/${pid}/health-score`),
  recalculateDirty: (pid: number) =>
    request<any>(`/projects/${pid}/calculate:dirty`, { method: "POST" }),

  // Valuation management (GB/T50500-2024 workflow)
  getValuationOverview: (pid: number) =>
    request<ValuationOverview>(`/projects/${pid}/valuation-management/overview`),
  getValuationConfig: (pid: number) =>
    request<ValuationStandardConfig>(`/projects/${pid}/valuation-management/config`),
  updateValuationConfig: (pid: number, data: ValuationStandardConfigUpdate) =>
    request<ValuationStandardConfig>(`/projects/${pid}/valuation-management/config`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  listContractMeasurements: (pid: number) =>
    request<ContractMeasurement[]>(`/projects/${pid}/valuation-management/measurements`),
  createContractMeasurement: (pid: number, data: ContractMeasurementCreate) =>
    request<ContractMeasurement>(`/projects/${pid}/valuation-management/measurements`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  approveContractMeasurement: (pid: number, measurementId: number, approvedBy: string) =>
    request<ContractMeasurement>(`/projects/${pid}/valuation-management/measurements/${measurementId}:approve`, {
      method: "POST",
      body: JSON.stringify({ approved_by: approvedBy }),
    }),
  listPriceAdjustments: (pid: number) =>
    request<PriceAdjustment[]>(`/projects/${pid}/valuation-management/adjustments`),
  createPriceAdjustment: (pid: number, data: PriceAdjustmentCreate) =>
    request<PriceAdjustment>(`/projects/${pid}/valuation-management/adjustments`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  listPaymentCertificates: (pid: number) =>
    request<PaymentCertificate[]>(`/projects/${pid}/valuation-management/payments`),
  createPaymentCertificate: (pid: number, data: PaymentCertificateCreate) =>
    request<PaymentCertificate>(`/projects/${pid}/valuation-management/payments`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  // AI Query
  query: (pid: number, q: string) =>
    request<QueryResponse>(`/projects/${pid}/query`, { method: "POST", body: JSON.stringify({ q }) }),

  // AI Generate BOQ
  generateBoq: (pid: number, description: string) =>
    request<GenerateBoqResponse>(`/projects/${pid}/ai-generate-boq`, {
      method: "POST", body: JSON.stringify({ description }),
    }),

  // AI Settings
  getAISettings: () => request<AISettingsPayload>("/ai/settings"),
  updateAISettings: (data: AISettingsPayload) =>
    request<AISettingsPayload>("/ai/settings", { method: "PUT", body: JSON.stringify(data) }),
  testAIConnection: (data: { provider: string; api_key: string; base_url: string; model: string }) =>
    request<AITestConnectionResponse>("/ai/test-connection", { method: "POST", body: JSON.stringify(data) }),

  // AI Analyze (insight)
  aiAnalyze: (pid: number, contextType: string, contextData: Record<string, unknown> = {}) =>
    request<AIAnalyzeResponse>(`/projects/${pid}/ai-analyze`, {
      method: "POST",
      body: JSON.stringify({ context_type: contextType, context_data: contextData }),
    }),

  // AI Auto Valuate (match + bind + calc)
  autoValuate: (pid: number) =>
    request<AutoValuateResponse>(`/projects/${pid}/auto-valuate`, { method: "POST" }),

  // AI Chat
  aiChat: (pid: number, message: string, history: Array<{ role: string; content: string }> = []) =>
    request<AIChatResponse>(`/projects/${pid}/ai-chat`, {
      method: "POST",
      body: JSON.stringify({ message, history }),
    }),

  // Agent Valuate (streaming SSE)
  agentValuateStream: (
    pid: number,
    boqItemId: number,
    instruction: string,
    onStep: (step: AgentStep) => void,
  ): Promise<void> => {
    const BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000/api";
    return fetch(`${BASE}/projects/${pid}/boq-items/${boqItemId}/agent-valuate/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ instruction }),
    }).then(async (res) => {
      if (!res.ok) throw new Error(`Agent request failed: ${res.status}`);
      const reader = res.body?.getReader();
      if (!reader) return;
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const step = JSON.parse(line.slice(6)) as AgentStep;
              onStep(step);
            } catch { /* skip malformed */ }
          }
        }
      }
    });
  },

  // Agent Valuate (non-streaming fallback)
  agentValuate: (pid: number, boqItemId: number, instruction = "") =>
    request<AgentValuateResponse>(
      `/projects/${pid}/boq-items/${boqItemId}/agent-valuate`,
      { method: "POST", body: JSON.stringify({ instruction }) },
    ),

  // Reorder BOQ items
  reorderBoqItems: (pid: number, items: Array<{ id: number; sort_order: number }>) =>
    request<{ ok: boolean; updated: number }>(`/projects/${pid}/boq-items:reorder`, {
      method: "POST", body: JSON.stringify({ items }),
    }),

  // Batch update BOQ items
  batchUpdateBoqItems: (pid: number, ids: number[], updates: { division?: string; trade_section?: string; remark?: string }) =>
    request<{ ok: boolean; updated: number }>(`/projects/${pid}/boq-items:batch-update`, {
      method: "PATCH", body: JSON.stringify({ ids, ...updates }),
    }),

  // Batch delete BOQ items
  batchDeleteBoqItems: (pid: number, ids: number[]) =>
    request<{ ok: boolean; deleted: number }>(`/projects/${pid}/boq-items:batch-delete`, {
      method: "POST", body: JSON.stringify({ ids }),
    }),

  // AI Batch Review
  aiBatchReview: (pid: number) =>
    request<BatchReviewResponse>(`/projects/${pid}/ai-batch-review`, { method: "POST" }),

  // AI Coefficient Suggestion
  suggestCoefficients: (boqItemId: number) =>
    request<CoeffSuggestResponse>(`/boq-items/${boqItemId}/suggest-coefficients`, { method: "POST" }),

  // AI Rate Suggestion (HKSMM4)
  suggestRate: (boqItemId: number) =>
    request<RateSuggestionResponse>(`/boq-items/${boqItemId}/suggest-rate`, { method: "POST" }),

  // ─── Knowledge Graph APIs ──────────────────────────────────────────

  // Tags
  listTags: (category?: string) =>
    request<TagOut[]>(`/tags${category ? `?category=${category}` : ""}`),
  createTag: (data: TagCreate) =>
    request<TagOut>("/tags", { method: "POST", body: JSON.stringify(data) }),
  deleteTag: (tagId: number) =>
    request<void>(`/tags/${tagId}`, { method: "DELETE" }),

  // Entity Tags
  listEntityTags: (params?: { entity_type?: string; entity_id?: number; tag_id?: number }) => {
    const qs = new URLSearchParams();
    if (params?.entity_type) qs.set("entity_type", params.entity_type);
    if (params?.entity_id != null) qs.set("entity_id", String(params.entity_id));
    if (params?.tag_id != null) qs.set("tag_id", String(params.tag_id));
    const q = qs.toString();
    return request<EntityTagOut[]>(`/entity-tags${q ? `?${q}` : ""}`);
  },
  attachTag: (data: EntityTagCreate) =>
    request<EntityTagOut>("/entity-tags", { method: "POST", body: JSON.stringify(data) }),
  detachTag: (entityTagId: number) =>
    request<void>(`/entity-tags/${entityTagId}`, { method: "DELETE" }),

  // Knowledge Links
  listKnowledgeLinks: (params?: { entity_type?: string; entity_id?: number; link_type?: string }) => {
    const qs = new URLSearchParams();
    if (params?.entity_type) qs.set("entity_type", params.entity_type);
    if (params?.entity_id != null) qs.set("entity_id", String(params.entity_id));
    if (params?.link_type) qs.set("link_type", params.link_type);
    const q = qs.toString();
    return request<KnowledgeLinkOut[]>(`/knowledge-links${q ? `?${q}` : ""}`);
  },
  createKnowledgeLink: (data: KnowledgeLinkCreate) =>
    request<KnowledgeLinkOut>("/knowledge-links", { method: "POST", body: JSON.stringify(data) }),
  updateKnowledgeLink: (linkId: number, data: KnowledgeLinkUpdate) =>
    request<KnowledgeLinkOut>(`/knowledge-links/${linkId}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteKnowledgeLink: (linkId: number) =>
    request<void>(`/knowledge-links/${linkId}`, { method: "DELETE" }),

  // Knowledge Notes
  listKnowledgeNotes: (params?: { entity_type?: string; entity_id?: number }) => {
    const qs = new URLSearchParams();
    if (params?.entity_type) qs.set("entity_type", params.entity_type);
    if (params?.entity_id != null) qs.set("entity_id", String(params.entity_id));
    const q = qs.toString();
    return request<KnowledgeNoteOut[]>(`/knowledge-notes${q ? `?${q}` : ""}`);
  },
  createKnowledgeNote: (data: KnowledgeNoteCreate) =>
    request<KnowledgeNoteOut>("/knowledge-notes", { method: "POST", body: JSON.stringify(data) }),
  updateKnowledgeNote: (noteId: number, data: KnowledgeNoteUpdate) =>
    request<KnowledgeNoteOut>(`/knowledge-notes/${noteId}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteKnowledgeNote: (noteId: number) =>
    request<void>(`/knowledge-notes/${noteId}`, { method: "DELETE" }),

  // Graph Data
  getGraphData: (params?: {
    scope?: string; project_id?: number; entity_type?: string;
    entity_id?: number; depth?: number; types?: string; tag_filter?: string;
  }) => {
    const qs = new URLSearchParams();
    if (params?.scope) qs.set("scope", params.scope);
    if (params?.project_id != null) qs.set("project_id", String(params.project_id));
    if (params?.entity_type) qs.set("entity_type", params.entity_type);
    if (params?.entity_id != null) qs.set("entity_id", String(params.entity_id));
    if (params?.depth != null) qs.set("depth", String(params.depth));
    if (params?.types) qs.set("types", params.types);
    if (params?.tag_filter) qs.set("tag_filter", params.tag_filter);
    const q = qs.toString();
    return request<GraphDataOut>(`/graph/data${q ? `?${q}` : ""}`);
  },

  // ─── Orchestrator & Pipeline APIs ──────────────────────────────────

  orchestrate: (pid: number, instruction: string, extras?: OrchestrateRequestExtras) =>
    request<OrchestrateResponse>(`/projects/${pid}/orchestrate`, {
      method: "POST",
      body: JSON.stringify({ instruction, ...(extras ?? {}) }),
    }),

  orchestrateStream: (
    pid: number,
    instruction: string,
    onStep: (step: AgentStep) => void,
    extras?: OrchestrateRequestExtras,
  ): Promise<void> => {
    const BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000/api";
    return fetch(`${BASE}/projects/${pid}/orchestrate/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ instruction, ...(extras ?? {}) }),
    }).then(async (res) => {
      if (!res.ok) throw new Error(`Orchestrator request failed: ${res.status}`);
      const reader = res.body?.getReader();
      if (!reader) return;
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const step = JSON.parse(line.slice(6)) as AgentStep;
              onStep(step);
            } catch { /* skip malformed */ }
          }
        }
      }
    });
  },

  runPricingPipeline: (pid: number, boqItemId: number) =>
    request<PipelineResponse>(`/projects/${pid}/boq-items/${boqItemId}/pipeline/pricing`, {
      method: "POST",
    }),

  runAuditPipeline: (pid: number) =>
    request<PipelineResponse>(`/projects/${pid}/pipeline/audit`, {
      method: "POST",
    }),

  // ─── Traces & Cost Dashboard APIs ──────────────────────────────────

  listTraces: (params?: { project_id?: number; agent_name?: string; limit?: number; offset?: number }) => {
    const qs = new URLSearchParams();
    if (params?.project_id != null) qs.set("project_id", String(params.project_id));
    if (params?.agent_name) qs.set("agent_name", params.agent_name);
    if (params?.limit != null) qs.set("limit", String(params.limit));
    if (params?.offset != null) qs.set("offset", String(params.offset));
    const q = qs.toString();
    return request<TraceListResponse>(`/ai/traces${q ? `?${q}` : ""}`);
  },

  getTraceStats: (params?: { project_id?: number; days?: number }) => {
    const qs = new URLSearchParams();
    if (params?.project_id != null) qs.set("project_id", String(params.project_id));
    if (params?.days != null) qs.set("days", String(params.days));
    const q = qs.toString();
    return request<CostStatsResponse>(`/ai/traces/stats${q ? `?${q}` : ""}`);
  },

  // ─── Memory Management APIs (Phase H9) ─────────────────────────────

  listMemories: (params: { scope: MemoryScope; scope_id?: number | null; limit?: number }) => {
    const qs = new URLSearchParams();
    qs.set("scope", params.scope);
    if (params.scope_id != null) qs.set("scope_id", String(params.scope_id));
    if (params.limit != null) qs.set("limit", String(params.limit));
    return request<ListMemoriesResponse>(`/memories?${qs.toString()}`);
  },

  searchMemories: (params: {
    scope: MemoryScope;
    scope_id?: number | null;
    query?: string;
    tags?: string;
    min_importance?: number;
    limit?: number;
  }) => {
    const qs = new URLSearchParams();
    qs.set("scope", params.scope);
    if (params.scope_id != null) qs.set("scope_id", String(params.scope_id));
    if (params.query) qs.set("query", params.query);
    if (params.tags) qs.set("tags", params.tags);
    if (params.min_importance != null) qs.set("min_importance", String(params.min_importance));
    if (params.limit != null) qs.set("limit", String(params.limit));
    return request<SearchMemoriesResponse>(`/memories/search?${qs.toString()}`);
  },

  searchMemoriesSemantic: (params: {
    scope: MemoryScope;
    query: string;
    scope_id?: number | null;
    limit?: number;
    min_similarity?: number;
  }) => {
    const qs = new URLSearchParams();
    qs.set("scope", params.scope);
    qs.set("query", params.query);
    if (params.scope_id != null) qs.set("scope_id", String(params.scope_id));
    if (params.limit != null) qs.set("limit", String(params.limit));
    if (params.min_similarity != null) qs.set("min_similarity", String(params.min_similarity));
    return request<SemanticMemoriesResponse>(`/memories/search/semantic?${qs.toString()}`);
  },

  upsertMemory: (payload: UpsertMemoryRequest) =>
    request<AgentMemoryDTO>("/memories", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  deleteMemory: (memoryId: number) =>
    request<{ deleted: boolean; memory_id: number }>(`/memories/${memoryId}`, {
      method: "DELETE",
    }),

  // ─── Skills Browsing APIs (Phase H9) ───────────────────────────────

  listSkills: () => request<ListSkillsResponse>("/skills"),

  getSkill: (name: string) =>
    request<SkillDetail>(`/skills/${encodeURIComponent(name)}`),

  searchSkills: (params: { query?: string; tags?: string }) => {
    const qs = new URLSearchParams();
    if (params.query) qs.set("query", params.query);
    if (params.tags) qs.set("tags", params.tags);
    const q = qs.toString();
    return request<SearchSkillsResponse>(`/skills/search${q ? `?${q}` : ""}`);
  },

  searchSkillsSemantic: (params: {
    query: string;
    limit?: number;
    min_similarity?: number;
  }) => {
    const qs = new URLSearchParams();
    qs.set("query", params.query);
    if (params.limit != null) qs.set("limit", String(params.limit));
    if (params.min_similarity != null) qs.set("min_similarity", String(params.min_similarity));
    return request<SemanticSkillsResponse>(`/skills/search/semantic?${qs.toString()}`);
  },

  // ─── Quota Library APIs ─────────────────────────────────────────

  listQuotaItems: (params: {
    skip?: number;
    limit?: number;
    chapter?: string;
    keyword?: string;
  }) => {
    const qs = new URLSearchParams();
    if (params.skip != null) qs.set("skip", String(params.skip));
    if (params.limit != null) qs.set("limit", String(params.limit));
    if (params.chapter) qs.set("chapter", params.chapter);
    if (params.keyword) qs.set("keyword", params.keyword);
    return request<QuotaListResponse>(`/quota-items?${qs.toString()}`);
  },

  getQuotaStats: () => request<QuotaStatsResponse>("/quota-items/stats"),

  importQuota2024: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return upload<{ imported: number; errors: string[] }>("/quota-items/import-2024", fd);
  },

  // ─── OtherItem APIs ────────────────────────────────────────────

  listOtherItems: (pid: number, category?: string) => {
    const qs = category ? `?category=${category}` : "";
    return request<OtherItem[]>(`/projects/${pid}/other-items${qs}`);
  },

  createOtherItem: (pid: number, data: OtherItemCreate) =>
    request<OtherItem>(`/projects/${pid}/other-items`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updateOtherItem: (pid: number, itemId: number, data: OtherItemUpdate) =>
    request<OtherItem>(`/projects/${pid}/other-items/${itemId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  deleteOtherItem: (pid: number, itemId: number) =>
    request<{ deleted: boolean }>(`/projects/${pid}/other-items/${itemId}`, {
      method: "DELETE",
    }),

  getOtherItemsSummary: (pid: number) =>
    request<OtherItemSummary>(`/projects/${pid}/other-items/summary`),

  getRegulatoryFees: (pid: number, params?: { social_insurance_rate?: number; housing_fund_rate?: number }) => {
    const qs = new URLSearchParams();
    if (params?.social_insurance_rate != null) qs.set("social_insurance_rate", String(params.social_insurance_rate));
    if (params?.housing_fund_rate != null) qs.set("housing_fund_rate", String(params.housing_fund_rate));
    const q = qs.toString();
    return request<RegulatoryFees>(`/projects/${pid}/regulatory-fees${q ? `?${q}` : ""}`);
  },

  // ─── Report APIs ──────────────────────────────────────────────

  getReport: (pid: number, opts?: { division?: string; search?: string }) => {
    const qs = new URLSearchParams();
    if (opts?.division) qs.set("division", opts.division);
    if (opts?.search) qs.set("search", opts.search);
    const q = qs.toString();
    return request<any>(`/projects/${pid}/report${q ? `?${q}` : ""}`);
  },

  exportReport: (
    pid: number,
    format: "pdf" | "excel" | "docx" = "pdf",
    opts?: { narrative?: boolean },
  ) => {
    const qs = new URLSearchParams({ format });
    if (opts?.narrative) qs.set("narrative", "true");
    const url = `${BASE}/projects/${pid}/report/export?${qs.toString()}`;
    return fetch(url).then((r) => {
      if (!r.ok) throw new Error(`Export failed: ${r.status}`);
      return r.blob();
    });
  },

  // ─── Sprint 9 Phase 2: BOQ Drafts ─────────────────────────────

  listBoqDrafts: (pid: number) =>
    request<BoqDraftResponse[]>(`/projects/${pid}/boq-drafts`),

  getBoqDraft: (pid: number, token: string) =>
    request<BoqDraftResponse>(`/projects/${pid}/boq-drafts/${token}`),

  commitBoqDraft: (pid: number, token: string, items: BoqDraftItem[]) =>
    request<BoqDraftCommitResponse>(`/projects/${pid}/boq-drafts/${token}/commit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ items }),
    }),

  discardBoqDraft: (pid: number, token: string) =>
    request<{ discarded: boolean; token: string }>(
      `/projects/${pid}/boq-drafts/${token}`,
      { method: "DELETE" },
    ),

  // ─── Enterprise Quota Library ────────────────────────────────

  listEnterpriseQuotas: (params: {
    status?: string; source_type?: string; keyword?: string;
    profession?: string; chapter?: string;
    skip?: number; limit?: number;
  } = {}) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") qs.set(k, String(v));
    });
    const q = qs.toString();
    return request<EnterpriseQuotaListResponse>(`/enterprise-quota${q ? `?${q}` : ""}`);
  },

  getEnterpriseQuotaStats: () =>
    request<EnterpriseQuotaStats>("/enterprise-quota/stats"),

  getEnterpriseQuota: (id: number) =>
    request<EnterpriseQuotaItem>(`/enterprise-quota/${id}`),

  createEnterpriseQuota: (data: EnterpriseQuotaCreate) =>
    request<EnterpriseQuotaItem>("/enterprise-quota", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updateEnterpriseQuota: (id: number, data: Partial<EnterpriseQuotaCreate>) =>
    request<EnterpriseQuotaItem>(`/enterprise-quota/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  deleteEnterpriseQuota: (id: number) =>
    request<{ deleted: boolean }>(`/enterprise-quota/${id}`, { method: "DELETE" }),

  submitEnterpriseQuota: (id: number, actor = "") =>
    request<EnterpriseQuotaItem>(`/enterprise-quota/${id}/submit`, {
      method: "POST",
      body: JSON.stringify({ actor }),
    }),

  approveEnterpriseQuota: (id: number, actor = "", comment = "") =>
    request<EnterpriseQuotaItem>(`/enterprise-quota/${id}/approve`, {
      method: "POST",
      body: JSON.stringify({ actor, comment }),
    }),

  rejectEnterpriseQuota: (id: number, actor = "", comment = "") =>
    request<EnterpriseQuotaItem>(`/enterprise-quota/${id}/reject`, {
      method: "POST",
      body: JSON.stringify({ actor, comment }),
    }),

  archiveEnterpriseQuota: (id: number, actor = "") =>
    request<EnterpriseQuotaItem>(`/enterprise-quota/${id}/archive`, {
      method: "POST",
      body: JSON.stringify({ actor }),
    }),

  restoreEnterpriseQuota: (id: number, actor = "") =>
    request<EnterpriseQuotaItem>(`/enterprise-quota/${id}/restore`, {
      method: "POST",
      body: JSON.stringify({ actor }),
    }),

  importEnterpriseQuotaExcel: (file: File, createdBy = "") => {
    const fd = new FormData();
    fd.append("file", file);
    const qs = createdBy ? `?created_by=${encodeURIComponent(createdBy)}` : "";
    return upload<{ imported: number; skipped: number; errors: string[] }>(
      `/enterprise-quota/import${qs}`, fd,
    );
  },

  downloadEnterpriseQuotaTemplateUrl: () =>
    `${BASE}/enterprise-quota/template/download`,

  // Precipitation candidates
  listEnterpriseQuotaCandidates: (params: {
    status?: string; min_confidence?: number; keyword?: string;
    skip?: number; limit?: number;
  } = {}) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") qs.set(k, String(v));
    });
    const q = qs.toString();
    return request<CandidateListResponse>(`/enterprise-quota/candidates/list${q ? `?${q}` : ""}`);
  },

  analyzeEnterpriseQuotaCandidates: () =>
    request<AnalyzeResult>("/enterprise-quota/candidates/analyze", { method: "POST" }),

  promoteEnterpriseQuotaCandidate: (id: number, actor = "", quotaCodeOverride?: string) =>
    request<EnterpriseQuotaItem>(`/enterprise-quota/candidates/${id}/promote`, {
      method: "POST",
      body: JSON.stringify({ actor, quota_code_override: quotaCodeOverride ?? null }),
    }),

  dismissEnterpriseQuotaCandidate: (id: number, reason = "", actor = "") =>
    request<EnterpriseQuotaCandidate>(`/enterprise-quota/candidates/${id}/dismiss`, {
      method: "POST",
      body: JSON.stringify({ reason, actor }),
    }),
};

// ─── Sprint 9 Phase 2 types ──────────────────────────────────────

export interface BoqDraftItem {
  draft_id?: string | null;
  code: string;
  name: string;
  unit: string;
  quantity: number;
  division: string;
  characteristics: string;
  remark: string;
}

export interface BoqDraftResponse {
  token: string;
  project_id: number;
  created_at: number;
  items: BoqDraftItem[];
}

export interface BoqDraftCommitResponse {
  created_count: number;
  created_ids: number[];
  division_summary: Record<string, number>;
  errors: string[];
}

// ─── Enterprise Quota types ────────────────────────────────────────

export type EnterpriseQuotaStatus =
  | "draft" | "in_review" | "approved" | "rejected" | "archived";

export type EnterpriseQuotaSource = "manual" | "precipitated" | "imported";

export interface EnterpriseQuotaItem {
  id: number;
  quota_code: string;
  name: string;
  unit: string;
  labor_qty: number;
  material_qty: number;
  machine_qty: number;
  labor_fee: number;
  material_fee: number;
  machine_fee: number;
  base_price: number;
  work_content: string;
  applicable_scope: string;
  chapter: string;
  profession: string;
  region: string;
  version: string;
  coefficient_default: number;
  tags: string[];
  status: EnterpriseQuotaStatus;
  source_type: EnterpriseQuotaSource;
  source_ref: Record<string, unknown>;
  created_by: string;
  created_at: string | null;
  submitted_at: string | null;
  reviewed_by: string;
  reviewed_at: string | null;
  review_comment: string;
  usage_count: number;
}

export interface EnterpriseQuotaCreate {
  quota_code: string;
  name: string;
  unit: string;
  labor_qty?: number;
  material_qty?: number;
  machine_qty?: number;
  labor_fee?: number;
  material_fee?: number;
  machine_fee?: number;
  base_price?: number;
  work_content?: string;
  applicable_scope?: string;
  chapter?: string;
  profession?: string;
  region?: string;
  version?: string;
  coefficient_default?: number;
  tags?: string[];
  source_type?: EnterpriseQuotaSource;
  source_ref?: Record<string, unknown>;
  created_by?: string;
}

export interface EnterpriseQuotaListResponse {
  total: number;
  items: EnterpriseQuotaItem[];
}

export interface EnterpriseQuotaStats {
  total: number;
  by_status: Record<string, number>;
  by_source: Record<string, number>;
  pending_review: number;
  pending_candidates: number;
  recent_created: number;
}

export interface EnterpriseQuotaCandidate {
  id: number;
  boq_code_pattern: string;
  name_canonical: string;
  unit: string;
  suggested_labor_qty: number;
  suggested_material_qty: number;
  suggested_machine_qty: number;
  suggested_unit_price: number;
  suggested_coefficient: number;
  sample_count: number;
  confidence: number;
  source_quota_ids: number[];
  source_project_ids: number[];
  evidence: Record<string, number>;
  status: "pending" | "promoted" | "dismissed";
  promoted_to_id: number | null;
  dismiss_reason: string;
  created_at: string | null;
  last_analyzed_at: string | null;
}

export interface CandidateListResponse {
  total: number;
  items: EnterpriseQuotaCandidate[];
}

export interface AnalyzeResult {
  snapshots_scanned: number;
  bindings_scanned: number;
  candidates_created: number;
  candidates_updated: number;
}
