# Phase 3：前端全量复刻 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `html/ui-prototype.html` 的 7 个屏幕完整复刻为 Next.js 前端，同时重构后端 LangGraph 报告输出为 6 模块结构化 JSON，使前端可直接消费。

**Architecture:** 单页状态机 `/report/[id]?step=parsing|confirm|directions|researching|done`，SSE 事件驱动状态迁移；后端重构 `generate_report_node` prompt，输出统一 6 模块 JSON，存入 `Report.content`。

**Tech Stack:** Next.js 14 App Router + TypeScript + Tailwind CSS；后端 FastAPI + LangGraph + OpenAI json_object mode；SSE via Redis Pub/Sub。

---

## Context

**问题：** 当前后端报告以调研方向为维度（`direction/heading/content/sources`），前端无独立的解析/确认/方向选择状态，HiTL 用弹窗实现而非原型的卡片解锁风格。

**目标结构：**

```
后端报告 JSON（存入 Report.content）:
{
  "job_interpretation": { hard: [], soft: [], hidden: [], summary: "" },
  "resume_match":        { strengths: [], gaps: [] },
  "company_profile":     { summary: "", tags: [] },
  "interview_qa":        [{ question: "", tip: "" }],
  "salary_range":        { market_min, market_max, median, suggested_min, suggested_max },
  "prep_suggestions":    [{ title: "", content: "" }]
}

前端路由: /report/[id]?step=parsing|confirm|directions|researching|done
状态机迁移:
  submit → parsing (SSE 连接)
  SSE parse_complete → confirm (卡片2解锁)
  用户确认 → directions (卡片3解锁)
  用户选方向 → researching (SSE 继续)
  SSE done → done (显示报告)
```

---

## 文件变更总览

**后端（6 个文件）：**
- Modify: `backend/app/graphs/state.py`（加 `report_data` 字段）
- Modify: `backend/app/graphs/nodes.py`（重构 prompt + 输出）
- Modify: `backend/app/schemas/report.py`（6 模块 Pydantic 模型）
- Modify: `backend/app/api/v1/reports.py`（返回结构化数据）
- Modify: `backend/app/tasks/research.py`（保存结构化 report）
- Create: `backend/alembic/versions/xxx_report_structured.py`（若模型变更）

**前端（14 个文件）：**
- Modify: `frontend/src/lib/types.ts`（报告类型）
- Modify: `frontend/src/lib/api.ts`（report API）
- Modify: `frontend/src/app/page.tsx`（首页对齐原型）
- Modify: `frontend/src/components/JobInputForm.tsx`（加简历上传）
- Rewrite: `frontend/src/app/report/[id]/page.tsx`（状态机）
- Create: `frontend/src/components/report/StepProgress.tsx`
- Create: `frontend/src/components/report/StageCard.tsx`
- Create: `frontend/src/components/report/JDConfirmCard.tsx`
- Create: `frontend/src/components/report/DirectionsCard.tsx`
- Create: `frontend/src/components/report/ResearchingCard.tsx`
- Create: `frontend/src/components/report/modules/JobInterpretationModule.tsx`
- Create: `frontend/src/components/report/modules/ResumeMatchModule.tsx`
- Create: `frontend/src/components/report/modules/CompanyProfileModule.tsx`
- Create: `frontend/src/components/report/modules/InterviewQAModule.tsx`
- Create: `frontend/src/components/report/modules/SalaryModule.tsx`
- Create: `frontend/src/components/report/modules/PrepSuggestionsModule.tsx`
- Create: `frontend/src/components/report/ReportView.tsx`

---

## Task 1：后端 — 更新 ResearchState 加 report_data 字段

**Files:**
- Modify: `backend/app/graphs/state.py`

- [ ] **Step 1: 在 ResearchState 加 report_data 字段**

  在 `state.py` 末尾的 `error` 字段后追加：

  ```python
  # ── 结构化报告（6 模块 JSON，存入 Report.content）──
  report_data: dict | None
  ```

- [ ] **Step 2: 验证**

  ```bash
  uv run python -c "from app.graphs.state import ResearchState; print('ok')"
  ```
  Expected: `ok`

---

## Task 2：后端 — 重构 generate_report_node 输出 6 模块结构

**Files:**
- Modify: `backend/app/graphs/nodes.py`

