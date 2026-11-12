"""부활 연출 (revive.py · revive_view.py) — 가디언이 되살린 울트론이 처음 뜰 때의 장면.

지켜야 하는 것: 해킹이 4초 넘게 점점 심해지다 자연스럽게 TV 지직으로 넘어가 2초 유지된다 → 눈이 먼저 옅게 떠올라 진해지고
그 뒤에 코어가 나타난다 → 검은 바탕이 걷히며 울트론이 그 자리에서 HUD 크기로 줄어 실제 HUD 와 겹친다,
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
    return R.build(desktop(), (W, H), np.random.default_rng(5), target=(500.0, 180.0, 107.0))


# ---------------------------------------------------------------- 시간표
def test_timeline_order_long_hack_and_two_second_static(scene):
    m = scene.marks()
    assert list(m) == ["hack", "static", "settle", "eyes", "form", "hold", "shrink", "end"]
    assert m["hack"] >= 4.0 and R.HACK - R.TUNE >= 3.5             # 해킹은 4초 넘게, 지직이 차오르기 전까지 3.5초 넘게
    assert m["static"] - m["hack"] == pytest.approx(2.0)            # TV 지직은 2초 유지
    assert m["eyes"] - m["settle"] >= 2.0 and m["form"] - m["eyes"] >= 2.5   # 눈 · 코어는 천천히
    assert [R.phase(scene, t)[0] for t in (0.1, m["hack"] + 1, m["static"] + 0.1, m["settle"] + 0.1, m["eyes"] + 0.1,
                                            m["form"] + 0.1, m["hold"] + 0.1, m["shrink"] + 0.1, m["end"] + 1)] == \
        ["hack", "static", "settle", "eyes", "form", "hold", "shrink", "handoff", "end"]


def test_hacking_gets_worse_over_time(scene):
    assert R.intensity(0.2) < 0.05 and R.intensity(R.HACK - R.TUNE) > 0.7 and R.intensity(R.HACK - R.TUNE / 2) == 1
    ks = [R.intensity(t / 10) for t in range(int(R.HACK * 10))]
    assert all(b >= a for a, b in zip(ks, ks[1:]))                  # 한 번도 약해지지 않는다

    def busy(t0, t1):                                                # 그 사이에 일어난 찢김 · 블록 · 얼룩 수
        return sum(int(((rows[:, 0] >= t0) & (rows[:, 0] < t1)).sum()) for rows in (scene.tears, scene.blocks, scene.smears))
    assert busy(3.0, 4.0) > busy(0.0, 1.0) * 3                      # 갈수록 훨씬 잦아진다
    assert len(scene.codes) >= 10 and scene.codes[-1][0] > 3.5      # 해킹 글자가 끝까지 늘어난다
    assert R.stutter(0.3) == 0.3 and R.stutter(4.0) != 4.0          # 심해지면 움직임이 버벅거린다


def test_static_creeps_in_only_at_the_end_of_the_hack():
    assert R.tune(R.HACK - R.TUNE - 0.01) == 0 and R.tune(R.HACK) == 1
    assert R.tune(4.0) < 0.3                                        # 4초까지는 아직 해킹 화면이 주인공


def test_static_is_mid_gray_and_steady():
    tiles = R.static_tiles(W, H, np.random.default_rng(1))
    assert len(tiles) == R.STATIC_TILES and tiles[0].shape == (H // 2, W // 2)
    means = [t.mean() for t in tiles]
    assert all(100 < m < 155 for m in means)                        # 중간 회색 둘레
    assert max(means) - min(means) < 3                              # 장마다 바뀌어도 밝기는 그대로 (번쩍이지 않는다)


def test_target_defaults_to_the_screen_center_at_hud_size():
    sc = R.build(desktop(), (W, H), np.random.default_rng(2))
    assert sc.target == (W / 2, H / 2, float(R.HUD_SIZE))


def test_drop_pixels_keeps_the_timeline_and_events():
    sc = R.build(desktop(), (W, H), np.random.default_rng(3))
    before, tears = sc.duration, len(sc.tears)
    sc.drop_pixels()
    assert sc.duration == before and len(sc.tears) == tears and sc.shot.size <= 3 and sc.static == []


# ---------------------------------------------------------------- 소리
def test_sound_follows_the_scene(scene):
    a = R.sound(scene, np.random.default_rng(1))
    sr = glitch.SOUND_RATE
    assert a.dtype == np.int16 and abs(len(a) / sr - scene.duration) < 0.05
    m = scene.marks()

    def loud(t0, t1):
        return float(np.abs(a[int(t0 * sr):int(t1 * sr)].astype(float)).mean())
    assert loud(3.0, 4.0) > loud(0.0, 1.0) * 2                      # 해킹 소리가 갈수록 커진다
    assert loud(m["hack"] + 0.2, m["static"] - 0.2) > 2000          # TV 지직은 쉭 하고 들린다
    assert loud(m["eyes"], m["form"]) > loud(m["settle"], m["settle"] + 0.5)   # 울림은 작게 시작해 차오른다
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


def test_eyes_rise_faint_then_deepen_before_the_core(V, scene):
    lights = [V.eye_light(k / 50) for k in range(51)]
    assert lights[0] == 0 and lights[-1] == 1 and all(b >= a for a, b in zip(lights, lights[1:]))   # 깜빡이지 않고 차오른다
    assert V.eye_light(0.15) < 0.12                                 # 처음엔 아주 옅다
    m = scene.marks()
    during = V.looks(scene, m["settle"] + 1.2)
    assert 0 < during["eyes"] < 1 and all(v == 0 for v in during["core"].values())   # 눈이 먼저 — 코어는 아직
    early = V.looks(scene, m["eyes"] + 0.3)
    assert early["eyes"] == 1 and 0 < early["core"]["disc"] < 0.5 and early["core"]["hex"] == 0   # 안쪽부터, 옅게
    assert all(v == pytest.approx(1, abs=1e-3) for v in V.looks(scene, m["form"] - 0.001)["core"].values())


def test_ultron_shrinks_in_place_onto_the_hud_and_the_black_lifts(V, scene):
    m = scene.marks()
    tx, ty, ts = scene.target
    hold = V.looks(scene, m["hold"] - 0.1)
    assert hold["black"] == 1 and hold["done"][:2] == (W / 2, H / 2)  # 다 나타나 가운데에 크게
    mid = V.looks(scene, (m["hold"] + m["shrink"]) / 2)
    assert 0 < mid["black"] < 1 and ts < mid["done"][2] < hold["done"][2]   # 걷히는 중 · 줄어드는 중
    end = V.looks(scene, m["shrink"] + 0.001)
    assert end["black"] == 0 and end["done"][:3] == pytest.approx((tx, ty, ts), abs=0.5)   # HUD 엠블럼 자리 · 크기에 딱
    assert V.looks(scene, m["end"] - 0.01)["done"][3] < 0.05        # 실제 HUD 와 겹친 채 옅어진다


def test_frames_render_and_end_on_the_real_screen(V, scene):
    m = scene.marks()
    a = V.Assets(scene, W, H)
    shot = desktop().astype(int)
    first = V.render(scene, 0.05, desktop(), a)
    d_first = np.abs(first.astype(int) - shot).mean()
    assert d_first < 12                                              # 처음엔 거의 그대로 (살짝 번짐)
    late = V.render(scene, 3.6, desktop(), a)
    assert np.abs(late.astype(int) - shot).mean() > d_first * 2     # 갈수록 크게 망가진다
    dark = V.render(scene, m["settle"] + 0.05, desktop(), a)
    assert dark.mean() < 25                                          # 지직이 가라앉아 캄캄
    eyes = V.render(scene, m["eyes"] - 0.05, desktop(), a)
    red = eyes[..., 0].astype(int) - eyes[..., 1]
    ys, xs = np.nonzero(red > 60)
    assert len(ys) > 50 and abs(xs.mean() - W / 2) < W * 0.1 and ys.mean() < H / 2   # 한가운데 위쪽에 붉은 두 눈
    back = V.render(scene, m["end"], desktop(), a)
    assert np.abs(back.astype(int) - shot).mean() < 3                # 끝나면 원래 화면 그대로 (그 자리엔 실제 HUD)


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
            times.append(round(t, 2))
        prev = r
    worst = max((sum(1 for u in times if s <= u < s + 1.0) for s in times), default=0)
    assert worst <= glitch.MAX_CHANGES_PER_SEC, times


def test_view_hands_off_then_lets_go(V):
    from PySide6.QtCore import QRect
    sc = R.build(desktop(), (W, H), np.random.default_rng(9))
    view = V.ReviveView()
    events = []
    view.handoff.connect(lambda: events.append("handoff"))
    view.finished.connect(lambda: events.append("finished"))
    view.play(QRect(0, 0, W, H), sc)
    assert view.playing and sc.shot.size <= 3                       # 그릴 그림은 Qt 쪽에만 (numpy 는 놓아 줌)
    view.grab()                                                      # 한 번 그려 본다 (오류 없이)
    view.stop()                                                      # 중간에 멈춰도 HUD 는 넘겨받는다
    assert events == ["handoff", "finished"] and not view.playing and view._assets is None


# ---------------------------------------------------------------- 울트론 본체 연결
@pytest.fixture
def app(monkeypatch):
    import jarvis.app as app_mod
    J = app_mod.Jarvis

    class App:
        _revive_begin, _revive_done, _revived_line = J._revive_begin, J._revive_done, J._revived_line
        _revive_handoff, _revive_target = J._revive_handoff, J._revive_target
        guardian_status, _revive_test = J.guardian_status, J._revive_test

        def __init__(self):
            self.cfg = {"guardian_show": True, "user_title": "창조자"}
            self.args = types.SimpleNamespace(closed="vision")
            self.shown, self.toasts, self.said, self.events = {}, [], [], []
            self.bridge = types.SimpleNamespace(set=lambda k, v: self.shown.__setitem__(k, v), _compact=True,
                                                toast=types.SimpleNamespace(emit=lambda kind, m: self.toasts.append(m)))
            self._reviving, self._revive_demo = False, False
            self.listener = types.SimpleNamespace(muted=False)
            self.visible = True
            me = self
            self.win = types.SimpleNamespace(isVisible=lambda: me.visible, show=lambda: me.events.append("show"),
                                             setGeometry=lambda r: me.events.append(("geometry", r)))

        def say(self, text, follow_up=True):
            self.said.append(text)

        def _release_fx(self, name):
            pass

        def _unmute(self):
            self.listener.muted = False

        def toggle_visible(self, show=None, force=False):
            self.events.append(("toggle", show, force))

        def _core_point(self):
            return 115.0, 107.0

        def _start_guardian(self):
            self.events.append("start_guardian")

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


def test_preview_plays_even_over_a_fullscreen_app(app, monkeypatch):
    me, mod = app
    monkeypatch.setattr(mod.winutil, "fullscreen_app", lambda: True)
    grabbed = []

    def grab(_):
        grabbed.append(1)
        raise RuntimeError("화면을 찍을 수 없는 시험 환경")
    me.win.screen = lambda: types.SimpleNamespace(grabWindow=grab)
    monkeypatch.setattr(mod.QGuiApplication, "screenAt", lambda pos: None)
    me._revive_begin(demo=True)                                      # 사용자가 시킨 시범은 전체 화면 앱 앞에서도 보여 준다
    assert grabbed == [1]


def test_guardian_status_line(app, monkeypatch):
    me, mod = app
    monkeypatch.setattr(mod.sys, "platform", "win32")
    me.cfg["guardian"] = True
    monkeypatch.setattr(mod.guardian, "running", lambda d: True)
    assert "작동 중" in me.guardian_status()
    monkeypatch.setattr(mod.guardian, "running", lambda d: False)
    assert "띄우는 중" in me.guardian_status()
    me.cfg["guardian"] = False
    assert "꺼짐" in me.guardian_status()


def test_revive_test_kills_itself_only_when_the_guardian_watches(app, monkeypatch):
    me, mod = app
    exits = []
    monkeypatch.setattr(mod.os, "_exit", lambda code: exits.append(code))
    monkeypatch.setattr(mod.logging, "shutdown", lambda: None)
    me.cfg["guardian"] = True
    monkeypatch.setattr(mod.guardian, "running", lambda d: False)
    me._revive_test()                                                # 지켜보는 가디언이 없으면 끄지 않는다 (돌아오지 못하므로)
    assert exits == [] and "start_guardian" in me.events and "시험하지 않겠다" in me.said[-1]
    monkeypatch.setattr(mod.guardian, "running", lambda d: True)
    me._revive_test()
    assert exits == [3]                                              # 정리 없이 바로 꺼진다 — 누가 강제로 끈 것과 같다


def test_demo_line_after_the_preview_and_the_hud_comes_back(app):
    me, mod = app
    me._revive_demo, me._reviving, me.visible = True, True, False
    me._revive_done()
    assert "이렇게 깨어난다" in me.said[0] and not me._reviving
    assert ("toggle", True, True) in me.events                       # 장면을 못 마쳤어도 HUD 는 다시 보인다


def test_hud_target_puts_its_emblem_at_the_screen_center(app):
    from PySide6.QtCore import QRect
    me, mod = app
    screen = types.SimpleNamespace(geometry=lambda: QRect(0, 0, 1920, 1080), availableGeometry=lambda: QRect(0, 0, 1920, 1040))
    (tx, ty, size), rect = me._revive_target(screen)
    assert (tx, ty, size) == (960.0, 540.0, 214.0)                   # 울트론이 나타난 바로 그 자리 · HUD 엠블럼 크기
    assert (rect.x(), rect.y(), rect.width(), rect.height()) == (960 - 115, 540 - 107, *mod.COMPACT)
    me._revive_hud = rect
    me._revive_handoff()
    assert me.events == [("geometry", rect), "show"]                 # 그 자리에 실제 HUD 를 띄운다
    me.bridge._compact = False                                        # 큰 HUD 는 화면 밖으로 나가지 않게 당긴다
    (tx, ty, size), rect = me._revive_target(screen)
    assert rect.bottom() <= 1039 and size == 212.0 and ty == rect.y() + 107


def test_saying_show_me_the_revival_plays_the_preview():
    from jarvis.brain import REVIVE_SHOW
    from jarvis.local_router import normalize
    for text in ("부활 연출 보여 줘", "되살아나는 장면 보여줘", "부활 연출"):
        assert REVIVE_SHOW.fullmatch(normalize(text)), text
    assert not REVIVE_SHOW.fullmatch(normalize("부활절 언제야"))


def test_saying_test_the_revival_runs_the_real_test():
    from jarvis.brain import REVIVE_SHOW, REVIVE_TEST
    from jarvis.local_router import normalize
    for text in ("부활 시험해 줘", "가디언 테스트", "강제 종료 시험해 봐", "부활 테스트 한 번"):
        assert REVIVE_TEST.fullmatch(normalize(text)), text
    for text in ("부활 연출 보여 줘", "시험 공부해야 해", "가디언 꺼"):
        assert not REVIVE_TEST.fullmatch(normalize(text)), text
    assert not REVIVE_SHOW.fullmatch(normalize("부활 시험해 줘"))


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
