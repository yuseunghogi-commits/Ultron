"""속도 — 말소리 캐시, 빠른 모드(막히면 보통 속도로), 카드뉴스 저장 속도."""
import threading
import time
import types

import numpy as np
import pytest

from jarvis import tts_cache
from jarvis.tts_cache import TTSCache


# ---------------------------------------------------------------- 말소리 캐시
def test_cache_returns_the_same_sound_from_memory_and_disk(tmp_path):
    c = TTSCache(tmp_path)
    k = c.key("볼륨을 낮췄다.", "ko-KR-InJoonNeural", "-4%", "-14Hz", 0.6)
    assert c.get(k) is None
    pcm = np.linspace(-1, 1, 2400, dtype=np.float32)
    c.put(k, pcm)
    assert np.array_equal(c.get(k), pcm)
    fresh = TTSCache(tmp_path)                                   # 다시 켜도 디스크에서 꺼낸다
    assert np.array_equal(fresh.get(k), pcm)
    # 목소리 · 빠르기 · 음높이 · 기계음이 다르면 다른 소리
    others = {c.key("볼륨을 낮췄다.", v, r, p, f) for v, r, p, f in
              [("ko-KR-SunHiNeural", "-4%", "-14Hz", 0.6), ("ko-KR-InJoonNeural", "+0%", "-14Hz", 0.6),
               ("ko-KR-InJoonNeural", "-4%", "+0Hz", 0.6), ("ko-KR-InJoonNeural", "-4%", "-14Hz", 0.0)]}
    assert k not in others and len(others) == 4


def test_only_short_lines_are_cached_and_the_folder_stays_small(tmp_path, monkeypatch):
    assert TTSCache.wanted("알았다. 바로 만들지.") and not TTSCache.wanted("") and not TTSCache.wanted("가" * 200)
    monkeypatch.setattr(tts_cache, "MAX_FILES", 5)
    c = TTSCache(tmp_path, memory=2)
    for i in range(12):
        c.put(c.key(f"말 {i}", "v", "r", "p", 0), np.ones(10, np.float32))
        time.sleep(0.01)
    c.trim()
    assert len(list(tmp_path.glob("*.npy"))) == 5 and len(c._mem) == 2
    assert c.get(c.key("말 11", "v", "r", "p", 0)) is not None                # 가장 최근 것은 남는다


def test_broken_cache_files_are_ignored(tmp_path):
    c = TTSCache(tmp_path)
    k = c.key("x", "v", "r", "p", 0)
    (tmp_path / f"{k}.npy").write_bytes(b"not numpy")
    assert c.get(k) is None


def test_speech_render_uses_the_cache_and_skips_sapi(monkeypatch, tmp_path):
    pytest.importorskip("PySide6.QtMultimedia")
    from jarvis import speech
    monkeypatch.setattr(speech, "CACHE", TTSCache(tmp_path))
    calls = []

    def synth(text, voice, rate, pitch="+0Hz"):
        calls.append(text)
        return b"mp3", suffix[0]
    suffix = [".mp3"]
    monkeypatch.setattr(speech, "synthesize", synth)
    monkeypatch.setattr(speech, "decode", lambda data, sfx: np.ones(4800, np.float32) * 0.5)
    monkeypatch.setattr(speech, "trim_silence", lambda a: a)
    monkeypatch.setattr(speech, "robotize", lambda a, fx: a)
    a = speech.render("볼륨을 낮췄다.", "v", "r", "p", 0.5)
    b = speech.render("볼륨을 낮췄다.", "v", "r", "p", 0.5)
    assert calls == ["볼륨을 낮췄다."] and np.array_equal(a, b)          # 두 번째는 인터넷 합성 없이
    suffix[0] = ".wav"                                                    # SAPI(대체 음성)는 저장하지 않는다
    speech.render("인터넷이 끊겼다.", "v", "r", "p", 0.5)
    speech.render("인터넷이 끊겼다.", "v", "r", "p", 0.5)
    assert calls.count("인터넷이 끊겼다.") == 2


# ---------------------------------------------------------------- 빠른 모드
def _rate_limited():
    import anthropic
    import httpx
    return anthropic.RateLimitError("fast mode limit", response=httpx.Response(429, request=httpx.Request("POST", "https://x")),
                                    body=None)


def test_fast_mode_is_sent_only_when_on_and_falls_back_when_refused():
    pytest.importorskip("anthropic")
    from test_office import Block, brain
    b = brain(brain="api", fast_mode=True, model="claude-opus-5-5")
    sent = []

    def create(**kw):
        sent.append(dict(kw))
        if kw.get("speed") == "fast":
            raise _rate_limited()
        return types.SimpleNamespace(content=[Block(type="text", text="됐다.")], stop_reason="end_turn")
    b._client_for = lambda key: types.SimpleNamespace(beta=types.SimpleNamespace(messages=types.SimpleNamespace(create=create)))
    assert b._claude("오늘 날씨 어때", "key", threading.Event()) == "됐다."
    assert [kw.get("speed") for kw in sent] == ["fast", None]               # 막히면 보통 속도로 다시
    sent.clear()
    b._claude("내일은?", "key", threading.Event())
    assert [kw.get("speed") for kw in sent] == [None]                       # 10분 동안은 빠른 모드를 다시 시도하지 않는다
    off = brain(brain="api", fast_mode=False, model="claude-opus-5-5")
    assert not off._fast("claude-opus-5-5")
    assert not brain(brain="api", fast_mode=True, model="claude-haiku-5-5")._fast("claude-haiku-5-5")


# ---------------------------------------------------------------- 카드뉴스 저장
def test_cards_are_saved_with_the_fast_halving(tmp_path, monkeypatch):
    from PIL import Image
    from jarvis import design
    img = Image.new("RGB", (design.CARD * design.SS, design.CARD * design.SS), (10, 20, 30))
    out = design._save(img, design.CARD, design.CARD, tmp_path / "a.png")
    assert out.size == (design.CARD, design.CARD) and (tmp_path / "a.png").exists()