- [ ] **Step 1: 替换 `_build_report_prompt` 函数**

  将整个 `_build_report_prompt` 函数替换为：

  ```python
  def _build_report_prompt(state: ResearchState) -> str:
      has_resume = bool(state.get("resume_content"))
      resume_section = f"\n## 候选人简历摘要\n{state.get('resume_content', '')}\n" if has_resume else ""
      salary_hint = f"JD 中标注薪资：{state['salary_range']}" if state.get("salary_range") else "JD 未标注薪资，请基于市场调研估算"

      directions_done = list(state.get("search_results", {}).keys())
      search_summary = ""
      for direction, items in state.get("search_results", {}).items():
          search_summary += f"\n### {direction}\n"
          for item in items[:3]:
              search_summary += f"- {item.get('title', '')}: {item.get('snippet', '')}\n"

      return f"""你是一位专业的求职情报分析师。请基于以下信息，生成一份结构化面试情报报告。

  ## 职位信息
  - 职位：{state['title']}
  - 公司：{state['company']}
  - 核心要求：{', '.join(state.get('requirements', []))}
  - JD 摘要：{state.get('jd_summary', '')}
  - {salary_hint}
  {resume_section}
  ## 调研分析
  {state.get('research_analysis', '')}

  ## 调研来源数据
  {search_summary}

  ## 输出要求
  返回严格的 JSON，包含以下 6 个模块：

  {{
    "job_interpretation": {{
      "hard_requirements": ["硬性要求标签列表，3-6个"],
      "soft_requirements": ["软性偏好标签列表，2-4个"],
      "hidden_bonuses": ["隐性加分项列表，1-3个"],
      "summary": "对该岗位的 AI 解读，2-3句话，揭示隐性门槛和真实要求"
    }},
    "resume_match": {{
      "strengths": ["优势匹配点列表，每条15字内，{('基于简历内容分析' if has_resume else '基于行业通用标准给出示例')}"],
      "gaps": ["待补强 Gap 列表，每条15字内"]
    }},
    "company_profile": {{
      "summary": "公司近期动态和团队画像，3-4句话",
      "tags": ["画像标签，3-5个，如：规模扩张期/技术中台化/晋升节奏快"]
    }},
    "interview_qa": [
      {{
        "question": "高概率面试题，结合JD和候选人背景",
        "tip": "答题思路，50字内，聚焦具体方法论"
      }}
    ],
    "salary_range": {{
      "market_min": 最低市场薪资（整数，月薪元），
      "market_max": 最高市场薪资（整数，月薪元），
      "median": 市场中位数（整数，月薪元），
      "suggested_min": 建议报价下限（整数，月薪元），
      "suggested_max": 建议报价上限（整数，月薪元）
    }},
    "prep_suggestions": [
      {{
        "title": "建议标题，含时间预期如（3天）",
        "content": "具体行动方案，40字内"
      }}
    ]
  }}

  要求：
  - interview_qa 给出 3-5 道题
  - prep_suggestions 给出 3-4 条，优先针对 Gap
  - salary_range 单位统一为月薪（元），若无法估算则用 0
  - 所有字段不可为 null，列表最少 1 个元素
  """
  ```

- [ ] **Step 2: 替换 `generate_report_node` 函数**

  将 `generate_report_node` 替换为：

  ```python
  async def generate_report_node(state: ResearchState) -> dict:
      """LLM 生成结构化 6 模块报告"""
      await _publish_progress(state["job_id"], "generate_report")

      resp = await chat(
          messages=[{"role": "user", "content": _build_report_prompt(state)}],
          model="gpt-4o",
          response_format={"type": "json_object"},
      )
      try:
          report_data = json.loads(resp)
      except json.JSONDecodeError:
          report_data = {}

      return {
          "report_data": report_data,
          "final_report": json.dumps(report_data, ensure_ascii=False),
          "current_step": "review_draft",
      }
  ```

- [ ] **Step 3: 验证语法**

  ```bash
  cd backend && uv run python -c "from app.graphs.nodes import generate_report_node; print('ok')"
  ```
  Expected: `ok`

---

## Task 3：后端 — 更新 research.py 保存结构化报告

**Files:**
- Modify: `backend/app/tasks/research.py`

- [ ] **Step 1: 确认当前保存逻辑**

  读取 `backend/app/tasks/research.py`，找到将 `final_report` 存入 `Report.content` 的代码段。

- [ ] **Step 2: 改为保存 report_data JSON**

  找到类似 `report.content = state["final_report"]` 的行，改为：

  ```python
  import json as _json
  report_data = state.get("report_data") or {}
  report.content = _json.dumps(report_data, ensure_ascii=False)
  ```

- [ ] **Step 3: 验证**

  ```bash
  cd backend && uv run python -c "from app.tasks.research import run_research_graph; print('ok')"
  ```
  Expected: `ok`

---

## Task 4：后端 — 更新 report schema + API 端点

**Files:**
- Modify: `backend/app/schemas/report.py`
- Modify: `backend/app/api/v1/reports.py`

- [ ] **Step 1: 重写 `backend/app/schemas/report.py`**

  ```python
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
  ```

- [ ] **Step 2: 更新 `reports.py` 中的 GET 端点**

  找到 `GET /reports/{report_id}` 路由，修改返回逻辑：

  ```python
  import json
  from app.schemas.report import ReportResponse, ReportData

  @router.get("/{report_id}", response_model=ReportResponse)
  async def get_report(report_id: str, db: AsyncSession = Depends(get_db)):
      report = await db.get(Report, report_id)
      if not report:
          raise HTTPException(status_code=404, detail="Report not found")

      data = None
      if report.content:
          try:
              raw = json.loads(report.content)
              data = ReportData(**raw)
          except Exception:
              data = None

      return ReportResponse(
          id=report.id,
          job_id=report.job_id,
          status=report.status,
          data=data,
      )
  ```

- [ ] **Step 3: 验证 schema 导入**

  ```bash
  cd backend && uv run python -c "from app.schemas.report import ReportResponse, ReportData; print('ok')"
  ```
  Expected: `ok`

---

## Task 5：前端 — 更新 TypeScript 类型

**Files:**
- Modify: `frontend/src/lib/types.ts`

- [ ] **Step 1: 追加报告类型到 `types.ts`**

  在文件末尾追加：

  ```typescript
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
  ```

- [ ] **Step 2: 更新 `frontend/src/lib/api.ts` 加 fetchReport**

  追加：

  ```typescript
  import type { ReportResponse } from './types'

  export async function fetchReport(reportId: string): Promise<ReportResponse> {
    const res = await fetch(`/api/v1/reports/${reportId}`, { credentials: 'include' })
    if (!res.ok) throw new Error('Failed to fetch report')
    return res.json()
  }
  ```

---

## Task 6：前端 — StepProgress + StageCard 基础组件

**Files:**
- Create: `frontend/src/components/report/StepProgress.tsx`
- Create: `frontend/src/components/report/StageCard.tsx`

