# SSE HiTL 中断 & 前端状态 Bug 修复计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复三个测试发现的 Bug：研究阶段 HiTL interrupt 被前端忽略导致永久卡死；刷新后 interrupt 丢失；确认表单因 React state 初始化时序问题显示空；方向数量刷新后显示"全部"。

**Architecture:** 
- Bug 1/1b：ResearchingCard 新增 interrupt 事件分支，展示分析结果供用户确认；backend 同时写 Redis Key 持久化 interrupt payload，SSE 重连时先读 key 回放。
- Bug 2：ReportPage 确认步骤改为先加载数据再渲染表单（loading gate），避免 JDConfirmCard useState 只初始化一次的问题。
- Bug 3：进入 researching 步骤时从 job API 读取 selected_directions 填充 selectedDirs state。

**Tech Stack:** FastAPI (SSE), Redis Pub/Sub + Redis Key, LangGraph MemorySaver, Next.js (React hooks, EventSource)

---

## 文件地图

| 文件 | 变更类型 | 职责 |
|------|---------|------|
| `backend/app/tasks/research.py` | 修改 | interrupt 事件写入 Redis Key；resume/complete 时删除 Key |
| `backend/app/api/v1/reports.py` | 修改 | SSE 连接时先检查 Redis Key，有 pending interrupt 立即回放 |
| `frontend/src/lib/api.ts` | 修改 | 新增 `resumeJob()` 函数 |
| `frontend/src/components/report/ResearchingCard.tsx` | 修改 | 处理 `type=interrupt` 事件，展示 HiTL 确认 UI |
| `frontend/src/app/report/[id]/page.tsx` | 修改 | 确认步骤加 loading gate；researching 步骤加载 selectedDirs |

---

## Task 1：后端 — 持久化 interrupt payload 到 Redis Key

**Files:**
- Modify: `backend/app/tasks/research.py`

研究图触发 interrupt 时，除了 Pub/Sub，同时写一个 TTL=3600s 的 Redis Key，供 SSE 重连时回放。  
resume/complete 时删除该 Key。

- [ ] **Step 1：在 `_do_run_research` 中，发布 interrupt 事件时同时写 Redis Key**

定位 `backend/app/tasks/research.py` 中处理 `__interrupt__` 事件的代码块（约第 380-388 行）：

```python
if node_name == "__interrupt__":
    interrupt_values = event["__interrupt__"]
    if interrupt_values:
        val = interrupt_values[0]
        interrupt_payload = (
            val.value if hasattr(val, "value") else val
        )
        payload_json = json.dumps(interrupt_payload)
        await redis.publish(f"job:{job_id}", payload_json)
```

替换为：

```python
if node_name == "__interrupt__":
    interrupt_values = event["__interrupt__"]
    if interrupt_values:
        val = interrupt_values[0]
        interrupt_payload = (
            val.value if hasattr(val, "value") else val
        )
        payload_json = json.dumps(interrupt_payload)
        # 持久化，供 SSE 重连回放（TTL 1 小时）
        await redis.setex(
            f"job:{job_id}:pending_interrupt", 3600, payload_json
        )
        await redis.publish(f"job:{job_id}", payload_json)
```

同样处理 `except GraphInterrupt as exc` 内的 publish（约第 398-401 行）：

```python
except GraphInterrupt as exc:
    for item in (exc.interrupts if hasattr(exc, "interrupts") else []):
        val = item.value if hasattr(item, "value") else item
        payload_json = json.dumps(val)
        await redis.setex(
            f"job:{job_id}:pending_interrupt", 3600, payload_json
        )
        await redis.publish(f"job:{job_id}", payload_json)
    return
```

以及外层 `except GraphInterrupt as exc`（约第 422-426 行）同理添加 `setex`。

- [ ] **Step 2：research 正常完成（completed）时删除 pending_interrupt Key**

在 `_do_run_research` 中，`completed` 事件 publish 之前（约第 419-420 行），添加删除：

