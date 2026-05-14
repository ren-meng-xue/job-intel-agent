# Job Intel Agent — 主控规范

## 全局约束（始终生效，任何情况不可跳过）

1. 始终使用**简体中文**回复
2. 所有配置走环境变量，**禁止硬编码** Key / Secret
3. commit / push 前必须等待用户回复「**1**」，否则不执行
   - push 完成后，若当前分支非 main/master，**必须询问用户是否需要合并到 main 分支**
4. LLM 调用只在 `services/` 层，`api/` 层禁止直接调用
5. 实时状态用 SSE + Redis Pub/Sub，**禁止轮询**
6. 数据库变更必须走 Alembic，禁止直接改表结构
7. commit 前，若新增或修改了 ORM 模型（`models/` 下任意文件），必须完成：
   - `alembic revision --autogenerate -m "描述"` 已执行并 review
   - `alembic upgrade head` 本地运行成功（表/字段与模型一致）
   - 迁移文件已纳入本次 commit
8. 本地开发环境通过 `./dev.sh` 启动（混合模式：Docker 跑 postgres + redis，其余服务直接在本机跑）。新增或删除服务时，**必须同步更新 `dev.sh`**，保持脚本与实际架构一致
9. 每次会话开始时，以及用户说「todo」或询问下一步时，读取 `changelogs/` 下日期最新的 `.md` 文件（格式与分支检查规则见 `.claude/skills/changelog.md`），了解当前进展和下一步方向。**不需要扫所有 changelog，只读最新一篇**。读完后**必须执行 `git branch --show-current`** 检查当前分支，若与 changelog 中记录的分支不一致，提醒用户切换；**若一致，直接进入下一步工作，不再提示未提交文件**
10. 切换分支前，**必须先执行 `git status`** 检查未提交的改动。如有未提交文件，列出文件清单，询问用户：是先 commit 再切，还是直接切（改动会带过去）。用户回复「1」即同意推荐方案

---

## Skill 路由表

遇到以下情境时，**主动读取**对应 Skill 文件，按其规范执行：

| 触发情境 | 读取 Skill |
|---|---|
| 讨论产品方向、功能边界、用户价值、竞品对比 | `.claude/skills/product.md` → 结合 `superpowers: brainstorming` |
| 开发新功能、新 API、新模块 | `.claude/skills/feature-dev.md` → 结合 `superpowers: writing-plans` |
| 修复 Bug、排查问题、分析报错 | `.claude/skills/bug-fix.md` → 结合 `gstack: /investigate` |
| 编写测试、输出测试报告 | `.claude/skills/testing.md` → 结合 `superpowers: tdd` + `gstack: /qa` |
| 前端 UI 开发、页面验证、设计审计 | `.claude/skills/frontend.md` → 结合 `gstack: /browse /qa /design-review` |
| 部署上线、环境配置、迁移 | `.claude/skills/deploy.md` → 结合 `gstack: /cso /ship` |
| 代码审查（任意场景） | `gstack: /review` |
| 并行子任务开发（多模块同步） | `superpowers: subagent-driven-development` |
| 写 changelog、读 changelog、更新进度 | `.claude/skills/changelog.md` |

---

## 技术栈（快速参考）

- 后端：FastAPI + **uvicorn**（ASGI）+ Celery + Redis + SQLAlchemy（异步）
- Agent 编排：**LangGraph**（多步调研 Agent 图、Human-in-the-Loop 节点）
- 前端：Next.js + TypeScript + Tailwind CSS
- LLM：`gpt-4o`（主推理）/ `gpt-4o-mini`（轻量任务）
- 爬取：Firecrawl | 搜索：Tavily API | 数据库：PostgreSQL + pgvector
- 包管理：**uv**（后端，Python 3.12，`pyproject.toml` + `uv sync`）/ **pnpm**（前端）
- 测试：**pytest** + pytest-asyncio + httpx
- 目录：`backend/`（FastAPI + Alembic）/ `frontend/`（Next.js）/ `dev.sh`（一键启动）
