"""음성 인식 엔진 선택 규칙 테스트 — 특히 '호출어 대기 중 주변 대화는 Google 로 보내지 않는다'."""
from __future__ import annotations

import numpy as np
import pytest
import speech_recognition as sr

from jarvis.listener import Listener
from jarvis.local_stt import clean

PCM = (np.sin(np.arange(16000) / 5) * 3000).astype(np.int16)


class FakeLocal:
    def __init__(self, text, ready=True):
        self.text, self.ready, self.calls = text, ready, 0

    def recognize(self, pcm):
        self.calls += 1
        return self.text


def make(engine="auto", local_text="울트론 크롬 열어", google=("울트론 크롬 열어 줘",), wake_needed=True,
         local_ready=True):
    lis = Listener("ko-KR", on_level=lambda *_: None, on_speech_start=lambda: None, on_utterance=lambda *_: None)
    lis.stt_engine = engine
    lis.local_stt = FakeLocal(local_text, local_ready)
    lis.wake_needed = lambda: wake_needed
    lis.has_wake = lambda t: "울트론" in t
    sent = []

    def fake_google(rec, sr_, pcm):
        sent.append(len(pcm))
        g = google[0]
        if isinstance(g, Exception):
            raise g
        return g

    lis._recognize = fake_google
    return lis, sent


def run(lis):
    return lis._transcribe(sr.Recognizer(), sr, PCM, False)


def test_standby_background_talk_stays_local():
    lis, sent = make(local_text="오늘 저녁 뭐 먹지")
    assert run(lis) is None
    assert sent == [], "호출어가 없는 주변 대화가 Google 로 전송됨"


def test_standby_wake_word_uses_google_for_accuracy():
    lis, sent = make()
    assert run(lis) == "울트론 크롬 열어 줘"
    assert len(sent) == 1 and lis.last_engine == "google"


def test_standby_wake_google_misheard_gets_prefix():
    lis, _ = make(google=("크롬 열어 줘",))
    assert run(lis) == "울트론 크롬 열어 줘"


def test_standby_wake_offline_uses_local():
    lis, _ = make(google=(sr.RequestError("getaddrinfo failed"),))
    assert run(lis) == "울트론 크롬 열어"
    assert lis.last_engine == "local"


def test_active_conversation_google_first():
    lis, sent = make(wake_needed=False, google=("볼륨 30으로 해 줘",))
    assert run(lis) == "볼륨 30으로 해 줘"
    assert lis.local_stt.calls == 0


def test_active_offline_falls_back_to_local_and_skips_google_for_a_while():
    lis, sent = make(wake_needed=False, local_text="볼륨 30으로", google=(OSError("net down"),))
    assert run(lis) == "볼륨 30으로"
    assert run(lis) == "볼륨 30으로"
    assert len(sent) == 1, "끊긴 뒤 바로 다시 Google 을 기다리면 안 됨"


def test_local_engine_never_uses_google():
    lis, sent = make(engine="local", wake_needed=False)
    assert run(lis) == "울트론 크롬 열어" and sent == []


def test_google_engine_never_uses_local():
    lis, _ = make(engine="google")
    assert run(lis) == "울트론 크롬 열어 줘" and lis.local_stt.calls == 0


def test_model_not_ready_behaves_like_before():
    lis, sent = make(local_ready=False, google=("오늘 저녁 뭐 먹지",))
    assert run(lis) == "오늘 저녁 뭐 먹지" and len(sent) == 1


@pytest.mark.parametrize("raw,out", [
    ("<|ko|><|NEUTRAL|><|Speech|><|withitn|>크롬 열어 줘.", "크롬 열어 줘"),
    ("볼륨 30으로 해 줘?", "볼륨 30으로 해 줘"),
    ("<|ko|>我", None),
    ("", None),
])
def test_clean(raw, out):
    assert clean(raw) == out


# ---- 호출어 뒤쪽만 다시 받아 적기 (오프라인 결과를 그대로 쓰게 될 때) --------------------------------
class ScriptedLocal:
    """부를 때마다 정해 둔 글을 차례로 돌려주고, 받은 소리 길이를 기록한다."""

    def __init__(self, *texts):
        self.texts, self.ready, self.lengths = list(texts), True, []
        self.last = (["울", "트", "론", " 줄", "여", "줘"], [0.6, 0.8, 1.0, 1.9, 2.0, 2.2])

    def recognize(self, pcm):
        self.lengths.append(len(pcm))
        return self.texts.pop(0) if self.texts else None


LONG = (np.sin(np.arange(3 * 16000) / 5) * 3000).astype(np.int16)        # 3초짜리 발화


def second(engine="local", texts=("울트론 줄여줘", "소리 좀 줄여줘"), google=(OSError("net down"),), cut=1.2,
           understood=("소리 좀 줄여줘",)):
    lis, sent = make(engine=engine, google=google)
    lis.local_stt = ScriptedLocal(*texts)
    lis.retry_cut = lambda text, tokens, stamps: cut
    lis.understands = lambda t: t in understood
    return lis, sent


def run_long(lis):
    return lis._transcribe(sr.Recognizer(), sr, LONG, False)


def test_local_retry_recovers_the_word_dropped_after_the_wake_word():
    lis, _ = second()
    assert run_long(lis) == "울트론 소리 좀 줄여줘"
    full, rest = lis.local_stt.lengths
    assert rest == full - int(1.2 * 16000)                 # 호출어가 끝난 뒤의 소리만 다시 받아 적었다


def test_local_retry_keeps_the_first_transcript_when_the_second_is_not_a_command():
    lis, _ = second(texts=("울트론 줄여줘", "어쩌고 저쩌고"))
    assert run_long(lis) == "울트론 줄여줘"
    lis, _ = second(texts=("울트론 줄여줘", None))
    assert run_long(lis) == "울트론 줄여줘"


def test_local_retry_is_skipped_when_not_needed_or_not_wired():
    lis, _ = second(cut=None)                              # 이미 알아들었거나 호출어가 없는 경우
    assert run_long(lis) == "울트론 줄여줘" and len(lis.local_stt.lengths) == 1
    lis, _ = second(cut=2.8)                               # 호출어 뒤에 남은 소리가 너무 짧다 (0.2초)
    assert run_long(lis) == "울트론 줄여줘" and len(lis.local_stt.lengths) == 1
    lis, _ = second()
    lis.retry_cut = None
    assert run_long(lis) == "울트론 줄여줘" and len(lis.local_stt.lengths) == 1
    lis, _ = make(engine="local", local_text="울트론 줄여줘")  # 시각 정보를 주지 않는 인식기
    lis.retry_cut = lambda *a: 0.1
    lis.understands = lambda t: True
    assert run_long(lis) == "울트론 줄여줘"


def test_auto_mode_retries_only_when_the_local_transcript_becomes_final():
    lis, sent = second(engine="auto", google=("울트론 소리 좀 줄여 줘",), cut=0.3)
    assert run_long(lis) == "울트론 소리 좀 줄여 줘"              # Google 이 받아 적었으면 그걸 쓴다 — 다시 인식하지 않음
    assert len(lis.local_stt.lengths) == 1 and len(sent) == 1
    lis, sent = second(engine="auto", cut=0.3)             # 인터넷이 끊겼으면 오프라인 결과를 보완한다
    assert run_long(lis) == "울트론 소리 좀 줄여줘" and len(lis.local_stt.lengths) == 2


def test_retry_failure_never_loses_the_first_transcript():
    lis, _ = second()

    def boom(text, tokens, stamps):
        raise RuntimeError("x")

    lis.retry_cut = boom
    assert run_long(lis) == "울트론 줄여줘"
