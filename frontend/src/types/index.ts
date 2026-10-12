export interface SourceRecord {
  id: number;
  source_type: "linkedin" | "instagram";
  submitted_url: string;
  acquisition_method: string;
  acquisition_status: string;
  verification_notes: string;
  permitted_content_preview: string;
  /** Full text the agent read. Only sent on the participant detail endpoint. */
  content: string;
  fetched_at: string | null;
}

export interface Participant {
  id: number;
  display_name: string;
  linkedin_url: string;
  instagram_url: string;
  source_verification_status: string;
  consent_status: string;
  adult_eligibility_confirmed: boolean;
  is_synthetic: boolean;
  created_at: string;
  updated_at: string;
  sources: SourceRecord[];
  has_analysis: boolean;
  headline: string;
}

export interface EvidenceItem {
  value: string;
  evidence?: string;
  source_type?: string;
  confidence?: number;
  /** How the evidence supports the claim — set on inferred needs. */
  why?: string;
}

export interface Analysis {
  id: number;
  participant_id: number;
  headline: string;
  summary: string;
  needs: EvidenceItem[];
  interests: EvidenceItem[];
  hobbies: EvidenceItem[];
  core_values: EvidenceItem[];
  personality_traits: EvidenceItem[];
  explicitly_stated_preferences: EvidenceItem[];
  communication_clues: EvidenceItem[];
  lifestyle_clues: EvidenceItem[];
  relationship_preferences: EvidenceItem[];
  ideal_date: string;
  evidence_items: EvidenceItem[];
  uncertainty_notes: string[];
  confidence_by_attribute: Record<string, number>;
  source_coverage: Record<string, unknown>;
  contradictions: string[];
  missing_information: string[];
  model_name: string;
  prompt_version: string;
  status: string;
  is_demo: boolean;
  created_at: string;
}

export interface Run {
  id: number;
  name: string;
  mode: string;
  status: string;
  participant_count: number;
  session_count: number;
  completed_sessions: number;
  progress: number;
  error_summary: string;
  max_turns: number;
  config: { engine?: string; skipped_without_analysis?: string[] } & Record<string, unknown>;
  created_at: string;
  completed_at: string | null;
}

/** One agent's private verdict on how well the other person fits its own person. */
export interface AgentFeedback {
  verdict?: string;
  overall_impression?: string;
  shared_interests?: string[];
  needs_met?: string[];
  needs_unmet?: string[];
  potential_friction?: string[];
  unanswered_questions?: string[];
  compatibility_estimate?: number;
  confidence?: number;
  reasoning?: string;
}

export interface ScoreComponent {
  score?: number;
  weight?: number;
  evidence?: string[];
  uncertainty?: number;
  insufficient_reason?: string | null;
}

export interface PersonalFit {
  score: number;
  own_agent_estimate: number;
  their_agent_estimate: number;
  mutual_session_score: number;
  verdict: string;
  reasoning: string;
}

export interface DateSession {
  id: number;
  participant_a_id: number;
  participant_b_id: number;
  run_id: number;
  status: string;
  current_turn: number;
  max_turns: number;
  date_summary: string;
  shared_interests: string[];
  potential_friction: string[];
  unanswered_questions: string[];
  agent_a_feedback: AgentFeedback;
  agent_b_feedback: AgentFeedback;
  compatibility_score: number | null;
  confidence: number | null;
  score_breakdown: Record<string, ScoreComponent>;
  is_demo_replay: boolean;
  error_message: string;
  created_at: string;
  completed_at: string | null;
  participant_a_name?: string | null;
  participant_b_name?: string | null;
}

export interface DateMessage {
  id: number;
  speaker_participant_id: number;
  turn_index: number;
  message: string;
  question: string;
  referenced_interests: string[];
  intent: string;
  confidence: number;
  is_live_llm: boolean;
  model_name: string;
  created_at: string;
}

export interface Ranking {
  id: number;
  run_id: number;
  participant_id: number;
  candidate_id: number;
  rank: number;
  compatibility_score: number;
  confidence: number;
  score_breakdown: Record<string, ScoreComponent> & { personal_fit?: PersonalFit };
  positive_evidence: string[];
  potential_mismatches: string[];
  unanswered_questions: string[];
  date_session_id: number | null;
  created_at: string;
  candidate_name?: string | null;
  candidate_is_synthetic?: boolean | null;
}

export interface TopMatch {
  participant_id: number;
  participant_name: string;
  candidate_id: number;
  candidate_name: string;
  score: number;
  date_session_id: number | null;
}

export interface DemoPayload {
  label: string;
  /** False while only the synthetic placeholder sample exists. */
  is_real: boolean;
  run: Run;
  participant_count: number;
  participant_ids: number[];
  session_count: number;
  ranking_count: number;
  showcase_date_ids: number[];
  first_participant_id: number;
  video_url: string;
  notes: string[];
  top_matches: TopMatch[];
}

export interface PublicSettings {
  app_env: string;
  llm_provider: string;
  llm_model: string | null;
  llm_configured: boolean;
  agent_engine: string;
  scraping_enabled: boolean;
  apify_configured: boolean;
  profile_readers: string[];
  demo_video_url: string;
  max_concurrent_dates: number;
  default_max_turns: number;
  notes: string[];
}

export interface NewParticipant {
  display_name?: string;
  linkedin_url: string;
  instagram_url: string;
  linkedin_text?: string;
  instagram_text?: string;
  adult_eligibility_confirmed: boolean;
  consent_to_agent_dating: boolean;
}
