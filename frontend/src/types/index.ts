/* ── Types matching the backend Pydantic models ──────────────── */

// ── Candidate Profile ──────────────────────────────────────────

export interface PersonalProfile {
  full_name?: string;
  email?: string;
  phone?: string;
  location?: string;
  nationality?: string;
  linkedin?: string;
  github?: string;
  portfolio?: string;
  languages: string[];
  personal_summary?: string;
}

export interface ProfessionalSummary {
  summary?: string;
  years_of_experience?: number;
  current_role?: string;
  specializations: string[];
}

export interface Employment {
  id: string;
  company: string;
  title: string;
  start_date?: string;
  end_date?: string;
  is_current: boolean;
  location?: string;
  responsibilities: string[];
  achievements: string[];
  technologies: string[];
  reason_for_leaving?: string;
  source: string;
  confidence: number;
}

export interface Project {
  id: string;
  name: string;
  description?: string;
  role?: string;
  company?: string;
  technologies: string[];
  outcomes: string[];
  challenges: string[];
  duration?: string;
  team_size?: number;
  source: string;
  confidence: number;
}

export interface Education {
  id: string;
  institution: string;
  degree?: string;
  field?: string;
  graduation_date?: string;
  gpa?: string;
  honors: string[];
  source: string;
  confidence: number;
}

export interface Certification {
  id: string;
  name: string;
  issuer?: string;
  obtained_date?: string;
  expiry_date?: string;
  credential_id?: string;
  source: string;
  confidence: number;
}

export interface Skill {
  name: string;
  category?: string;
  proficiency?: string;
  years_used?: number;
  evidence: string[];
  source: string;
  confidence: number;
}

export interface TargetRole {
  id: string;
  field?: string;
  specialization?: string;
  // Legacy fields may exist on profiles saved before specialization-only mode.
  company?: string;
  position?: string;
  job_description?: string;
  required_skills: string[];
  preferred_skills: string[];
  seniority_level?: string;
  interview_language?: string;
  department?: string;
  industry?: string;
}

export interface ExpectedQuestion {
  id?: string;
  prompt: string;
  answer: string;
}

export interface CandidateProfile {
  id: string;
  personal_profile: PersonalProfile;
  professional_summary: ProfessionalSummary;
  education: Education[];
  certifications: Certification[];
  employment_history: Employment[];
  projects: Project[];
  technical_skills: Skill[];
  management_skills: Skill[];
  soft_skills: Skill[];
  achievements: { fact: string; source: string; confidence: number }[];
  career_transitions: { from_role: string; to_role: string; reason?: string }[];
  interview_preferences: InterviewPreferences;
  target_roles: TargetRole[];
  expected_questions?: ExpectedQuestion[];
  verified_personal_facts: { fact: string; source: string }[];
  topics_to_avoid: string[];
  is_verified: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProfileExtractionResult {
  extracted_profile: CandidateProfile;
  warnings: string[];
  missing_fields: string[];
  contradictions: string[];
  raw_text?: string;
  extraction_status?: 'partial' | 'complete';
  enrichment_job_id?: string | null;
}

// ── Interview Session ──────────────────────────────────────────

export type SessionState =
  | 'IDLE' | 'LISTENING' | 'INTERVIEWER_SPEAKING' | 'CANDIDATE_SPEAKING'
  | 'QUESTION_DETECTED' | 'QUESTION_FINALIZING' | 'CONTEXT_RETRIEVAL'
  | 'ANSWER_GENERATING' | 'ANSWER_PARTIAL' | 'ANSWER_READY' | 'WAITING_FOR_CANDIDATE'
  | 'CANDIDATE_ANSWERING' | 'ANSWER_REVIEW' | 'PAUSED' | 'ERROR_RECOVERY';

export type SessionMode = 'COACHING' | 'PRACTICE' | 'PREPARATION';

export interface InterviewSession {
  id: string;
  candidate_id: string;
  target_role_id?: string;
  meeting_platform?: string | null;
  mode: SessionMode;
  state: SessionState;
  questions_asked: number;
  current_question?: string | null;
  current_answer?: GeneratedAnswer | null;
  started_at?: string;
  ended_at?: string;
}

// ── Answers ────────────────────────────────────────────────────

export interface ConfidenceScores {
  question_confidence: number;
  context_confidence: number;
  answer_confidence: number;
  technical_confidence: number;
}

export interface ValidationResult {
  is_valid: boolean;
  hallucination_detected: boolean;
  hallucinated_claims: string[];
  consistency_warning: boolean;
  contradictions: string[];
  technical_errors: string[];
  missing_context: boolean;
  missing_context_details?: string;
}

export interface EvidenceSource {
  fact: string;
  source_type: string;
  source_section?: string;
  relevance: number;
}

export interface GeneratedAnswer {
  question_id?: string;
  question: string;
  normalized_question: string;
  answer_en: string;
  answer_ar?: string;
  strategy: string;
  length_mode: string;
  confidence: ConfidenceScores;
  validation: ValidationResult;
  candidate_evidence: EvidenceSource[];
  conversation_context: string[];
  action: string;
}

// ── Settings ───────────────────────────────────────────────────

export type AnswerLengthMode = 'QUICK' | 'STANDARD' | 'DETAILED';
export type AnswerLanguageMode =
  | 'ANSWER_IN_QUESTION_LANGUAGE'
  | 'ALWAYS_ARABIC'
  | 'ALWAYS_ENGLISH'
  | 'SHOW_ARABIC_AND_ENGLISH';

export interface InterviewPreferences {
  answer_length: AnswerLengthMode;
  answer_language: AnswerLanguageMode;
  preferred_language: string;
  show_confidence: boolean;
  show_evidence: boolean;
  enable_teleprompter: boolean;
}

// ── WebSocket Messages ─────────────────────────────────────────

export interface WSMessage {
  type: string;
  [key: string]: unknown;
}

// ── Audio Devices ──────────────────────────────────────────────

export interface AudioDevice {
  index: number;
  name: string;
  channels: number;
  sample_rate: number;
  is_input: boolean;
  is_loopback: boolean;
  host_api: string;
  is_default?: boolean;
}
