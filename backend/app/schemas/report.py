from pydantic import BaseModel


class JobInterpretation(BaseModel):
    hard_requirements: list[str] = []
    soft_requirements: list[str] = []
    hidden_bonuses: list[str] = []
    summary: str = ""


class ResumeMatch(BaseModel):
    strengths: list[str] = []
    gaps: list[str] = []


class CompanyProfile(BaseModel):
    summary: str = ""
    tags: list[str] = []


class InterviewQA(BaseModel):
    question: str
    tip: str


class SalaryRange(BaseModel):
    market_min: int = 0
    market_max: int = 0
    median: int = 0
    suggested_min: int = 0
    suggested_max: int = 0


class PrepSuggestion(BaseModel):
    title: str
    content: str


class ReportData(BaseModel):
    job_interpretation: JobInterpretation = JobInterpretation()
    resume_match: ResumeMatch = ResumeMatch()
    company_profile: CompanyProfile = CompanyProfile()
    interview_qa: list[InterviewQA] = []
    salary_range: SalaryRange = SalaryRange()
    prep_suggestions: list[PrepSuggestion] = []


class ReportResponse(BaseModel):
    id: str
    job_id: str
    status: str
    data: ReportData | None = None

    model_config = {"from_attributes": True}
