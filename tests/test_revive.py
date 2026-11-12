"""부활 연출 (revive.py · revive_view.py) — 가디언이 되살린 울트론이 처음 뜰 때의 장면.

지켜야 하는 것: 해킹이 점점 심해진다 → TV 지직이 2초 유지된다 → 눈이 먼저 켜지고 그 뒤에 코어가 나타난다 → 원래 화면으로 돌아온다,
어느 1초 동안이든 넓은 면의 밝기가 크게 바뀌는 일이 3번을 넘지 않는다 (빛에 민감한 사람), 다 보여 준 뒤 그림을 놓아 준다.
"""
import os
import types

import numpy as np
import pytest

from jarvis import glitch, revive as R

W, H = 640, 360


def desktop(bright: bool = True) -> np.ndarray:
    """가짜 화면: 밝은 문서 창 (또는 어두운 화면) + 작업 표시줄."""
    img = np.zeros((H, W, 3), np.uint8)
    img[:] = (36, 74, 128) if bright else (14, 14, 18)
    if bright:
        img[30:300, 60:450] = 250
        for i in range(12):
            img[60 + i * 18:66 + i * 18, 80:80 + 90 + (i * 53) % 300] = 60
    img[-20:] = (28, 30, 36)
    return img


@pytest.fixture(scope="module")
def scene():
    return R.build(desktop(), (W, H), np.random.default_rng(5))


# ---------------------------------------------------------------- 시간표
def test_timeline_order_and_the_two_second_static(scene):
    m = scene.marks()
    assert list(m) == ["hack", "static", "settle", "eyes", "form", "hold", "end"]
    assert 1.2 <= m["hack"] <= 2.4                                   # 해킹이 점점 심해지는 시간
    assert m["static"] - m["hack"] == pytest.approx(2.0)            # TV 지직은 2초 유지
    assert m["settle"] < m["eyes"] < m["form"] < m["end"] and scene.duration == m["end"]
    assert [R.phase(scene, t)[0] for t in (0.1, m["hack"] + 1, m["static"] + 0.1, m["settle"] + 0.1,
                                            m["eyes"] + 0.1, m["form"] + 0.1, m["hold"] + 0.1, m["end"] + 1)] == \
        ["hack", "static", "settle", "eyes", "form", "hold", "fade", "end"]