- [ ] **Step 1: 创建 `StepProgress.tsx`**

  ```tsx
  type StepState = 'locked' | 'active' | 'done'

  interface Props {
    steps: string[]
    states: StepState[]
  }

  export default function StepProgress({ steps, states }: Props) {
    return (
      <div className="flex items-center gap-0 pb-2">
        {steps.map((label, i) => {
          const s = states[i]
          const circleClass =
            s === 'done' ? 'bg-green-500 border-green-500 text-white' :
            s === 'active' ? 'bg-blue-600 border-blue-600 text-white' :
            'bg-white border-gray-300 text-gray-400'
          const labelClass = s === 'locked' ? 'text-gray-400' : 'text-gray-700 font-medium'
          return (
            <div key={i} className="flex items-center">
              <div className="flex flex-col items-center">
                <div className={`w-8 h-8 rounded-full border-2 flex items-center justify-center text-sm font-bold ${circleClass}`}>
                  {s === 'done' ? '✓' : i + 1}
                </div>
                <span className={`text-xs mt-1.5 text-center w-16 ${labelClass}`}>{label}</span>
              </div>
              {i < steps.length - 1 && (
                <div className={`flex-1 h-0.5 mb-5 w-16 ${s === 'done' ? 'bg-green-400' : 'bg-gray-200'}`} />
              )}
            </div>
          )
        })}
      </div>
    )
  }
  ```

- [ ] **Step 2: 创建 `StageCard.tsx`**

  ```tsx
  interface Props {
    state: 'locked' | 'active' | 'done'
    step: number
    title: string
    subtitle?: string
    badge?: string
    children?: React.ReactNode
  }

  export default function StageCard({ state, step, title, subtitle, badge, children }: Props) {
    if (state === 'locked') {
      return (
        <div className="bg-gray-50 rounded-2xl border border-gray-200 p-5 opacity-50">
          <div className="flex items-center gap-3">
            <div className="w-6 h-6 rounded-full bg-gray-200 flex items-center justify-center text-gray-400 text-xs">🔒</div>
            <p className="text-gray-400 font-medium">{title}</p>
          </div>
        </div>
      )
    }
    if (state === 'done') {
      return (
        <div className="bg-green-50 rounded-2xl border border-green-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded-full bg-green-500 flex items-center justify-center text-white text-sm">✓</div>
            <div>
              <p className="font-semibold text-green-700 text-sm">{title}</p>
              {subtitle && <p className="text-xs text-green-500">{subtitle}</p>}
            </div>
          </div>
        </div>
      )
    }
    return (
      <div className="bg-white rounded-2xl border-2 border-blue-400 p-5 shadow-md animate-[unlockCard_0.4s_ease_forwards]">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-7 h-7 rounded-full bg-blue-600 flex items-center justify-center text-white text-sm font-bold">{step}</div>
          <p className="font-semibold text-gray-800">{title}</p>
          {badge && <span className="ml-auto text-xs bg-blue-100 text-blue-600 px-2 py-0.5 rounded-full">{badge}</span>}
        </div>
        {children}
      </div>
    )
  }
  ```

- [ ] **Step 3: 在 `globals.css` 或 `tailwind.config` 加 unlockCard 动画**

  在 `frontend/src/app/globals.css` 的 `@layer utilities` 或 `@layer base` 中追加：

  ```css
  @keyframes unlockCard {
    from { opacity: 0.4; transform: translateY(8px); }
    to   { opacity: 1;   transform: translateY(0); }
  }
  ```

---

## Task 7：前端 — JDConfirmCard 组件

**Files:**
- Create: `frontend/src/components/report/JDConfirmCard.tsx`

- [ ] **Step 1: 创建组件**

  ```tsx
  'use client'
  import { useState } from 'react'

  interface JDData {
    title: string
    company: string
    requirements: string[]
  }

  interface Props {
    initial: JDData
    onConfirm: (data: JDData) => void
    onCancel: () => void
  }

  export default function JDConfirmCard({ initial, onConfirm, onCancel }: Props) {
    const [title, setTitle] = useState(initial.title)
    const [company, setCompany] = useState(initial.company)
    const [reqs, setReqs] = useState(initial.requirements)
    const [tagInput, setTagInput] = useState('')

    function addTag(val: string) {
      const v = val.trim()
      if (v && !reqs.includes(v)) setReqs([...reqs, v])
    }

    return (
      <div className="space-y-3">
        <div>
          <label className="text-xs text-gray-500 font-medium mb-1 block">职位名称</label>
          <input value={title} onChange={e => setTitle(e.target.value)}
            className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-400" />
        </div>
        <div>
          <label className="text-xs text-gray-500 font-medium mb-1 block">公司名称</label>
          <input value={company} onChange={e => setCompany(e.target.value)}
            className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-400" />
        </div>
        <div>
          <label className="text-xs text-gray-500 font-medium mb-1 block">
            核心要求
            <span className="text-gray-400 font-normal ml-1">（点击标签可删除，回车添加）</span>
          </label>
          <div className="flex flex-wrap gap-2 p-2 border border-gray-200 rounded-lg min-h-[44px] focus-within:ring-2 focus-within:ring-blue-400">
            {reqs.map((r, i) => (
              <span key={i} onClick={() => setReqs(reqs.filter((_, j) => j !== i))}
                className="inline-flex items-center gap-1 bg-blue-50 text-blue-700 text-xs px-2.5 py-1 rounded-full cursor-pointer hover:bg-red-50 hover:text-red-600 transition-colors">
                {r} <span>×</span>
              </span>
            ))}
            <input value={tagInput} onChange={e => setTagInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') { addTag(tagInput); setTagInput('') } }}
              placeholder="回车添加…"
              className="text-xs outline-none flex-1 min-w-[80px] px-1" />
          </div>
        </div>
        <div className="flex gap-3 mt-4">
          <button onClick={onCancel}
            className="flex-1 rounded-lg border border-gray-300 py-2.5 text-sm text-gray-600 hover:bg-gray-50">取消</button>
          <button onClick={() => onConfirm({ title, company, requirements: reqs })}
            className="flex-1 rounded-lg bg-blue-600 py-2.5 text-sm text-white font-semibold hover:bg-blue-700">
            确认，开始调研 →
          </button>
        </div>
      </div>
    )
  }
  ```

