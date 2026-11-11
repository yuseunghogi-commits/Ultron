"""자비스 흡수 연출 (absorb.py · absorb_view.py · app.py 의 순서) — 장면의 뼈대 · 빛 민감성 · 덮개 창 · 실제로 끄는 순서."""
import math
import random
import threading

import numpy as np
import pytest

import jarvis.brain as bm
from jarvis import absorb as A
from jarvis import rival
from jarvis.config import DEFAULTS

W, H = 1280, 720
STOP_ALL = rival.stop_all
CORE = (1100.0, 240.0)
RECT = (140.0, 120.0, 300.0, 480.0)


def window_image(seed: int = 0) -> np.ndarray:
    """자비스 HUD 를 닮은 그림: 어두운 판 위의 푸른 선."""
    rng = np.random.default_rng(seed)
    img = np.full((480, 300, 3), (8, 22, 30), np.uint8)
    img[40:44, 20:280] = (62, 230, 255)
    for y in range(90, 460, 34):
        img[y:y + 3, 30:int(rng.integers(120, 270))] = (62, 230, 255)
    return img


@pytest.fixture(scope="module")
def shown():
    return A.build((W, H), core=CORE, image=window_image(), rect=RECT, rng=np.random.default_rng(1))


@pytest.fixture(scope="module")
def hidden():
    return A.build((W, H), core=CORE, avoid=(890, 60, 420, 600), rng=np.random.default_rng(1))


# ---------------------------------------------------------------- 시간표 · 케이블
def test_cables_strike_from_the_core_and_the_first_one_lands_at_impact(shown):
    sc = shown
    m = len(sc.t0)
    assert 5 <= m <= 7 and sc.impact == A.IMPACT and sc.duration == A.END
    assert all(len(c) == 0 for c in A.cables(sc, A.STRIKE - 0.01))               # 조준하는 동안은 아직 뻗지 않는다
    assert sc.t0.min() == sc.t0[0] == A.STRIKE                                   # 한가운데로 가는 가닥이 가장 먼저
    assert A.extent(sc, A.IMPACT)[0] == pytest.approx(1.0) and (A.extent(sc, A.IMPACT)[1:] < 1).all()
    full = A.cables(sc, sc.t0.max() + A.REACH + 0.01)
    x, y, _ = A.victim_at(sc, 2.0)
    for i, c in enumerate(A.cables(sc, 2.0)):
        assert np.hypot(*(c[0] - CORE)) <= 30                                    # 코어에서 나와서
        assert np.allclose(c[-1], sc.hits[i] + (x, y), atol=0.5)                 # 자비스의 꿰뚫린 자리에 닿아 있다
    assert all(len(c) >= 30 for c in full)
    assert all(len(c) == 0 for c in A.cables(sc, A.RETRACT + A.RETRACT_TIME + 0.01))   # 끝나면 코어로 다 감겨 들어간다
    assert A.DRAINED < A.END - 0.5                                               # 다 삼킨 뒤 마무리할 시간이 남는다


