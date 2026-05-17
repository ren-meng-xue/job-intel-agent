"""
端到端 API 全流程测试
注册 → 登录 → 上传简历 → 创建 Job → JD 解析 → 确认 → 调研方向 → 启动调研
"""
import json
import sys
import time
import uuid
import httpx

BASE = "http://localhost:8001"
RESUME_PATH = "/Users/xuebao/learn/面试/任孟雪WEB前端工程师.pdf"
MOCK_JD_URL = "https://www.zhipin.com/job_detail/mock_test_123.html"

# 随机账号，避免重复注册冲突
SUFFIX = str(uuid.uuid4())[:8]
EMAIL = f"test_{SUFFIX}@example.com"
USERNAME = f"tester_{SUFFIX}"
PASSWORD = "Test@123456"


def ok(msg):
    print(f"\033[32m✅  {msg}\033[0m")

def fail(msg):
    print(f"\033[31m❌  {msg}\033[0m")
    sys.exit(1)

def info(msg):
    print(f"\033[34m→   {msg}\033[0m")

def section(msg):
    print(f"\n\033[1m{'='*60}\033[0m")
    print(f"\033[1m  {msg}\033[0m")
    print(f"\033[1m{'='*60}\033[0m")


def sse_read(client: httpx.Client, url: str, token: str, timeout: int = 60) -> list[dict]:
    """读取 SSE 流，直到收到终态事件（parsed/error/completed）"""
    events = []
    headers = {"Authorization": f"Bearer {token}"}
    deadline = time.time() + timeout
    with client.stream("GET", url, headers=headers, timeout=timeout) as resp:
        if resp.status_code != 200:
            body = resp.read()
            fail(f"SSE 连接失败 {resp.status_code}: {body.decode()[:200]}")
        for line in resp.iter_lines():
            if time.time() > deadline:
                fail(f"SSE 超时 ({timeout}s)，最后收到: {events[-3:] if events else []}")
            if not line or line.startswith(":"):
                continue
            if line.startswith("data:"):
                raw = line[5:].strip()
                try:
                    ev = json.loads(raw)
                    events.append(ev)
                    ev_type = ev.get("type", "")
                    info(f"  SSE [{ev_type}] {ev.get('message', ev.get('step', ''))}")
                    if ev_type in ("parsed", "error", "completed"):
                        break
                except json.JSONDecodeError:
                    pass
    return events