---

## Task 8：前端 — DirectionsCard 组件

**Files:**
- Create: `frontend/src/components/report/DirectionsCard.tsx`

- [ ] **Step 1: 创建组件**

  ```tsx
  'use client'
  import { useState } from 'react'

  const DEFAULT_DIRECTIONS = [
    { id: '公司近期动态',    desc: '融资、新产品、组织变动' },
    { id: '技术栈市场评价',  desc: '技术热度与前景' },
    { id: '薪资参考区间',    desc: '同级别行业对比' },
    { id: '简历匹配度分析',  desc: '针对你的背景个性化' },
    { id: '面试风格&题型',   desc: '来自社区公开信息' },
    { id: '备战建议',        desc: '针对 Gap 的具体方案' },
  ]

  interface Props {
    suggested?: string[]
    onStart: (selected: string[]) => void
  }

  export default function DirectionsCard({ suggested, onStart }: Props) {
    const dirs = suggested?.length
      ? suggested.map(s => ({ id: s, desc: '' }))
      : DEFAULT_DIRECTIONS

    const [selected, setSelected] = useState<Set<string>>(new Set(dirs.map(d => d.id)))

    function toggle(id: string) {
      const next = new Set(selected)
      if (next.has(id)) {
        if (next.size <= 1) return
        next.delete(id)
      } else {
        next.add(id)
      }
      setSelected(next)
    }

    return (
      <div>
        <p className="text-xs text-gray-400 mb-4">默认全选，去掉不感兴趣的方向</p>
        <div className="grid grid-cols-2 gap-2.5 mb-4">
          {dirs.map(d => {
            const on = selected.has(d.id)
            return (
              <div key={d.id} onClick={() => toggle(d.id)}
                className={`rounded-xl border-2 p-3.5 cursor-pointer transition-all select-none ${on ? 'border-blue-400 bg-blue-50' : 'border-gray-200 bg-white hover:border-gray-300'}`}>
                <div className="flex items-center gap-2 mb-0.5">
                  <div className={`w-4 h-4 rounded flex items-center justify-center text-xs ${on ? 'bg-blue-600 text-white' : 'border border-gray-300'}`}>
                    {on ? '✓' : ''}
                  </div>
                  <span className="text-sm font-medium text-gray-800">{d.id}</span>
                </div>
                {d.desc && <p className="text-xs text-gray-400 ml-6">{d.desc}</p>}
              </div>
            )
          })}
        </div>
        <button onClick={() => onStart(Array.from(selected))}
          className="w-full rounded-xl bg-blue-600 py-3 text-sm text-white font-semibold hover:bg-blue-700 transition-colors">
          开始调研（已选 {selected.size} 个方向）
        </button>
      </div>
    )
  }
  ```

---

## Task 9：前端 — ResearchingCard（SSE 实时进度）

**Files:**
- Create: `frontend/src/components/report/ResearchingCard.tsx`

- [ ] **Step 1: 创建组件**

  复用现有 SSE 逻辑（参考 `ProgressStream.tsx`），展示原型风格的逐条进度列表：

  ```tsx
  'use client'
  import { useEffect, useState } from 'react'

  const STEP_LABELS: Record<string, string> = {
    search:          '信息检索',
    analyze:         '分析整合',
    generate_report: '报告生成',
    done:            '完成',
  }

  interface ProgressItem {
    direction: string
    status: 'pending' | 'running' | 'done'
  }

  interface Props {
    reportId: string
    directions: string[]
    onDone: () => void
  }

  export default function ResearchingCard({ reportId, directions, onDone }: Props) {
    const [items, setItems] = useState<ProgressItem[]>(
      directions.map(d => ({ direction: d, status: 'pending' }))
    )
    const [currentStep, setCurrentStep] = useState('')

    useEffect(() => {
      const es = new EventSource(`/api/v1/reports/${reportId}/stream`)

      es.onmessage = (e) => {
        const data = JSON.parse(e.data)
        const step: string = data.step || ''
        setCurrentStep(step)

        if (step === 'done') {
          setItems(prev => prev.map(i => ({ ...i, status: 'done' })))
          es.close()
          onDone()
          return
        }

        setItems(prev => {
          const matchDir = directions.find(d => step.includes(d))
          return prev.map(item => {
            if (item.direction === matchDir) return { ...item, status: 'running' }
            if (prev.findIndex(i => i.direction === matchDir) > prev.findIndex(i => i.direction === item.direction)) {
              return { ...item, status: 'done' }
            }
            return item
          })
        })
      }

      es.onerror = () => es.close()
      return () => es.close()
    }, [reportId, directions, onDone])

    return (
      <div className="space-y-2 text-sm">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-2 h-2 rounded-full bg-blue-600 animate-[dotPulse_1.2s_ease-in-out_infinite]" />
          <p className="font-semibold text-gray-800">调研 & 报告生成中…</p>
          <span className="ml-auto text-xs text-gray-400">预计 3-5 分钟</span>
        </div>
        {items.map((item, i) => (
          <div key={i} className="flex items-center gap-2.5">
            {item.status === 'done' && (
              <div className="w-4 h-4 rounded-full bg-green-500 flex items-center justify-center text-white text-xs flex-shrink-0">✓</div>
            )}
            {item.status === 'running' && (
              <div className="w-4 h-4 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0">
                <div className="w-2 h-2 rounded-full bg-blue-600 animate-[dotPulse_1.2s_ease-in-out_infinite]" />
              </div>
            )}
            {item.status === 'pending' && (
              <div className="w-4 h-4 rounded-full bg-gray-200 flex-shrink-0" />
            )}
            <span className={item.status === 'pending' ? 'text-gray-400' : item.status === 'running' ? 'text-gray-800 font-medium' : 'text-gray-600'}>
              {item.direction}
            </span>
            {item.status === 'running' && <span className="ml-auto text-xs text-blue-500">搜索中…</span>}
            {item.status === 'done' && <span className="ml-auto text-xs text-green-500">完成</span>}
          </div>
        ))}
      </div>
    )
  }
  ```

