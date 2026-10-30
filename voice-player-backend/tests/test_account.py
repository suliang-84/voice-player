import time

import jwt

from conftest import upload

API = "/api/v1"
SECRET = "test-secret"


def test_settings_defaults_and_merge(client):
    d = client.get(f"{API}/users/settings").json()["data"]
    assert d == {"playback": {"defaultSpeed": 1.0, "seekStep": 5, "playMode": "single", "skipSilence": False, "stereo": False},
                 "ui": {"theme": "light", "chatPanelVisible": False}}
    r = client.put(f"{API}/users/settings", json={"playback": {"seekStep": 10}, "ui": {"theme": "dark"}}).json()
    assert r["message"] == "设置更新成功" and r["data"]["updatedAt"].endswith("Z")
    assert r["data"]["playback"] == {"defaultSpeed": 1.0, "seekStep": 10, "playMode": "single", "skipSilence": False, "stereo": False}
    # 部分更新：未传字段保持，且已持久化
    client.put(f"{API}/users/settings", json={"playback": {"skipSilence": True}})
    d = client.get(f"{API}/users/settings").json()["data"]
    assert d["playback"]["seekStep"] == 10 and d["playback"]["skipSilence"] is True and d["ui"]["theme"] == "dark"


def test_settings_validation(client):
    for body in ({"playback": {"defaultSpeed": 9}}, {"playback": {"seekStep": 0}},
                 {"playback": {"playMode": "loop"}}, {"ui": {"theme": "blue"}},
                 {"playback": {"skipSilence": "maybe"}}):
        r = client.put(f"{API}/users/settings", json=body)
        assert r.status_code == 400 and r.json()["code"] == 400, body


def test_unknown_route_and_health(client):
    r = client.get("/api/v1/nothing")
    assert r.status_code == 404 and r.json()["code"] == 404 and r.json()["data"] is None
    h = client.get("/health").json()["data"]
    assert h["status"] == "ok" and h["asr"] is True and h["llm"] is False


def _token(sub="u1", typ="access", ttl=3600, secret=SECRET):
    now = int(time.time())
    return jwt.encode({"sub": sub, "typ": typ, "iat": now, "exp": now + ttl}, secret, algorithm="HS256")


def test_auth_required_when_enabled(make_client, tmp_path):
    c = make_client(auth_enabled=True, jwt_secret=SECRET)
    for path in ("/users/settings", "/audios/a1/peaks"):
        r = c.get(API + path)
        assert r.status_code == 401 and r.json()["code"] == 401
    assert c.get(f"{API}/users/settings", headers={"Authorization": "Bearer junk"}).status_code == 401
    assert c.get(f"{API}/users/settings", headers={"Authorization": f"Bearer {_token(secret='other')}"}).status_code == 401
    assert c.get(f"{API}/users/settings", headers={"Authorization": f"Bearer {_token(typ='refresh')}"}).status_code == 401
    assert c.get(f"{API}/users/settings", headers={"Authorization": f"Bearer {_token(ttl=-10)}"}).status_code == 401
    assert c.get(f"{API}/users/settings", headers={"Authorization": f"Bearer {_token()}"}).status_code == 200


def test_settings_are_per_user(make_client):
    c = make_client(auth_enabled=True, jwt_secret=SECRET)
    h1, h2 = ({"Authorization": f"Bearer {_token(u)}"} for u in ("u1", "u2"))
    c.put(f"{API}/users/settings", json={"ui": {"theme": "dark"}}, headers=h1)
    assert c.get(f"{API}/users/settings", headers=h1).json()["data"]["ui"]["theme"] == "dark"
    assert c.get(f"{API}/users/settings", headers=h2).json()["data"]["ui"]["theme"] == "light"


def test_stream_accepts_query_token(make_client, tmp_path):
    c = make_client(auth_enabled=True, jwt_secret=SECRET)
    h = {"Authorization": f"Bearer {_token()}"}
    p = tmp_path / "a.wav"
    from conftest import make_stereo
    make_stereo(p, seconds=1)
    with p.open("rb") as f:
        assert c.post(f"{API}/audios", files={"file": ("a.wav", f)}, data={"audioId": "a1"}, headers=h).json()["code"] == 0
    assert c.get(f"{API}/audios/a1/stream").status_code == 401
    assert c.get(f"{API}/audios/a1/stream", params={"token": _token()}).status_code == 200


def test_refresh_flows(make_client):
    c = make_client(auth_enabled=True, jwt_secret=SECRET)
    # 1) 前端默认方式：用（已过期的）访问令牌换新令牌
    r = c.post(f"{API}/auth/refresh", headers={"Authorization": f"Bearer {_token(ttl=-100)}"})
    d = r.json()["data"]
    assert r.status_code == 200 and d["expiresIn"] == 3600 and d["token"] and d["refreshToken"]
    assert c.get(f"{API}/users/settings", headers={"Authorization": f"Bearer {d['token']}"}).status_code == 200
    # 2) 用 refreshToken
    r2 = c.post(f"{API}/auth/refresh", json={"refreshToken": d["refreshToken"]})
    assert r2.status_code == 200 and r2.json()["data"]["token"]
    # 3) 访问令牌不能当 refreshToken；缺失/伪造/超期都是 401
    assert c.post(f"{API}/auth/refresh", json={"refreshToken": d["token"]}).status_code == 401
    assert c.post(f"{API}/auth/refresh").status_code == 401
    assert c.post(f"{API}/auth/refresh", headers={"Authorization": "Bearer junk"}).status_code == 401
    too_old = _token(ttl=-(7 * 24 * 3600 + 100))
    assert c.post(f"{API}/auth/refresh", headers={"Authorization": f"Bearer {too_old}"}).status_code == 401
    assert c.post(f"{API}/auth/refresh", headers={"Authorization": f"Bearer {_token(typ='refresh')}"}).status_code == 401


def test_websocket_requires_token(make_client):
    import pytest
    from starlette.websockets import WebSocketDisconnect
    c = make_client(auth_enabled=True, jwt_secret=SECRET)
    with pytest.raises(WebSocketDisconnect):
        with c.websocket_connect("/ws"):
            pass
    with c.websocket_connect(f"/ws?token={_token()}"):
        pass
