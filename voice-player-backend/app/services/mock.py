"""演示用的假转写引擎与假大模型（ASR_PROVIDER=mock、LLM_PROVIDER=mock）。

不加载任何模型，用来在没有真实模型时跑通「转写 → 说话人 → 场景 → 翻译」整条流程并返回给前端：
· 转写：按音频里真实的说话时段切句，播放时高亮的句子与波形对得上；句子文字是编的，
  内容为「遥控器设计启动会议」，A 路是项目经理，B 路是工业设计师。
· 大模型：说话人身份、场景、翻译都是固定的演示数据。
"""
import random
import time
from collections import deque
from pathlib import Path
from typing import Callable

import numpy as np

from ..config import Settings
from . import audio
from .asr import Segment
from .llm import normalize_analysis

# (英文原文, 中文译文)。A 路：项目经理（主持、协调）
LINES_A = [
    ("Okay, shall we get started?", "好的，我们开始吧？"),
    ("Welcome everyone, thanks for coming to the kickoff meeting.", "欢迎大家，感谢参加启动会议。"),
    ("Today we are going to talk about the design of our new remote control.", "今天我们要讨论新款遥控器的设计。"),
    ("The project has three phases: functional design, conceptual design and detailed design.",
     "项目分为三个阶段：功能设计、概念设计和详细设计。"),
    ("Let's start with a quick round of introductions.", "我们先简单做个自我介绍。"),
    ("I'll be the project manager, so I'll keep track of time and the budget.", "我是项目经理，负责把控时间和预算。"),
    ("Does anyone have questions before we move on?", "继续之前，大家有什么问题吗？"),
    ("Our target is to produce a remote control that is original, trendy and user friendly.",
     "我们的目标是做出一款新颖、时尚且易用的遥控器。"),
    ("The selling price should be around twenty five euros.", "售价应该在二十五欧元左右。"),
    ("We are aiming at a profit of about fifty million euros.", "我们的目标是约五千万欧元的利润。"),
    ("Could you say a bit more about that?", "你能再多说一点吗？"),
    ("That's a good point.", "这个想法不错。"),
    ("Right.", "好的。"),
    ("Mm-hmm.", "嗯。"),
    ("I think we should keep the number of buttons small.", "我觉得我们应该减少按键数量。"),
    ("Let's make a note of that on the whiteboard.", "我们把这个记在白板上。"),
    ("We have about ten minutes left, so let's summarise.", "我们还剩大约十分钟，来总结一下吧。"),
    ("Before the next meeting, please send me your ideas by email.", "下次会议之前，请把你们的想法用邮件发给我。"),
    ("Marketing will look into what users actually want from a remote.", "市场部会调查用户对遥控器的真实需求。"),
    ("And the designers will work on the working principle and the look and feel.",
     "设计师会研究工作原理和外观手感。"),
    ("So what do you think about using a different material for the case?", "那你觉得外壳换一种材料怎么样？"),
    ("We need to be careful about the cost, though.", "不过我们得注意成本。"),
    ("Can everyone see the slide on the screen?", "大家能看到屏幕上的幻灯片吗？"),
    ("Let me just check the time, we are a little behind.", "我看一下时间，我们稍微有点落后了。"),
    ("Great, so that's settled then.", "太好了，那就这么定了。"),
    ("Is there anything else we should cover today?", "今天还有什么需要讨论的吗？"),
    ("I'm not sure we have enough information to decide that right now.", "我不确定我们现在有足够的信息来做这个决定。"),
    ("Okay, thank you very much, see you in half an hour.", "好的，非常感谢，半小时后见。"),
]