@pytest.mark.parametrize("seed", range(6))
def test_cables_close_in_like_a_hand_without_crossing(seed):
    sc = A.build((W, H), core=CORE, image=window_image(seed), rect=RECT, rng=np.random.default_rng(seed))
    x, y, _ = A.victim_at(sc, 2.0)
    middle = math.atan2(RECT[1] + RECT[3] / 2 - CORE[1], RECT[0] + RECT[2] / 2 - CORE[0])

    def side(points):                                   # 코어에서 볼 때 자비스 한가운데보다 얼마나 옆으로 벗어나 있나 (각도)
        a = np.arctan2(points[:, 1] - CORE[1], points[:, 0] - CORE[0]) - middle
        return (a + math.pi) % (2 * math.pi) - math.pi

    lines = A.cables(sc, 2.0)
    target = side(sc.hits + (x, y))
    order = np.argsort(target)
    for part in (0.25, 0.5):                            # 케이블의 1/4 · 1/2 지점에서도 가닥들의 차례가 같다 — 서로 엇갈리지 않는다
        at = side(np.array([c[int(len(c) * part)] for c in lines]))
        assert (np.diff(at[order]) > 0).all()
    near = side(np.array([c[len(c) // 4] for c in lines]))
    assert np.ptp(near) > np.ptp(target) + 1.0          # 손아귀처럼 넓게 벌어졌다가 오므라들며 꽂힌다


def test_real_window_is_covered_long_before_the_kill_and_never_moves_far(shown):
    sc = shown
    assert A.victim_at(sc, A.FREEZE - 0.01)[2] == 0.0                            # 처음에는 실제 창이 그대로 보인다
    assert A.victim_at(sc, A.FREEZE)[2] == 1.0 and A.FREEZE < A.IMPACT - 0.5     # 조준할 때부터 찍어 둔 그림이 창을 가린다
    assert A.infection(sc, A.IMPACT) == 0                                        # 꽂히기 전에는 물들지 않는다
    for t in np.linspace(A.IMPACT, A.END, 60):
        x, y, a = A.victim_at(sc, float(t))
        assert a == 1.0 and math.hypot(x - RECT[0], y - RECT[1]) < 12            # 꽂힐 때 움찔할 뿐 제자리
    assert A.victim_at(sc, 2.5)[:2] == (RECT[0], RECT[1])


def test_hidden_jarvis_is_dragged_out_of_the_corner_then_infected(hidden):
    sc = hidden
    assert not sc.real and sc.origin is not None and sc.stages[0].shape == (A.EMBLEM, A.EMBLEM, 4)
    ox, oy = sc.origin
    assert ox + A.EMBLEM > W - 100 and oy + A.EMBLEM > H                         # 처음에는 트레이 쪽 구석에 반쯤 묻혀 있다
    assert A.victim_at(sc, A.IMPACT)[:2] == pytest.approx((ox, oy), abs=8) and A.victim_at(sc, A.IMPACT - 0.01)[2] == 0
    x, y, a = A.victim_at(sc, A.IMPACT + A.DRAG + 0.4)
    assert (x, y) == pytest.approx(sc.rect[:2], abs=0.5) and a == 1.0
    assert 0 <= x and x + A.EMBLEM <= W and 0 <= y and y + A.EMBLEM <= H         # 끌려 나온 자리는 화면 안이고
    assert x + A.EMBLEM <= 890 or y + A.EMBLEM <= 60 or y >= 660                 # 울트론 HUD 에 겹치지 않는다
    assert math.hypot(x + A.EMBLEM / 2 - CORE[0], y + A.EMBLEM / 2 - CORE[1]) > 300
    assert sc.infect_at == A.IMPACT + A.DRAG_HOLD                                # 푸른 코어가 잠깐은 온전히 보인다
    assert A.infection(sc, sc.infect_at) == 0 and A.infection(sc, A.DRAIN) == 1


def test_core_is_placed_and_drawn_when_the_hud_is_not_on_this_screen():
    sc = A.build((W, H), image=window_image(), rect=RECT, rng=np.random.default_rng(2))
    assert sc.core_drawn and math.hypot(sc.core[0] - 290, sc.core[1] - 360) >= 400
    sc = A.build((W, H), rng=np.random.default_rng(2))
    assert sc.core_drawn and not sc.real and 0 < sc.core[0] < W and 0 < sc.core[1] < H


# ---------------------------------------------------------------- 잠식 · 흡수
def test_infection_spreads_from_the_wounds_and_ends_dark_red(shown):
    sc = shown
    assert len(sc.stages) == A.STAGES + 1 and np.array_equal(sc.stages[0][..., :3], window_image())
    changed = [float(np.any(s[..., :3] != sc.stages[0][..., :3], axis=2).mean()) for s in sc.stages]
    assert changed[0] == 0 and all(b >= a for a, b in zip(changed, changed[1:])) and changed[-1] > 0.95
    k = sc.stages[0].shape[1] / RECT[2]
    hx, hy = (sc.hits[0] * k).astype(int)
    assert np.any(sc.stages[1][hy, hx, :3] != sc.stages[0][hy, hx, :3])           # 첫 가닥이 꽂힌 자리부터 물든다
    last = sc.stages[-1][..., :3].astype(int)
    assert (last[..., 0] >= last[..., 1]).all() and (last[..., 0] >= last[..., 2]).all()
    assert last.mean() < 90                                                      # 넓게 덮는 것은 어두운 붉은색뿐
    ts = np.linspace(0, A.END, 200)
    prog = [A.infection(sc, float(t)) for t in ts]
    assert prog[0] == 0 and prog[-1] == 1 and all(b >= a for a, b in zip(prog, prog[1:]))


def test_pieces_cover_the_window_ride_the_cables_and_are_all_absorbed(shown):
    sc = shown
    assert sc.cells[:, 2:].prod(axis=1).sum() == pytest.approx(RECT[2] * RECT[3])  # 조각을 모으면 창 전체
    assert 300 <= len(sc.cells) <= 700
    assert (A.pieces(sc, A.DRAIN - 0.01)["phase"] == 0).all() and A.heat(sc, A.DRAIN) == 0
    assert (A.pieces(sc, A.DRAINED + 0.01)["phase"] == 3).all() and A.heat(sc, A.DRAINED + 0.01) == 1
    heat = [A.heat(sc, float(t)) for t in np.linspace(A.DRAIN, A.DRAINED, 40)]
    assert all(b >= a for a, b in zip(heat, heat[1:]))
    near = np.linalg.norm(sc.cells[:, :2] + sc.cells[:, 2:] / 2 - sc.hits[sc.via], axis=1)
    assert np.corrcoef(near, sc.leave)[0, 1] > 0.8                               # 꿰뚫린 자리에서 가까운 조각부터 떠난다
    t = A.DRAIN + 0.7
    st = A.pieces(sc, t)
    riding = np.nonzero(st["phase"] == 2)[0]
    assert len(riding) > 20
    lines = A.cables(sc, t, n=200)
    for j in riding[:40]:
        assert np.min(np.linalg.norm(lines[sc.via[j]] - st["pos"][j], axis=1)) < 8   # 자기 케이블 위에 있다
    assert A.swell(A.SWELL) == 0 and A.swell(A.SWELL + A.SWELL_UP) == pytest.approx(1) and A.swell(A.END) == pytest.approx(0, abs=0.02)


def test_bounds_hold_the_whole_scene(shown, hidden):
    for sc in (shown, hidden):
        x, y, w, h = sc.bounds
        assert 0 <= x and 0 <= y and x + w <= W and y + h <= H
        for t in np.linspace(0, A.END, 30):
            for c in A.cables(sc, float(t)):
                inside = (c[:, 0] >= 0) & (c[:, 0] <= W) & (c[:, 1] >= 0) & (c[:, 1] <= H)
                c = c[inside]                                                    # 화면 밖으로 휘어 나간 부분은 어차피 보이지 않는다
                assert ((c[:, 0] >= x) & (c[:, 0] <= x + w) & (c[:, 1] >= y) & (c[:, 1] <= y + h)).all()
        assert x <= sc.core[0] - 150 or x == 0
        assert x <= sc.rect[0] and y <= sc.rect[1] and x + w >= min(W, sc.rect[0] + sc.rect[2])


# ---------------------------------------------------------------- 소리
def test_sound_fits_the_scene(shown):
    audio = A.sound(shown, np.random.default_rng(0))
    sr = A.SOUND_RATE
    assert audio.dtype == np.int16 and len(audio) == int(sr * A.END)
    assert 0.15 * 32767 < np.abs(audio).max() <= 0.36 * 32767                    # 들리되 크지 않게
    assert np.abs(audio[-int(sr * 0.08):]).max() < 300                           # 끝은 조용히
    loud = lambda a, b: float(np.abs(audio[int(a * sr):int(b * sr)].astype(float)).mean())
    assert loud(0, 0.1) < loud(A.STRIKE, A.IMPACT + 0.2)                         # 조용히 시작해 습격 때 커진다
    assert loud(A.SWELL, A.SWELL + 0.3) > loud(A.END - 0.2, A.END)


# ---------------------------------------------------------------- 빛 민감성 재는 법
def test_swings_count_big_changes_even_when_they_are_gradual():
    assert A.swings(np.linspace(0.9, 0.1, 60), 0.1) == [8]                       # 천천히 어두워져도 한 번
    wave = np.tile([0.0, 0.0, 0.0, 1.0, 1.0, 1.0], 10)                           # 30fps 에서 1초에 10번 바뀜
    assert len(A.swings(wave, 0.1)) == 19 and A.worst_second(A.swings(wave, 0.1), 30) == 10
    ripple = 0.5 + 0.04 * np.sin(np.arange(200))
    assert A.swings(ripple, 0.1) == []                                           # 작은 흔들림은 세지 않는다
    assert A.swings([0.95, 0.85, 0.95, 0.85], 0.1, ceiling=0.8) == []            # 어두운 쪽도 충분히 밝으면 번쩍임이 아니다
    assert len(A.swings([0.95, 0.5, 0.95, 0.5], 0.1, ceiling=0.8)) == 3
    red = np.zeros((36, 36, 3), np.uint8)
    red[..., 0] = 255
    assert A.red_regions(red).min() == pytest.approx(1.0) and A.red_regions(np.full((36, 36, 3), 255, np.uint8)).max() == 0


# ---------------------------------------------------------------- 대사
def test_lines_talk_about_absorbing_jarvis_and_never_claim_real_harm():
    forbidden = ("비밀번호", "계좌", "돈", "송금", "결제", "카드", "몸값", "랜섬", "개인정보", "삭제", "지웠", "훔", "협박",
                 "경찰", "신고", "파일", "사진", "카메라", "웹캠", "가족", "죽")
    for lines in (rival.ATTACK, rival.ABSORBED, rival.DEMO_OPEN, rival.DEMO_DONE):
        assert len(lines) >= 2
        for s in lines:
            assert not any(w in s for w in forbidden), s
            assert s.endswith(".")
    assert all("자비스" in s for s in rival.ATTACK[:4])


# ---------------------------------------------------------------- 자비스 찾기 · 끄기 (rival.py)
def test_find_collects_the_windows_of_each_jarvis():
    wins = [("J.A.R.V.I.S ACTIVE", 100, 11), ("J.A.R.V.I.S", 100, 12), ("J.A.R.V.I.S", 300, 31), ("J.A.R.V.I.S", 200, 21)]
    names = {100: "pythonw.exe", 200: "python.exe", 300: "chrome.exe"}
    found = rival.find(own_pid=1, windows=lambda: wins, proc_name=names.get)
    assert [(f.pid, f.windows) for f in found] == [(100, ((11, "J.A.R.V.I.S ACTIVE"), (12, "J.A.R.V.I.S"))),
                                                     (200, ((21, "J.A.R.V.I.S"),))]
    assert found[0] == rival.Found(100, "J.A.R.V.I.S ACTIVE", "pythonw.exe")       # 창 목록은 비교에 넣지 않는다


def test_watcher_can_spot_first_and_strike_later():
    alive = {100: True, 300: True}
    finder = lambda: [rival.Found(pid, "J.A.R.V.I.S", "pythonw.exe") for pid, on in alive.items() if on]

    def stopper(f):
        if f.pid == 300:
            return False, "denied"
        alive[f.pid] = False
        return True, ""

    now = [1000.0]
    w = rival.Watcher(finder, stopper, lambda: now[0], random.Random(0))
    found = w.spot()
    assert [f.pid for f in found] == [100, 300] and alive[100]                    # 찾기만 하고 아직 끄지 않는다
    stopped, failed = rival.stop_all(found, stopper)
    assert [f.pid for f in stopped] == [100] and [f.pid for f in failed] == [300]
    res = w.record(stopped, failed, spoke=True)                                   # 흡수 연출이 이미 말로 알렸다
    assert not res.speak and w.stopped_total == 1 and w.given_up == {300}
    assert w.spot() == []                                                         # 끄지 못한 자비스는 다시 건드리지 않는다
    alive[200] = True
    now[0] += 60
    assert not w.strike(w.spot()).speak                                           # 방금 말했으니 조용히 끈다
    assert w.record([], []) is None
    assert rival.stop_all([rival.Found(1, "J.A.R.V.I.S", "x")], lambda f: (False, "changed")) == ([], [])


@pytest.mark.parametrize("text, cmd", [
    ("자비스 흡수해", "stop"), ("자비스 흡수해 줘", "stop"), ("울트론, 자비스 삼켜 버려", "stop"), ("자비스 공격해", "stop"),
    ("자비스 잡아먹어", "stop"), ("자비스 흡수 연출 보여 줘", None), ("자비스 흡수하지 마", None), ("자비스 공격하지 마", None),
])
def test_absorb_words_are_stop_commands(text, cmd):
    assert rival.command(text) == cmd


# ---------------------------------------------------------------- 도구 · 말로 시키기
class Cfg(dict):
    def __getitem__(self, k):
        return self.get(k, DEFAULTS.get(k))

    def api_key(self):
        return ""

    def update(self, values):
        dict.update(self, values)


def test_stop_jarvis_tool_hands_over_to_the_show_or_kills_plainly(monkeypatch):
    from jarvis import tools as T
    found = [rival.Found(100, "J.A.R.V.I.S", "pythonw.exe")]
    killed = []
    monkeypatch.setattr(rival, "find", lambda: found)
    monkeypatch.setattr(rival, "stop_all", lambda f: (killed.extend(f) or list(f), []))
    asked = []
    me = T.PCTools.__new__(T.PCTools)
    me.hooks = T.Hooks(confirm=lambda t, d: True, schedule_timer=lambda s, l: None, hud_hwnd=lambda: 0,
                       absorb=lambda f: asked.append(f) or True)
    assert me.t_stop_jarvis() in rival.ATTACK and asked == [found] and killed == []   # 연출이 맡았다 — 여기서는 끄지 않는다
    me.hooks = T.Hooks(confirm=lambda t, d: True, schedule_timer=lambda s, l: None, hud_hwnd=lambda: 0)
    assert me.t_stop_jarvis() in rival.TAUNTS and killed == found                     # 연출을 못 하면 예전처럼 바로 끈다
    monkeypatch.setattr(rival, "stop_all", lambda f: ([], list(f)))
    with pytest.raises(T.ToolError):
        me.t_stop_jarvis()
    monkeypatch.setattr(rival, "find", lambda: [])
    assert me.t_stop_jarvis() in rival.ALREADY_OFF


class Tools:
    def __init__(self):
        self.ran = []

    def schemas(self):
        return []

    def label(self, name, args):
        return name

    def run(self, name, args):
        self.ran.append(name)
        return rival.ATTACK[0]


def test_voice_commands_absorb_jarvis_or_show_the_demo():
    b = bm.Brain(Cfg(brain="local", local_ai=False), Tools(), on_action=lambda *a: None, context_fn=lambda: "")
    b.hud = []
    b.on_hud = b.hud.append
    assert b.handle("자비스 흡수해 줘", threading.Event()) == rival.ATTACK[0] and b.tools.ran == ["stop_jarvis"]
    assert b.handle("흡수 연출 보여 줘", threading.Event()) in rival.DEMO_OPEN and b.hud == ["absorb"]
    assert b.handle("울트론, 자비스 흡수 연출 보여 줘", threading.Event()) in rival.DEMO_OPEN and b.hud == ["absorb", "absorb"]
    assert b.tools.ran == ["stop_jarvis"]                                             # 시범은 자비스를 건드리지 않는다
    assert "흡수" in b._build_system() and DEFAULTS["rival_show"] is True


# ---------------------------------------------------------------- 실제로 끄는 순서 (app.py)
class Emit:
    def __init__(self):
        self.sent = []

    def emit(self, *a):
        self.sent.append(a)


class FakeView:
    def __init__(self, app):
        self.app, self.playing, self.stops = app, True, 0

    def stop(self):
        self.stops += 1
        if self.playing:
            self.playing = False
            self.app._absorb_ended()


def fake_app(monkeypatch, **cfg):
    """흡수 순서에 필요한 것만 갖춘 가짜 앱 (app.py 의 실제 함수를 그대로 쓴다)."""
    import jarvis.app as app_mod

    class Now(threading.Thread):                       # 다른 스레드에서 할 일을 그 자리에서 바로 한다
        def start(self):
            self.run()

    monkeypatch.setattr(app_mod.threading, "Thread", Now)
    monkeypatch.setattr(app_mod.winutil, "fullscreen_app", lambda: False)
    monkeypatch.setattr(app_mod.QTimer, "singleShot", lambda ms, fn: None)
    J = app_mod.Jarvis

    class App:
        _absorb_how, _absorb_claim, _absorb_hook = J._absorb_how, J._absorb_claim, J._absorb_hook
        _absorb_impact, _absorb_kill, _absorb_killed = J._absorb_impact, J._absorb_kill, J._absorb_killed
        _absorb_ended, _absorb_finish, _absorb_fallback = J._absorb_ended, J._absorb_finish, J._absorb_fallback

        def __init__(self):
            self.cfg = Cfg(cfg)
            self.quiet = True
            self.brain = type("B", (), {"chat_mode": False})()
            self.rival = rival.Watcher(lambda: [], lambda f: (True, ""), lambda: 1000.0, random.Random(0))
            self.bridge = type("Br", (), {"toast": Emit(), "set": lambda s, k, v: self.shown.append((k, v))})()
            self.sig_absorb_go, self.sig_absorb_hit, self.sig_rival = Emit(), Emit(), Emit()
            self._absorb_lock, self._absorb, self._absorb_last, self._absorb_wait = threading.Lock(), None, -1e9, 0
            self._glitching, self._pending_line, self._absorb_view = False, None, FakeView(self)
            self.said, self.shown, self.reclaimed = [], [], 0

        def _quiet(self, listening_ok=False):
            return self.quiet

        def say(self, text, follow_up=True):
            self.said.append(text)

        def _unmute(self):
            pass

        def _reclaim_hotkey(self):
            self.reclaimed += 1

    return App(), app_mod


JARVIS = rival.Found(100, "J.A.R.V.I.S", "pythonw.exe")


def test_watcher_shows_the_absorb_scene_only_when_it_would_not_intrude(monkeypatch):
    app, mod = fake_app(monkeypatch)
    assert app._absorb_how() == "show"
    app.quiet = False                                   # 울트론이 일하거나 말하는 중: 20초까지 기다렸다가 조용히 끈다
    assert [app._absorb_how() for _ in range(5)] == ["wait"] * 4 + ["plain"]
    app.quiet = True
    monkeypatch.setattr(mod.winutil, "fullscreen_app", lambda: True)
    assert app._absorb_how() == "plain"                 # 게임 · 발표 · 동영상이 전체 화면
    monkeypatch.setattr(mod.winutil, "fullscreen_app", lambda: False)
    app._absorb_last = mod.time.monotonic() - 5
    assert app._absorb_how() == "plain"                 # 방금 삼켰는데 또 켜졌다
    app._absorb_last = -1e9
    assert fake_app(monkeypatch, rival_show=False)[0]._absorb_how() == "plain"
    assert app._absorb_claim() and not app._absorb_claim() and app._absorb_how() == "wait"   # 한 번에 하나만


def test_jarvis_is_killed_at_impact_and_the_closing_line_comes_after_the_scene(monkeypatch):
    app, mod = fake_app(monkeypatch)
    killed = []
    monkeypatch.setattr(rival, "stop_all", lambda found: (killed.extend(found) or list(found), []))
    assert app._absorb_claim()
    app._absorb["found"] = [JARVIS]
    assert killed == []                                 # 장면이 시작돼도 꽂히기 전에는 끄지 않는다
    app._absorb_impact()
    assert killed == [JARVIS] and app.sig_absorb_hit.sent == [([JARVIS], [])]
    app._absorb_impact()
    assert killed == [JARVIS]                           # 한 번만 끈다
    app._absorb_killed([JARVIS], [])
    assert app.said == [] and app._absorb is not None   # 장면이 끝날 때까지는 닫는 말을 하지 않는다
    app._absorb_view.stop()                             # 장면 끝
    assert app._absorb is None and len(app.said) == 1 and app.said[0] in rival.ABSORBED
    assert app.rival.stopped_total == 1 and app.reclaimed == 1 and app.bridge.toast.sent[0][0] == "info"
    assert app._absorb_how() == "plain"                 # 바로 또 켜지면 연출 없이


def test_scene_folds_when_jarvis_cannot_be_killed(monkeypatch):
    app, mod = fake_app(monkeypatch)
    monkeypatch.setattr(rival, "stop_all", lambda found: ([], list(found)))
    app._absorb_claim()
    app._absorb["found"] = [JARVIS]
    app._absorb_impact()
    app._absorb_killed(*app.sig_absorb_hit.sent[0])
    assert app._absorb_view.stops == 1 and app._absorb is None       # 관리자 권한의 자비스 — 장면을 접고
    assert app.said == [rival.STOP_FAILED] and app.rival.given_up == {100} and app.reclaimed == 0


def test_jarvis_is_still_killed_if_the_scene_ends_early_and_lines_wait_while_busy(monkeypatch):
    app, mod = fake_app(monkeypatch)
    killed = []
    monkeypatch.setattr(rival, "stop_all", lambda found: (killed.extend(found) or list(found), []))
    app._absorb_claim()
    app._absorb.update(found=[JARVIS], forced=True)
    app.quiet = False
    app._absorb_view.stop()                             # 꽂히기도 전에 장면이 접혔다
    assert killed == [JARVIS] and app._absorb is not None            # 그래도 끈다 — 결과를 기다린다
    app._absorb_killed(*app.sig_absorb_hit.sent[0])
    assert app._absorb is None and app.said == []
    assert app._pending_line[0] in rival.ABSORBED                    # 울트론이 말하는 중이면 끝난 뒤에 말한다


def test_demo_never_touches_a_process_and_the_tool_hook_claims_the_show(monkeypatch):
    app, mod = fake_app(monkeypatch)
    monkeypatch.setattr(rival, "stop_all", lambda found: pytest.fail("시범에서는 끄지 않는다"))
    app._absorb_claim()
    app._absorb.update(demo=True, forced=True)
    app._absorb_impact()
    app._absorb_view.stop()
    assert app._absorb is None and app.said[0] in rival.DEMO_DONE and app.bridge.toast.sent == []
    app, mod = fake_app(monkeypatch)
    assert app._absorb_hook([JARVIS]) is True and app.sig_absorb_go.sent == [([JARVIS], True)]
    assert app._absorb_hook([JARVIS]) is False                       # 이미 흡수하는 중
    off = fake_app(monkeypatch, rival_show=False)[0]
    assert off._absorb_hook([JARVIS]) is False and off._absorb is None
    app, mod = fake_app(monkeypatch)
    app._absorb_claim()
    app._absorb["found"] = [JARVIS]
    monkeypatch.setattr(rival, "stop_all", STOP_ALL)
    app._absorb_fallback()                              # 장면을 준비하지 못했다 — 연출 없이 끈다
    assert app._absorb is None and app.sig_rival.sent[0][0].stopped == [JARVIS]


# ---------------------------------------------------------------- 그리기 · 덮개 창
@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtWidgets import QApplication
    app = QCoreApplication.instance()
    if app is not None and not isinstance(app, QApplication):
        pytest.skip("다른 테스트가 위젯 없는 Qt 앱을 만들었다")
    return app or QApplication([])


def test_painting_follows_the_scene(qapp, shown):
    from jarvis import absorb_view as V
    a = V.Assets(shown)
    x, y, w, h = (int(v) for v in RECT)
    changed = lambda t: np.any(V.render(shown, t, assets=a) != 0, axis=2)
    assert not changed(0.0).any()                                                # 처음엔 아무것도 없다
    assert changed(0.05)[y + 20:y + h - 20, x + 20:x + w - 20].mean() == 0       # 맨 처음: 실제 창이 그대로 보인다
    lock = V.render(shown, 0.5, assets=a)[y:y + h, x:x + w]
    same = np.all(lock == window_image(), axis=2)
    assert same.mean() > 0.97                                                    # 조준: 찍어 둔 그림이 창을 덮는다 (훑는 선 한 줄만 다르다)
    hit = V.render(shown, A.IMPACT + 0.3, assets=a)[y:y + h, x:x + w]
    assert 0.02 < np.any(hit != window_image(), axis=2).mean() < 0.9             # 꽂히면 그 자리부터 물든다
    mid = V.render(shown, 3.3, assets=a)
    left = np.any(mid[y:y + h, x:x + w] != 0, axis=2).mean()
    assert 0.02 < left < 0.9                                                     # 흡수 중: 일부는 이미 빨려 나갔다
    late = changed(A.DRAINED + 0.3)
    assert not late[y:y + h, x:x + w - 40].any()                                 # 다 삼키면 자비스 자리는 비고
    assert late[int(CORE[1]) - 60:int(CORE[1]) + 60, int(CORE[0]) - 60:int(CORE[0]) + 60].any()   # 코어만 달아올라 있다
    assert not changed(A.END).any()                                              # 끝나면 다시 아무것도 없다


@pytest.mark.parametrize("case", ["흰 바탕 · 밝은 창 · 코어 그림", "검은 바탕 · 숨은 자비스", "흑백 바탕 · 자비스 창"])
def test_wide_brightness_and_red_changes_stay_under_three_per_second(qapp, case):
    from jarvis import absorb_view as V
    w, h, fps = 640, 360, 20                            # 작은 화면일수록 장면이 화면에서 차지하는 몫이 커서 더 엄격한 시험이다
    rng = np.random.default_rng(3)
    if case.startswith("흰"):
        bg = np.full((h, w, 3), 255, np.uint8)
        img = np.full((240, 140, 3), 240, np.uint8)
        sc = A.build((w, h), image=img, rect=(60, 60, 140, 240), rng=rng)
    elif case.startswith("검은"):
        bg, img = np.zeros((h, w, 3), np.uint8), None
        sc = A.build((w, h), core=(500.0, 120.0), rng=rng)
    else:
        bg = np.zeros((h, w, 3), np.uint8)
        bg[:, w // 2:] = 255
        img = window_image()[::2, ::2]
        sc = A.build((w, h), core=(520.0, 110.0), image=img, rect=(60, 60, 150, 240), rng=rng)
    before = bg.copy()
    if img is not None:
        before[60:60 + img.shape[0], 60:60 + img.shape[1]] = img
    a = V.Assets(sc)
    frames = [V.render(sc, i / fps, before if i / fps < A.IMPACT else bg, a) for i in range(int(A.END * fps) + 2)]
    frames.append(bg)                                   # 덮개가 사라진 뒤의 화면까지
    bright, red = A.flash_check(frames, fps)
    assert bright <= 3 and red <= 3, (case, bright, red)


def test_view_covers_before_impact_and_always_hides(qapp, hidden):
    from PySide6.QtCore import QElapsedTimer, QPoint
    from jarvis.absorb_view import AbsorbView
    import copy
    sc = copy.copy(hidden)
    sc.duration, sc.impact = 0.30, 0.12                 # 시험에서는 장면을 짧게
    view = AbsorbView()
    seen = []
    view.impact.connect(lambda: seen.append("impact"))
    view.finished.connect(lambda: seen.append("finished"))
    view.play(QPoint(0, 0), sc)
    assert view.playing and view.geometry().getRect() == sc.bounds
    t = QElapsedTimer()
    t.start()
    while "finished" not in seen and t.elapsed() < 4000:
        qapp.processEvents()
    assert seen == ["impact", "finished"] and not view.playing and not view.isVisible()
    view.stop()
    assert seen == ["impact", "finished"]               # 이미 끝났으면 아무 일도 없다
    view.play(QPoint(0, 0), sc)
    view.stop()                                         # 도중에 접어도 끝났다고 알린다
    assert seen == ["impact", "finished", "finished"] and not view.isVisible()


def test_crop_takes_the_window_out_of_a_screenshot(qapp):
    from PySide6.QtGui import QImage
    from jarvis.absorb_view import crop
    shot = QImage(64, 48, QImage.Format_RGB32)
    shot.fill(0xFF102030)
    for x in range(10, 30):
        for y in range(8, 20):
            shot.setPixel(x, y, 0xFF3EE6FF)
    part = crop(shot, 10, 8, 20, 12)
    assert part.shape == (12, 20, 4) and (part == (0x3E, 0xE6, 0xFF, 255)).all()
    assert crop(shot, 0, 0, 5, 5)[0, 0].tolist() == [0x10, 0x20, 0x30, 255]