def main():
    client = httpx.Client(base_url=BASE, timeout=30)

    # ── 1. 注册 ────────────────────────────────────────────────────────────
    section("Step 1: 注册")
    info(f"注册账号: {EMAIL}")
    r = client.post("/api/v1/auth/register", json={
        "email": EMAIL,
        "username": USERNAME,
        "password": PASSWORD,
    })
    if r.status_code != 201:
        fail(f"注册失败 {r.status_code}: {r.text[:300]}")
    user = r.json()
    ok(f"注册成功 — user_id={user['id']} email={user['email']}")

    # ── 2. 登录 ────────────────────────────────────────────────────────────
    section("Step 2: 登录")
    r = client.post("/api/v1/auth/login", json={
        "email": EMAIL,
        "password": PASSWORD,
    })
    if r.status_code != 200:
        fail(f"登录失败 {r.status_code}: {r.text[:300]}")
    login_data = r.json()
    token = login_data.get("access_token")
    if not token:
        fail(f"登录响应中无 access_token: {login_data}")
    ok(f"登录成功 — token 前缀: {token[:20]}...")
    auth_headers = {"Authorization": f"Bearer {token}"}

    # ── 3. 验证 /me ────────────────────────────────────────────────────────
    section("Step 3: /me 验证")
    r = client.get("/api/v1/auth/me", headers=auth_headers)
    if r.status_code != 200:
        fail(f"/me 失败 {r.status_code}: {r.text[:300]}")
    ok(f"/me 成功 — {r.json()}")

    # ── 4. 上传简历 ────────────────────────────────────────────────────────
    section("Step 4: 上传简历 PDF")
    with open(RESUME_PATH, "rb") as f:
        resume_bytes = f.read()
    info(f"文件: {RESUME_PATH} ({len(resume_bytes)//1024} KB)")
    r = client.post(
        "/api/v1/resume/",
        files={"file": ("resume.pdf", resume_bytes, "application/pdf")},
        headers=auth_headers,
        timeout=60,
    )
    if r.status_code != 202:
        fail(f"上传简历失败 {r.status_code}: {r.text[:300]}")
    resume = r.json()
    resume_id = resume["id"]
    ok(f"简历已接受 — resume_id={resume_id} status={resume['status']}")

    # ── 5. 等待简历解析（SSE） ─────────────────────────────────────────────
    section("Step 5: 等待简历解析（SSE）")
    info(f"订阅: GET /api/v1/resume/{resume_id}/stream")
    events = sse_read(client, f"/api/v1/resume/{resume_id}/stream", token, timeout=90)
    last = events[-1] if events else {}
    if last.get("type") == "error":
        fail(f"简历解析失败: {last}")
    elif last.get("type") == "parsed":
        ok(f"简历解析完成 — skills: {last.get('skills', [])[:3]}")
    else:
        fail(f"未收到 parsed 终态，最后事件: {last}")

    # ── 6. 创建 Job ────────────────────────────────────────────────────────
    section("Step 6: 创建 Job (mock JD URL)")
    info(f"JD URL: {MOCK_JD_URL}")
    r = client.post("/api/v1/jobs/", json={
        "url": MOCK_JD_URL,
        "resume_id": resume_id,
    }, headers=auth_headers)
    if r.status_code != 201:
        fail(f"创建 Job 失败 {r.status_code}: {r.text[:300]}")
    job = r.json()
    job_id = job["id"]
    ok(f"Job 已创建 — job_id={job_id} status={job['status']}")

    # ── 7. 等待 JD 解析（SSE） ─────────────────────────────────────────────
    section("Step 7: 等待 JD 解析（SSE）")
    info(f"订阅: GET /api/v1/reports/{job_id}/stream")
    events = sse_read(client, f"/api/v1/reports/{job_id}/stream", token, timeout=60)
    last = events[-1] if events else {}
    if last.get("type") == "error":
        fail(f"JD 解析失败: {last}")
    elif last.get("type") == "parsed":
        ok(f"JD 解析完成 — title={last.get('title')} company={last.get('company')}")
    else:
        fail(f"未收到 parsed 终态，最后事件: {last}")

    # ── 8. 确认 Job 信息 ───────────────────────────────────────────────────
    section("Step 8: 确认 Job 信息 (confirm)")
    r = client.post(f"/api/v1/jobs/{job_id}/confirm",
                    json={},  # 不修改，直接接受 LLM 结果
                    headers=auth_headers, timeout=30)
    if r.status_code != 200:
        fail(f"confirm 失败 {r.status_code}: {r.text[:300]}")
    confirmed = r.json()
    suggestions = confirmed.get("suggested_directions", [])
    ok(f"确认成功 — status={confirmed['status']} 方向建议数={len(suggestions)}")
    for i, s in enumerate(suggestions[:4], 1):
        info(f"  [{i}] {s}")

    # ── 9. 启动调研 ────────────────────────────────────────────────────────
    section("Step 9: 启动调研 (start research)")
    selected = suggestions[:2] if suggestions else ["公司背景与业务", "技术栈深度研究"]
    info(f"选择方向: {selected}")
    r = client.post(f"/api/v1/jobs/{job_id}/start",
                    json={"selected_directions": selected},
                    headers=auth_headers)
    if r.status_code != 200:
        fail(f"start 失败 {r.status_code}: {r.text[:300]}")
    started = r.json()
    ok(f"调研已启动 — status={started['status']}")

    # ── 10. 监听调研进度（等待第一个 interrupt 或 completed） ──────────────
    section("Step 10: 监听调研进度（等 HiTL interrupt）")
    info("订阅 SSE，等待 review_results 节点中断或 completed 事件（最多等 120s）...")
    events = sse_read(client, f"/api/v1/reports/{job_id}/stream", token, timeout=120)
    last = events[-1] if events else {}
    ev_type = last.get("type", "")
    if ev_type == "completed":
        ok(f"调研直接完成（无 HiTL），type=completed")
    elif ev_type in ("review_results", "review_draft"):
        ok(f"收到 HiTL 中断 — type={ev_type}")
        # 用 approve 继续
        section("Step 10b: HiTL approve → 继续调研")
        r = client.post(f"/api/v1/jobs/{job_id}/resume",
                        json={"action": "approve"},
                        headers=auth_headers)
        if r.status_code != 200:
            fail(f"resume approve 失败 {r.status_code}: {r.text[:300]}")
        ok("approve 成功，等待调研继续完成（最多 120s）...")
        events2 = sse_read(client, f"/api/v1/reports/{job_id}/stream", token, timeout=120)
        last2 = events2[-1] if events2 else {}
        if last2.get("type") == "completed":
            ok("调研已完成！type=completed")
        else:
            info(f"  最后事件: {last2}（可能还有更多 HiTL 轮次）")
    elif ev_type == "error":
        fail(f"调研出错: {last}")
    else:
        info(f"  最后事件: {last}（可能还需更多 HiTL 轮次，手动继续）")

    print(f"\n\033[1;32m{'='*60}\033[0m")
    print(f"\033[1;32m  全流程测试完成！job_id={job_id}\033[0m")
    print(f"\033[1;32m{'='*60}\033[0m\n")


if __name__ == "__main__":
    main()
