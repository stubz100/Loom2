// Hand-written mirrors of the orchestrator's pydantic records (06 §5). Request bodies come from the generated
// schema.d.ts; these are the response shapes the endpoints return as plain dicts.

export type Suite = 'catalogue' | 'generate' | 'edit' | 'animate' | 'models'
export type JobStatus = 'staged' | 'queued' | 'running' | 'done' | 'failed' | 'cancelled'
export type Health = 'present' | 'verified' | 'missing' | 'retired'

export interface Backend { host: string; port: number; token: string }

export interface HealthInfo { ok: boolean; version: string; project_open: boolean; engine_running: boolean; variant: 'full' | 'open' }

export interface ProjectFormat { aspect: [number, number]; width: number; height: number; fps: number; default_tier: string }
export interface ProjectInfo {
  open: boolean; path?: string; id?: string; name?: string; format?: ProjectFormat; size_cap_gb?: number
  free_space_gb?: number; created_at?: string; assets?: number; usage_gb?: number; jobs_indexed?: number
}

export interface EngineState {
  running: boolean; responding?: boolean; pid: number | null; port: number; started_at: number | null; uptime_s: number | null
  jobs_since_start: number; restarts: number; last_error: string | null; log: string | null
  version: { comfyui_version?: string; pytorch_version?: string } | null; job_object: boolean
  vram_free_gb?: number; vram_total_gb?: number
}

export interface QueueState { paused: boolean; running: string | null; counts: Partial<Record<JobStatus, number>>; last_warm_group: string | null; resumed_unclean?: boolean }

export interface Job {
  id: string; batch_id: string | null; kind: string; recipe: Record<string, unknown>; seed: number; status: JobStatus
  progress: number; progress_text: string; vram_estimate_gb: number; warm_group: string; created_at: string
  started_at: string | null; finished_at: string | null; wall_s: number | null; result: { asset_ids?: string[]; compiled?: Record<string, unknown> }
  error: string | null; log_tail: string[]; retry_count: number; prompt_id: string | null; node_times: Record<string, number>
}

export interface Asset {
  id: string; kind: 'image' | 'video' | 'mask' | 'document-render'; path: string; w: number | null; h: number | null
  frames: number | null; created_at: string; job_id: string | null; batch_id: string | null; session_id: string | null; root_id: string | null; parents: string[]; suite: string
  model_id: string | null; seed: number | null; prompt_text: string | null; prompt_json: Record<string, unknown> | null
  params: Record<string, unknown>; timings: Record<string, unknown>; compiled_graph_hash: string | null
  variant?: string; state: 'none' | 'keep' | 'reject'; rating: number; tags: string[]; collection_ids: string[]; has_document: boolean; trashed_at: string | null
  thumb_status: 'pending' | 'done' | 'failed'; bytes: number | null; sha256: string | null
}

export interface ModelEntry {
  id: string; name: string; folder: string; family: string; role: string; repo: string | null; file: string | null; license: string
  variants: string[]; approx_gb: number | null; retired: string | null; note: string | null
  path: string | null; health: Health; size: number | null; sha256: string | null; source_tree: string | null
}

export interface FetchState { model_id: string; name: string; status: string; error: string | null; bytes_done: number; bytes_total_est: number; progress: number | null; elapsed_s: number }

export interface EngineSettings { python: string; main: string; extra_model_paths: string; host: string; port: number; flags: string[]; restart_every_jobs: number; health_timeout_s: number }
export interface Settings {
  schema_version: number; models_root: string; mounted_model_trees: string[]; vram_budget_gb: number; variant: 'full' | 'open'; hf_home: string
  engine: EngineSettings; api_host: string; api_port: number; thumbnail_sizes: number[]; log_level: string
}

export interface Capabilities {
  recipes: string[]; variant: string; vram_budget_gb: number
  models: Record<string, { family: string; health: Health; steps: number; guidance: number; distilled: boolean; turbo: boolean; json_prompt: boolean; vram_gb: number | null }>
  tiers: Record<string, Record<string, [number, number]>>
}

export interface EventFrame { seq: number; type: string; t: number; data: Record<string, unknown> }
