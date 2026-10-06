// Hand-written mirrors of the orchestrator's pydantic records (06 §5). Request bodies come from the generated
// schema.d.ts; these are the response shapes the endpoints return as plain dicts.

export type Suite = 'catalogue' | 'generate' | 'edit' | 'animate' | 'models'
export type JobStatus = 'staged' | 'queued' | 'running' | 'done' | 'failed' | 'cancelled'
export type Health = 'present' | 'verified' | 'missing' | 'retired'

export interface Backend { host: string; port: number; token: string }

export interface HealthInfo { ok: boolean; version: string; project_open: boolean; engine_running: boolean; variant: 'full' | 'open'; start_suite?: string | null; session_id?: string }

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

export interface QueueState { paused: boolean; running: string | null; counts: Partial<Record<JobStatus, number>>; last_warm_group: string | null; resumed_unclean?: boolean; recovery?: string[] }

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

export interface EngineSettings { python: string; main: string; extra_model_paths: string; host: string; port: number; flags: string[]; restart_every_jobs: number; health_timeout_s: number; stall_timeout_s: number; reserve_vram_gb: number }
export interface Settings {
  schema_version: number; models_root: string; mounted_model_trees: string[]; vram_budget_gb: number; variant: 'full' | 'open'; hf_home: string
  engine: EngineSettings; api_host: string; api_port: number; thumbnail_sizes: number[]; log_level: string
  reopen_last_project?: boolean; h3_licence_confirmed?: boolean
}

export interface Capabilities {
  recipes: string[]; i2v?: I2vCaps; facesim?: { available: boolean; dir: string }; variant: string; vram_budget_gb: number; samplers: string[]; schedulers: string[]
  models: Record<string, { family: string; label: string; health: Health; steps: number; guidance: number; cfg: number; distilled: boolean; turbo: boolean; turbo_steps: number; json_prompt: boolean; max_refs: number; sampler: string; scheduler: string; vram_gb: number | null; wired: boolean; license: string; variants: string[] }>
  tiers: Record<string, Record<string, [number, number]>>
  weight_dtypes: string[]; te_devices: string[]
  advanced: { model_shift: Record<string, number>; shift_node_defaults: { base: number; max: number }; tile_size_default: number; flux2_schedule: string }
}

export interface EventFrame { seq: number; type: string; t: number; data: Record<string, unknown> }

// ---- M6 Animate (11 §10, 06 §5) ------------------------------------------------------------------------------------
export interface Clip {
  schema_version: number; id: string; created_at: string; job_id: string | null; batch_id: string | null; asset_id: string | null
  model_id: string; preset: string; prompt: string; seed: number; frames: number; fps: number; w: number; h: number
  start_asset_id: string; end_asset_id: string | null; beats: { frame: number; asset_id: string; strength: number }[]
  master_dir: string; proxy_path: string | null; proxy_bytes: number; extracted_asset_ids: string[]
  params: Record<string, unknown>; timings: Record<string, unknown>
  identity?: { status: string; sampled: number; with_face: number; mean?: number; min?: number; min_frame?: number; per_frame?: { frame: number; sim: number | null; faces: number }[]; scale?: string } | null
}
export interface I2vModelCaps {
  family: string; label: string; health: string; missing: string[]; fps: number; frames: number; frame_step: number; size_mult: number; size: [number, number]
  presets: Record<string, string>; beats: boolean; flf: boolean; vram_gb: number | null; license: string; approx_gb: number
}
export interface I2vCaps { models: Record<string, I2vModelCaps>; tiers: Record<string, Record<string, [number, number]>>; portrait: Record<string, [number, number]>; square: Record<string, [number, number]> }
