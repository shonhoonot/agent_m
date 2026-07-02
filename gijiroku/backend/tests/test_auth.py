"""JWT 認証のテスト。"""


async def test_login_success(client, test_user):
    resp = await client.post(
        "/api/auth/login",
        json={"email": "tanaka@example.com", "password": "secret-password"},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    # 取得したトークンで保護エンドポイントにアクセスできる
    resp = await client.get("/api/meetings", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


async def test_login_wrong_password(client, test_user):
    resp = await client.post(
        "/api/auth/login",
        json={"email": "tanaka@example.com", "password": "wrong"},
    )
    assert resp.status_code == 401


async def test_protected_endpoint_requires_token(client):
    resp = await client.get("/api/meetings")
    assert resp.status_code == 401