```python
# stream 正常结束 → 检查是否真正完成（非 interrupt 暂停）
final_state = await graph.aget_state(config)
if final_state and not final_state.next:
    fsv = final_state.values or {}
    final_report = fsv.get("final_report")
    if final_report:
        from app.models.report import Report
        report_data = fsv.get("report_data") or {}
        content = json.dumps(report_data, ensure_ascii=False)
        async with AsyncSessionLocal() as session:
            session.add(Report(
                job_id=job_id, content=content, status="done",
            ))
            repo = JobRepository(session)
            await repo.update_status(job_id, "done")
        # 清理 pending interrupt（已完成，不再需要）
        await redis.delete(f"job:{job_id}:pending_interrupt")
        await redis.publish(f"job:{job_id}", json.dumps({"type": "completed"}))
```

- [ ] **Step 3：`_do_run_research` resume 路径读取 action 后删除 pending_interrupt**

在 `_do_run_research` 的 resume 分支中，读取 `resume_action` 并 `delete` 后（约第 313-315 行），添加：

```python
if raw:
    action_data = json.loads(raw)
    await redis.delete(f"job:{job_id}:resume_action")
# 用户已 resume，清理 pending interrupt key
await redis.delete(f"job:{job_id}:pending_interrupt")
```

- [ ] **Step 4：运行后端测试确认没有回归**

```bash
cd backend && uv run pytest tests/test_research_graph_bugfix.py tests/test_reports_sse.py -v 2>&1 | tail -20
```

期望：现有测试全部 PASS（或无相关测试时 no tests collected）。

---

## Task 2：后端 — SSE 重连时回放 pending interrupt

**Files:**
- Modify: `backend/app/api/v1/reports.py`

- [ ] **Step 1：修改 `_sse_generator` 函数签名，接受 `job_id` 同时做回放检查**

当前 `_sse_generator(job_id: str)` 在订阅 Pub/Sub 之后直接进入消息循环。

在 `await pubsub.subscribe(f"job:{job_id}")` 之后、`while True` 之前插入：

```python
# 回放：检查 pending interrupt（刷新/重连场景恢复）
pending = await redis.get(f"job:{job_id}:pending_interrupt")
if pending:
    yield f"data: {pending}\n\n"
```

完整改动后的函数头部：

```python
async def _sse_generator(job_id: str):
    redis: aioredis.Redis = await aioredis.from_url(
        settings.REDIS_URL, decode_responses=True
    )
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"job:{job_id}")

    try:
        # 回放：检查 pending interrupt（刷新/重连场景恢复）
        pending = await redis.get(f"job:{job_id}:pending_interrupt")
        if pending:
            yield f"data: {pending}\n\n"

        while True:
            # ... 原有循环不变
```

- [ ] **Step 2：启动后端，手工验证 SSE 回放**

```bash
# 1. 确认 redis 中有 pending_interrupt key（用上一个 job_id 或创建新的）
docker exec job-intel-agent-redis-1 redis-cli keys "job:*:pending_interrupt"

# 2. 打开新 SSE 连接，确认立即收到 interrupt 数据
# （可用 curl 测试）
TOKEN=$(curl -s -X POST http://localhost:8001/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"917596600@qq.com","password":"qq1.2.3."}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))")
curl -N "http://localhost:8001/api/v1/reports/31e463ea-9a41-4d9e-98f8-8b3420c71b30/stream?token=$TOKEN"
```

期望：连接后立即收到 `data: {"type":"interrupt",...}` 行。

---

## Task 3：前端 — 新增 `resumeJob` API 函数

**Files:**
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1：在 `frontend/src/lib/api.ts` 末尾添加 `resumeJob` 函数**

```typescript
export async function resumeJob(
  jobId: string,
  action: 'approve' | 'retry',
  feedback?: string
): Promise<void> {
  await checkOk(
    await http(`/jobs/${jobId}/resume`, {
      method: 'POST',
      body: JSON.stringify({ action, feedback: feedback ?? null, edits: null }),
    })
  )
}
```

- [ ] **Step 2：TypeScript 类型检查**

```bash
cd frontend && pnpm tsc --noEmit 2>&1 | head -20
```

期望：无新增错误。

---

## Task 4：前端 — ResearchingCard 处理 interrupt 事件

**Files:**
- Modify: `frontend/src/components/report/ResearchingCard.tsx`

