export interface SSEEvent {
  type: "progress" | "done" | "error" | "awaiting_manual_input" | "parsed" | "interrupt" | "completed";
  message: string;
  data?: unknown;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user_id: string;
  email: string;
  username: string;
}

export interface UserInfo {
  id: string;
  email: string;
  username: string;
  status: string;
  email_verified: boolean;
}

export interface JobInterpretation {
  hard_requirements: string[]
  soft_requirements: string[]
  hidden_bonuses: string[]
  summary: string
}

export interface ResumeMatch {
  strengths: string[]
  gaps: string[]
}

export interface CompanyProfile {
  summary: string
  tags: string[]
}

export interface InterviewQA {
  question: string
  tip: string
}

export interface SalaryRange {
  market_min: number
  market_max: number
  median: number
  suggested_min: number
  suggested_max: number
}

export interface PrepSuggestion {
  title: string
  content: string
}

export interface ReportData {
  job_interpretation: JobInterpretation
  resume_match: ResumeMatch
  company_profile: CompanyProfile
  interview_qa: InterviewQA[]
  salary_range: SalaryRange
  prep_suggestions: PrepSuggestion[]
}

export interface ReportResponse {
  id: string
  job_id: string
  status: string
  data: ReportData | null
}

export type ReportStep = 'parsing' | 'confirm' | 'directions' | 'researching' | 'done'

// ---- 错误码 ----
export type ErrorCode =
  | 'AUTH_TOKEN_MISSING'
  | 'AUTH_TOKEN_INVALID'
  | 'AUTH_TOKEN_EXPIRED'
  | 'AUTH_REFRESH_INVALID'
  | 'AUTH_CREDENTIALS_WRONG'
  | 'NOT_FOUND'
  | 'ALREADY_EXISTS'
  | 'ACCESS_DENIED'
  | 'CONFLICT'
  | 'BAD_REQUEST'
  | 'VALIDATION_ERROR'
  | 'RATE_LIMITED'
  | 'INTERNAL_ERROR'
  | 'UPSTREAM_ERROR'

export interface ErrorResponseBody {
  code: ErrorCode
  message: string
  detail?: Record<string, unknown> | null
}
