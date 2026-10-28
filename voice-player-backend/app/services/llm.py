"""OpenAI 兼容的大模型调用：身份推断 / 场景分析 / 翻译。未配置时调用方走降级。"""
import json
import logging
import re

import httpx

from ..config import Settings

log = logging.getLogger("voice_player")

ANALYZE_SYSTEM = """你是通话/对话内容分析助手。根据转写文本推断说话人和场景，只输出一个 JSON 对象，不要任何解释。
每行格式为 [轨道 mm:ss] 内容，轨道 A、B 各代表一位说话人。

规则：
- identity：根据对话内容推测该说话人的身份，用简短中文自由描述，可包含公司/职务，如“某公司老板”“某运营商客服人员”“客户”。
  只能依据文本中的线索推断，不得编造具体姓名或公司名；线索不足时填 "unknown"，confidence 取低值。
- role：agent（坐席/客服/服务方）、customer（客户/咨询方）或 unknown。
- confidence、complaintScore：0~1 的小数；sentimentScore：-1~1；emotionDistribution 各项为占比，合计约 1。
- dominantIntent：如 complaint、inquiry、consultation、troubleshooting 等英文小写标签。

输出结构：
{"speakers":[{"trackId":"A","identity":"","confidence":0,"role":"","emotionDistribution":{"neutral":1},"sentimentScore":0,"dominantIntent":""}],
 "scenes":[{"type":"","subType":"","confidence":0,"description":"","keywords":[]}],
 "callType":"inbound|outbound|unknown","callPurpose":"","callResolution":"resolved|unresolved|unknown",
 "analysis":{"hasComplaint":false,"complaintScore":0,"hasPraise":false,"isEscalated":false}}
scenes 按置信度从高到低，type 示例 call_center。"""

TRANSLATE_SYSTEM = """你是专业翻译。把输入 JSON 数组中每条 text 翻译成目标语言，保持含义与语气，不增删信息。
只输出 JSON：{"items":[{"id":"原样返回","text":"译文"}]}，条目数量和 id 必须与输入一致。"""


class LlmError(Exception):
    pass


def _clamp(v, lo, hi, default=None):
    try:
        return max(lo, min(hi, float(v)))
    except (TypeError, ValueError):
        return default


def _extract_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise LlmError("模型返回的内容不是 JSON")
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError as e:
            raise LlmError(f"模型返回的 JSON 无法解析：{e}")


class LlmClient:
    def __init__(self, settings: Settings, client: httpx.Client | None = None):
        self.s = settings
        self._client = client or httpx.Client(timeout=settings.llm_timeout)

    def _chat_json(self, system: str, user: str) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.s.llm_api_key:
            headers["Authorization"] = f"Bearer {self.s.llm_api_key}"
        body = {
            "model": self.s.llm_model,
            "temperature": 0.2,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        try:
            r = self._client.post(f"{self.s.llm_base_url.rstrip('/')}/chat/completions", json=body, headers=headers)
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
            raise LlmError(f"调用大模型失败：{e}")
        return _extract_json(content)

    # ── 身份 / 场景 ───────────────────────────────────────────────────────
    def analyze(self, dialogue: str, track_ids: list[str]) -> dict:
        raw = self._chat_json(ANALYZE_SYSTEM, dialogue[: self.s.llm_max_chars])
        return normalize_analysis(raw, track_ids)

    # ── 翻译 ──────────────────────────────────────────────────────────────
    def translate(self, items: list[dict], language: str, batch: int = 40) -> dict[str, str]:
        """items: [{id, text}] → {id: 译文}；缺失的 id 不出现在结果中。"""
        out: dict[str, str] = {}
        for i in range(0, len(items), batch):
            chunk = items[i:i + batch]
            user = f"目标语言：{language}\n{json.dumps(chunk, ensure_ascii=False)}"
            raw = self._chat_json(TRANSLATE_SYSTEM, user)
            for it in raw.get("items", []):
                if isinstance(it, dict) and it.get("id") and isinstance(it.get("text"), str) and it["text"].strip():
                    out[str(it["id"])] = it["text"].strip()
        return out


def unknown_speakers(track_ids: list[str]) -> list[dict]:
    return [{
        "trackId": t, "identity": "unknown", "confidence": 0.0,
        "role": "agent" if t == "A" else "customer",
        "emotionDistribution": {}, "sentimentScore": 0.0, "dominantIntent": "",
    } for t in track_ids]


def default_scenes() -> dict:
    return {"scenes": [], "callType": "unknown", "callPurpose": "", "callResolution": "unknown", "analysis": None}


def normalize_analysis(raw: dict, track_ids: list[str]) -> dict:
    """把模型输出收敛为接口约定的结构：缺失/越界字段用安全默认值。"""
    by_track = {str(s.get("trackId")): s for s in raw.get("speakers", []) if isinstance(s, dict)}
    speakers = []
    for base in unknown_speakers(track_ids):
        s = by_track.get(base["trackId"], {})
        identity = str(s.get("identity") or "").strip() or "unknown"
        role = s.get("role") if s.get("role") in ("agent", "customer") else base["role"]
        emo = s.get("emotionDistribution")
        emo = {str(k): _clamp(v, 0, 1, 0.0) for k, v in emo.items()} if isinstance(emo, dict) else {}
        speakers.append({
            "trackId": base["trackId"], "identity": identity,
            "confidence": _clamp(s.get("confidence"), 0, 1, 0.0) if identity != "unknown" else 0.0,
            "role": role, "emotionDistribution": emo,
            "sentimentScore": _clamp(s.get("sentimentScore"), -1, 1, 0.0),
            "dominantIntent": str(s.get("dominantIntent") or ""),
        })

    scenes = []
    for sc in raw.get("scenes", []):
        if not isinstance(sc, dict):
            continue
        kw = sc.get("keywords")
        scenes.append({
            "type": str(sc.get("type") or ""), "subType": str(sc.get("subType") or ""),
            "confidence": _clamp(sc.get("confidence"), 0, 1, 0.0),
            "description": str(sc.get("description") or ""),
            "keywords": [str(k) for k in kw] if isinstance(kw, list) else [],
        })
    scenes.sort(key=lambda x: -x["confidence"])

    an = raw.get("analysis")
    analysis = None
    if isinstance(an, dict):
        analysis = {
            "hasComplaint": bool(an.get("hasComplaint")),
            "complaintScore": _clamp(an.get("complaintScore"), 0, 1, 0.0),
            "hasPraise": bool(an.get("hasPraise")),
            "isEscalated": bool(an.get("isEscalated")),
        }
    call_type = raw.get("callType") if raw.get("callType") in ("inbound", "outbound") else "unknown"
    resolution = raw.get("callResolution") if raw.get("callResolution") in ("resolved", "unresolved") else "unknown"
    return {
        "speakers": speakers,
        "scenes": {"scenes": scenes, "callType": call_type, "callPurpose": str(raw.get("callPurpose") or ""),
                   "callResolution": resolution, "analysis": analysis},
    }