当 SSE 收到 `type=interrupt` 事件时，展示 AI 分析摘要，提供「确认 → 继续」和「重新分析」按钮。用户操作后调用 `resumeJob`，然后继续等待下一个事件。

- [ ] **Step 1：重写 `ResearchingCard.tsx`**

```tsx
'use client'
import { useEffect, useState } from 'react'
import { streamReport, resumeJob } from '@/lib/api'

interface ProgressItem {
  direction: string
  status: 'pending' | 'running' | 'done'
}

interface InterruptData {
  node: string
  data: {
    analysis?: string
    draft_sections?: Array<{ heading: string; content: string }>
    search_results?: Record<string, unknown[]>
  }
}

interface Props {
  reportId: string
  directions: string[]
  onDone: () => void
}

export default function ResearchingCard({ reportId, directions, onDone }: Props) {
  const [items, setItems] = useState<ProgressItem[]>(
    directions.map((d) => ({ direction: d, status: 'pending' }))
  )
  const [currentMsg, setCurrentMsg] = useState('正在初始化调研任务...')
  const [interrupt, setInterrupt] = useState<InterruptData | null>(null)
  const [resuming, setResuming] = useState(false)
  const [esRef, setEsRef] = useState<EventSource | null>(null)

  useEffect(() => {
    const es = streamReport(
      reportId,
      (e) => {
        let data: {
          step?: string
          type?: string
          node?: string
          message?: string
          data?: InterruptData['data']
        } = {}
        try {
          data = JSON.parse(e.data)
        } catch {
          return
        }

        if (data.message) {
          setCurrentMsg(data.message)
        }

        // HiTL interrupt：暂停等待用户确认
        if (data.type === 'interrupt') {
          setInterrupt({
            node: data.node || 'unknown',
            data: data.data || {},
          })
          return
        }

        const step = data.step || data.node || ''

        if (step === 'done' || data.type === 'completed') {
          setItems((prev) => prev.map((i) => ({ ...i, status: 'done' })))
          setCurrentMsg('报告生成完成！')
          es.close()
          onDone()
          return
        }

        setItems((prev) => {
          const matchIdx = directions.findIndex((d) => step.includes(d))
          if (matchIdx >= 0) {
            return prev.map((item, i) => {
              if (i === matchIdx) return { ...item, status: 'running' }
              if (i < matchIdx) return { ...item, status: 'done' }
              return item
            })
          }
          return prev
        })
      }
    )
    setEsRef(es)
    return () => es.close()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reportId, directions, onDone])

  async function handleResume(action: 'approve' | 'retry', feedback?: string) {
    setResuming(true)
    setInterrupt(null)
    setCurrentMsg(action === 'approve' ? '正在继续生成报告...' : '正在重新分析...')
    try {
      await resumeJob(reportId, action, feedback)
    } finally {
      setResuming(false)
    }
  }

  // 展示 HiTL 确认面板
  if (interrupt) {
    const analysis = interrupt.data.analysis
    return (
      <div className="space-y-4">
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
          <p className="font-semibold text-amber-800 mb-1">⏸ AI 需要你确认分析结果</p>
          <p className="text-xs text-amber-700">
            {interrupt.node === 'review_results'
              ? '请确认调研分析是否符合预期，再继续生成报告'
              : '请确认报告草稿是否符合预期'}
          </p>
        </div>

        {analysis && (
          <div className="bg-gray-50 border border-gray-200 rounded-xl p-4 text-sm text-gray-700 leading-relaxed max-h-60 overflow-y-auto">
            <p className="font-medium text-gray-500 text-xs mb-2 uppercase tracking-wider">调研分析摘要</p>
            {analysis}
          </div>
        )}

        <div className="flex gap-3">
          <button
            onClick={() => handleResume('retry')}
            disabled={resuming}
            className="flex-1 rounded-lg border border-gray-300 py-2.5 text-sm text-gray-600 hover:bg-gray-50 disabled:opacity-50"
          >
            重新分析
          </button>
          <button
            onClick={() => handleResume('approve')}
            disabled={resuming}
            className="flex-1 rounded-lg bg-blue-600 py-2.5 text-sm text-white font-semibold hover:bg-blue-700 disabled:opacity-50"
          >
            {resuming ? '处理中...' : '确认，继续生成报告 →'}
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-2 text-sm">
      <div className="bg-blue-50 border border-blue-100 rounded-xl p-4 mb-6">
        <div className="flex items-center gap-3">
          <div className="w-2.5 h-2.5 rounded-full bg-blue-600 animate-pulse" />
          <div>
            <p className="font-semibold text-blue-900">AI 正在深度调研中</p>
            <p className="text-blue-700 text-xs mt-0.5">{currentMsg}</p>
          </div>
        </div>
      </div>

      <div className="px-1 space-y-3">
        <p className="text-xs text-gray-400 uppercase tracking-wider font-medium">调研维度</p>
        {items.map((item, i) => (
          <div key={i} className="flex items-center gap-3">
            {item.status === 'done' ? (
              <div className="w-5 h-5 rounded-full bg-green-500 flex items-center justify-center text-white text-[10px] flex-shrink-0 shadow-sm">✓</div>
            ) : item.status === 'running' ? (
              <div className="w-5 h-5 rounded-full bg-blue-600 flex items-center justify-center flex-shrink-0 shadow-sm">
                <div className="w-1.5 h-1.5 rounded-full bg-white animate-ping" />
              </div>
            ) : (
              <div className="w-5 h-5 rounded-full border-2 border-gray-200 flex-shrink-0" />
            )}
            <span className={`transition-colors ${item.status === 'pending' ? 'text-gray-400' : 'text-gray-700 font-medium'}`}>
              {item.direction}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 2：TypeScript 编译检查**

```bash
cd frontend && pnpm tsc --noEmit 2>&1 | head -20
```

期望：无错误。

---

## Task 5：前端 — 修复确认表单 loading gate（Bug 2）

**Files:**
- Modify: `frontend/src/app/report/[id]/page.tsx`

问题：`JDConfirmCard` 用 `useState(initial.title)` 初始化，`getJob` 异步返回前表单已渲染空值，之后 `initial` 变化无法触发 useState 重新初始化。  
Fix：增加 `jobLoading` 状态，等 `getJob` 返回后再渲染 `JDConfirmCard`。同时去掉 `|| jobInfo.title` 条件，始终从 API 刷新数据。

- [ ] **Step 1：在 `ReportPage` 中增加 `jobLoading` 状态**

在 `const [error, setError] = useState('')` 下方添加：

```typescript
const [jobLoading, setJobLoading] = useState(false)
```

- [ ] **Step 2：修改确认步骤 useEffect，去掉 `|| jobInfo.title` 条件，加 loading 控制**

将现有的确认步骤 useEffect（约第 103-116 行）：

```typescript
useEffect(() => {
  if (step !== 'confirm' || jobInfo.title) return
  getJob(reportId)
    .then((job) => {
      setJobInfo({
        title: job.title || '',
        company: job.company || '',
        requirements: job.requirements || [],
        suggested_directions: job.suggested_directions || [],
      })
    })
    .catch(() => {/* jobInfo stays empty, user can still fill in */})
}, [step, reportId])
```

替换为：

```typescript
useEffect(() => {
  if (step !== 'confirm') return
  setJobLoading(true)
  getJob(reportId)
    .then((job) => {
      setJobInfo({
        title: job.title || '',
        company: job.company || '',
        requirements: job.requirements || [],
        suggested_directions: (job as { suggested_directions?: string[] }).suggested_directions || [],
      })
    })
    .catch(() => {/* keep empty, user can fill in manually */})
    .finally(() => setJobLoading(false))
}, [step, reportId])
```

- [ ] **Step 3：在渲染 `JDConfirmCard` 时，加 loading 门控**

找到 JSX 中渲染 `JDConfirmCard` 的部分（约第 204-210 行）：

```tsx
) : step === 'confirm' ? (
  <StageCard state="active" step={2} title="确认职位信息" badge="需要你确认">
    <JDConfirmCard
      initial={jobInfo}
      onConfirm={handleConfirm}
      onCancel={() => {}}
    />
  </StageCard>
```

替换为：

```tsx
) : step === 'confirm' ? (
  <StageCard state="active" step={2} title="确认职位信息" badge="需要你确认">
    {jobLoading ? (
      <div className="py-6 text-center text-sm text-gray-400">正在加载职位信息…</div>
    ) : (
      <JDConfirmCard
        initial={jobInfo}
        onConfirm={handleConfirm}
        onCancel={() => {}}
      />
    )}
  </StageCard>
```

- [ ] **Step 4：TypeScript 编译检查**

```bash
cd frontend && pnpm tsc --noEmit 2>&1 | head -20
```

期望：无错误。

---

## Task 6：前端 — 修复方向数量刷新后显示"全部"（Bug 3）

**Files:**
- Modify: `frontend/src/app/report/[id]/page.tsx`

问题：`selectedDirs` 是内存 state，刷新后为 `[]`，`0 || '全部'` 显示"全部"。  
Fix：进入 `researching` 步骤时从 `getJob` 读取 `selected_directions`。

- [ ] **Step 1：在 `ReportPage` 中增加 researching 步骤的 job 加载 useEffect**

在现有「Load report when done」useEffect（约第 119-129 行）之后添加：

```typescript
// Load selected directions from job API when entering researching step
useEffect(() => {
  if (step !== 'researching' || selectedDirs.length > 0) return
  getJob(reportId)
    .then((job) => {
      const dirs = (job as { selected_directions?: string[] }).selected_directions
      if (dirs && dirs.length > 0) setSelectedDirs(dirs)
    })
    .catch(() => {/* keep empty */})
}, [step, reportId])
```

- [ ] **Step 2：TypeScript 编译检查**

```bash
cd frontend && pnpm tsc --noEmit 2>&1 | head -30
```

期望：无错误（如有 selectedDirs 相关警告，检查 useEffect 依赖）。

---

## Task 7：端到端验证

- [ ] **Step 1：重启后端服务（使代码热重载）**

后端用 uvicorn `--reload` 已自动热重载，无需手动重启。确认日志无报错：

```bash
tail -5 /Users/xuebao/learn/AI项目/job-intel-agent/backend.log
```

- [ ] **Step 2：用 gstack 跑完整流程**

```bash
# 确认前端已编译
curl -s -o /dev/null -w "%{http_code}" http://localhost:3001  # 期望 307

# 确认后端健康
curl -s http://localhost:8001/health  # 期望 {"status":"ok"} 或 200
```

- [ ] **Step 3：验证 interrupt 后 HiTL 面板出现**

重新执行一次完整流程：
1. 上传职位截图
2. 上传简历
3. 点击确认提交 → 确认职位信息（验证：表单有预填数据）
4. 选择调研方向 → 开始调研
5. 等待 AI 调研完成
6. 验证：出现「⏸ AI 需要你确认分析结果」面板（而非永久卡死）
7. 点击「确认，继续生成报告 →」
8. 验证：报告正常生成

- [ ] **Step 4：验证刷新恢复**

在 HiTL 面板出现后刷新页面，验证：刷新后仍能看到 interrupt 面板（Redis Key 回放生效）。

- [ ] **Step 5：验证方向数量显示**

进入 `?step=researching` 后刷新页面，验证：显示「已选择 6 个调研方向」而非「已选择 全部 个调研方向」。

---

## 自审

**Spec 覆盖检查：**
- Bug 1（ResearchingCard 不处理 interrupt）→ Task 4 ✅
- Bug 1b（刷新后 interrupt 丢失）→ Task 1 + Task 2 ✅
- Bug 2（确认表单空）→ Task 5 ✅
- Bug 3（方向数量显示）→ Task 6 ✅
- API 函数缺失（resumeJob）→ Task 3 ✅

**类型一致性：**
- `resumeJob(jobId, action, feedback?)` 在 Task 3 定义，Task 4 中使用 → 一致 ✅
- `InterruptData.data.analysis` 在 Task 4 中使用 → 服务端 interrupt payload 的 `data.analysis` 字段由 `analyze_node` 返回的 `research_analysis` 填充 ✅

**无占位符：** 所有步骤含完整代码 ✅