# B 路：工业设计师（提方案、回应）
LINES_B = [
    ("Yeah, sure.", "好的，没问题。"),
    ("I'm the industrial designer, so I'll be working on how the remote actually works.",
     "我是工业设计师，负责遥控器的实际工作原理。"),
    ("I was thinking we could use a curved case so that it fits comfortably in the hand.",
     "我在想可以用弧形外壳，这样握起来更舒服。"),
    ("Maybe we could add a speech recognition feature, so you can find it when it's lost.",
     "也许可以加一个语音识别功能，这样遗失时能找到它。"),
    ("The problem is that most remote controls end up lost behind the sofa.", "问题是大多数遥控器最后都丢在沙发后面。"),
    ("It depends on the battery, because a smaller battery means a smaller case.",
     "这取决于电池，因为电池越小外壳就越小。"),
    ("I think the colour should be bright, something young and fashionable.", "我觉得颜色应该鲜艳一点，年轻又时尚。"),
    ("Well, I'm not sure that will fit within the budget.", "嗯，我不确定这在预算之内是否可行。"),
    ("We could use rubber for the buttons, it feels nicer and it's cheap.", "按键可以用橡胶，手感更好而且便宜。"),
    ("Okay.", "好。"),
    ("Uh-huh.", "嗯哼。"),
    ("Right, I'll look into that and get back to you.", "好的，我去研究一下再回复你。"),
    ("Do we want it to work with other devices as well, like the DVD player?",
     "我们要不要让它也能控制其他设备，比如 DVD 播放机？"),
    ("Most people only use a few buttons, like volume and channel.", "大多数人只用几个按键，比如音量和频道。"),
    ("So the interface should be as simple as possible.", "所以界面应该尽可能简单。"),
    ("Yeah, I agree.", "是的，我同意。"),
    ("An LCD screen would make it more expensive, though.", "不过液晶屏会让成本更高。"),
    ("We could put the teletext button on the side so it doesn't get in the way.",
     "可以把图文电视按键放在侧面，这样不碍事。"),
    ("I'll prepare a first sketch for the next meeting.", "我会为下次会议准备一份初步草图。"),
    ("Sorry, could you repeat that? I missed the last part.", "抱歉，能再说一遍吗？最后一部分我没听清。"),
    ("I think kids and older people have very different needs.", "我觉得孩子和老年人的需求很不一样。"),
    ("It should be easy to hold with one hand and easy to press without looking.",
     "它应该能单手握持，并且不用看就能按。"),
    ("Titanium is too expensive, plastic is probably the way to go.", "钛太贵了，塑料可能是更合适的选择。"),
    ("That sounds good to me.", "我觉得不错。"),
    ("Can I draw something on the whiteboard to show what I mean?", "我可以在白板上画一下来说明我的意思吗？"),
    ("Fine, thanks.", "好的，谢谢。"),
]

WORDS_PER_SECOND = 2.7  # 按语速估算一句话该有多少词
RECENT = 8  # 最近用过的句子不重复使用，避免相邻几句一模一样


def speech_spans(path: Path, *, merge_gap=0.5, min_len=0.6, max_len=9.0, chunk=6.0) -> list[tuple[float, float]]:
    """按音频能量找出说话时段：自适应阈值 → 合并近距离的段 → 丢掉太短的 → 把过长的段切开。"""
    rms, frame_sec, duration = audio.frame_rms(path, 10)
    if not rms.size or not rms.shape[1]:
        return []
    x = audio.smooth_rms(rms[0], max(1, round(0.15 / frame_sec)))
    active = x >= audio.adaptive_threshold(x, 12.0, -65.0, -35.0, 10.0, 20.0)
    edges = np.diff(np.concatenate(([0], active.astype(np.int8), [0])))
    spans: list[list[float]] = []
    for s, e in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)):
        start, end = s * frame_sec, min(e * frame_sec, duration)
        if spans and start - spans[-1][1] < merge_gap:
            spans[-1][1] = end
        else:
            spans.append([start, end])
    out: list[tuple[float, float]] = []
    for start, end in spans:
        if end - start < min_len:
            continue
        parts = max(1, round((end - start) / chunk)) if end - start > max_len else 1
        step = (end - start) / parts
        out += [(start + i * step, start + (i + 1) * step) for i in range(parts)]
    return [(round(s, 3), round(e, 3)) for s, e in out]