def test_hacking_gets_worse_over_time(scene):
    def covered(f):                                                  # 화면을 덮은 비율 (None = 잠깐 정상)
        return 0.0 if f.image is None else float((f.image[..., 3] > 0).mean())
    cov = [covered(f) for f in scene.hack]
    third = max(1, len(cov) // 3)
    assert max(cov[:third]) < 0.6 and cov[-1] > 0.95                # 처음엔 일부만 찢기고, 끝에는 화면 전체가 무너진다
    assert np.mean(cov[-third:]) > np.mean(cov[:third]) + 0.4
    assert any(f.image is None for f in scene.hack[:4])             # 처음에는 화면이 잠깐씩 돌아온다
    assert all(f.image is not None for f in scene.hack[-4:])        # 끝으로 가면 돌아오지 않는다
    shot = desktop().astype(int)

    def broken(f):                                                   # 원래 화면과 눈에 띄게 달라진 칸의 비율
        if f.image is None:
            return 0.0
        seen = np.where(f.image[..., 3:4] > 0, f.image[..., :3].astype(int), shot)
        return float((np.abs(seen - shot).max(axis=2) > 40).mean())
    first = next(f for f in scene.hack if f.image is not None)
    assert broken(scene.hack[-1]) > broken(first) * 2                # 끝으로 갈수록 화면이 더 많이 망가진다


def test_static_is_mid_gray_and_steady():
    tiles = R.static_tiles(W, H, np.random.default_rng(1))
    assert len(tiles) == R.STATIC_TILES and tiles[0].shape == (H // 2, W // 2)
    means = [t.mean() for t in tiles]
    assert all(100 < m < 155 for m in means)                        # 중간 회색 둘레
    assert max(means) - min(means) < 3                              # 장마다 바뀌어도 밝기는 그대로 (번쩍이지 않는다)


def test_big_screens_are_built_small():
    sc = R.build(np.zeros((2160, 3840, 3), np.uint8), (3840, 2160), np.random.default_rng(2))
    img = next(f.image for f in sc.hack if f.image is not None)
    assert max(img.shape[:2]) <= R.MAX_EDGE and max(sc.static[0].shape) <= R.STATIC_EDGE


def test_drop_pixels_keeps_the_timeline():
    sc = R.build(desktop(), (W, H), np.random.default_rng(3))
    before = sc.duration
    sc.drop_pixels()
    assert sc.duration == before and all(f.image is None for f in sc.hack) and sc.static == []


# ---------------------------------------------------------------- 소리
def test_sound_follows_the_scene(scene):
    a = R.sound(scene, np.random.default_rng(1))
    sr = glitch.SOUND_RATE
    assert a.dtype == np.int16 and abs(len(a) / sr - scene.duration) < 0.05
    m = scene.marks()

    def loud(t0, t1):
        return float(np.abs(a[int(t0 * sr):int(t1 * sr)].astype(float)).mean())
    assert loud(m["hack"] + 0.2, m["static"] - 0.2) > 2000          # TV 지직은 쉭 하고 들린다
    assert loud(m["eyes"], m["form"]) > 500                         # 코어가 나타날 때 낮게 울린다
    assert loud(m["end"] - 0.02, m["end"]) < 400                    # 끝은 조용히


# ---------------------------------------------------------------- 그리기 (Qt)
@pytest.fixture(scope="module")
def V():
    pytest.importorskip("PySide6.QtWidgets")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from jarvis import revive_view
    return revive_view


def test_eyes_light_up_before_the_core_appears(V, scene):
    m = scene.marks()
    during_eyes = V.looks(scene, m["settle"] + 0.8)
    assert during_eyes["eyes"] > 0.9 and all(v == 0 for v in during_eyes["core"].values())
    early_form = V.looks(scene, m["eyes"] + 0.2)
    assert early_form["eyes"] == 1 and early_form["core"]["disc"] > 0 and early_form["core"]["hex"] == 0   # 안쪽부터
    assert all(v == 1 for v in V.looks(scene, m["form"] + 0.1)["core"].values())
    assert V.looks(scene, m["end"] - 0.01)["alpha"] < 0.05           # 끝에는 원래 화면으로
    assert V.looks(scene, m["hack"] + 1)["static"] == 1 and V.looks(scene, m["static"] + 0.1)["black"] == 1


def test_eyes_flicker_on_like_neon_then_open(V):
    lights = [V.eye_light(k / 100) for k in range(100)]
    dips = sum(1 for a, b in zip(lights, lights[1:]) if b < a - 0.01)
    assert lights[0] == 0 and lights[-1] == 1 and 1 <= dips <= 40  # 두어 번 깜빡이다 켜진다
    assert V.eye_open(0.1) < 0.15 and V.eye_open(1.0) == pytest.approx(1.0)   # 가는 틈으로 켜졌다가 뜬다


def test_frames_render_and_eyes_show_in_the_dark(V, scene):
    m = scene.marks()
    a = V.Assets(scene, W, H)
    dark = V.render(scene, m["settle"] + 0.05, desktop(), a)
    assert dark.mean() < 25                                          # 지직이 가라앉아 캄캄
    eyes = V.render(scene, m["settle"] + 1.0, desktop(), a)
    red = eyes[..., 0].astype(int) - eyes[..., 1]
    ys, xs = np.nonzero(red > 60)
    assert len(ys) > 50 and abs(xs.mean() - W / 2) < W * 0.1       # 화면 한가운데에 붉은 두 눈
    assert ys.mean() < H / 2                                         # 눈은 코어의 위쪽 절반에 있다
    done = V.render(scene, m["form"] + 0.2, desktop(), a)
    assert (done[..., 0].astype(int) - done[..., 1] > 60).sum() > len(ys) * 3   # 코어가 다 나타나면 붉은 면이 훨씬 넓다
    back = V.render(scene, m["end"], desktop(), a)
    assert np.abs(back.astype(int) - desktop().astype(int)).mean() < 3        # 끝나면 원래 화면 그대로


@pytest.mark.parametrize("bright", [True, False])
def test_whole_scene_never_flashes_more_than_three_times_a_second(V, bright):
    """30장/초로 장면 전체를 그려, 넓은 면(화면 1/3)의 밝기가 크게 바뀐 순간을 센다 (WCAG 2.3.1 보다 엄격하게 3번 이하)."""
    sc = R.build(desktop(bright), (W, H), np.random.default_rng(11))
    a = V.Assets(sc, W, H)
    bg = desktop(bright)
    times, prev = [], glitch.regions(bg)
    for i in range(int(sc.duration * 30) + 2):
        t = i / 30
        r = glitch.regions(V.render(sc, t, bg, a))
        if glitch.big_change(prev, r):
            times.append(t)
        prev = r
    worst = max((sum(1 for u in times if s <= u < s + 1.0) for s in times), default=0)
    assert worst <= glitch.MAX_CHANGES_PER_SEC, times


def test_view_plays_then_lets_go(V, scene, monkeypatch):
    from PySide6.QtCore import QRect
    sc = R.build(desktop(), (W, H), np.random.default_rng(9))
    view = V.ReviveView()
    done = []
    view.finished.connect(lambda: done.append(1))
    view.play(QRect(0, 0, W, H), sc)
    assert view.playing and all(f.image is None for f in sc.hack)   # 그릴 그림은 Qt 쪽에만 (numpy 는 놓아 줌)
    view.grab()                                                      # 한 번 그려 본다 (오류 없이)
    view.stop()
    assert done == [1] and not view.playing and sc.hack == [] and view._assets is None


# ---------------------------------------------------------------- 울트론 본체 연결
@pytest.fixture
def app(monkeypatch):
    import jarvis.app as app_mod
    J = app_mod.Jarvis

    class App:
        _revive_begin, _revive_done, _revived_line = J._revive_begin, J._revive_done, J._revived_line

        def __init__(self):
            self.cfg = {"guardian_show": True, "user_title": "창조자"}
            self.args = types.SimpleNamespace(closed="vision")
            self.shown, self.toasts, self.said, self.later = {}, [], [], []
            self.bridge = types.SimpleNamespace(set=lambda k, v: self.shown.__setitem__(k, v),
                                                toast=types.SimpleNamespace(emit=lambda kind, m: self.toasts.append(m)))
            self._reviving, self._revive_demo = False, False
            self.listener = types.SimpleNamespace(muted=False)

        def say(self, text, follow_up=True):
            self.said.append(text)

        def _release_fx(self, name):
            pass

        def _unmute(self):
            self.listener.muted = False

    monkeypatch.setattr(app_mod.winutil, "fullscreen_app", lambda: False)
    monkeypatch.setattr(app_mod.QTimer, "singleShot", lambda ms, fn: None)
    return App(), app_mod


def test_revived_line_comes_right_away_when_the_show_is_off(app):
    me, mod = app
    me.cfg["guardian_show"] = False
    me._revive_begin()
    assert me.said and "되살아났다" in me.said[0] and "vision" in me.said[0] and not me._reviving


def test_no_show_over_a_fullscreen_game(app, monkeypatch):
    me, mod = app
    monkeypatch.setattr(mod.winutil, "fullscreen_app", lambda: True)
    me._revive_begin()
    assert me.said and not me._reviving and not me.listener.muted


def test_demo_line_after_the_preview(app):
    me, mod = app
    me._revive_demo, me._reviving = True, True
    me._revive_done()
    assert "이렇게 깨어난다" in me.said[0] and not me._reviving


def test_saying_show_me_the_revival_plays_the_preview():
    from jarvis.brain import REVIVE_SHOW
    from jarvis.local_router import normalize
    for text in ("부활 연출 보여 줘", "되살아나는 장면 보여줘", "부활 연출"):
        assert REVIVE_SHOW.fullmatch(normalize(text)), text
    assert not REVIVE_SHOW.fullmatch(normalize("부활절 언제야"))


# ---------------------------------------------------------------- 가디언 기본값
def test_guardian_is_on_by_default_and_old_configs_move_once(tmp_path, monkeypatch):
    import json
    from jarvis import config as C
    monkeypatch.setattr(C, "DATA_DIR", tmp_path)
    monkeypatch.setattr(C, "CONFIG_PATH", tmp_path / "config.json")
    assert C.DEFAULTS["guardian"] is True and C.DEFAULTS["guardian_show"] is True
    (tmp_path / "config.json").write_text(json.dumps({"guardian": False}), encoding="utf-8")   # 예전 기본값이 저장된 파일
    assert C.load_config()["guardian"] is True
    cfg = C.Config()
    assert cfg["guardian"] is True
    cfg.update({"guardian": False})                                  # 그 뒤에 사용자가 끄면
    assert C.Config()["guardian"] is False and C.load_config()["guardian"] is False   # 꺼진 채로 남는다