- [ ] **Step 2: 在 `globals.css` 追加 dotPulse 动画**

  ```css
  @keyframes dotPulse {
    0%, 100% { transform: scale(1); opacity: 1; }
    50%       { transform: scale(0.5); opacity: 0.4; }
  }
  ```

---

## Task 10：前端 — 6 个报告模块组件

**Files:**
- Create: `frontend/src/components/report/modules/JobInterpretationModule.tsx`
- Create: `frontend/src/components/report/modules/ResumeMatchModule.tsx`
- Create: `frontend/src/components/report/modules/CompanyProfileModule.tsx`
- Create: `frontend/src/components/report/modules/InterviewQAModule.tsx`
- Create: `frontend/src/components/report/modules/SalaryModule.tsx`
- Create: `frontend/src/components/report/modules/PrepSuggestionsModule.tsx`

- [ ] **Step 1: 创建 `JobInterpretationModule.tsx`**

  ```tsx
  import type { JobInterpretation } from '@/lib/types'

  export default function JobInterpretationModule({ data }: { data: JobInterpretation }) {
    return (
      <div className="bg-white rounded-2xl border border-gray-200 p-6">
        <h2 className="text-base font-bold text-gray-900 mb-3 flex items-center gap-2">
          <span className="w-6 h-6 rounded-lg bg-blue-100 text-blue-600 flex items-center justify-center text-xs font-bold">1</span>
          职位解读
        </h2>
        <div className="flex flex-wrap gap-2 mb-3">
          {data.hard_requirements.map((r, i) => (
            <span key={i} className="text-xs px-2.5 py-1 rounded-full bg-red-50 text-red-600 border border-red-200">{r}</span>
          ))}
          {data.soft_requirements.map((r, i) => (
            <span key={i} className="text-xs px-2.5 py-1 rounded-full bg-yellow-50 text-yellow-700 border border-yellow-200">{r}</span>
          ))}
          {data.hidden_bonuses.map((r, i) => (
            <span key={i} className="text-xs px-2.5 py-1 rounded-full bg-gray-100 text-gray-500 border border-gray-200">{r}</span>
          ))}
        </div>
        <div className="flex gap-3 text-xs mb-3">
          <span className="inline-flex items-center gap-1"><span className="w-3 h-3 rounded bg-red-100 border border-red-300 inline-block" /> 硬性要求</span>
          <span className="inline-flex items-center gap-1"><span className="w-3 h-3 rounded bg-yellow-100 border border-yellow-300 inline-block" /> 软性偏好</span>
          <span className="inline-flex items-center gap-1"><span className="w-3 h-3 rounded bg-gray-100 border border-gray-300 inline-block" /> 隐性加分项</span>
        </div>
        <p className="text-sm text-gray-600 bg-gray-50 rounded-lg p-3 leading-relaxed">{data.summary}</p>
      </div>
    )
  }
  ```

- [ ] **Step 2: 创建 `ResumeMatchModule.tsx`**

  ```tsx
  import type { ResumeMatch } from '@/lib/types'

  export default function ResumeMatchModule({ data }: { data: ResumeMatch }) {
    return (
      <div className="bg-white rounded-2xl border border-gray-200 p-6">
        <h2 className="text-base font-bold text-gray-900 mb-4 flex items-center gap-2">
          <span className="w-6 h-6 rounded-lg bg-green-100 text-green-600 flex items-center justify-center text-xs font-bold">2</span>
          简历匹配度分析
        </h2>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-xs font-semibold text-green-600 uppercase tracking-wide mb-2">✅ 优势匹配</p>
            <ul className="space-y-2">
              {data.strengths.map((s, i) => (
                <li key={i} className="text-sm bg-green-50 rounded-lg px-3 py-2 text-gray-700">{s}</li>
              ))}
            </ul>
          </div>
          <div>
            <p className="text-xs font-semibold text-orange-500 uppercase tracking-wide mb-2">⚠️ 待补强 Gap</p>
            <ul className="space-y-2">
              {data.gaps.map((g, i) => (
                <li key={i} className="text-sm bg-orange-50 rounded-lg px-3 py-2 text-gray-700">{g}</li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    )
  }
  ```

