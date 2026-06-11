export type VoiceMode = "standard" | "clone";
export type VoiceSource = "tts" | "uploaded_voiceover";
export type KnowledgePolicy = "none" | "project_default" | "selected";
export type ClipStyle = "summary" | "highlight" | "analysis" | "short_hook";
export type PipelineMode = string;

export interface WorkflowPort {
  name: string;
  schema_ref?: string;
  required?: boolean;
  description?: string;
}

export interface WorkflowNode {
  id: string;
  type: string;
  title: string;
  description?: string;
  inputs?: WorkflowPort[];
  outputs?: WorkflowPort[];
  config_schema?: Record<string, unknown>;
}

export interface WorkflowEdge {
  from_node: string;
  from_port: string;
  to_node: string;
  to_port: string;
}

export interface WorkflowTemplate {
  id: string;
  title: string;
  description?: string;
  version?: string;
  entry_node?: string;
  terminal_node?: string;
  task_mode?: string;
  nodes?: WorkflowNode[];
  edges?: WorkflowEdge[];
  tags?: string[];
  is_default?: boolean;
  enabled?: boolean;
}

export interface CurrentUser {
  id: string;
  username: string;
  display_name?: string;
  is_active?: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface AuthSession {
  authenticated: boolean;
  user: CurrentUser | null;
}

export interface TaskDeleteResult {
  task_id?: string;
  deleted: boolean;
  deleted_count?: number;
  task_ids?: string[];
  delete_source_requested?: boolean;
  deleted_source?: boolean;
  deleted_asr_cache?: boolean;
  deleted_asr_cache_record?: boolean;
  deleted_asr_cache_audio?: boolean;
  source_reference_count?: number;
  asr_cache_reference_count?: number;
  source_retained_reason?: string;
  asr_cache_retained_reason?: string;
  items?: TaskDeleteResult[];
}

export interface RuntimeStatus {
  topology?: Record<string, any>;
  backend?: Record<string, any>;
  llm?: Record<string, any>;
  asr?: Record<string, any>;
  tts?: Record<string, any>;
}

export interface VoiceProfile {
  id: string;
  label: string;
  description?: string;
  language?: string;
  source_type?: string;
  voice_kind?: VoiceMode | string;
  is_default?: boolean;
  is_active?: boolean;
  preview_available?: boolean;
  preview_url?: string;
  sample_text?: string;
}

export interface Project {
  id: string;
  title: string;
  description?: string;
  default_knowledge_base_id?: string;
  default_pipeline_mode?: PipelineMode | string;
  default_knowledge_policy?: KnowledgePolicy | string;
  default_duration_seconds?: number;
  default_style?: ClipStyle | string;
  default_enable_dubbing?: boolean;
  default_voice_mode?: VoiceMode | string;
  default_voice_profile_id?: string;
  default_tts_speed?: number;
  default_keep_original_audio?: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface ProjectKnowledge {
  id: string;
  project_id?: string;
  title: string;
  content: string;
  created_at?: string;
  updated_at?: string;
}

export interface ProjectKnowledgeDeleteResult {
  deleted: boolean;
  id: string;
  project_id: string;
  replacement_knowledge_base_id?: string;
  items?: ProjectKnowledge[];
}

export interface ProjectDeleteResult {
  deleted: boolean;
  id: string;
  replacement_project_id?: string;
  deleted_knowledge_ids?: string[];
  items?: Project[];
}

export interface DraftBeat {
  id: string;
  title: string;
  text: string;
  order: number;
  voice_duration_ms?: number;
}

export interface TaskEvent {
  id?: number;
  event_type?: string;
  status?: string;
  stage?: string;
  progress?: number;
  message?: string;
  detail?: Record<string, unknown>;
  created_at?: string;
}

export interface MatchedSegment {
  start: number;
  end: number;
  source_start?: number;
  source_end?: number;
  semantic_start?: number;
  semantic_end?: number;
  duration_fit_adjusted?: boolean;
  duration_fit_original_start?: number;
  duration_fit_original_end?: number;
  content?: string;
  dubbing?: string;
  voice_duration_ms?: number;
}

export interface TaskPayload {
  original_filename?: string;
  request_text?: string;
  request_mode?: string;
  project_id?: string;
  project_title?: string;
  project_default_knowledge_base_id?: string;
  pipeline_mode?: PipelineMode | string;
  workflow_template_title?: string;
  knowledge_policy?: KnowledgePolicy | string;
  knowledge_used?: boolean;
  project_context?: string;
  project_context_extra?: string;
  knowledge_base_id?: string;
  knowledge_base_title?: string;
  knowledge_base_context?: string;
  knowledge_base_updated_at?: string;
  duration_seconds?: number;
  style?: ClipStyle | string;
  enable_dubbing?: boolean;
  voice_source?: VoiceSource | string;
  voice_mode?: VoiceMode | string;
  voice_profile_id?: string;
  voice_profile_label?: string;
  tts_voice?: string;
  tts_speed?: number;
  keep_original_audio?: boolean;
  uploaded_voiceover_name?: string;
  uploaded_voiceover_duration_ms?: number;
  [key: string]: unknown;
}

export interface TaskResult {
  subtitle_count?: number;
  segment_count?: number;
  matched_segments?: MatchedSegment[];
  draft_script?: string;
  draft_beats?: DraftBeat[];
  grounding?: Record<string, unknown>;
  review_status?: string;
  script?: string;
  suggestions?: string[];
  plan_mode?: string;
  selection_strategy?: string;
  asr_cache_hit?: boolean;
  total_duration_ms?: number;
  actual_duration_ms?: number;
  voiceover_duration_ms?: number;
  clip_plan_id?: string;
  voiceover_enabled?: boolean;
  voiceover_script?: string;
  voiceover_segment_count?: number;
  [key: string]: unknown;
}

export interface TaskItem {
  id: string;
  project_id?: string;
  status: string;
  progress: number;
  stage: string;
  message?: string;
  error?: string;
  created_at?: string;
  updated_at?: string;
  payload: TaskPayload;
  artifacts: Record<string, string>;
  result: TaskResult;
  events?: TaskEvent[];
}

export interface ClipPlan {
  id: string;
  request_text?: string;
  script?: string;
  suggestions?: string[];
  segments?: MatchedSegment[];
  duration_seconds?: number;
  total_duration_ms?: number;
  style?: string;
  plan_mode?: string;
  request_mode?: string;
  created_at?: string;
}