class _LinePicker:
    """按时长挑句子：词数最接近的几句里，选最近没用过的。"""

    def __init__(self, lines, rng: random.Random):
        self.lines, self.rng = lines, rng
        self.recent: deque[int] = deque(maxlen=RECENT)
        self.started = False

    def pick(self, seconds: float) -> str:
        if not self.started:  # 开场第一句固定，听起来更像一场会议的开头
            self.started = True
            self.recent.append(0)
            return self.lines[0][0]
        target = seconds * WORDS_PER_SECOND
        ranked = sorted(range(len(self.lines)), key=lambda i: abs(len(self.lines[i][0].split()) - target))
        choices = [i for i in ranked[:6] if i not in self.recent] or ranked[:6]
        i = self.rng.choice(choices)
        self.recent.append(i)
        return self.lines[i][0]


class MockAsrProvider:
    """假转写引擎：不加载模型，随时就绪。delay 为每个声道模拟的处理时长（秒），用来演示进度。"""

    state = "ready"
    error = ""

    def __init__(self, settings: Settings):
        self.delay = settings.mock_delay

    def start_preload(self) -> None:
        pass

    def wait_ready(self, timeout: float) -> None:
        pass

    def transcribe(self, path: Path, on_progress: Callable[[float], None]) -> tuple[str, list[Segment]]:
        track = "B" if "track_B" in path.name else "A"  # 单声道音频只有 A 轨
        rng = random.Random(f"mock-{track}")  # 同一声道每次结果一致
        picker = _LinePicker(LINES_B if track == "B" else LINES_A, rng)
        for frac in (0.3, 0.6):
            time.sleep(self.delay / 3)
            on_progress(frac)
        segments = [Segment(s, e, picker.pick(e - s), round(rng.uniform(0.82, 0.98), 2))
                    for s, e in speech_spans(path)]
        time.sleep(self.delay / 3)
        on_progress(1.0)
        return "en-US", segments


ZH_BY_EN = {en: zh for en, zh in LINES_A + LINES_B}

MOCK_ANALYSIS = {
    "speakers": [
        {"trackId": "A", "identity": "项目经理（会议主持人）", "confidence": 0.9, "role": "agent",
         "emotionDistribution": {"neutral": 0.7, "happy": 0.2, "surprised": 0.1}, "sentimentScore": 0.25,
         "dominantIntent": "coordination"},
        {"trackId": "B", "identity": "工业设计师", "confidence": 0.85, "role": "customer",
         "emotionDistribution": {"neutral": 0.65, "happy": 0.2, "surprised": 0.15}, "sentimentScore": 0.2,
         "dominantIntent": "proposal"},
    ],
    "scenes": [
        {"type": "meeting", "subType": "product_design", "confidence": 0.93,
         "description": "产品设计团队的启动会议，讨论新款遥控器的设计目标、用户需求和分工",
         "keywords": ["遥控器", "产品设计", "预算", "分工"]},
        {"type": "meeting", "subType": "brainstorming", "confidence": 0.55,
         "description": "围绕外观、材料和功能的头脑风暴", "keywords": ["外壳", "按键", "材料"]},
    ],
    "callType": "unknown",
    "callPurpose": "启动会议：确定遥控器的设计目标并分配后续任务",
    "callResolution": "unresolved",
    "analysis": {"hasComplaint": False, "complaintScore": 0.02, "hasPraise": True, "isEscalated": False},
}


class MockLlm:
    """假大模型：身份、场景为固定演示数据；翻译查表（中文用内置译文，其它语种加语种前缀）。"""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings

    def analyze(self, dialogue: str, track_ids: list[str]) -> dict:
        return normalize_analysis(MOCK_ANALYSIS, track_ids)

    def translate(self, items: list[dict], language: str, batch: int = 40) -> dict[str, str]:
        lang = language.lower()
        out = {}
        for it in items:
            text = it["text"]
            if lang.startswith("en"):
                out[it["id"]] = text  # 转写本身就是英文
            elif lang.startswith("zh"):
                out[it["id"]] = ZH_BY_EN.get(text, f"[{language}] {text}")
            else:
                out[it["id"]] = f"[{language}] {text}"
        return out
