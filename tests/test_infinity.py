"""인피니티 울트론 (infinity.py) · 그 부활 연출 (revive.py · revive_view.py) · 스톤 연출 (stones.py · stones_view.py) · 본체 연결.

지켜야 하는 것:
  · 되살아날 때 눈이 먼저, 그다음 스톤 여섯이 하나씩 천천히 (눈 + 스톤 ≈ 10초), 그 뒤에 바깥 링 · 가시 · 이름이 나타난다.
  · 다 나타난 인피니티 울트론이 그 자리에서 HUD 크기로 줄어들고, HUD 도 인피니티 울트론으로 켜진다.
  · 인피니티 울트론일 때 자비스는 흡수 대신 파워 스톤으로 가루가 되고(끄는 순서는 흡수 연출과 같다),
    강제로 꺼졌다가 곧바로 되살아나면 타임 스톤 장면이 나온다 — 싸우는 중에는 20초에 한 번만.
  · 이 장면들은 일부러 과격하다 (사용자가 원했다 — 보는 사람 가운데 빛에 민감한 사람이 없다): 화면이 번쩍이고 흔들리고 번개가 친다.
    다른 연출이 지키는 '1초에 3번 이하' 규칙은 여기서는 지키지 않는다. 대신 설정에서 끄면 하나도 나오지 않아야 한다.
"""
import os
import random
import threading
import types

import numpy as np
import pytest

from jarvis import absorb, glitch, revive as R, rival, stones as S
from jarvis.config import DEFAULTS

W, H = 640, 360
BIG = (1280, 720)
CORE = (1100.0, 150.0)
RECT = (300.0, 300.0, 260.0, 300.0)


