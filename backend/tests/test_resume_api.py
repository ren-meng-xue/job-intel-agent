from unittest.mock import MagicMock, patch

# ── 辅助函数 ──────────────────────────────────────────────────────────────


async def _register_and_login(client, email="user@example.com", password="pw123"):
    """注册并登录，返回 Authorization header"""
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": email.split("@")[0], "password": password},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _pdf_upload(filename="resume.pdf"):
    return {"file": (filename, b"%PDF-1.4 fake content", "application/pdf")}


# ── 上传端点 ──────────────────────────────────────────────────────────────


async def test_upload_resume_returns_202(client):
    """正常上传 PDF → 202，status=parsing"""
    headers = await _register_and_login(client)

    with (
        patch("app.api.v1.resume.extract_text", return_value="张三 Python工程师"),
        patch("app.api.v1.resume.task_parse_resume") as mock_task,
    ):
        mock_task.delay = MagicMock()
        resp = await client.post(
            "/api/v1/resume/",
            headers=headers,
            files=_pdf_upload(),
        )

    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "parsing"
    assert data["filename"] == "resume.pdf"
    mock_task.delay.assert_called_once()


async def test_upload_resume_duplicate_returns_409(client):
    """已有简历再次上传 → 409"""
    headers = await _register_and_login(client)

    with (
        patch("app.api.v1.resume.extract_text", return_value="文本"),
        patch("app.api.v1.resume.task_parse_resume") as mock_task,
    ):
        mock_task.delay = MagicMock()
        await client.post("/api/v1/resume/", headers=headers, files=_pdf_upload())
        resp = await client.post("/api/v1/resume/", headers=headers, files=_pdf_upload())

    assert resp.status_code == 409


async def test_upload_resume_invalid_format_returns_400(client):
    """上传 .txt 文件 → 400"""
    headers = await _register_and_login(client)
    resp = await client.post(
        "/api/v1/resume/",
        headers=headers,
        files={"file": ("resume.txt", b"some text", "text/plain")},
    )
    assert resp.status_code == 400


async def test_upload_resume_unauthenticated_returns_401(client):
    """未登录上传 → 401"""
    resp = await client.post("/api/v1/resume/", files=_pdf_upload())
    assert resp.status_code == 401


# ── 获取端点 ──────────────────────────────────────────────────────────────


async def test_get_resume_returns_detail(client):
    """上传后 GET /resume/ → 返回简历详情"""
    headers = await _register_and_login(client)

    with (
        patch("app.api.v1.resume.extract_text", return_value="文本"),
        patch("app.api.v1.resume.task_parse_resume") as mock_task,
    ):
        mock_task.delay = MagicMock()
        await client.post("/api/v1/resume/", headers=headers, files=_pdf_upload())

    resp = await client.get("/api/v1/resume/", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["filename"] == "resume.pdf"


async def test_get_resume_no_resume_returns_404(client):
    """未上传简历时 GET /resume/ → 404"""
    headers = await _register_and_login(client)
    resp = await client.get("/api/v1/resume/", headers=headers)
    assert resp.status_code == 404


async def test_get_resume_unauthenticated_returns_401(client):
    """未登录 → 401"""
    resp = await client.get("/api/v1/resume/")
    assert resp.status_code == 401


# ── 删除端点 ──────────────────────────────────────────────────────────────


async def test_delete_resume_returns_204(client):
    """删除自己的简历 → 204"""
    headers = await _register_and_login(client)

    with (
        patch("app.api.v1.resume.extract_text", return_value="文本"),
        patch("app.api.v1.resume.task_parse_resume") as mock_task,
    ):
        mock_task.delay = MagicMock()
        upload_resp = await client.post("/api/v1/resume/", headers=headers, files=_pdf_upload())

    resume_id = upload_resp.json()["id"]
    resp = await client.delete(f"/api/v1/resume/{resume_id}", headers=headers)
    assert resp.status_code == 204

    # 删除后 GET → 404
    get_resp = await client.get("/api/v1/resume/", headers=headers)
    assert get_resp.status_code == 404


async def test_delete_resume_other_user_returns_403(client):
    """删除他人简历 → 403"""
    headers_a = await _register_and_login(client, "a@example.com")
    headers_b = await _register_and_login(client, "b@example.com")

    with (
        patch("app.api.v1.resume.extract_text", return_value="文本"),
        patch("app.api.v1.resume.task_parse_resume") as mock_task,
    ):
        mock_task.delay = MagicMock()
        upload_resp = await client.post("/api/v1/resume/", headers=headers_a, files=_pdf_upload())

    resume_id = upload_resp.json()["id"]
    resp = await client.delete(f"/api/v1/resume/{resume_id}", headers=headers_b)
    assert resp.status_code == 403


async def test_delete_resume_not_found_returns_404(client):
    """删除不存在的简历 → 404"""
    headers = await _register_and_login(client)
    resp = await client.delete("/api/v1/resume/nonexistent-id", headers=headers)
    assert resp.status_code == 404
