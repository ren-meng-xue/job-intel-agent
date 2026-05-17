async def test_register_returns_201(client):
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "newuser@example.com",
            "username": "newuser",
            "password": "password123",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "newuser@example.com"
    assert "id" in data


async def test_register_duplicate_email_returns_409(client):
    payload = {"email": "dup@example.com", "username": "dup1", "password": "pw"}
    await client.post("/api/v1/auth/register", json=payload)
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "dup@example.com", "username": "dup2", "password": "pw"},
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "ALREADY_EXISTS"


async def test_login_returns_access_token_and_cookie(client):
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "loginuser@example.com",
            "username": "loginuser",
            "password": "password",
        },
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "loginuser@example.com", "password": "password"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in resp.cookies


async def test_me_with_valid_token(client):
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "meuser@example.com",
            "username": "meuser",
            "password": "pw123",
        },
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "meuser@example.com", "password": "pw123"},
    )
    token = login_resp.json()["access_token"]

    resp = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["email"] == "meuser@example.com"


async def test_me_without_token_returns_401(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_logout_clears_cookie(client):
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "logout@example.com",
            "username": "logoutuser",
            "password": "pw",
        },
    )
    await client.post(
        "/api/v1/auth/login",
        json={"email": "logout@example.com", "password": "pw"},
    )
    resp = await client.post("/api/v1/auth/logout")
    assert resp.status_code == 200
    # cookie 被清除（httpx 响应中已无此 cookie）
    assert "refresh_token" not in resp.cookies or resp.cookies.get("refresh_token") == ""
