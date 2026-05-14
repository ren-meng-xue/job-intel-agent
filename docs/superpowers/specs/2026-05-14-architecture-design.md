# Job Intel Agent — 架构设计决策文档

> 记录日期：2026-05-14  
> 用途：开发参考 + 面试复习

---

## 一、产品定位（一句话）

粘贴 JD 链接 + 上传简历 → AI Agent 自主调研 → 3-5 分钟生成专属面试情报报告。

---

## 二、UI 原型屏幕流（共 7 屏）

| 编号 | 屏幕 | 关键交互 |
|---|---|---|
| ① | 登录 / 注册 | 左侧动画角色 + 右侧表单，Tab 切换登录/注册 |
| ② | 首页输入 | JD URL 输入框 + 简历拖拽上传（可选）|
| ③ | 解析中 | 4 阶段进度卡片，阶段 1 转圈，2-4 锁定 |
| ④ | 确认 JD | 阶段 1 完成，阶段 2 解锁：可编辑职位名/公司/标签 |
| ⑤ | 选择方向 | 阶段 3 解锁：6 个调研方向卡片，默认全选可反选 |
| ⑥ | 调研进行中 | 阶段 4：6 个子任务逐条完成动画 |
| ⑦ | 报告完成 | 6 模块：职位解读、匹配度、公司画像、面试题(折叠)、薪资、备战建议 |

**前端实现：** 完全按原型 (`ui-prototype.html`) 复刻，技术栈 Next.js + TypeScript + Tailwind CSS。

---

## 三、Auth 方案

**参考：** offer-copilot 项目的完整实现，直接复用该模式。

| 要素 | 设计 |
|---|---|
| Access Token | JWT，短期（15 分钟），放响应体 |
| Refresh Token | 随机字符串，长期，**HttpOnly Cookie** 存储 |
| 数据库 | `users` 表 + `auth_sessions` 表（session 可撤销） |
| Refresh Token 存储 | DB 存 hash，Cookie 存明文，登录时 hash 比对 |
| 安全措施 | 密码 bcrypt hash、refresh token rotation、logout 撤销 session |

**关键决策依据：** HttpOnly Cookie 存 refresh token 可防 XSS 窃取；DB 存 session hash 支持强制下线/撤销。

---

## 四、核心 Pipeline 架构

### 整体流程

```
POST /api/v1/jobs
  → 存 Job 记录（status=parsing）
  → 触发 Celery task: task_parse_jd
  → SSE 推进度

[用户收到解析结果，确认职位信息]

POST /api/v1/jobs/{id}/confirm  (携带修正后的 title/company/requirements)
  → 更新 Job 记录
  → 触发 Celery task: task_run_research（携带方向参数）
  → SSE 推进度 → 报告完成
```

### Human-in-the-Loop 实现方式：拆任务（方案 A）

**选择理由：** 这两个 HiTL 节点是固定暂停点，不需要 LangGraph 的状态序列化。拆成两个独立 Celery 任务，用 API 触发，最简洁，最好排查。

**不选"LangGraph 全程 interrupt"的原因：** 线性固定流程用 interrupt 是为用而用，面试官看出来反而扣分。技术选型要有依据。

---

## 五、LangGraph 的正确使用位置

**不用在 HiTL 暂停，用在研究阶段的多步 Agent 图。**

### research 图结构

```
START
  └─→ [parallel_search_nodes]  ← 根据用户选择的方向，并行搜索
       ├─ search_company_news
       ├─ search_tech_stack
       ├─ search_salary
       ├─ search_interview_style
       └─ ...（用户选了哪些方向就跑哪些节点）
  └─→ [synthesis_node]         ← LLM 汇总每个方向的搜索结果
  └─→ [report_node]            ← 整合生成 6 模块报告
  └─→ END
```

**LangGraph 在这里的价值：**
- 并行节点（用户选 4 个方向就并发跑 4 个 search）
- 条件路由（哪些方向被选中）
- 图状态（`AgentState`）天然管理中间搜索结果，不需要手动传参

**面试时如何解释这个决策：**
> "HiTL 的两个暂停点是固定位置、固定行为，用任务拆分更简洁。LangGraph 用在研究阶段，因为那里有真正的并行节点和条件路由需求——用户选了哪些调研方向，图会动态决定跑哪些搜索节点，这才是 LangGraph 发挥价值的场景。"

---

## 六、实时进度推送

**方案：** SSE（Server-Sent Events）+ Redis Pub/Sub，**禁止轮询**。

```
Celery worker 每完成一个子步骤
  → publish 到 Redis channel: job:{job_id}:progress
  → FastAPI SSE 端点订阅该 channel
  → 推送给前端

前端 EventSource 监听 /api/v1/reports/{id}/stream
  → 更新进度 UI（调研进行中屏幕）
```

**客户端断连处理：** SSE 端点在 finally 块中主动 unsubscribe Redis channel，避免订阅泄漏。

---

## 七、简历解析

**时机：** 用户上传后立即异步解析（eager），不等到调研时才解析。

**实现：**
1. `POST /api/v1/resume/upload` → 存文件 → 触发 `task_parse_resume`
2. `task_parse_resume`：pdfplumber/docx2txt 提取文本 → LLM 结构化提取关键字段
3. 解析结果存 DB，调研时作为 `AgentState` 的输入

**扫描版 PDF 风险：** 预留 OCR 回退（pytesseract），但 MVP 阶段暂不实现。

---

## 八、数据模型（核心表）

| 表 | 关键字段 |
|---|---|
| `users` | id, email, username, password_hash, status |
| `auth_sessions` | id, user_id, refresh_token_hash, expires_at, revoked_at |
| `jobs` | id, user_id, url, raw_content, title, company, requirements(JSON), status |
| `resumes` | id, user_id, filename, parsed_content(JSON), status |
| `reports` | id, job_id, resume_id, content(JSON/Text), status |

---

## 九、技术栈速查

| 层 | 技术 |
|---|---|
| 后端框架 | FastAPI + uvicorn（ASGI） |
| 任务队列 | Celery + Redis broker |
| Agent 编排 | LangGraph（仅研究阶段） |
| LLM | GPT-4o（推理）/ GPT-4o-mini（轻量） |
| 爬取 | Firecrawl |
| 搜索 | Tavily API |
| 数据库 | PostgreSQL + pgvector，SQLAlchemy（异步） |
| 迁移 | Alembic |
| 实时推送 | SSE + Redis Pub/Sub |
| 前端 | Next.js + TypeScript + Tailwind CSS |
| 包管理 | uv（后端）/ pnpm（前端） |

