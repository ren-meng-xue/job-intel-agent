export interface Job {
  id: string;
  url: string;
  status: "pending" | "parsing" | "researching" | "done" | "failed";
  title?: string;
  company?: string;
}

export interface ReportContent {
  jobAnalysis: string;
  resumeMatch: string;
  companyProfile: string;
  interviewQuestions: string[];
  salaryRange: string;
  prepAdvice: string;
}

export interface Report {
  id: string;
  jobId: string;
  status: "pending" | "generating" | "done" | "failed";
  content?: ReportContent;
}

export interface SSEEvent {
  type: "progress" | "done" | "error";
  message: string;
  data?: unknown;
}
