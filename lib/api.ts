/**
 * lib/api.ts — Client-side API caller for TamilNyaya-Bench backend.
 * 
 * Rules:
 * - Always points to /api (proxied) or http://127.0.0.1:8000/api
 * - Provides typed methods
 * - Handles errors cleanly without throwing unhandled exceptions to UI
 */

const API_BASE = typeof window !== 'undefined'
  ? (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api')
  : (process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api')

async function fetchJson<T>(endpoint: string, options?: RequestInit): Promise<{ data: T | null; error: string | null; status: number }> {
  const url = endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint.startsWith('/') ? '' : '/'}${endpoint}`
  try {
    const res = await fetch(url, {
      headers: {
        'Accept': 'application/json',
        ...(options?.body ? { 'Content-Type': 'application/json' } : {}),
        ...options?.headers,
      },
      ...options,
    })

    const status = res.status
    if (!res.ok) {
      let errorDetail = `Request failed with status ${status}`
      try {
        const errJson = await res.json()
        errorDetail = errJson.detail?.detail || errJson.detail || errJson.error || errorDetail
      } catch {
        // ignore json parse error
      }
      return { data: null, error: errorDetail, status }
    }

    const data = await res.json()
    return { data, error: null, status }
  } catch (err: any) {
    return { data: null, error: err.message || 'Network connection failed. Ensure backend is running.', status: 0 }
  }
}

// ── Types ──────────────────────────────────────────────────────────

export interface HealthInfo {
  status: 'ok' | 'degraded'
  api_key_configured: boolean
  llm_enabled: boolean
  llm_disabled_reason: string
  models: Record<string, boolean>
  kb_record_count: number
  integrity_status: string
  started_at: string | null
  notice: string
}

export interface KBRecord {
  record_id: string
  act_name_ta: string
  act_name_en: string
  section_no: string
  text_ta: string
  text_en: string | null
  jurisdiction: 'Central' | 'Tamil Nadu'
  in_force: boolean | null
  repealed_by: string | null
  as_of_date: string | null
  source_url: string
  source_document_title: string
  source_file_sha256: string
  retrieved_at: string
  parser_name_and_version: string
  extraction_method: string
  ocr_confidence: number | null
  raw_span: string | null
}

export interface CoverageRow {
  act_name_en: string
  jurisdiction: string
  sections_in_source: number | null
  sections_ingested: number
  coverage_pct: number | null
  coverage_note: string | null
  complete: boolean | null
}

export interface QualityReport {
  total_records: number
  records_with_empty_tamil: number
  records_with_ocr: number
  ocr_confidence_mean: number | null
  ocr_confidence_min: number | null
  duplicate_check_note: string
  rejection_summary: string
  spot_check_sample: Array<{
    record_id: string
    act_name_en: string
    section_no: string
    text_ta_preview: string
    source_url: string
    extraction_method: string
    raw_span: string | null
  }>
}

export interface BenchmarkItem {
  item_id: string
  task_family: string
  template_name: string
  template_version: string
  generator_script: string
  primary_source_record_id: string
  all_source_record_ids: string
  gold_answer: string | null
  gold_derivation: string | null
  gold_status: string
  jurisdiction: string
  topic_tag: string
  is_adversarial: boolean
  adversarial_perturbation: string | null
  created_at: string
}

export interface DatasetStats {
  total_items: number
  by_task_family: Record<string, number>
  by_jurisdiction: Record<string, number>
  by_topic_tag: Record<string, number>
  adversarial_count: number
  needs_human_annotation_count: number
  derived_gold_count: number
  human_labeled_count: number
  note: string
}

export interface RunSummary {
  run_id: string
  status: string
  model_id: string
  provider: string
  temperature: number
  max_tokens: number
  started_at: string
  completed_at: string | null
  total_items: number
  completed_items: number
  error_count: number
}

export interface TraceData {
  run_id: string
  item_id: string
  item: {
    item_id?: string
    task_family?: string
    jurisdiction?: string
    topic_tag?: string
    gold_answer?: string
    gold_status?: string
    is_adversarial?: boolean
  }
  raw_response: string
  user_prompt: string
  system_prompt: string | null
  latency_ms: number | null
  prompt_tokens: number | null
  completion_tokens: number | null
  http_status: number | null
  retry_count: number
  layer1_result: any | null
  layer2_result: any | null
  layer3_result: any | null
  error_categories: string[] | null
  max_severity: number | null
}

export interface ModelMetricRow {
  model_id: string
  provider: string
  display_name: string
  is_fine_tuned_for_tamil_law: boolean
  run_count: number
  total_items_evaluated: number
  citation_accuracy: number | null
  citation_accuracy_ci_low: number | null
  citation_accuracy_ci_high: number | null
  severity3_rate: number | null
  severity3_rate_ci_low: number | null
  severity3_rate_ci_high: number | null
  faithfulness_score: number | null
  jurisdiction_confusion: number | null
  adversarial_delta: number | null
  identical_item_set_note: string
}

export interface LeaderboardResponse {
  models: ModelMetricRow[]
  note: string
  bootstrap_resamples: number
  bootstrap_seed: number
}

export interface ModelDetailResponse {
  model_id: string
  display_name: string
  provider: string
  is_fine_tuned_for_tamil_law: boolean
  description: string
  run_count: number
  total_items_evaluated: number
  citation_accuracy: number | null
  severity3_rate: number | null
  jurisdiction_confusion: number | null
  adversarial_delta: number | null
  category_breakdown: Record<string, number>
  fairness: Record<string, any>
  flagged_examples: Array<{
    item_id: string
    task_family: string
    jurisdiction: string
    max_severity: number
    error_categories: string[]
    raw_response_snippet: string
    user_prompt_snippet: string
  }>
}

export interface LiveCheckRequest {
  question: string
  answer: string
  required_jurisdiction?: string | null
  run_faithfulness?: boolean
  run_judge?: boolean
}

export interface LiveCheckResponse {
  question: string
  answer: string
  layer1: {
    total_citations: number
    correct_citations: number
    verdicts: Array<{
      raw_text: string
      char_start: number
      char_end: number
      pattern_name: string
      normalized_section: string
      verdict: string
      branch_fired: string
      severity: number
      matched_record_id: string | null
      matched_act_name: string | null
      fuzzy_score: number | null
      fuzzy_threshold: number
      lookup_description: string
      kb_has_complete_coverage: boolean | null
      is_correct: boolean
    }>
    error?: string
  }
  layer2: any | null
  layer3: any | null
  llm_enabled: boolean
  llm_disabled_reason: string
}

export interface AnnotationItem {
  id: number
  item_id: string
  run_result_id: number | null
  annotator_id: string
  timestamp: string
  error_categories: string[]
  severity: number
  notes: string | null
  is_adjudicated: boolean
  adjudicated_by: string | null
}

export interface CalibrationRow {
  category: string
  labeled_items: number
  kappa: number | null
  kappa_threshold: number
  status: string
  note: string
}

export interface AuditEntry {
  id: number
  timestamp: string
  level: string
  action: string
  detail: string
  run_id: string | null
  item_id: string | null
  source_url: string | null
}

export interface MetricExplanation {
  name: string
  formula: string
  description: string
  numerator: string
  denominator: string
  null_condition: string
  implementation: string
}

export interface TaxonomyCategory {
  category: string
  group: string
  severity: number
  severity_label: string
  description: string
  layer: string
  rule_reference: string
}

// ── API Functions ──────────────────────────────────────────────────

export const api = {
  getHealth: () => fetchJson<HealthInfo>('/health'),
  
  // KB
  searchKB: (params?: { q?: string; jurisdiction?: string; act_name?: string; limit?: number; offset?: number }) => {
    const sp = new URLSearchParams()
    if (params?.q) sp.append('q', params.q)
    if (params?.jurisdiction) sp.append('jurisdiction', params.jurisdiction)
    if (params?.act_name) sp.append('act_name', params.act_name)
    if (params?.limit) sp.append('limit', String(params.limit))
    if (params?.offset) sp.append('offset', String(params.offset))
    return fetchJson<KBRecord[]>(`/kb/search?${sp.toString()}`)
  },
  getKBRecord: (recordId: string) => fetchJson<KBRecord>(`/kb/${recordId}`),
  getKBCoverage: () => fetchJson<CoverageRow[]>('/kb/coverage'),
  getKBQuality: () => fetchJson<QualityReport>('/kb/quality'),

  // Dataset / Items
  getItems: (params?: { task_family?: string; jurisdiction?: string; topic_tag?: string; is_adversarial?: boolean; limit?: number; offset?: number }) => {
    const sp = new URLSearchParams()
    if (params?.task_family) sp.append('task_family', params.task_family)
    if (params?.jurisdiction) sp.append('jurisdiction', params.jurisdiction)
    if (params?.topic_tag) sp.append('topic_tag', params.topic_tag)
    if (params?.is_adversarial !== undefined) sp.append('is_adversarial', String(params.is_adversarial))
    if (params?.limit) sp.append('limit', String(params.limit))
    if (params?.offset) sp.append('offset', String(params.offset))
    return fetchJson<BenchmarkItem[]>(`/items?${sp.toString()}`)
  },
  getItem: (itemId: string) => fetchJson<BenchmarkItem>(`/items/${itemId}`),
  getDatasetStats: () => fetchJson<DatasetStats>('/dataset/stats'),
  generateItems: (seed = 42) => fetchJson<{ total_generated: number; by_family: Record<string, number>; skipped: number; errors: string[] }>(`/items/generate?seed=${seed}`, { method: 'POST' }),

  // Runs
  listRuns: (limit = 50, offset = 0) => fetchJson<RunSummary[]>(`/runs?limit=${limit}&offset=${offset}`),
  getRun: (runId: string) => fetchJson<RunSummary>(`/runs/${runId}`),
  startRun: (payload: { model_id?: string; temperature?: number; max_tokens?: number; seed?: number; system_prompt?: string }) =>
    fetchJson<RunSummary>('/runs', { method: 'POST', body: JSON.stringify(payload) }),
  getTrace: (runId: string, itemId: string) => fetchJson<TraceData>(`/trace/${runId}/${itemId}`),

  // Verification & Live Check
  liveCheck: (req: LiveCheckRequest) => fetchJson<LiveCheckResponse>('/check', { method: 'POST', body: JSON.stringify(req) }),
  explainMetric: (name: string) => fetchJson<MetricExplanation>(`/metrics/${name}/explain`),
  getTaxonomy: () => fetchJson<{ version: string; categories: TaxonomyCategory[] }>('/taxonomy'),

  // Leaderboard
  getLeaderboard: () => fetchJson<LeaderboardResponse>('/leaderboard'),
  getModelDetail: (modelId: string) => fetchJson<ModelDetailResponse>(`/models/${encodeURIComponent(modelId)}`),

  // Annotations & Calibration
  getAnnotations: (params?: { item_id?: string; annotator_id?: string; limit?: number; offset?: number }) => {
    const sp = new URLSearchParams()
    if (params?.item_id) sp.append('item_id', params.item_id)
    if (params?.annotator_id) sp.append('annotator_id', params.annotator_id)
    if (params?.limit) sp.append('limit', String(params.limit))
    if (params?.offset) sp.append('offset', String(params.offset))
    return fetchJson<AnnotationItem[]>(`/annotations?${sp.toString()}`)
  },
  createAnnotation: (body: { item_id: string; run_result_id?: number; annotator_id: string; error_categories: string[]; severity: number; notes?: string }) =>
    fetchJson<AnnotationItem>('/annotations', { method: 'POST', body: JSON.stringify(body) }),
  getCalibration: () => fetchJson<CalibrationRow[]>('/calibration'),
  getDisagreements: () => fetchJson<any[]>('/annotations/disagreements'),
  adjudicate: (body: { item_id: string; adjudicated_by: string; resolved_error_categories: string[]; resolved_severity: number; resolution_notes?: string }) =>
    fetchJson<any>('/annotations/adjudicate', { method: 'POST', body: JSON.stringify(body) }),

  // Audit & Integrity
  getAuditLog: (params?: { level?: string; action?: string; run_id?: string; limit?: number; offset?: number }) => {
    const sp = new URLSearchParams()
    if (params?.level) sp.append('level', params.level)
    if (params?.action) sp.append('action', params.action)
    if (params?.run_id) sp.append('run_id', params.run_id)
    if (params?.limit) sp.append('limit', String(params.limit))
    if (params?.offset) sp.append('offset', String(params.offset))
    return fetchJson<AuditEntry[]>(`/audit?${sp.toString()}`)
  },
  runIntegrityCheck: () => fetchJson<any>('/integrity'),
}