- [ ] **Step 3: 创建 `CompanyProfileModule.tsx`**

  ```tsx
  import type { CompanyProfile } from '@/lib/types'

  export default function CompanyProfileModule({ data }: { data: CompanyProfile }) {
    return (
      <div className="bg-white rounded-2xl border border-gray-200 p-6">
        <h2 className="text-base font-bold text-gray-900 mb-3 flex items-center gap-2">
          <span className="w-6 h-6 rounded-lg bg-purple-100 text-purple-600 flex items-center justify-center text-xs font-bold">3</span>
          公司画像
        </h2>
        <p className="text-sm text-gray-600 leading-relaxed">{data.summary}</p>
        <div className="mt-3 flex flex-wrap gap-2">
          {data.tags.map((t, i) => (
            <span key={i} className="text-xs bg-purple-50 text-purple-600 px-2.5 py-1 rounded-full">{t}</span>
          ))}
        </div>
      </div>
    )
  }
  ```

- [ ] **Step 4: 创建 `InterviewQAModule.tsx`**

  ```tsx
  'use client'
  import { useState } from 'react'
  import type { InterviewQA } from '@/lib/types'

  export default function InterviewQAModule({ data }: { data: InterviewQA[] }) {
    const [open, setOpen] = useState<number | null>(null)
    return (
      <div className="bg-white rounded-2xl border border-gray-200 p-6">
        <h2 className="text-base font-bold text-gray-900 mb-3 flex items-center gap-2">
          <span className="w-6 h-6 rounded-lg bg-yellow-100 text-yellow-600 flex items-center justify-center text-xs font-bold">4</span>
          个性化面试题预测
        </h2>
        <div className="space-y-2">
          {data.map((qa, i) => (
            <div key={i} className="rounded-xl border border-gray-100 overflow-hidden">
              <button onClick={() => setOpen(open === i ? null : i)}
                className="w-full flex items-center gap-3 p-3.5 text-left hover:bg-gray-50 transition-colors">
                <span className="w-5 h-5 rounded-full bg-yellow-100 text-yellow-700 flex items-center justify-center text-xs flex-shrink-0 font-bold">Q</span>
                <span className="text-sm text-gray-700 flex-1">{qa.question}</span>
                <span className={`text-gray-400 transition-transform ${open === i ? 'rotate-180' : ''}`}>▾</span>
              </button>
              {open === i && (
                <div className="px-4 pb-4 text-sm text-gray-500 bg-gray-50 border-t border-gray-100 leading-relaxed pt-3">
                  💡 <strong className="text-gray-700">答题思路：</strong>{qa.tip}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    )
  }
  ```

- [ ] **Step 5: 创建 `SalaryModule.tsx`**

  ```tsx
  import type { SalaryRange } from '@/lib/types'

  function fmt(n: number) { return n >= 10000 ? `${(n/1000).toFixed(0)}K` : `${n}` }

  export default function SalaryModule({ data }: { data: SalaryRange }) {
    const total = data.market_max - data.market_min || 1
    const fillLeft = ((data.market_min - data.market_min) / total) * 100
    const fillWidth = 50
    const medianPos = ((data.median - data.market_min) / total) * 100
    const myPos = ((data.suggested_min - data.market_min) / total) * 100

    return (
      <div className="bg-white rounded-2xl border border-gray-200 p-6">
        <h2 className="text-base font-bold text-gray-900 mb-4 flex items-center gap-2">
          <span className="w-6 h-6 rounded-lg bg-teal-100 text-teal-600 flex items-center justify-center text-xs font-bold">5</span>
          薪资参考区间
        </h2>
        <div className="mb-2 flex justify-between text-xs text-gray-400">
          <span>{fmt(data.market_min)}</span>
          <span>{fmt(data.median)}</span>
          <span>{fmt(data.market_max)}+</span>
        </div>
        <div className="relative h-5 bg-gray-100 rounded-full overflow-hidden mb-1">
          <div className="absolute top-0 h-full bg-teal-100 rounded-full" style={{ left: '0%', width: '80%' }} />
          <div className="absolute top-0 h-full w-0.5 bg-teal-500" style={{ left: `${medianPos}%` }} />
          <div className="absolute top-1/2 -translate-y-1/2 w-4 h-4 rounded-full bg-blue-600 border-2 border-white shadow" style={{ left: `${myPos}%` }} />
        </div>
        <div className="mt-5 flex flex-wrap gap-4 text-sm text-gray-600">
          <div className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-full bg-teal-400" />市场区间：{fmt(data.market_min)}–{fmt(data.market_max)} / 月</div>
          <div className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-full bg-teal-600" />中位数：约 {fmt(data.median)}</div>
          <div className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-full bg-blue-600" />建议报价：{fmt(data.suggested_min)}–{fmt(data.suggested_max)}</div>
        </div>
      </div>
    )
  }
  ```

- [ ] **Step 6: 创建 `PrepSuggestionsModule.tsx`**

  ```tsx
  import type { PrepSuggestion } from '@/lib/types'

  export default function PrepSuggestionsModule({ data }: { data: PrepSuggestion[] }) {
    return (
      <div className="bg-white rounded-2xl border border-gray-200 p-6">
        <h2 className="text-base font-bold text-gray-900 mb-3 flex items-center gap-2">
          <span className="w-6 h-6 rounded-lg bg-rose-100 text-rose-600 flex items-center justify-center text-xs font-bold">6</span>
          备战建议
        </h2>
        <ol className="space-y-2.5">
          {data.map((s, i) => (
            <li key={i} className="flex gap-3 text-sm text-gray-700">
              <span className="w-5 h-5 rounded-full bg-rose-100 text-rose-600 flex items-center justify-center text-xs flex-shrink-0 font-bold mt-0.5">{i+1}</span>
              <span><strong>{s.title}</strong> — {s.content}</span>
            </li>
          ))}
        </ol>
      </div>
    )
  }
  ```

---

## Task 11：前端 — ReportView 组件（组合 6 模块）

**Files:**
- Create: `frontend/src/components/report/ReportView.tsx`

