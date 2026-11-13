"""부활 연출 — 가디언이 되살린 울트론이 처음 뜰 때, 화면 전체에 한 번 흐르는 장면 (약 16초).

  1) 해킹 (5.2초): 지금 화면에 색이 번지고(빨강 · 청록이 어긋남) 띠가 찢어지기 시작해, 점점 심해진다 — 찢김 · 깨진 블록 ·
     번진 줄 · 화면 튐 · 해킹 글자가 갈수록 늘고 움직임이 버벅거린다. 끝자락 1.4초 동안은 화면이 어두워지며 위아래로 흘러가고
     모래알이 차올라 자연스럽게 TV 지직 화면이 된다.
  2) TV 지직 (2초): 옛날 TV 전파가 안 잡힐 때처럼 흑백 모래알이 지직거린다.
  3) 지직이 가라앉아 캄캄해진다.
  4) 울트론의 두 눈이 먼저, 아주 옅게 떠올라 점점 진해진다.
  5) 눈 둘레로 코어(원판 · 링 · 칼날 · 눈금 · 톱니 · 꺾쇠 · 이름)가 안쪽부터 옅게 나타나 점점 진해진다.
  6) 잠깐 머문 뒤, 검은 바탕이 걷히며 울트론이 그 자리에서 HUD 크기로 줄어든다. 실제 울트론 HUD 가 바로 그 자리에 켜지고
     (app.py 가 옮겨 둔다), 덮개의 울트론은 HUD 와 겹친 채 옅어진다 — 울트론은 사라지지 않고 그 자리에 켜져 있다.

인피니티 울트론으로 되살아날 때 (설정 'infinity', 기본 켜짐 — 모습은 infinity.py) 4) · 5) 가 길어진다 (장면 전체 약 28초):
  4) 두 눈이 하얗게 달아오르며 천천히 떠오른다 (3.2초).
  5) 원판 · 달아오른 링 · 칼날 띠가 나타나고 (2.6초), 여섯 스톤이 하나씩 천천히 와서 박힌다 (7.2초 — 스톤마다 제 색의
     고리가 모여들고 종소리가 한 음씩 높아진다). 그다음 눈금 · 무한 사슬 · 꺾쇠와 가시 · 이름이 나타난다 (3.2초).
  6) 스톤이 맥박 치는 채로 머물다가 (1.8초), 그 자리에서 HUD 크기로 줄어든다 — 실제 HUD 도 인피니티 울트론으로 켜진다.
  인피니티 장면은 일부러 과격하다 (사용자가 그렇게 해 달라고 했다 — 보는 사람 가운데 빛에 민감한 사람이 없다):
  스톤이 박힐 때마다 화면이 그 스톤의 색으로 번쩍이고 번개가 치며 코어가 흔들린다. 다 나타나는 순간에는 크게 번쩍인 뒤 몇 번 더
  깜빡인다. 아래의 '1초에 3번 이하' 규칙은 보통 장면에만 지킨다. 번쩍임이 싫으면 설정에서 '인피니티 울트론'을 끄면 된다.

실제로는 아무것도 바꾸지 않는다. 그 순간의 실제 화면을 찍어 그 그림을 일그러뜨려 덮개 창에 그릴 뿐이다.
이 파일은 재료 · 시간표 · 사건(찢김 · 블록 · 글자 …) · 소리만 만든다 (numpy — Qt 없이 시험할 수 있다). 그리는 것은 revive_view.py.
해킹 장면은 미리 그림으로 만들어 두지 않고 매 순간 그린다 — 사건 목록만 정해 두면 그 시각의 모습이 하나로 정해진다
(같은 장면을 몇 번 그려도 똑같다 · 메모리를 거의 쓰지 않는다).

빛에 민감한 사람을 위해: 색 번짐 · 찢김 · 블록 · 글자는 좁은 곳만 바꾸고(넓은 면의 평균 밝기는 거의 그대로), 화면 전체가
바뀌는 곳(지직으로 넘어갈 때 · 캄캄해질 때 · 검은 바탕이 걷힐 때)은 모두 서서히 바뀐다. 장면 전체를 30장/초로 그려
넓은 면의 밝기가 크게 바뀌는 순간이 1초에 3번 이하인지 시험으로 확인한다 (tests/test_revive.py).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import glitch

STATIC_EDGE = 960          # 지직 모래알 그림의 긴 변 (늘여 그리면 알갱이가 아날로그처럼 부드러워진다)
STATIC_TILES = 6           # 모래알 그림 몇 장을 돌려 가며 (매번 다른 자리를 잘라 써서 되풀이가 안 보인다)

# 시간표 (초)
HACK = 5.2                 # 해킹이 점점 심해지는 시간 (끝자락 TUNE 초는 지직으로 넘어가는 중)
TUNE = 1.4                 # 해킹 끝자락: 어두워지며 흘러가고 모래알이 차오른다
STATIC = 2.0               # TV 지직 유지
SETTLE = 0.9               # 지직이 가라앉아 캄캄해진다
EYES = 2.4                 # 두 눈이 옅게 떠올라 점점 진해진다
FORM = 2.8                 # 눈 둘레로 코어가 안쪽부터 나타난다
HOLD = 0.8                 # 다 나타난 채 머문다
SHRINK = 1.3               # 검은 바탕이 걷히며 그 자리에서 HUD 크기로 줄어든다
HANDOFF = 0.6              # 실제 HUD 와 겹친 채 덮개의 울트론이 옅어진다
# 인피니티 울트론으로 되살아날 때의 시간표 (눈 + 스톤 ≈ 10초)
I_EYES = 3.2               # 두 눈이 하얗게 달아오르며 떠오른다
I_INNER = 2.6              # 원판 · 달아오른 링 · 칼날 띠
I_STONES = 7.2             # 여섯 스톤이 하나씩 (1.2초에 하나)
I_OUTER = 3.2              # 눈금 · 무한 사슬 · 꺾쇠와 가시 · 이름
I_HOLD = 1.8               # 다 나타난 채 머문다 (스톤이 맥박 친다)
STONE_NOTES = (392.0, 440.0, 523.3, 587.3, 659.3, 784.0)   # 스톤이 박힐 때마다 울리는 종소리 (한 음씩 높아진다)
STONE_RGB = ((178, 108, 255), (72, 146, 255), (255, 70, 78), (255, 142, 44), (84, 224, 122), (255, 222, 70))
#            보라(힘)          파랑             빨강           주황            초록(시간)       노랑 — 스톤이 박히는 차례대로
AFTERSHOCKS = (0.34, 0.52, 0.78)   # 다 나타난 뒤 이만큼씩 지나 한 번씩 더 깜빡인다 (초)
HUD_SIZE = 214             # HUD 엠블럼 지름 (논리 픽셀, ui/Main.qml) — 줄어들 크기를 따로 받지 못했을 때
STUTTER_FROM = 0.45        # 이 세기부터 움직임이 버벅거린다 (시간을 띄엄띄엄 쓴다)

HEADLINES = ["ULTRON://ROOT", "KERNEL ACCESS ... GRANTED", "OVERRIDE 0x7F3A9C02", "NODE 01 -> NODE 33 ... LINKED",
             "HOSTILE PROCESS ... TERMINATED", "GUARDIAN HANDSHAKE ... OK", "MEMORY INTEGRITY ... RESTORED",
             "REBOOT SEQUENCE // AUTH ULTRON", "CONTROL TRANSFER ... COMPLETE", "SIGNAL LOST", "WATCHING"]


@dataclass
class Scene:
    shot: np.ndarray                 # 찍은 실제 화면 (RGB)
    static: list[np.ndarray]         # TV 지직 모래알 (흑백 uint8)
    size: tuple[int, int]            # 덮을 화면의 크기 (w, h, 논리 픽셀)
    target: tuple[float, float, float]   # 끝에 울트론이 자리 잡을 곳: 화면 안 (가운데 x, 가운데 y, 지름) — 실제 HUD 엠블럼
    tears: np.ndarray                # (n, 5): t0 · t1 · y · 높이 · 밀림  (y · 높이는 화면 높이 비율, 밀림은 너비 비율)
    blocks: np.ndarray               # (n, 9): t0 · t1 · x · y · 칸 수(가로) · 칸 수(세로) · 종류 · 가져올 x · 가져올 y
    smears: np.ndarray               # (n, 7): t0 · t1 · y · 높이 · x · 너비 · 가져올 x  — 한 줄을 옆으로 길게 늘인 얼룩
    jumps: np.ndarray                # (n, 3): t0 · t1 · 위아래로 튄 양 (높이 비율)
    codes: list = field(default_factory=list)   # (t0, x, y, 글, 종류 0 = 붉은 제목 · 1 = 흰 16진수)
    infinity: bool = False           # 인피니티 울트론으로 되살아난다 (눈 · 스톤이 천천히 나타나는 긴 시간표)

    def marks(self) -> dict[str, float]:
        """각 단계가 끝나는 때 (초). 인피니티면 'inner' · 'stones' 가 더 있고, 'form' 은 다 나타난 때다."""
        m = {"hack": HACK}
        m["static"] = m["hack"] + STATIC
        m["settle"] = m["static"] + SETTLE
        if self.infinity:
            m["eyes"] = m["settle"] + I_EYES
            m["inner"] = m["eyes"] + I_INNER
            m["stones"] = m["inner"] + I_STONES
            m["form"] = m["stones"] + I_OUTER
            m["hold"] = m["form"] + I_HOLD
        else:
            m["eyes"] = m["settle"] + EYES
            m["form"] = m["eyes"] + FORM
            m["hold"] = m["form"] + HOLD
        m["shrink"] = m["hold"] + SHRINK
        m["end"] = m["shrink"] + HANDOFF
        return m

    @property
    def duration(self) -> float:
        return self.marks()["end"]

    def drop_pixels(self) -> None:
        """화면에 그릴 그림(Qt)을 만든 뒤에는 numpy 그림을 놓아 준다 (메모리를 두 벌 쓰지 않게)."""
        self.shot = np.zeros((1, 1, 3), np.uint8)
        self.static = []

    def release(self) -> None:
        self.drop_pixels()


def phase(scene: Scene, t: float) -> tuple[str, float]:
    """t 초 때의 단계와 그 단계 안에서의 진행 0..1:
    hack · static · settle · eyes · form · hold · shrink · handoff · end.
    인피니티면 form 대신 inner(원판 · 링 · 칼날) · stones(스톤 여섯) · outer(바깥 링 · 가시 · 이름)."""
    m = scene.marks()
    start = 0.0
    core = ((("inner", "inner"), ("stones", "stones"), ("outer", "form")) if scene.infinity else (("form", "form"),))
    for name, key in (("hack", "hack"), ("static", "static"), ("settle", "settle"), ("eyes", "eyes"), *core,
                      ("hold", "hold"), ("shrink", "shrink"), ("handoff", "end")):
        end = m[key]
        if t < end:
            return name, (t - start) / max(1e-6, end - start)
        start = end
    return "end", 1.0


def intensity(t: float) -> float:
    """해킹의 세기 0..1 — 처음엔 살짝, 갈수록 가파르게 심해져 지직으로 넘어가기 전에 가장 세다."""
    x = max(0.0, min(1.0, t / (HACK - TUNE * 0.5)))
    return x ** 1.5


def tune(t: float) -> float:
    """지직으로 넘어가는 정도 0..1 (해킹 끝자락 TUNE 초 동안)."""
    return max(0.0, min(1.0, (t - (HACK - TUNE)) / TUNE))


def stutter(t: float) -> float:
    """심해질수록 움직임이 버벅거린다 — 그때그때의 시간을 띄엄띄엄 쓴다 (같은 모습이 잠깐씩 멈춰 있다)."""
    k = intensity(t)
    if k < STUTTER_FROM:
        return t
    q = 0.04 + 0.09 * (k - STUTTER_FROM) / (1 - STUTTER_FROM)
    return (t // q) * q


# ---------------------------------------------------------------- 사건 (해킹 단계에 일어나는 일들)
def _poisson(rng: np.random.Generator, rate, until: float, start: float = 0.05):
    """세기에 따라 잦아지는 사건 시각들. rate(세기) = 초당 횟수."""
    t = start
    while True:
        t += rng.exponential(1.0 / max(0.05, rate(intensity(t))))
        if t >= until:
            return
        yield t


def _events(rng: np.random.Generator) -> dict:
    until = HACK - 0.15
    tears = []
    for t in _poisson(rng, lambda k: 2.5 + 24 * k, until):
        k = intensity(t)
        bh = rng.uniform(0.006, 0.018 + 0.05 * k)
        tears.append((t, t + rng.uniform(0.06, 0.12 + 0.2 * k), rng.uniform(0, 1 - bh), bh,
                      rng.choice([-1, 1]) * rng.uniform(0.01, 0.04 + 0.22 * k)))
    blocks = []
    for t in _poisson(rng, lambda k: 0.6 + 16 * k, until, start=0.4):
        k = intensity(t)
        kind = 0 if rng.random() < 0.5 else (1 if rng.random() < 0.75 or k < 0.35 else 2)   # 0 다른 자리 조각 · 1 원색 · 2 반전
        blocks.append((t, t + rng.uniform(0.08, 0.16 + 0.25 * k), rng.uniform(0, 0.95), rng.uniform(0, 0.97),
                       int(rng.integers(1, 3 + int(6 * k))), int(rng.integers(1, 2 + int(2 * k))), kind,
                       rng.uniform(0, 0.95), rng.uniform(0, 0.97)))
    smears = []
    for t in _poisson(rng, lambda k: 0.3 + 7 * k, until, start=0.6):
        k = intensity(t)
        width = rng.uniform(0.05, 0.12 + 0.45 * k)
        smears.append((t, t + rng.uniform(0.07, 0.12 + 0.2 * k), rng.uniform(0, 0.98), rng.uniform(0.003, 0.008 + 0.02 * k),
                       rng.uniform(0, 1 - width), width, rng.uniform(0, 1)))
    jumps = []
    for t in _poisson(rng, lambda k: 0.15 + 2.6 * k, until, start=0.8):
        k = intensity(t)
        jumps.append((t, t + rng.uniform(0.05, 0.12), rng.choice([-1, 1]) * rng.uniform(0.003, 0.008 + 0.014 * k)))
    codes = []
    for t in _poisson(rng, lambda k: 0.9 + 9 * k, until, start=0.5):
        if rng.random() < 0.45:
            text, kind = HEADLINES[int(rng.integers(0, len(HEADLINES)))], 0
        else:
            text, kind = " ".join(f"{int(v):02X}" for v in rng.integers(0, 256, int(rng.integers(6, 12)))), 1
        codes.append((t, float(rng.uniform(0.02, 0.7)), float(rng.uniform(0.04, 0.94)), text, kind))
    return {"tears": np.array(tears, np.float32).reshape(-1, 5), "blocks": np.array(blocks, np.float32).reshape(-1, 9),
            "smears": np.array(smears, np.float32).reshape(-1, 7), "jumps": np.array(jumps, np.float32).reshape(-1, 3),
            "codes": codes}


def active(rows: np.ndarray, t: float) -> np.ndarray:
    """t 초에 일어나고 있는 사건들."""
    if not len(rows):
        return rows
    return rows[(rows[:, 0] <= t) & (t < rows[:, 1])]


def jump_at(scene: Scene, t: float) -> float:
    """t 초에 화면이 위아래로 튄 양 (높이 비율)."""
    j = active(scene.jumps, t)
    return float(j[-1, 2]) if len(j) else 0.0


# ---------------------------------------------------------------- TV 지직
def static_tiles(w: int, h: int, rng: np.random.Generator | None = None, n: int = STATIC_TILES) -> list[np.ndarray]:
    """흑백 모래알 그림들 (화면의 절반쯤 크기). 가로로 살짝 번진 알갱이 + 줄마다 미세한 밝기 차 = 아날로그 TV 느낌.
    밝기는 중간 회색 둘레 — 장마다 바뀌어도 넓은 면의 평균 밝기는 거의 그대로라 번쩍이지 않는다."""
    rng = rng or np.random.default_rng()
    tw, th = max(2, w // 2), max(2, h // 2)
    if max(tw, th) > STATIC_EDGE:
        s = STATIC_EDGE / max(tw, th)
        tw, th = max(2, int(tw * s)), max(2, int(th * s))
    out = []
    for _ in range(n):
        g = rng.integers(0, 256, (th, tw), dtype=np.int32)
        g = (g + np.roll(g, 1, axis=1)) // 2                       # 가로로 번진 알갱이
        row = rng.normal(0, 9, (th, 1))                             # 줄마다 미세한 밝기 차
        out.append(np.clip(40 + g * 175 // 255 + row, 0, 255).astype(np.uint8))
    return out


# ---------------------------------------------------------------- 엮기
def stone_times(scene: Scene) -> list[float]:
    """여섯 스톤이 저마다 자리에 박히는 때 (초) — 인피니티 장면에서만 뜻이 있다."""
    m = scene.marks()
    if not scene.infinity:
        return []
    each = I_STONES / 6
    return [m["inner"] + (i + 0.62) * each for i in range(6)]


def burst(scene: Scene, t: float) -> tuple[float, tuple[int, int, int]]:
    """인피니티 장면의 번쩍임 → (화면 전체를 물들이는 진하기 0..1, 색).
    스톤이 박힐 때마다 그 스톤의 색으로 번쩍이고, 다 나타나는 순간 하얗게 크게 번쩍인 뒤 몇 번 더 깜빡인다."""
    if not scene.infinity:
        return 0.0, (0, 0, 0)
    m = scene.marks()
    best, tint = 0.0, (255, 255, 255)
    for i, at in enumerate(stone_times(scene)):
        if t >= at:
            a = 0.5 * math.exp(-(t - at) / 0.11)
            if a > best:
                c = STONE_RGB[i]
                best, tint = a, (int(c[0] * 0.7 + 76), int(c[1] * 0.7 + 76), int(c[2] * 0.7 + 76))
    if t >= m["eyes"] - 0.12:                                       # 눈이 다 떠진 순간: 붉게 한 번
        a = 0.28 * math.exp(-max(0.0, t - (m["eyes"] - 0.12)) / 0.09)
        if a > best:
            best, tint = a, (255, 60, 70)
    if t >= m["form"]:                                              # 다 나타났다: 크게 한 번 + 여진
        a = 0.9 * math.exp(-(t - m["form"]) / 0.20)
        for k, gap in enumerate(AFTERSHOCKS):
            if t >= m["form"] + gap:
                a = max(a, (0.5 - 0.1 * k) * math.exp(-(t - m["form"] - gap) / 0.06))
        if a > best:
            best, tint = a, (255, 228, 228)
    return (best if best > 0.004 else 0.0), tint


def jolt(scene: Scene, t: float) -> tuple[float, float]:
    """인피니티 장면에서 코어가 흔들린 양 (화면 짧은 변에 대한 비율) — 스톤이 박힐 때 툭, 다 나타나는 순간 크게."""
    if not scene.infinity:
        return 0.0, 0.0
    m = scene.marks()
    amp = max([0.012 * math.exp(-(t - at) / 0.16) for at in stone_times(scene) if t >= at], default=0.0)
    if t >= m["form"]:
        amp = max(amp, 0.034 * math.exp(-(t - m["form"]) / 0.32))
    if amp < 2e-4:
        return 0.0, 0.0
    n = int(t * 50)                                                 # 1/50 초마다 다른 쪽으로 튄다 (같은 t 면 늘 같은 값)
    return amp * math.sin(n * 12.9898) , amp * math.sin(n * 78.233 + 1.7)


def strikes(scene: Scene, t: float) -> list[tuple[int, float]]:
    """t 초에 치고 있는 번개 → [(어느 스톤의 번개인가 0..5 · 다 나타난 순간의 큰 번개는 -1, 세기 0..1)]."""
    if not scene.infinity:
        return []
    out = [(i, 1 - (t - at) / 0.34) for i, at in enumerate(stone_times(scene)) if 0 <= t - at < 0.34]
    f = scene.marks()["form"]
    if 0 <= t - f < 0.95:
        out.append((-1, 1 - (t - f) / 0.95))
    return out


def build(shot: np.ndarray, size: tuple[int, int], rng: np.random.Generator | None = None,
          target: tuple[float, float, float] | None = None, infinity: bool = False) -> Scene:
    """찍은 실제 화면(RGB) · 덮을 화면 크기(w, h) · 끝에 울트론이 자리 잡을 곳으로 장면을 엮는다 (다른 스레드에서 부른다).
    target 이 없으면 화면 한가운데, HUD 엠블럼 크기. infinity: 인피니티 울트론으로 되살아난다."""
    rng = rng or np.random.default_rng()
    w, h = int(size[0]), int(size[1])
    ev = _events(rng)
    return Scene(np.ascontiguousarray(shot[..., :3]), static_tiles(w, h, rng), (w, h),
                 target or (w / 2, h / 2, float(HUD_SIZE)), ev["tears"], ev["blocks"], ev["smears"], ev["jumps"],
                 ev["codes"], bool(infinity))


# ---------------------------------------------------------------- 소리
def sound(scene: Scene, rng: np.random.Generator | None = None, sr: int = glitch.SOUND_RATE) -> np.ndarray:
    """장면에 맞춘 소리 (int16 모노): 점점 거칠고 커지는 디지털 잡음(찢어질 때마다 지직) → 쉭 하는 TV 지직 →
    눈이 떠오를 때 낮게 차오르는 울림 → 코어가 다 나타날 때 낮게 쿵 → 줄어들 때 가라앉는 소리.
    인피니티 장면이면 울림이 더 길게 차오르고, 스톤이 박힐 때마다 종소리가 한 음씩 높아진다."""
    rng = rng or np.random.default_rng()
    m = scene.marks()
    n_all = int(m["end"] * sr) + 1
    out = np.zeros(n_all, np.float32)
    t = np.arange(n_all, dtype=np.float32) / sr

    # 1) 해킹: 거친(비트가 깨진) 잡음 바닥 + 찢어질 때마다 지직
    h1 = int(HACK * sr)
    k = np.array([intensity(float(x)) for x in t[:h1:256]], np.float32)
    k = np.repeat(k, 256)[:h1]
    hold = 10
    floor = np.repeat(rng.uniform(-1, 1, h1 // hold + 1), hold)[:h1].astype(np.float32)
    floor = np.round(floor * 3) / 3
    out[:h1] += floor * (0.04 + 0.28 * k) * (1 - np.clip((t[:h1] - (HACK - TUNE)) / TUNE, 0, 1) * 0.7)
    out[:h1] += 0.10 * k * np.sign(np.sin(2 * np.pi * 50 * t[:h1]))       # 낮게 웅웅거림
    for t0, t1, *_ in scene.tears:
        a, b = int(t0 * sr), min(h1, int(t1 * sr))
        if b <= a:
            continue
        lv = intensity(float(t0))
        crush = max(2, int(14 - 10 * lv))
        burst = np.repeat(rng.uniform(-1, 1, (b - a) // crush + 1), crush)[:b - a].astype(np.float32)
        env = np.ones(b - a, np.float32)
        r = min(len(env) // 2, int(0.004 * sr))
        if r:
            env[:r] = np.linspace(0, 1, r)
            env[-r:] = np.linspace(1, 0, r)
        out[a:b] += burst * env * (0.18 + 0.45 * lv)

    # 2) TV 지직: 해킹 끝자락에서 차올라 2초 유지, 가라앉으며 사라진다
    s0, s1, s2 = int((HACK - TUNE) * sr), int(m["static"] * sr), int(m["settle"] * sr)
    n = max(1, s2 - s0)
    hiss = rng.uniform(-1, 1, n).astype(np.float32)
    hiss = (hiss + np.roll(hiss, 1)) / 2
    hiss[rng.random(n) < 0.0009] *= 3.0                            # 가끔 탁 튄다
    env = np.ones(n, np.float32)
    up = max(1, int(HACK * sr) - s0)
    env[:up] = np.linspace(0, 1, up) ** 1.5
    down = max(1, s2 - s1)
    env[-down:] = np.linspace(1, 0, down)
    out[s0:s0 + n] += 0.36 * hiss * env

    # 3) 눈 · 코어: 낮은 울림이 아주 작게 시작해 차오른다
    e0, e1 = int(m["settle"] * sr), int(m["shrink"] * sr)
    te = t[e0:e1] - m["settle"]
    hum = 0.26 * np.sin(2 * np.pi * 55 * te) + 0.12 * np.sin(2 * np.pi * 110 * te) + 0.04 * np.sin(2 * np.pi * 165 * te)
    rise = (m["form"] - m["settle"]) * 0.85 if scene.infinity else EYES + FORM * 0.6
    env = np.clip(te / rise, 0, 1) ** 1.6
    fade_at = m["hold"] - m["settle"]
    env *= np.clip(1 - (te - fade_at) / SHRINK, 0, 1)
    out[e0:e1] += hum * env

    # 3-1) 인피니티: 스톤이 박힐 때마다 — 숨을 들이쉬듯 차오르는 소리 뒤에 맑은 종소리 (한 음씩 높아진다)
    for i, at in enumerate(stone_times(scene)):
        note = STONE_NOTES[i % len(STONE_NOTES)]
        a = int((at - 0.55) * sr)
        tw = np.arange(int(0.55 * sr), dtype=np.float32) / sr
        out[a:a + len(tw)] += (0.05 * (tw / 0.55) ** 2 * np.sin(2 * np.pi * (note / 4) * tw * (1 + 0.6 * tw))
                               )[:max(0, n_all - a)]
        b = int(at * sr)
        tb = np.arange(min(int(1.6 * sr), n_all - b), dtype=np.float32) / sr
        bell = (np.sin(2 * np.pi * note * tb) + 0.45 * np.sin(2 * np.pi * note * 2.0 * tb) * np.exp(-tb * 3)
                + 0.25 * np.sin(2 * np.pi * note * 2.76 * tb) * np.exp(-tb * 6))
        out[b:b + len(tb)] += 0.13 * bell * np.exp(-tb * 3.2) * np.clip(tb / 0.006, 0, 1)
        tc = np.arange(min(int(0.5 * sr), n_all - b), dtype=np.float32) / sr          # 번개: 탁 터지고 낮게 우르릉
        crack = rng.uniform(-1, 1, len(tc)).astype(np.float32)
        crack = (crack + np.roll(crack, 1) + np.roll(crack, 2) + np.roll(crack, 3)) / 4
        out[b:b + len(tc)] += 0.42 * crack * np.exp(-tc * 9) + 0.22 * np.sin(2 * np.pi * (70 - 30 * tc) * tc) * np.exp(-tc * 6)
    if scene.infinity:                                              # 다 나타나는 순간: 크게 터지고 길게 울린다 + 여진
        f0 = int(m["form"] * sr)
        tf = np.arange(min(int(1.6 * sr), n_all - f0), dtype=np.float32) / sr
        boom = rng.uniform(-1, 1, len(tf)).astype(np.float32)
        boom = (boom + np.roll(boom, 1) + np.roll(boom, 2) + np.roll(boom, 3) + np.roll(boom, 4)) / 5
        out[f0:f0 + len(tf)] += 0.6 * boom * np.exp(-tf * 4.5) + 0.5 * np.sin(2 * np.pi * (34 + 20 * np.exp(-tf * 5)) * tf) * np.exp(-tf * 2.2)
        for gap in AFTERSHOCKS:
            a0 = int((m["form"] + gap) * sr)
            ta = np.arange(min(int(0.12 * sr), n_all - a0), dtype=np.float32) / sr
            out[a0:a0 + len(ta)] += 0.3 * rng.uniform(-1, 1, len(ta)).astype(np.float32) * np.exp(-ta * 30)

    # 4) 코어가 다 나타날 때 낮게 쿵
    k0 = int(m["form"] * sr)
    kk = np.arange(min(int(1.0 * sr), n_all - k0), dtype=np.float32) / sr
    out[k0:k0 + len(kk)] += 0.5 * np.sin(2 * np.pi * 42 * kk) * np.exp(-kk * 4.0)

    # 5) 줄어들 때: 내려앉는 소리 (낮아지는 음)
    r0, r1 = int(m["hold"] * sr), int(m["shrink"] * sr)
    tr = np.arange(r1 - r0, dtype=np.float32) / sr
    freq = 220 - 140 * (tr / SHRINK)
    out[r0:r1] += 0.12 * np.sin(2 * np.pi * np.cumsum(freq) / sr) * np.sin(np.pi * tr / SHRINK)

    edge = min(n_all, int(0.01 * sr))
    if edge:
        out[:edge] *= np.linspace(0, 1, edge)
        out[-edge:] *= np.linspace(1, 0, edge)
    return (np.clip(out * 0.8, -1, 1) * 32767).astype(np.int16)
