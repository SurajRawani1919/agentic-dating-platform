export interface SourceRecord {
  id: number;
  source_type: "linkedin" | "instagram";
  submitted_url: string;
  acquisition_method: string;
  acquisition_status: string;
  verification_notes: string;
  permitted_content_preview: string;
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
}

export interface Analysis {
  id: number;
  participant_id: number;
  summary: string;
  interests: EvidenceItem[];
  hobbies: EvidenceItem[];
  explicitly_stated_preferences: EvidenceItem[];
  communication_clues: EvidenceItem[];
  lifestyle_clues: EvidenceItem[];
  relationship_preferences: EvidenceItem[];
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

export interface EvidenceItem {
  value: string;
  evidence?: string;
  source_type?: string;
  confidence?: number;
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
  config: Record<string, unknown>;
  created_at: string;
  completed_at: string | null;
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
  agent_a_feedback: Record<string, unknown>;
  agent_b_feedback: Record<string, unknown>;
  compatibility_score: number | null;
  confidence: number | null;
  score_breakdown: Record<string, unknown>;
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
  score_breakdown: Record<string, unknown>;
  positive_evidence: string[];
  potential_mismatches: string[];
  unanswered_questions: string[];
  date_session_id: number | null;
  created_at: string;
  candidate_name?: string | null;
  candidate_is_synthetic?: boolean | null;
}

export interface DemoPayload {
  label: string;
  run: Run;
  synthetic_participant_count: number;
  session_count: number;
  ranking_count: number;
  showcase_date_ids: number[];
  first_participant_id: number;
  notes: string[];
}
