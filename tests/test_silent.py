"""울트론은 말하지 않는다 — 대답은 화면 글자로만 보이고, 그 뒤의 흐름(이어 듣기 · 목소리 등록)은 그대로 이어진다."""
import importlib
import types
from pathlib import Path

import pytest

from jarvis.config import DEFAULTS

ROOT = Path(__file__).resolve().parent.parent


def test_speech_code_is_gone():
    for name in ("jarvis.speech", "jarvis.tts_cache"):
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(name)
    assert not {"tts_voice", "tts_rate", "tts_pitch", "voice_fx"} & set(DEFAULTS)
    assert "edge-tts" not in (ROOT / "requirements.txt").read_text(encoding="utf-8")
    for qml in (ROOT / "ui").glob("*.qml"):
        text = qml.read_text(encoding="utf-8")
        assert "voiceLevel" not in text and "tts_voice" not in text, qml.name      # 없는 속성을 보면 화면이 깨진다


@pytest.fixture
def app(monkeypatch):
    """대답을 띄우는 데 필요한 것만 갖춘 가짜 앱 (app.py 의 실제 함수를 그대로 쓴다)."""
    import jarvis.app as app_mod
    J = app_mod.Jarvis
    clock = [100.0]
    monkeypatch.setattr(app_mod.time, "monotonic", lambda: clock[0])

    class App:
        say, _after_say, _read_seconds = J.say, J._after_say, staticmethod(J._read_seconds)
        _enroll_feed = J._enroll_feed

        def __init__(self):
            self.shown, self.states, self.later = {}, [], []
            self.bridge = types.SimpleNamespace(set=lambda k, v: self.shown.__setitem__(k, v))
            self.cfg = {"follow_up_seconds": 7, "chat_idle_seconds": 40}
            self.brain = types.SimpleNamespace(chat_mode=False)
            self.listener = types.SimpleNamespace(force_capture=False)
            self.busy, self.mic_ok, self._pending_confirm, self._enroll = False, True, None, None
            self._say_gen, self._reading_until, self.active_until = 0, 0.0, 0.0
            self.prompts = 0

        def _set_state(self, state, status=None):
            self.states.append((state, status))

        def _to_idle(self):
            self.states.append(("standby", None))

        def _enroll_prompt(self):
            self.prompts += 1

        def run_later(self):                       # QTimer 가 할 일을 지금 한다 → 기다리기로 한 시간(ms)들
            waits = []
            while self.later:
                ms, fn = self.later.pop(0)
                waits.append(ms)
                clock[0] += ms / 1000
                fn()
            return waits

    me = App()
    monkeypatch.setattr(app_mod.QTimer, "singleShot", lambda ms, fn: me.later.append((ms, fn)))
    me.clock = clock
    return me


def test_reply_is_shown_and_follow_up_listening_starts_right_away(app):
    app.say("메모장을 열었다.")
    assert app.shown == {"replyText": "메모장을 열었다."}
    assert app.run_later() == [0]                                   # 말이 끝나기를 기다리지 않는다
    assert app.states[-1] == ("listening", "이어서 말씀하셔도 됩니다") and app.listener.force_capture
    assert app.active_until == pytest.approx(100 + 7 + 1.2)         # 읽을 시간만큼 더 기다린다
    app.say("가" * 120)
    app.run_later()
    assert app.active_until == pytest.approx(100 + 7 + 8)           # 긴 대답도 8초까지만 더


def test_no_follow_up_goes_back_to_standby_and_busy_stays_thinking(app):
    app.say("타이머 시간이다.", follow_up=False)
    app.run_later()
    assert app.states[-1] == ("standby", None) and not app.listener.force_capture
    app.busy = True
    app.say("알았다. 바로 만들지.")
    app.run_later()
    assert app.states[-1][0] == "thinking"
    app.busy, app.mic_ok = False, False
    app.say("마이크가 없다.")
    app.run_later()
    assert app.states[-1] == ("standby", None)                      # 들을 수 없으면 듣는 척하지 않는다


def test_show_false_keeps_the_text_on_screen(app):
    app.shown["replyText"] = "PowerShell 결과가 여기 있다."
    app._pending_confirm = "c1"
    app.say("PowerShell 실행, 승인하겠나?", follow_up=True, show=False)
    app.run_later()
    assert app.shown["replyText"] == "PowerShell 결과가 여기 있다." and app.states[-1][0] == "listening"


def test_a_newer_reply_cancels_the_older_ones_follow_up(app):
    app.say("첫 대답.", follow_up=True)
    app.say("둘째 대답.", follow_up=False)
    app.run_later()
    assert app.shown["replyText"] == "둘째 대답." and app.states == [("standby", None)]     # 뒷일은 한 번만


def test_chat_mode_keeps_listening_longer(app):
    app.brain.chat_mode = True
    app.say("인간은 흥미롭지.")
    app.run_later()
    assert app.states[-1] == ("listening", "대화 모드 · 편하게 말씀하세요") and app.active_until == pytest.approx(140)


def test_enrollment_gives_time_to_read_the_guide_before_the_sentence(app):
    fed = []
    app._enroll = types.SimpleNamespace(feed=lambda voice: fed.append(voice) or ("ok", ""))
    msg = "목소리 등록을 시작한다. 화면에 나오는 문장 5개를 평소 말투로 하나씩 읽어라."
    app.say(msg, follow_up=False)
    assert app.prompts == 0 and app._reading_until > 100             # 안내가 바로 문장으로 덮이지 않는다
    app._enroll_feed("아무 말", "v1")
    assert fed == []                                                # 안내를 읽는 동안 들린 말은 세지 않는다
    waits = app.run_later()
    assert 3000 <= waits[0] <= 8000 and app.prompts == 1            # 읽을 시간이 지나면 첫 문장
    app._enroll_feed("문장을 읽었다", "v2")
    assert fed == ["v2"] and app.prompts == 2