- [ ] **Step 1: 创建 `ReportView.tsx`**

  ```tsx
  import type { ReportData } from '@/lib/types'
  import JobInterpretationModule from './modules/JobInterpretationModule'
  import ResumeMatchModule from './modules/ResumeMatchModule'
  import CompanyProfileModule from './modules/CompanyProfileModule'
  import InterviewQAModule from './modules/InterviewQAModule'
  import SalaryModule from './modules/SalaryModule'
  import PrepSuggestionsModule from './modules/PrepSuggestionsModule'

  interface Props {
    data: ReportData
    jobTitle?: string
    company?: string
    date?: string
  }

  export default function ReportView({ data, jobTitle, company, date }: Props) {
    return (
      <div className="space-y-3 pb-20">
        <div className="flex items-center gap-2 p-3 bg-green-50 rounded-xl border border-green-200 mb-2">
          <span className="text-green-600 font-semibold text-sm">✅ 报告已生成</span>
          <span className="text-green-500 text-xs">{jobTitle} · {company} · {date}</span>
        </div>
        <JobInterpretationModule data={data.job_interpretation} />
        <ResumeMatchModule data={data.resume_match} />
        <CompanyProfileModule data={data.company_profile} />
        <InterviewQAModule data={data.interview_qa} />
        <SalaryModule data={data.salary_range} />
        <PrepSuggestionsModule data={data.prep_suggestions} />
      </div>
    )
  }
  ```

---

## Task 12：前端 — 重写 /report/[id]/page.tsx 为状态机

**Files:**
- Rewrite: `frontend/src/app/report/[id]/page.tsx`

