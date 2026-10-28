import json

import httpx
import pytest

from app.config import Settings
from app.services.llm import LlmClient, LlmError, normalize_analysis


def client_with(handler, **kw) -> LlmClient:
    s = Settings(llm_base_url="http://llm.test/v1/", llm_model="m1", llm_api_key="k", **kw)
    return LlmClient(s, httpx.Client(transport=httpx.MockTransport(handler)))


def reply(content: str):
    def handler(request: httpx.Request):
        handler.requests.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})
    handler.requests = []
    return handler


def test_analyze_request_and_free_form_identity():
    h = reply('```json\n{"speakers":[{"trackId":"A","identity":"某公司老板","confidence":0.7,"role":"customer"},'
              '{"trackId":"B","identity":"某客服人员","confidence":0.9,"role":"agent"}],'
              '"scenes":[{"type":"sales","confidence":0.6},{"type":"call_center","confidence":0.9,"keywords":["网络"]}]}\n```')
    r = client_with(h).analyze("[A 00:01] 我是老板\n[B 00:03] 您好", ["A", "B"])
    req = h.requests[0]
    assert str(req.url) == "http://llm.test/v1/chat/completions" and req.headers["authorization"] == "Bearer k"
    body = json.loads(req.content)
    assert body["model"] == "m1" and "[A 00:01] 我是老板" in body["messages"][1]["content"]
    assert [s["identity"] for s in r["speakers"]] == ["某公司老板", "某客服人员"]  # 自由描述原样保留
    assert [s["type"] for s in r["scenes"]["scenes"]] == ["call_center", "sales"]  # 按置信度降序
    assert r["scenes"]["analysis"] is None and r["scenes"]["callType"] == "unknown"


def test_normalize_clamps_and_defaults():
    r = normalize_analysis({
        "speakers": [{"trackId": "A", "identity": "  ", "confidence": 5, "role": "boss", "sentimentScore": -9,
                      "emotionDistribution": {"angry": 3}}],
        "analysis": {"hasComplaint": 1, "complaintScore": "x"}, "callType": "weird",
    }, ["A", "B"])
    a, b = r["speakers"]
    assert a["identity"] == "unknown" and a["confidence"] == 0.0  # 无身份 → 置信度归零
    assert a["role"] == "agent" and a["sentimentScore"] == -1.0 and a["emotionDistribution"] == {"angry": 1.0}
    assert b["identity"] == "unknown" and b["role"] == "customer"  # 模型漏掉的轨道补默认
    assert r["scenes"]["analysis"]["hasComplaint"] is True and r["scenes"]["analysis"]["complaintScore"] == 0.0
    assert r["scenes"]["callType"] == "unknown"


def test_translate_batches_and_ignores_bad_items():
    def handler(request):
        items = json.loads(json.loads(request.content)["messages"][1]["content"].split("\n", 1)[1])
        out = [{"id": i["id"], "text": f"T-{i['text']}"} for i in items if i["id"] != "skip"]
        out.append({"id": "ghost", "text": ""})
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({"items": out})}}]})

    items = [{"id": f"i{n}", "text": f"t{n}"} for n in range(5)] + [{"id": "skip", "text": "x"}]
    r = client_with(handler).translate(items, "en", batch=2)
    assert r == {f"i{n}": f"T-t{n}" for n in range(5)}


@pytest.mark.parametrize("response", [
    lambda req: httpx.Response(500, text="boom"),
    lambda req: httpx.Response(200, json={"unexpected": 1}),
    lambda req: httpx.Response(200, json={"choices": [{"message": {"content": "not json at all"}}]}),
])
def test_failures_raise_llm_error(response):
    with pytest.raises(LlmError):
        client_with(response).analyze("[A 00:01] hi", ["A"])
