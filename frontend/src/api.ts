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
  id: number; name: string; region: string;
  standard_type: string; language: string; currency: string;
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
}

export interface AgentValuateResponse {
  answer: string;
  steps: AgentStep[];
  bindings_changed: boolean;
  error: string | null;
}

// ─── API ─────────────────────────────────────────────────────────

export const api = {
  // Projects
  listProjects: () => request<Project[]>("/projects"),
  getProject: (pid: number) => request<Project>(`/projects/${pid}`),
  createProject: (data: { name: string; region: string; standard_type?: string; language?: string; currency?: string }) =>
    request<Project>("/projects", { method: "POST", body: JSON.stringify(data) }),

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
};