- [ ] **Step 1: 重写页面组件**

  ```tsx
  'use client'
  import { useEffect, useState, useCallback } from 'react'
  import { useSearchParams, useRouter } from 'next/navigation'
  import type { ReportStep, ReportData } from '@/lib/types'
  import { fetchReport } from '@/lib/api'
  import StepProgress from '@/components/report/StepProgress'
  import StageCard from '@/components/report/StageCard'
  import JDConfirmCard from '@/components/report/JDConfirmCard'
  import DirectionsCard from '@/components/report/DirectionsCard'
  import ResearchingCard from '@/components/report/ResearchingCard'
  import ReportView from '@/components/report/ReportView'

  const STEP_LABELS = ['JD 解析', '确认信息', '选择方向', '生成报告']

  function stepToStates(step: ReportStep) {
    const map: Record<ReportStep, ('locked'|'active'|'done')[]> = {
      parsing:     ['active','locked','locked','locked'],
      confirm:     ['done','active','locked','locked'],
      directions:  ['done','done','active','locked'],
      researching: ['done','done','done','active'],
      done:        ['done','done','done','done'],
    }
    return map[step]
  }

  interface JobInfo { title: string; company: string; requirements: string[]; suggested_directions?: string[] }

  export default function ReportPage({ params }: { params: { id: string } }) {
    const reportId = params.id
    const searchParams = useSearchParams()
    const router = useRouter()

    const [step, setStep] = useState<ReportStep>(
      (searchParams.get('step') as ReportStep) || 'parsing'
    )
    const [jobInfo, setJobInfo] = useState<JobInfo | null>(null)
    const [selectedDirs, setSelectedDirs] = useState<string[]>([])
    const [reportData, setReportData] = useState<ReportData | null>(null)
    const [confirmedSubtitle, setConfirmedSubtitle] = useState('')

    function goStep(s: ReportStep) {
      setStep(s)
      router.replace(`/report/${reportId}?step=${s}`)
    }

    // SSE for parsing phase
    useEffect(() => {
      if (step !== 'parsing') return
      const es = new EventSource(`/api/v1/reports/${reportId}/stream`)
      es.onmessage = (e) => {
        const data = JSON.parse(e.data)
        if (data.step === 'parse_complete' || data.step === 'confirm') {
          setJobInfo({
            title: data.title || '',
            company: data.company || '',
            requirements: data.requirements || [],
            suggested_directions: data.suggested_directions || [],
          })
          es.close()
          goStep('confirm')
        }
      }
      es.onerror = () => es.close()
      return () => es.close()
    }, [reportId, step])

    // Load report when done
    useEffect(() => {
      if (step !== 'done') return
      fetchReport(reportId).then(r => {
        if (r.data) setReportData(r.data)
      })
    }, [step, reportId])

    async function handleConfirm(data: { title: string; company: string; requirements: string[] }) {
      await fetch(`/api/v1/jobs/${reportId}/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(data),
      })
      setConfirmedSubtitle(`${data.title} · ${data.company}`)
      goStep('directions')
    }

    async function handleStartResearch(dirs: string[]) {
      setSelectedDirs(dirs)
      await fetch(`/api/v1/jobs/${reportId}/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ selected_directions: dirs }),
      })
      goStep('researching')
    }

    const handleResearchDone = useCallback(() => goStep('done'), [reportId])

    return (
      <main className="max-w-3xl mx-auto px-4 pt-10 pb-16">
        <div className="mb-4">
          <StepProgress steps={STEP_LABELS} states={stepToStates(step)} />
        </div>

        <div className="space-y-3">
          {/* 卡片1：JD 解析 */}
          <StageCard state={step === 'parsing' ? 'active' : 'done'} step={1} title="JD 解析中…" subtitle="解析完成">
            {step === 'parsing' && (
              <div className="flex items-center gap-3">
                <div className="w-2 h-2 rounded-full bg-blue-600 animate-[dotPulse_1.2s_ease-in-out_infinite]" />
                <div>
                  <p className="font-semibold text-gray-800">正在解析 JD…</p>
                  <p className="text-xs text-gray-400 mt-0.5">Firecrawl 抓取页面 → LLM 提取关键信息</p>
                </div>
              </div>
            )}
          </StageCard>

          {/* 卡片2：确认 JD */}
          {step === 'parsing' ? (
            <StageCard state="locked" step={2} title="确认职位信息（等待解析完成）" />
          ) : step === 'confirm' ? (
            <StageCard state="active" step={2} title="确认职位信息" badge="需要你确认">
              <JDConfirmCard
                initial={jobInfo || { title: '', company: '', requirements: [] }}
                onConfirm={handleConfirm}
                onCancel={() => {}}
              />
            </StageCard>
          ) : (
            <StageCard state="done" step={2} title="职位信息已确认" subtitle={confirmedSubtitle} />
          )}

          {/* 卡片3：选择方向 */}
          {['parsing','confirm'].includes(step) ? (
            <StageCard state="locked" step={3} title="选择调研方向（等待确认）" />
          ) : step === 'directions' ? (
            <StageCard state="active" step={3} title="选择调研方向" badge="需要你选择">
              <DirectionsCard suggested={jobInfo?.suggested_directions} onStart={handleStartResearch} />
            </StageCard>
          ) : (
            <StageCard state="done" step={3} title={`已选择 ${selectedDirs.length} 个调研方向`} />
          )}

          {/* 卡片4：调研 & 报告 */}
          {['parsing','confirm','directions'].includes(step) ? (
            <StageCard state="locked" step={4} title="调研 & 生成报告（等待确认）" />
          ) : step === 'researching' ? (
            <StageCard state="active" step={4} title="调研 & 报告生成中">
              <ResearchingCard reportId={reportId} directions={selectedDirs} onDone={handleResearchDone} />
            </StageCard>
          ) : null}

          {/* 报告展示 */}
          {step === 'done' && reportData && (
            <ReportView
              data={reportData}
              jobTitle={jobInfo?.title}
              company={jobInfo?.company}
              date={new Date().toISOString().slice(0, 10)}
            />
          )}
        </div>
      </main>
    )
  }
  ```

---

## Task 13：前端 — 更新首页 + JobInputForm

**Files:**
- Modify: `frontend/src/app/page.tsx`
- Modify: `frontend/src/components/JobInputForm.tsx`

- [ ] **Step 1: 读取当前 `JobInputForm.tsx`，确认是否有文件上传逻辑**

  确认现有的 form submit 逻辑和 API 调用路径。

- [ ] **Step 2: 在 `JobInputForm.tsx` 加简历上传区域**

  在 URL 输入框下方、提交按钮上方，追加简历上传 UI：

  ```tsx
  {/* 简历上传区 */}
  <div
    className="rounded-xl border-2 border-dashed border-gray-300 bg-white px-6 py-8 text-center cursor-pointer hover:border-blue-400 hover:bg-blue-50 transition-all group"
    onClick={() => fileInputRef.current?.click()}
    onDragOver={e => e.preventDefault()}
    onDrop={e => { e.preventDefault(); handleFile(e.dataTransfer.files[0]) }}
  >
    <div className="text-3xl mb-2">📄</div>
    <p className="text-gray-500 text-sm group-hover:text-blue-600">
      {resumeFile ? resumeFile.name : '点击或拖拽上传简历（PDF / DOCX，可选）'}
    </p>
    <p className="text-gray-400 text-xs mt-1">上传后 AI 将生成个性化面试题预测</p>
    <input ref={fileInputRef} type="file" accept=".pdf,.docx" className="hidden" onChange={e => handleFile(e.target.files?.[0])} />
  </div>
  ```

  并在 form submit 时将 `resumeFile` 以 multipart/form-data 一同提交（若后端 `/jobs` 端点支持），或先上传简历获取 `resume_id` 再提交。

- [ ] **Step 3: 提交后跳转到 `/report/[id]?step=parsing`**

  修改 submit 成功后的跳转：

  ```typescript
  router.push(`/report/${job.id}?step=parsing`)
  ```

---

## Task 14：测试

- [ ] **Step 1: 后端 schema 测试**

  ```bash
  cd backend && uv run pytest tests/ -k "report" -v
  ```
  Expected: 所有 report 相关测试通过（或无测试则跳过）

- [ ] **Step 2: 前端类型检查**

  ```bash
  cd frontend && pnpm tsc --noEmit
  ```
  Expected: 0 errors

- [ ] **Step 3: 手动测试完整流程（需要 dev 环境启动）**

  ```bash
  ./dev.sh
  ```
  流程：
  1. 访问 `http://localhost:3000` → 看到首页输入框
  2. 输入 JD URL → 点击开始分析 → 跳转到 `/report/[id]?step=parsing`
  3. 卡片1 显示旋转点 + 解析中文案，卡片2/3/4 锁定
  4. SSE 触发后 → 卡片2 解锁，显示 JDConfirmCard
  5. 编辑字段、管理标签 → 点确认
  6. 卡片3 解锁，显示 DirectionsCard，6 个方向卡片
  7. 选方向 → 点开始调研
  8. 卡片4 解锁，ResearchingCard 实时更新进度
  9. 完成后 → 显示 ReportView 6 个模块

---

## 验证要点

1. `GET /api/v1/reports/{id}` 返回 `{ data: { job_interpretation, resume_match, ... } }` 结构
2. 页面刷新后 `?step=` 参数保持，不重置状态
3. 卡片解锁动画 `unlockCard` 正常执行
4. 薪资模块在 salary_range 全为 0 时不崩溃（graceful empty state）
5. 无简历时 `resume_match` 显示通用标准而非崩溃