def desktop(bright: bool = True, size=(W, H)) -> np.ndarray:
    w, h = size
    img = np.zeros((h, w, 3), np.uint8)
    img[:] = (36, 74, 128) if bright else (14, 14, 18)
    if bright:
        img[h // 12:h * 5 // 6, w // 10:w * 7 // 10] = 250
    img[-20:] = (28, 30, 36)
    return img


def window_image() -> np.ndarray:
    """자비스 HUD 를 닮은 그림: 어두운 판 위의 푸른 선."""
    img = np.full((300, 260, 3), (8, 22, 30), np.uint8)
    img[30:34, 20:240] = (62, 230, 255)
    for y in range(70, 280, 30):
        img[y:y + 3, 30:30 + (y * 7) % 190 + 20] = (62, 230, 255)
    return img


@pytest.fixture(scope="module")
def qt():
    pytest.importorskip("PySide6.QtWidgets")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def scene():
    return R.build(desktop(), (W, H), np.random.default_rng(5), target=(500.0, 180.0, 107.0), infinity=True)


# ---------------------------------------------------------------- 부활 연출의 시간표
def test_eyes_and_stones_take_about_ten_seconds_and_the_whole_rise_is_long(scene):
    m = scene.marks()
    assert list(m) == ["hack", "static", "settle", "eyes", "inner", "stones", "form", "hold", "shrink", "end"]
    assert 9.5 <= R.I_EYES + R.I_STONES <= 11.5                      # 눈 + 스톤 ≈ 10초
    assert R.I_STONES / 6 >= 1.0                                     # 스톤 하나에 1초 넘게 (하나씩 천천히)
    classic = R.build(desktop(), (W, H), np.random.default_rng(5)).marks()
    assert (m["form"] - m["settle"]) >= 2.5 * (classic["form"] - classic["settle"])   # 나타나는 시간이 훨씬 길다
    assert m["hack"] == classic["hack"] and m["static"] == classic["static"]          # 해킹 · 지직은 그대로
    assert [R.phase(scene, t)[0] for t in (m["settle"] + 0.1, m["eyes"] + 0.1, m["inner"] + 0.1, m["stones"] + 0.1,
                                            m["form"] + 0.1, m["hold"] + 0.1, m["shrink"] + 0.1, m["end"] + 1)] == \
        ["eyes", "inner", "stones", "outer", "hold", "shrink", "handoff", "end"]


def test_stones_arrive_one_at_a_time_in_order(qt, scene):
    from jarvis import infinity
    seen = [infinity.stones_in(k / 100) for k in range(101)]
    assert seen[0] == [0.0] * 6 and seen[-1] == [1.0] * 6
    for i in range(5):                                               # 앞 스톤이 자리 잡은 뒤에야 다음 스톤이 온다
        assert all(row[i + 1] == 0 for row in seen if row[i] < 1.0)
    firsts = [next(k for k, row in enumerate(seen) if row[i] > 0) for i in range(6)]
    assert firsts == sorted(firsts) and len(set(firsts)) == 6
    times = R.stone_times(scene)
    m = scene.marks()
    assert len(times) == 6 and times == sorted(times) and m["inner"] < times[0] and times[-1] < m["stones"]
    assert all(b - a == pytest.approx(R.I_STONES / 6) for a, b in zip(times, times[1:]))
    assert R.stone_times(R.build(desktop(), (W, H), np.random.default_rng(5))) == []   # 보통 장면에는 스톤이 없다


def test_parts_come_in_order_eyes_then_core_then_stones_then_the_rest(qt):
    from jarvis import revive_view as V
    eyes = V.infinity_parts("eyes", 0.6)
    assert 0 < eyes["eyes"] < 1 and eyes["disc"] == eyes["ring"] == eyes["word"] == 0 and eyes["stones"] == [0.0] * 6
    inner = V.infinity_parts("inner", 1.0)
    assert inner["eyes"] == inner["disc"] == inner["ring"] == inner["band"] == 1 and inner["stones"] == [0.0] * 6
    mid = V.infinity_parts("stones", 0.5)
    assert mid["stones"][:3] == [1.0] * 3 and mid["stones"][4:] == [0.0] * 2 and mid["chain"] == mid["spikes"] == 0
    outer = V.infinity_parts("outer", 0.5)
    assert outer["stones"] == [1.0] * 6 and outer["ticks"] == 1 and 0 < outer["hex"] < 1 and outer["word"] == 0
    done = V.infinity_parts("hold", 0.3)
    assert all(v == 1 for k, v in done.items() if k != "stones") and done["stones"] == [1.0] * 6
    glows = [V.infinity_parts(n, k)["glow"] for n in ("eyes", "inner", "stones", "outer") for k in (0.0, 0.5, 1.0)]
    assert all(b >= a for a, b in zip(glows, glows[1:])) and glows[0] == 0 and glows[-1] == 1   # 후광은 조금씩만 짙어진다


def test_sound_rings_a_higher_bell_for_each_stone(scene):
    snd = R.sound(scene, np.random.default_rng(2)).astype(np.float32)
    sr = glitch.SOUND_RATE
    assert abs(len(snd) / sr - scene.duration) < 0.05 and np.abs(snd).max() <= 32767
    assert list(R.STONE_NOTES) == sorted(R.STONE_NOTES) and len(set(R.STONE_NOTES)) == 6
    for at, note in zip(R.stone_times(scene), R.STONE_NOTES):       # 스톤이 박힌 직후 그 음이 뚜렷하다
        cut = snd[int(at * sr):int((at + 0.4) * sr)]
        spec = np.abs(np.fft.rfft(cut * np.hanning(len(cut))))
        freq = np.fft.rfftfreq(len(cut), 1 / sr)
        peak = freq[(freq > 300) & (freq < 900)][np.argmax(spec[(freq > 300) & (freq < 900)])]
        assert abs(peak - note) < 12, (at, note, peak)


# ---------------------------------------------------------------- 그리기 (Qt)
def test_infinity_core_is_red_and_steel_with_six_coloured_stones_and_no_gold(qt):
    from PySide6.QtGui import QColor, QImage, QPainter
    from jarvis import infinity

    def shot(cv=None, eye_open=1.0):
        img = QImage(520, 520, QImage.Format_RGB888)
        img.fill(QColor(0, 0, 0))
        p = QPainter(img)
        p.translate(260, 260)
        p.scale(520 / infinity.BOX, 520 / infinity.BOX)
        infinity.paint(p, 1.3, cv=cv, eye_open=eye_open)
        p.end()
        raw = np.frombuffer(img.constBits(), np.uint8, count=img.sizeInBytes())
        return raw.reshape(520, img.bytesPerLine())[:, :520 * 3].reshape(520, 520, 3).astype(int)

    full = shot()
    r, g, b = full[..., 0], full[..., 1], full[..., 2]
    lit = full.max(axis=2) > 60
    assert lit.mean() > 0.08
    assert (r[lit] >= g[lit]).mean() > 0.85                          # 붉은색이 바탕이다
    gold = lit & (r > 200) & (g > 150) & (g < 215) & (b < 110)       # 금빛(노랑 스톤 한 알 말고는 없어야 한다)
    assert gold.mean() < 0.004
    for col in infinity.GEMS:                                         # 여섯 스톤의 색이 저마다 보인다
        near = (abs(r - col.red()) < 40) & (abs(g - col.green()) < 40) & (abs(b - col.blue()) < 40)
        assert near.sum() > 20, col.name()
    assert infinity.REACH > 220 and infinity.BOX >= 2 * infinity.REACH      # 가시는 440 상자 밖으로 나가고, BOX 안에는 다 든다
    edge = np.concatenate([full[0], full[-1], full[:, 0], full[:, -1]])
    assert edge.max() < 40                                            # BOX 가장자리에는 아무것도 닿지 않는다
    none = {k: 0.0 for k in infinity.parts(1.0)} | {"stones": [0.0] * 6}
    assert shot(none).max() == 0
    one = shot(none | {"stones": [1.0, 0, 0, 0, 0, 0]})              # 스톤 하나만
    assert one.max() > 150 and (one.max(axis=2) > 60).sum() < (lit.sum() * 0.2)
    wide, narrow = shot(none | {"eyes": 1.0}), shot(none | {"eyes": 1.0}, eye_open=0.4)
    assert (narrow.max(axis=2) > 200).sum() < (wide.max(axis=2) > 200).sum() * 0.7   # 눈을 가늘게 뜬다


def test_scene_shows_eyes_first_then_stones_one_by_one_then_lands_on_the_hud(qt, scene):
    from jarvis import infinity, revive_view as V
    a = V.Assets(scene, W, H)
    assert a.done is None                                             # 멈춘 그림 한 장으로 바꾸지 않는다 (끝까지 살아 움직인다)
    m = scene.marks()
    bg = desktop()

    def frame(t):
        return V.render(scene, t, bg, a).astype(int)

    def bright(f):
        return int((f.max(axis=2) > 90).sum())

    eyes = frame(m["eyes"] - 0.05)
    lit = np.argwhere(eyes.max(axis=2) > 90)
    assert len(lit) and abs(lit[:, 1].mean() - W / 2) < 6 and lit[:, 0].mean() < H / 2        # 눈만 (가운데 조금 위)
    assert bright(eyes) < bright(frame(m["inner"] - 0.05)) * 0.3
    counts = []                                                       # 스톤 색 가운데 몇 가지가 화면에 있는가
    for i in range(7):
        f = frame(m["inner"] + R.I_STONES * i / 6 + (0.0 if i < 6 else -0.01))
        seen = 0
        for col in infinity.GEMS:
            near = (abs(f[..., 0] - col.red()) < 45) & (abs(f[..., 1] - col.green()) < 45) & (abs(f[..., 2] - col.blue()) < 45)
            seen += int(near.sum() > 12)
        counts.append(seen)
    assert counts[0] <= 1 and counts[-1] == 6 and all(b >= a for a, b in zip(counts, counts[1:]))   # 하나씩 는다 (빨강은 처음부터 있다)
    look = V.looks(scene, m["hold"] - 0.1)
    assert look["black"] == 1 and look["inf"]["at"][:2] == (W / 2, H / 2) and look["inf"]["at"][3] == 1
    tx, ty, ts = scene.target
    end = V.looks(scene, m["shrink"] - 1e-3)["inf"]["at"]
    assert end[0] == pytest.approx(tx, abs=0.5) and end[1] == pytest.approx(ty, abs=0.5)
    assert end[2] == pytest.approx(ts / infinity.BOX, rel=0.01)      # HUD 엠블럼 자리에 BOX 가 딱 맞는 크기로
    assert V.looks(scene, m["shrink"] - 1e-3)["black"] < 0.01        # 검은 바탕은 다 걷혔다
    back = frame(m["end"] + 0.5)
    assert np.abs(back - bg).mean() < 3                               # 끝나면 원래 화면 그대로 (그 자리엔 실제 HUD)


def test_each_stone_lands_with_a_flash_of_its_colour_lightning_and_a_jolt(qt, scene):
    from jarvis import revive_view as V
    m = scene.marks()
    quiet = m["inner"] + 0.05                                        # 스톤이 오기 전: 조용하다
    assert R.burst(scene, quiet)[0] == 0 and R.jolt(scene, quiet) == (0.0, 0.0) and R.strikes(scene, quiet) == []
    for i, at in enumerate(R.stone_times(scene)):
        a, tint = R.burst(scene, at + 0.01)
        assert a > 0.4                                                # 박히는 순간 화면이 번쩍인다
        c = R.STONE_RGB[i]
        assert tint.index(max(tint)) == c.index(max(c))              # 그 스톤의 색으로
        assert R.burst(scene, at + 0.6)[0] < 0.01                     # 금방 가라앉는다 (다음 스톤 전에)
        assert R.jolt(scene, at + 0.02) != (0.0, 0.0) and R.strikes(scene, at + 0.05)[0][0] == i
    assert R.burst(scene, m["form"] + 0.01)[0] > 0.8                 # 다 나타나는 순간이 가장 세다
    assert R.strikes(scene, m["form"] + 0.1)[-1][0] == -1
    assert max(abs(v) for v in R.jolt(scene, m["form"] + 0.02)) > max(abs(v) for v in R.jolt(scene, R.stone_times(scene)[0] + 0.02))
    assert all(R.burst(scene, m["form"] + gap + 0.005)[0] > 0.25 for gap in R.AFTERSHOCKS)   # 몇 번 더 깜빡인다
    assert R.burst(scene, m["hold"])[0] == 0 and R.strikes(scene, m["hold"]) == []           # 줄어들기 전에는 다 가라앉는다
    classic = R.build(desktop(), (W, H), np.random.default_rng(5))
    assert all(R.burst(classic, t / 4)[0] == 0 and R.strikes(classic, t / 4) == [] for t in range(80))   # 보통 장면에는 없다
    a = V.Assets(scene, W, H)
    bg = desktop(False)
    at = R.stone_times(scene)[4]                                      # 초록 스톤
    lit, dark = V.render(scene, at + 0.02, bg, a).astype(int), V.render(scene, at - 0.3, bg, a).astype(int)
    corner = (slice(0, 40), slice(0, 60))                             # 코어에서 먼 구석까지 번쩍인다
    assert lit[corner].mean() > dark[corner].mean() + 40 and lit[corner][..., 1].mean() > lit[corner][..., 0].mean()
    assert V.bolt((0, 0), (100, 0), 7) == V.bolt((0, 0), (100, 0), 7) and V.bolt((0, 0), (100, 0), 7) != V.bolt((0, 0), (100, 0), 8)
    pts = V.bolt((0.0, 0.0), (100.0, 0.0), 3)
    assert len(pts) == 33 and (pts[0].x(), pts[0].y()) == (0, 0) and (pts[-1].x(), pts[-1].y()) == (100, 0)
    assert max(abs(q.y()) for q in pts) > 3                           # 곧은 줄이 아니라 꺾인 번개


def test_hud_emblem_follows_the_state():
    pytest.importorskip("PySide6.QtQuick")
    from jarvis import infinity_item as I
    assert I.speed("thinking") > I.speed("listening") > I.speed("standby") == 1.0 > I.speed("offline")
    assert I.eye("listening") > I.eye("standby") == 1.0 > I.eye("thinking") > I.eye("offline")
    x = 1.0
    for _ in range(60):
        x = I.follow(x, 0.6, 1 / 30)
    assert x == pytest.approx(0.6, abs=0.01) and I.follow(1.0, 0.6, 0.0) == 1.0 and I.follow(1.0, 0.6, 99) == 0.6


# ---------------------------------------------------------------- 파워 스톤
@pytest.fixture(scope="module")
def power():
    return S.build_power(BIG, core=CORE, image=window_image(), rect=RECT, rng=np.random.default_rng(1))


def test_power_scene_charges_fires_then_crumbles_from_the_hit(power):
    sc = power
    assert sc.kind == "power" and sc.real and not sc.core_drawn and sc.bounds == (0, 0, *BIG)
    assert S.FREEZE < sc.impact == S.KILL < 0.3 and S.IMPACT > S.CHARGE > 0.8 and sc.duration > S.IMPACT + S.CRUMBLE
    # (실제 자비스는 그림이 창을 가리자마자 끈다 — 힘을 모으는 동안 울트론이 먼저 꺼지지 않게. 줄기는 그 뒤에 닿는다)
    assert S.charge(0) == 0 and S.charge(S.CHARGE) == 1 and S.charge(sc.duration) < 0.5
    assert S.beam(sc, S.CHARGE - 0.01) == (0.0, 0.0)                 # 다 모이기 전에는 쏘지 않는다
    assert S.beam(sc, S.IMPACT)[0] == 1 and S.beam(sc, S.IMPACT + S.CRUMBLE)[1] == 0
    assert S.ring(S.IMPACT - 0.01) < 0 <= S.ring(S.IMPACT + 0.1) < 1
    x, y, w, h = sc.rect
    assert x < sc.hit[0] < x + w and y < sc.hit[1] < y + h           # 줄기는 자비스 그림 안에 꽂힌다
    assert sc.born.min() >= S.IMPACT                                  # 닿기 전에는 한 알도 무너지지 않는다
    assert sc.born.max() <= S.IMPACT + S.CRUMBLE + 0.1
    gy, gx = np.mgrid[0:sc.born.shape[0], 0:sc.born.shape[1]]
    far = np.hypot(x + (gx + 0.5) * sc.cell - sc.hit[0], y + (gy + 0.5) * sc.cell - sc.hit[1])
    assert np.corrcoef(far.ravel(), sc.born.ravel())[0, 1] > 0.8     # 맞은 자리에서 가까운 곳부터 무너진다
    assert sc.born.size <= S.MAX_GRAINS


def test_window_is_covered_before_the_hit_and_fully_gone_at_the_end(power):
    sc = power
    assert S.intact(sc, S.FREEZE - 0.01) is None                      # 그전에는 실제 창이 그대로 보인다
    before = S.intact(sc, S.IMPACT - 0.5)
    assert before is not None and (before[..., 3] == 255).all()       # 꺼지는 순간에는 찍어 둔 그림이 창을 다 가리고 있다
    assert np.array_equal(before[..., :3], sc.image[:before.shape[0], :before.shape[1], :3])
    mid = S.intact(sc, S.IMPACT + S.CRUMBLE * 0.5)
    assert 0.1 < (mid[..., 3] == 0).mean() < 0.9 and 0.1 < S.gone(sc, S.IMPACT + S.CRUMBLE * 0.5) < 0.9
    assert S.intact(sc, S.IMPACT + S.CRUMBLE + 0.2) is None and S.gone(sc, sc.duration) == 1
    pos, col = S.dust(sc, S.IMPACT + S.CRUMBLE * 0.5)
    assert len(pos) > 500 and col[:, 3].max() > 100
    assert len(S.dust(sc, S.IMPACT - 0.1)[0]) == 0 and len(S.dust(sc, sc.duration + 0.01)[0]) == 0   # 끝에는 한 알도 남지 않는다
    late = S.dust(sc, S.IMPACT + S.CRUMBLE)[0]
    away = (late[:, 0] - (sc.rect[0] + sc.rect[2] / 2)) * (sc.rect[0] - CORE[0])
    assert (away > 0).mean() > 0.6                                    # 가루는 울트론 반대쪽으로 밀려 날아간다


def test_hidden_jarvis_is_drawn_and_dragged_out_of_the_corner():
    sc = S.build_power(BIG, core=CORE, avoid=(980, 20, 240, 360), rng=np.random.default_rng(3))
    assert not sc.real and sc.origin is not None and sc.image.shape[:2] == (S.EMBLEM, S.EMBLEM)
    dx0, dy0, a0 = S.offset(sc, 0.0)
    assert (sc.rect[0] + dx0, sc.rect[1] + dy0) == pytest.approx(sc.origin) and a0 == 0
    assert S.offset(sc, S.DRAG) == (0.0, 0.0, 1.0) and S.DRAG < S.CHARGE          # 쏘기 전에 다 끌려 나와 있다
    assert S.intact(sc, 0.05) is not None                             # 가릴 실제 창이 없으니 처음부터 그린다
    lone = S.build_power(BIG, image=window_image(), rect=RECT, rng=np.random.default_rng(3))
    assert lone.core_drawn and np.hypot(lone.core[0] - (RECT[0] + 130), lone.core[1] - (RECT[1] + 150)) > 300


def test_power_scene_draws_a_violet_beam_flashes_and_shakes(qt, power):
    from jarvis import stones_view as V
    sc = power
    a = V.Assets(sc)
    bg = desktop(False, BIG)
    f = V.render(sc, S.IMPACT + 0.05, bg, a).astype(int)
    mx, my = int((CORE[0] + sc.hit[0]) / 2), int((CORE[1] + sc.hit[1]) / 2)
    patch = f[my - 6:my + 6, mx - 6:mx + 6]
    assert patch.max() > 200                                          # 코어와 자비스 사이에 줄기가 지나간다
    glow = f[int(CORE[1]) - 40:int(CORE[1]) + 40, int(CORE[0]) - 40:int(CORE[0]) + 40].mean(axis=(0, 1))
    assert glow[2] > glow[1] and glow[0] > glow[1]                    # 코어에 모인 힘은 보랏빛 (빨강 · 파랑이 초록보다 세다)
    assert S.flash(sc, 0.2)[0] == 0 and S.flash(sc, S.IMPACT + 0.005)[0] > 0.7     # 꽂히는 순간 화면이 번쩍인다
    tint = S.flash(sc, S.IMPACT + 0.005)[1]
    assert tint[2] > tint[1] and tint[0] > tint[1]                    # 보랏빛으로
    assert all(S.flash(sc, S.IMPACT + gap + 0.004)[0] > 0.12 for gap in S.QUAKES)   # 가루가 되는 동안 몇 번 더
    assert max(abs(v) for i in range(6) for v in S.shake(sc, S.IMPACT + i / 50)) > 8 and S.shake(sc, sc.duration) == (0.0, 0.0)
    assert S.sparks(sc, 0.0) == 0 and S.sparks(sc, S.CHARGE) == 1 and S.sparks(sc, sc.duration) == 0
    far = (slice(600, 700), slice(0, 100))                            # 코어 · 자비스에서 먼 구석
    assert f[far].mean() > bg[far].astype(int).mean() + 60
    blinks = [S.flash(sc, S.IMPACT + 0.25 + t / 400)[0] for t in range(180)]     # 꽂힌 직후 0.45초
    ons = sum(1 for x, y in zip(blinks, blinks[1:]) if y > x + 0.03)
    assert ons >= 5                                                   # 일부러 과격하다 — 1초에 3번을 훌쩍 넘게 깜빡인다
    assert np.abs(V.render(sc, sc.duration, bg, a).astype(int) - bg).mean() < 1   # 끝나면 아무것도 남지 않는다
    snd = S.sound(sc, np.random.default_rng(1))
    assert abs(len(snd) / glitch.SOUND_RATE - sc.duration) < 0.05 and np.abs(snd).max() > 3000


# ---------------------------------------------------------------- 타임 스톤
def test_time_scene_runs_the_clock_backwards_then_erases_the_name():
    sc = S.build_time(BIG, core=CORE, label="VISION", rng=np.random.default_rng(2))
    assert sc.kind == "time" and sc.impact > sc.duration             # 끄는 것이 없다 — impact 신호를 내지 않는다
    assert 3.5 < sc.duration < 6.5
    angles = [S.dial(t / 20, sc.duration)[1] for t in range(int(sc.duration * 20))]
    assert angles[0] == 0 and angles[-1] == pytest.approx(-720) and all(b <= a for a, b in zip(angles, angles[1:]))   # 거꾸로만 돈다
    clocks = [S.clock(t / 20) for t in range(int(S.T_NAME * 20) + 2)]
    assert clocks[0] == S.REWOUND and clocks[-1] == 0 and all(b <= a for a, b in zip(clocks, clocks[1:]))            # 0 까지 거꾸로 센다
    assert S.dial(0, sc.duration)[0] == 0 and S.dial(1.5, sc.duration)[0] == 1 and S.dial(sc.duration, sc.duration)[0] == 0
    assert S.rewind(0) == 0 and S.rewind(1.2) == 1 and S.rewind(S.T_NAME) == 0
    assert S.intact(sc, S.T_NAME - 0.05) is None                      # 되감는 동안에는 이름이 없다
    name = S.intact(sc, S.T_NAME + S.T_HOLD - 0.05)
    assert name is not None and name[..., 3].max() == 255             # 되감고 나면 닫힌 프로그램의 이름이 뜨고
    assert S.gone(sc, sc.duration) == 1 and S.intact(sc, sc.duration) is None      # 가루가 되어 사라진다
    assert len(S.dust(sc, S.T_NAME + S.T_HOLD + S.T_ERASE * 0.6)[0]) > 50
    bare = S.build_time(BIG, core=CORE, rng=np.random.default_rng(2))
    assert bare.image is None and bare.duration < sc.duration and len(S.dust(bare, 3.0)[0]) == 0
    drawn = S.build_time(BIG, label="x")
    assert drawn.core_drawn and 0 < drawn.core[0] < BIG[0]


def test_time_scene_is_green_flickers_while_rewinding_and_snaps_at_the_end(qt):
    from jarvis import stones_view as V
    sc = S.build_time(BIG, core=(640.0, 300.0), label="VISION", rng=np.random.default_rng(2))
    a = V.Assets(sc)
    for bright in (True, False):
        bg = desktop(bright, BIG)
        assert np.abs(V.render(sc, sc.duration, bg, a).astype(int) - bg).mean() < 1      # 끝나면 아무것도 남지 않는다
    blinks = [S.flash(sc, t / 200)[0] for t in range(int(S.T_NAME * 200))]
    ons = sum(1 for x, y in zip(blinks, blinks[1:]) if x == 0 and y > 0)
    assert ons >= 15 and max(blinks) <= 0.25                          # 되감는 동안 빠르게 깜빡인다
    snap, tint = S.flash(sc, S.T_NAME + 0.005)
    assert snap > 0.7 and tint[1] == max(tint)                        # 다 되감은 순간 초록빛으로 크게 번쩍인다
    assert max(abs(v) for i in range(6) for v in S.shake(sc, S.T_NAME + i / 50)) > 5 and S.flash(sc, sc.duration)[0] == 0
    dark = desktop(False, BIG)
    f = V.render(sc, 3.2, dark, a).astype(int) - dark               # 번쩍임이 가라앉은 뒤의 시계 고리
    ring = f[300 - 200:300 + 200, 640 - 200:640 + 200].reshape(-1, 3)
    drawn = ring[ring.max(axis=1) > 60]
    assert len(drawn) > 300 and (drawn[:, 1] >= drawn[:, 0]).mean() > 0.9 and (drawn[:, 1] >= drawn[:, 2]).mean() > 0.9   # 초록
    snd = S.sound(sc, np.random.default_rng(1))
    assert abs(len(snd) / glitch.SOUND_RATE - sc.duration) < 0.05 and np.abs(snd).max() > 3000


def test_time_scene_is_shown_at_most_once_every_twenty_seconds(tmp_path):
    stamp = tmp_path / "stones.json"
    assert S.time_due(stamp, now=1000.0)                              # 처음에는 보여 준다
    S.time_mark(stamp, now=1000.0)
    assert not S.time_due(stamp, now=1005.0) and not S.time_due(stamp, now=1000.0 + S.TIME_EVERY - 0.1)
    assert S.time_due(stamp, now=1000.0 + S.TIME_EVERY + 0.1)
    assert S.time_due(stamp, now=900.0)                               # 시계가 뒤로 갔으면 (적힌 때가 미래) 그냥 보여 준다
    stamp.write_text("broken", encoding="utf-8")
    assert S.time_due(stamp, now=1.0)                                 # 파일이 깨졌어도 멈추지 않는다
    assert S.TIME_EVERY >= 15


def test_lines_are_new_and_never_claim_real_harm():
    for line in S.POWER_OPEN + S.POWER_DONE + S.POWER_DEMO_DONE + S.TIME_DONE:
        assert len(line) < 60 and "죽" not in line and "사람" not in line
    said = S.time_line("vision", "창조자", random.Random(1))
    assert said.startswith("창조자, ") and "vision" in said and said.split(", ", 1)[1].split(" 나를")[0] in S.TIME_DONE
    assert S.time_line("", "", random.Random(1)) in S.TIME_DONE
    assert DEFAULTS["infinity"] is True


# ---------------------------------------------------------------- 울트론 본체 연결
class Emit:
    def __init__(self):
        self.sent = []

    def emit(self, *a):
        self.sent.append(a)


class FakeView:
    """덮개 창 대신: 재생한 장면을 적어 두고, stop() 하면 끝났다고 알린다."""

    def __init__(self, app, done):
        self.app, self.done, self.playing, self.played = app, done, False, []
        self.impact = self.finished = types.SimpleNamespace(connect=lambda fn: None)

    def play(self, top_left, scene):
        self.playing = True
        self.played.append(scene)

    def stop(self):
        self.playing = False
        getattr(self.app, self.done)()

    def winId(self):
        return 1


def fake_app(monkeypatch, tmp_path, infinity=True, **cfg):
    import jarvis.app as app_mod

    class Now(threading.Thread):                                       # 다른 스레드에서 할 일을 그 자리에서 바로 한다
        def start(self):
            self.run()

    monkeypatch.setattr(app_mod.threading, "Thread", Now)
    monkeypatch.setattr(app_mod.winutil, "fullscreen_app", lambda: False)
    monkeypatch.setattr(app_mod.QTimer, "singleShot", lambda ms, fn: None)
    monkeypatch.setattr(app_mod, "DATA_DIR", tmp_path)
    monkeypatch.setattr(app_mod.glitch, "write_wav", lambda audio, name="x": f"{name}.wav")
    J = app_mod.Jarvis
    screen = types.SimpleNamespace(geometry=lambda: types.SimpleNamespace(
        width=lambda: BIG[0], height=lambda: BIG[1], topLeft=lambda: "top-left", x=lambda: 0, y=lambda: 0))
    monkeypatch.setattr(app_mod.QGuiApplication, "primaryScreen", staticmethod(lambda: screen))

    class App:
        _absorb_claim, _absorb_build, _absorb_play = J._absorb_claim, J._absorb_build, J._absorb_play
        _absorb_impact, _absorb_kill, _absorb_killed = J._absorb_impact, J._absorb_kill, J._absorb_killed
        _absorb_ended, _absorb_finish = J._absorb_ended, J._absorb_finish
        _time_begin, _time_build, _time_play, _time_done = J._time_begin, J._time_build, J._time_play, J._time_done
        _revive_done, _revive_handoff, _revived_line = J._revive_done, J._revive_handoff, J._revived_line

        def __init__(self):
            self.cfg = {"guardian_show": True, "infinity": True, "user_title": "창조자", "rival_show": True} | cfg
            self.args = types.SimpleNamespace(revived=True, fast=True, closed="vision")
            self.state = {}
            self.bridge = types.SimpleNamespace(_infinity=infinity, _compact=True, toast=Emit(),
                                                set=lambda k, v: self.state.__setitem__(k, v))
            self.rival = rival.Watcher(lambda: [], lambda f: (True, ""), lambda: 1000.0, random.Random(0))
            self.sig_absorb_ready, self.sig_absorb_hit, self.sig_time = Emit(), Emit(), Emit()
            self._absorb_lock, self._absorb, self._absorb_last = threading.Lock(), None, -1e9
            self._absorb_view, self._stone_view = FakeView(self, "_absorb_ended"), FakeView(self, "_absorb_ended")
            self._time_view = FakeView(self, "_time_done")
            self._absorb_fx = self._time_fx = None
            self._time_closed, self._pending_line = "", None
            self._reviving, self._revive_demo, self._revive_inf = False, False, False
            self.listener = types.SimpleNamespace(muted=False)
            self.focus = types.SimpleNamespace(own_hwnds=set())
            self.win = types.SimpleNamespace(isVisible=lambda: True, screen=lambda: screen, show=lambda: None,
                                             geometry=lambda: types.SimpleNamespace(x=lambda: 1000, y=lambda: 40),
                                             setGeometry=lambda r: None)
            self.said = []

        def _core_point(self):
            return 100.0, 110.0

        def _play_fx(self, old, wav, volume):
            return wav

        def _release_fx(self, name):
            pass

        def _unmute(self):
            self.listener.muted = False

        def _quiet(self, listening_ok=False):
            return True

        def _reclaim_hotkey(self):
            pass

        def say(self, text, follow_up=True):
            self.said.append(text)

    return App(), app_mod


def test_infinity_ultron_crushes_jarvis_with_the_power_stone_instead_of_absorbing(monkeypatch, tmp_path):
    app, mod = fake_app(monkeypatch, tmp_path, infinity=True)
    app._absorb_build(BIG, CORE, window_image(), RECT, None, "top-left")
    scene, wav, top_left = app.sig_absorb_ready.sent[0][0]
    assert isinstance(scene, S.Scene) and scene.kind == "power" and wav == "ultron_power.wav"
    assert app._absorb_claim()
    app._absorb_play((scene, wav, top_left))
    assert app._stone_view.played == [scene] and app._absorb_view.played == [] and app._absorb["power"] is True
    app._absorb.update(found=[], demo=True)
    app._stone_view.stop()                                            # 장면 끝 (시범)
    assert app._absorb is None and app.said[-1] in S.POWER_DEMO_DONE

    plain, _ = fake_app(monkeypatch, tmp_path, infinity=False)         # 보통 울트론은 지금까지처럼 흡수한다
    plain._absorb_build(BIG, CORE, window_image(), RECT, None, "top-left")
    scene, wav, _ = plain.sig_absorb_ready.sent[0][0]
    assert isinstance(scene, absorb.Scene) and wav == "ultron_absorb.wav"
    assert plain._absorb_claim()
    plain._absorb_play((scene, wav, "top-left"))
    assert plain._absorb_view.played == [scene] and plain._stone_view.played == [] and plain._absorb["power"] is False


def test_power_stone_turns_jarvis_off_at_the_hit_and_says_dust_not_absorbed(monkeypatch, tmp_path):
    app, mod = fake_app(monkeypatch, tmp_path, infinity=True)
    victim = types.SimpleNamespace(pid=7, exe="pythonw.exe", title="J.A.R.V.I.S")
    killed = []
    monkeypatch.setattr(mod.rival, "stop_all", lambda found: (killed.extend(found) or list(found), []))
    scene = S.build_power(BIG, core=CORE, image=window_image(), rect=RECT)
    assert app._absorb_claim()
    app._absorb["found"] = [victim]
    app._absorb_play((scene, "x.wav", "top-left"))
    assert killed == []                                               # 줄기가 닿기 전에는 끄지 않는다
    app._absorb_impact()
    assert killed == [victim]
    app._absorb_killed(*app.sig_absorb_hit.sent[0])
    assert app.said == []                                             # 장면이 끝날 때까지는 닫는 말을 하지 않는다
    app._stone_view.stop()
    assert app._absorb is None and app.said[-1] in S.POWER_DONE and app.said[-1] not in rival.ABSORBED


def test_time_stone_plays_only_for_infinity_ultron_and_not_twice_in_a_row(monkeypatch, tmp_path):
    app, mod = fake_app(monkeypatch, tmp_path, infinity=True)
    assert app._time_begin("vision") is True and app.listener.muted
    scene, wav, top_left = app.sig_time.sent[0][0]
    assert scene.kind == "time" and scene.label == "vision" and wav == "ultron_time.wav"
    assert scene.core == (1100.0, 150.0)                              # HUD 엠블럼의 가운데 (창 자리 + 창 안의 자리)
    app._time_play((scene, wav, top_left))
    assert app._time_view.played == [scene] and app.said == []
    app._time_view.stop()                                             # 장면 끝 → 첫마디
    assert len(app.said) == 1 and "vision" in app.said[0] and "창조자" in app.said[0]
    assert "닫은 프로그램: vision" in app.bridge.toast.sent[0][1]
    assert app._time_begin("vision") is False                         # 싸우는 중 (20초 안에 또 꺼졌다) — 조용히 돌아온다

    normal, _ = fake_app(monkeypatch, tmp_path / "a", infinity=False)
    (tmp_path / "a").mkdir()
    assert normal._time_begin("vision") is False                      # 보통 울트론은 타임 스톤을 쓰지 않는다
    off, _ = fake_app(monkeypatch, tmp_path / "b", infinity=True, guardian_show=False)
    (tmp_path / "b").mkdir()
    assert off._time_begin("vision") is False                         # 연출을 껐으면 하지 않는다
    busy, mod2 = fake_app(monkeypatch, tmp_path / "c", infinity=True)
    (tmp_path / "c").mkdir()
    monkeypatch.setattr(mod2.winutil, "fullscreen_app", lambda: True)
    assert busy._time_begin("vision") is False                        # 게임 · 발표 앞에서는 화면을 덮지 않는다


def test_time_scene_failure_still_says_the_line(monkeypatch, tmp_path):
    app, mod = fake_app(monkeypatch, tmp_path, infinity=True)
    app._time_closed = "vision"
    app._time_play(None)                                              # 장면을 만들지 못했다
    assert len(app.said) == 1 and "vision" in app.said[0]


def test_revived_ultron_becomes_infinity_even_without_the_show(monkeypatch, tmp_path):
    app, mod = fake_app(monkeypatch, tmp_path, infinity=False)
    app._revive_done()                                                # 연출을 못 띄웠어도 되살아났으면 인피니티 울트론
    assert app.state.get("infinity") is True and app.said
    off, _ = fake_app(monkeypatch, tmp_path, infinity=False, infinity_cfg=None)
    off.cfg["infinity"] = False
    off._revive_done()
    assert "infinity" not in off.state                                # 설정에서 껐으면 보통 울트론 그대로
    hand, _ = fake_app(monkeypatch, tmp_path, infinity=False)
    hand._revive_inf = True
    hand._revive_handoff()
    assert hand.state.get("infinity") is True                         # 덮개를 넘겨받는 HUD 도 인피니티 울트론


def test_living_ultron_strikes_designated_enemies_first(monkeypatch, tmp_path):
    """가디언은 꺼진 뒤에만 친다 — 살아 있는 울트론이 켜지자마자, 그 뒤로도 지목한 비전을 먼저 닫는다."""
    import jarvis.app as mod
    J = mod.Jarvis
    calls = []

    class Now(threading.Thread):
        def start(self):
            self.run()

    monkeypatch.setattr(mod.threading, "Thread", Now)
    monkeypatch.setattr(mod.sys, "platform", "win32")
    monkeypatch.setattr(mod.guardian.Guard, "counter", lambda self, cfg, root: calls.append((cfg, root)) or ["vision"])

    class App:
        _enemy_tick, _enemy_work, _on_enemy = J._enemy_tick, J._enemy_work, J._on_enemy

        def __init__(self, infinity):
            self.cfg = {"guardian_counter": True, "enemy_installs": [r"C:\vision"], "enemy_titles": []}
            self._enemy_busy, self._enemy_spoke, self._pending_line = False, -1e9, None
            self.sig_enemy = Emit()
            self.toasts, self.said, self.state = [], [], {}
            self.bridge = types.SimpleNamespace(_infinity=infinity, set=lambda k, v: self.state.__setitem__(k, v),
                                                toast=types.SimpleNamespace(emit=lambda kind, m: self.toasts.append(m)))

        def _quiet(self, listening_ok=False):
            return True

        def say(self, text, follow_up=True):
            self.said.append(text)

    app = App(True)
    app._enemy_tick()
    assert calls and calls[0][0]["enemy_installs"] == [r"C:\vision"] and calls[0][1] == str(mod.ROOT)
    assert app.sig_enemy.sent == [(["vision"],)] and not app._enemy_busy
    app._on_enemy(["vision"])
    app._on_enemy(["vision"])                                         # 1분 안에 또: 알림만, 말은 한 번
    assert len(app.toasts) == 2 and len(app.said) == 1 and "vision" in app.said[0]
    calls.clear()
    app.cfg["guardian_counter"] = False                               # 되받아치기를 껐으면 치지 않는다
    app._enemy_tick()
    app.cfg.update(guardian_counter=True, enemy_installs=[])          # 지목한 것이 없으면 아무것도 건드리지 않는다
    app._enemy_tick()
    assert calls == []
