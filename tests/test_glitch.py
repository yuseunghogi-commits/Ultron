"""해킹 연출 (glitch.py · glitch_view.py) — 깨진 화면 장면 · 빛 민감성 제한 · 소리 · 일정 · 대사 · 덮개 창."""
import random
import threading
import wave

import numpy as np
import pytest

import jarvis.brain as bm
from jarvis import glitch as G
from jarvis.config import DEFAULTS
from jarvis.winutil import _idle_from

W, H = 640, 360


def screens():
    """번쩍임이 생기기 쉬운 화면들 (흑백 대비가 큰 것) + 평범한 화면."""
    half = np.zeros((H, W, 3), np.uint8)
    half[:, W // 2:] = 255
    rows = np.zeros((H, W, 3), np.uint8)
    rows[H // 2:] = 255
    checker = (np.indices((H, W)).sum(0) // 80 % 2 * 255).astype(np.uint8)[..., None].repeat(3, 2)
    stripes = np.zeros((H, W, 3), np.uint8)
    stripes[:, ::40] = 255
    page = np.full((H, W, 3), 243, np.uint8)
    page[:28] = (31, 42, 68)
    for y in range(50, 300, 22):
        page[y:y + 12, 30:230] = 60
    noise = np.random.default_rng(0).integers(0, 256, (H, W, 3), dtype=np.uint8)
    return {"좌우 흑백": half, "위아래 흑백": rows, "체커보드": checker, "세로 줄": stripes, "문서 화면": page, "잡음": noise,
            "흰 화면": np.full((H, W, 3), 250, np.uint8), "검은 화면": np.zeros((H, W, 3), np.uint8)}


# ---------------------------------------------------------------- 장면
def test_timeline_shape_and_length():
    shot = screens()["문서 화면"]
    for seed in range(6):
        fr = G.frames(shot, np.random.default_rng(seed))
        kinds = [f.kind for f in fr]
        assert {"tear", "freeze", "gap"} <= set(kinds)
        assert 900 <= sum(f.ms for f in fr) <= 2400                      # 1~2초 남짓
        for f in fr:
            if f.image is None:
                assert f.kind == "gap"
                continue
            assert f.image.shape == (H, W, 4) and f.image.dtype == np.uint8
            if f.kind == "freeze":
                assert (f.image[..., 3] == 255).all()                     # 멈칫: 화면 전체를 덮는다
            if f.kind == "tear":
                assert (f.image[..., 3] == 0).any()                       # 찢어짐: 띠 밖은 실제 화면이 보인다
                assert (f.image[..., 3] == 255).any()


def test_frames_are_really_broken_and_reproducible():
    shot = screens()["문서 화면"]
    a = G.frames(shot, np.random.default_rng(3))
    b = G.frames(shot, np.random.default_rng(3))
    assert [f.ms for f in a] == [f.ms for f in b]
    assert all((x.image is None and y.image is None) or np.array_equal(x.image, y.image) for x, y in zip(a, b))
    heavy = max((f for f in a if f.kind == "tear"), key=lambda f: int((f.image[..., 3] > 0).sum()))
    seen = G.composite(shot, heavy.image)
    changed = np.any(seen != shot, axis=2).mean()
    assert changed > 0.03                                                 # 눈에 띄게 깨져 보인다


@pytest.mark.parametrize("name", list(screens()))
def test_wide_brightness_changes_stay_under_three_per_second(name):
    shot = screens()[name]
    for seed in range(15):
        fr = G.frames(shot, np.random.default_rng(seed))
        assert G.flash_report(shot, fr) <= G.MAX_CHANGES_PER_SEC, (name, seed)


def test_limiter_tames_a_strobing_plan():
    shot = np.zeros((H, W, 3), np.uint8)
    white = np.full((H, W, 4), 255, np.uint8)
    plan = [G.Frame(white if i % 2 == 0 else None, 100, "tear" if i % 2 == 0 else "gap") for i in range(14)]
    assert G.flash_report(shot, plan) >= 10                              # 그대로 두면 1초에 10번 바뀐다 (번쩍임 5번)
    tamed = G.limit_flashes(shot, plan)
    assert G.flash_report(shot, tamed) <= G.MAX_CHANGES_PER_SEC
    assert sum(f.ms for f in tamed) >= sum(f.ms for f in plan)          # 장면을 건너뛴 만큼 앞 장면을 오래 보여 준다


# ---------------------------------------------------------------- 소리
def test_sound_follows_the_scenes(tmp_path):
    fr = G.frames(screens()["문서 화면"], np.random.default_rng(1))
    audio = G.sound(fr, np.random.default_rng(1))
    assert audio.dtype == np.int16
    assert abs(len(audio) - sum(int(G.SOUND_RATE * f.ms / 1000) for f in fr)) <= len(fr)
    assert 0 < np.abs(audio).max() <= 0.5 * 32767                         # 너무 크지 않게
    start = 0
    for f in fr:                                                          # 잠깐 정상인 동안은 조용하다
        n = int(G.SOUND_RATE * f.ms / 1000)
        if f.kind == "gap":
            assert not audio[start:start + n].any()
        start += n
    old = tmp_path / "ultron_glitch_1.wav"
    old.write_bytes(b"x")
    path = G.write_wav(audio, folder=tmp_path)
    assert not old.exists() and path.endswith(".wav")                    # 이름을 매번 바꾸고 예전 파일은 지운다
    with wave.open(path) as w:
        assert w.getframerate() == G.SOUND_RATE and w.getnframes() == len(audio)


# ---------------------------------------------------------------- 일정 · 대사
def test_schedule_first_after_twenty_seconds_then_by_frequency():
    now = [100.0]
    s = G.Schedule(clock=lambda: now[0], rng=random.Random(0))
    now[0] += 19.5
    assert not s.due()
    now[0] += 0.6
    assert s.due()
    for every, (lo, hi) in G.EVERY.items():
        s.done(every)
        assert lo <= s.next_at - now[0] <= hi
    s.done(None)
    assert G.EVERY["sometimes"][0] <= s.next_at - now[0] <= G.EVERY["sometimes"][1]
    s.later(30)
    assert s.next_at == now[0] + 30


def test_lines_are_ominous_but_never_claim_real_harm():
    forbidden = ("비밀번호", "계좌", "돈", "송금", "결제", "카드", "몸값", "랜섬", "개인정보", "삭제", "지웠", "훔", "협박",
                 "경찰", "신고", "파일", "사진", "카메라", "웹캠", "가족")
    assert len(G.LINES) >= 10
    for s in G.LINES:
        assert not any(w in s for w in forbidden), s
        assert s.endswith((".", "?"))
    rng = random.Random(0)
    last = None
    for _ in range(50):
        s = G.line(rng, last)
        assert s != last
        last = s


def test_idle_time_survives_the_tick_counter_wrapping():
    assert _idle_from(5_000, 3_800) == 1.2
    assert _idle_from(200, 0xFFFFFF00) == pytest.approx((200 + 0x100) / 1000)


# ---------------------------------------------------------------- 말로 시키기
class Cfg(dict):
    def __getitem__(self, k):
        return self.get(k, DEFAULTS.get(k))

    def api_key(self):
        return ""

    def update(self, values):
        dict.update(self, values)


class Tools:
    def schemas(self):
        return []


def brain():
    b = bm.Brain(Cfg(brain="local", local_ai=False), Tools(), on_action=lambda *a: None, context_fn=lambda: "")
    b.hud = []
    b.on_hud = b.hud.append
    return b


def test_voice_commands_show_and_toggle_the_effect():
    b = brain()
    assert b.handle("해킹 연출 보여 줘", threading.Event()) == "보여 주지." and b.hud == ["glitch"]
    assert b.handle("울트론 해킹 연출 해 봐", threading.Event()) == "보여 주지."
    assert "접어 두겠다" in b.handle("해킹 연출 꺼 줘", threading.Event()) and b.cfg["hack_show"] is False
    assert "보여 주지" in b.handle("해킹 연출 다시 켜 줘", threading.Event()) and b.cfg["hack_show"] is True
    assert b.hud == ["glitch", "glitch"]
    assert b.handle("해킹 연출이 뭐야", threading.Event()) != "보여 주지."


# ---------------------------------------------------------------- 덮개 창
@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtWidgets import QApplication
    app = QCoreApplication.instance()
    if app is not None and not isinstance(app, QApplication):
        pytest.skip("다른 테스트가 위젯 없는 Qt 앱을 만들었다")
    return app or QApplication([])


def test_qimage_round_trip(qapp):
    from jarvis.glitch_view import from_qimage, to_qimage
    rgba = np.zeros((37, 53, 4), np.uint8)                                # 한 줄 바이트 수가 4의 배수가 아닌 크기
    rgba[..., 0] = np.arange(53)[None, :] * 4
    rgba[..., 1] = np.arange(37)[:, None] * 6
    rgba[..., 3] = 255
    back = from_qimage(to_qimage(rgba))
    assert back.shape == (37, 53, 3) and np.array_equal(back, rgba[..., :3])


def test_view_plays_every_scene_then_hides(qapp):
    from PySide6.QtCore import QElapsedTimer, QRect
    from jarvis.glitch_view import GlitchView, to_qimage
    view = GlitchView()
    done = []
    view.finished.connect(lambda: done.append(True))
    img = to_qimage(np.full((20, 30, 4), 200, np.uint8))
    view.play(QRect(0, 0, 30, 20), [(img, 30), (None, 20), (img, 30)])
    assert view.playing
    t = QElapsedTimer()
    t.start()
    while not done and t.elapsed() < 3000:
        qapp.processEvents()
    assert done == [True] and not view.playing
    view.stop()                                                           # 이미 끝났으면 아무 일도 없다
    assert done == [True]
