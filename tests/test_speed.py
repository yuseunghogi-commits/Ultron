"""속도 — 빠른 모드(막히면 보통 속도로), 카드뉴스 저장 속도."""
import threading
import types

import pytest


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
