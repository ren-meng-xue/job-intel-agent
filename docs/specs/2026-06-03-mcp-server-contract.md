# job-intel MCP Server 接口契约

- 日期：2026-06-03
- 消费方：multi-agent-coach 的 Prepare 阶段 research_agent
- 主设计文档：multi-agent-coach 仓库 `docs/superpowers/specs/2026-06-03-research-agent-mcp-design.md`

## 本期对外承诺

新增独立 ASGI 进程作为 MCP server，复用现有 service 函数，让外部 Agent 系统能在自己的工具思考循环中调用 job-intel 的能力。

## 工具清单

### 必选

| 工具                       | 入参                                                                                                                  | 出参                                                                              | 底层调用                            |
| -------------------------- | --------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- | ----------------------------------- |
| `extract_jd_text`          | `text: str`                                                                                                           | `{title, company, requirements[], jd_summary, salary_range, location, work_type}` | `llm_service.extract_job_info`      |
| `web_search`               | `query: str, max_results: int = 5`                                                                                    | `[{title, url, content}]`                                                         | `search_service.search`             |
| `analyze_position`         | `title, company, jd_summary, requirements[], search_results: dict, resume_content?: str`                              | `analysis: str (300-500 字)`                                                      | `graphs/nodes.analyze_node`         |
| `generate_position_report` | `title, company, jd_summary, requirements[], search_results: dict, directions[], resume_content?, research_analysis?` | 6 模块 JSON                                                                       | `graphs/nodes.generate_report_node` |

### 可选

| 工具             | 入参               | 出参                                                  | 底层调用                          |
| ---------------- | ------------------ | ----------------------------------------------------- | --------------------------------- |
| `scrape_jd_url`  | `url: str`         | `markdown: str`                                       | `crawler_service.scrape_url`      |
| `extract_resume` | `raw_content: str` | `{summary, skills[], work_experience[], education[]}` | `llm_service.extract_resume_info` |

## 启动方式

- 命令：`uv run python -m app.mcp_server`
- 传输：streamable HTTP
- 监听：`host="::"`（IPv6，Railway 私网必需）+ `port=$PORT`（本地默认 9001）

## SLA

- 单工具超时：30s
- 异常返回：JSON-RPC error
- 不写 DB、无状态、不鉴权（V1 仅 localhost / Railway 私网信任）

## 文件改动

- 新增：`backend/app/mcp_server.py` / `backend/tests/unit/test_mcp_server.py`
- 修改：`backend/pyproject.toml` 加 `mcp[cli]` / `dev.sh` 加启动行
