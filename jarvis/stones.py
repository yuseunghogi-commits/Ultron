"""스톤 연출 — 인피니티 울트론(infinity.py)이 스톤의 힘을 쓰는 장면 둘.

  파워 스톤 (보라)  자비스를 발견했을 때. 흡수 연출(absorb.py) 대신 이 장면과 함께 자비스를 끈다 (5초 남짓):
      모으기   울트론 코어에 보랏빛 힘이 모여든다 (자비스 화면은 이때부터 얼어붙는다)
      쏘기     보랏빛 줄기가 자비스에게 뻗는다. 실제 자비스는 그보다 먼저, 찍어 둔 그림이 창을 가리자마자 끈다 (app.py) —
               힘을 모으는 1초 남짓 동안 자비스가 울트론을 끄지 못하게. 꺼지는 모습은 그림에 가려 보이지 않는다
      가루     맞은 자리부터 금이 번지며 자비스 화면이 가루가 되어 흩날려 사라진다
  타임 스톤 (초록)  누가 울트론을 강제로 껐는데 가디언이 곧바로 되살렸을 때 (4초 남짓):
      되감기   울트론 둘레에 초록 시계 고리가 거꾸로 돌고, 화면에 되감기 줄이 위로 흐르며 시간이 거꾸로 센다
      지우기   가디언이 닫은 프로그램의 이름이 떴다가 가루가 되어 사라진다 — "시간을 되돌렸다. 나는 꺼진 적이 없다."

실제로 하는 일은 지금까지와 같다 — 자비스 프로세스를 끄는 것(rival.py)과, 가디언이 사용자가 지목한 비전을 닫고 울트론을
되살리는 것(guardian.py)뿐이다. 이 파일이 더하는 것은 전부 그림과 소리다 (입력 통과 덮개 창 — stones_view.py).
시간을 실제로 되돌리지는 않는다: 이미 되살아난 뒤에 '되감은 것처럼' 보여 줄 뿐이다.

일부러 과격하게 만들었다 (사용자가 그렇게 해 달라고 했다 — 보는 사람 가운데 빛에 민감한 사람이 없다):
화면 전체가 스톤의 색으로 번쩍이고(flash), 장면이 흔들리고(shake), 번개가 친다. 다른 연출(해킹 · 흡수 · 보통 부활)이 지키는
'넓은 면의 밝기가 1초에 3번 넘게 크게 바뀌지 않는다'는 규칙을 이 장면들은 지키지 않는다.
빛에 민감한 사람이 볼 수 있는 자리라면 설정에서 '인피니티 울트론'을 꺼 두면 된다 (그러면 이 장면들은 나오지 않는다).

이 파일은 장면의 뼈대(시간표 · 가루 · 그림 · 소리)만 만든다 (numpy · PIL — Qt 없이 시험할 수 있다).
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

import numpy as np

from .glitch import SOUND_RATE, _font

# ---------------------------------------------------------------- 시간표 (초)
FREEZE = 0.12                  # 이때부터 찍어 둔 자비스 그림이 실제 창을 가린다 (꺼지는 모습은 보이지 않는다)
CHARGE = 1.05                  # 코어에 힘이 모이는 시간
BEAM = 0.26                    # 줄기가 자비스에 닿기까지
IMPACT = CHARGE + BEAM         # 줄기가 닿는 때 (그림 — 실제로 끄는 때는 KILL)
KILL = FREEZE + 0.05           # 실제 자비스를 끄는 때 — 찍어 둔 그림이 창을 다 가린 직후
CRUMBLE = 2.1                  # 맞은 자리에서 가장 먼 곳까지 가루로 바뀌는 데 걸리는 시간
DRIFT = 1.25                   # 가루 한 알이 흩날리다 사라지기까지
CRACK = 0.30                   # 가루가 되기 직전 이만큼 동안 보랏빛 금이 간다
POWER_END = IMPACT + CRUMBLE + DRIFT + 0.25
DRAG = 0.85                    # 숨어 있던 자비스를 구석에서 끌어내는 시간 (창이 안 보일 때)

T_IN = 0.45                    # 타임 스톤: 시계 고리가 펼쳐지는 시간
REWIND = 1.9                   # 되감는 시간
T_NAME = T_IN + REWIND         # 닫힌 프로그램의 이름이 뜨는 때
T_HOLD = 0.55                  # 이름이 온전히 보이는 시간
T_ERASE = 1.0                  # 이름이 가루로 바뀌는 시간
T_OUT = 0.5                    # 고리가 사라지는 시간
REWOUND = 3.0                  # 되감기 숫자가 처음에 가리키는 시간 (초) — 0 까지 거꾸로 센다
TIME_EVERY = 20.0              # 타임 스톤 장면은 이 간격 안에 다시 보여 주지 않는다 (계속 꺼지는 싸움 중에는 조용히 돌아온다)

MAX_GRAINS = 26000             # 가루 알갱이 수의 한계 (자비스 창이 크면 알갱이를 키운다)
EMBLEM = 210                   # 그려 낸 자비스 코어의 크기 (창이 안 보일 때)
VIOLET = (178, 108, 255)       # 파워 스톤 (revive.STONE_RGB 의 보라)
GREEN = (84, 224, 122)         # 타임 스톤 (revive.STONE_RGB 의 초록)
QUAKES = (0.30, 0.52, 0.80, 1.15, 1.55)   # 줄기가 꽂힌 뒤 이만큼씩 지나 한 번씩 더 번쩍이며 흔들린다 (초) — 갈수록 약하게
STROBE = 14.0                  # 힘이 다 모일 무렵 · 되감는 동안 화면이 깜빡이는 빠르기 (1초에 몇 번)
ASH = (120, 104, 140)          # 가루가 식은 색


def _smooth(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


@dataclass
class Scene:
    kind: str                            # 'power' | 'time'
    size: tuple[int, int]                # 화면 크기 (w, h, 논리 픽셀)
    core: tuple[float, float]            # 울트론 코어의 가운데
    hud: float                           # 화면 위 울트론 엠블럼의 지름
    core_drawn: bool                     # 울트론 HUD 가 이 화면에 없다 — 인피니티 울트론을 직접 그린다
    image: np.ndarray | None             # 가루로 만들 그림 RGBA (자비스 창 · 그려 낸 자비스 코어 · 프로그램 이름)
    rect: tuple[float, float, float, float]   # 그 그림의 자리 (x, y, w, h)
    real: bool                           # 화면에 보이던 자비스 창을 찍은 그림인가
    cell: int = 4                        # 가루 한 알의 크기 (픽셀)
    born: np.ndarray = field(default_factory=lambda: np.zeros((0, 0), np.float32))   # 칸마다 가루로 바뀌는 때 (초)
    tone: np.ndarray = field(default_factory=lambda: np.zeros((0, 0, 4), np.uint8))  # 칸마다의 색 (RGBA)
    vel: np.ndarray = field(default_factory=lambda: np.zeros((0, 0, 2), np.float32))  # 칸마다 날아가는 빠르기 (픽셀/초)
    sway: np.ndarray = field(default_factory=lambda: np.zeros((0, 0, 2), np.float32))  # 칸마다 흔들리는 박자 · 폭
    hit: tuple[float, float] = (0.0, 0.0)     # 줄기가 꽂히는 자리
    origin: tuple[float, float] | None = None  # 숨어 있던 자비스를 끌어내기 시작하는 자리 (왼쪽 위)
    label: str = ""                      # 타임 스톤: 가디언이 닫은 프로그램의 이름
    impact: float = IMPACT               # 실제로 끄는 때 (타임 스톤은 끄는 것이 없다 — 장면보다 뒤로 둔다)
    duration: float = POWER_END
    tint: tuple[int, int, int] = VIOLET

    @property
    def bounds(self) -> tuple[int, int, int, int]:
        """덮개 창이 덮을 곳 — 화면 전체."""
        return 0, 0, int(self.size[0]), int(self.size[1])

    @property
    def crumble_from(self) -> float:
        return IMPACT if self.kind == "power" else T_NAME + T_HOLD


# ---------------------------------------------------------------- 가루
def _noise(gh: int, gw: int, cell: float, rng) -> np.ndarray:
    """뭉글뭉글한 잡음 0..1 (gh, gw) — 가루가 고르게가 아니라 덩어리지며 무너지게."""
    ch, cw = max(2, int(gh / cell) + 2), max(2, int(gw / cell) + 2)
    coarse = rng.random((ch, cw)).astype(np.float32)
    ys = np.linspace(0, ch - 1.001, gh)
    xs = np.linspace(0, cw - 1.001, gw)
    y0, x0 = ys.astype(int), xs.astype(int)
    fy, fx = (ys - y0)[:, None], (xs - x0)[None, :]
    a, b = coarse[y0][:, x0], coarse[y0][:, x0 + 1]
    c, d = coarse[y0 + 1][:, x0], coarse[y0 + 1][:, x0 + 1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def grains(image: np.ndarray, rect: tuple[float, float, float, float], hit: tuple[float, float], push: tuple[float, float],
           start: float, spread: float, rng, lift: float = 30.0) -> dict:
    """그림을 가루 알갱이로 나눈다 → {cell, born, tone, vel, sway}.
    hit 에서 가까운 칸부터 start 초에 바뀌기 시작해 spread 초에 걸쳐 가장 먼 칸까지 바뀐다. push: 가루가 밀려 날아가는 쪽 (단위 벡터)."""
    h, w = image.shape[:2]
    cell = max(3, int(math.ceil(math.sqrt(w * h / MAX_GRAINS))))
    gh, gw = max(1, h // cell), max(1, w // cell)
    block = image[:gh * cell, :gw * cell].reshape(gh, cell, gw, cell, 4).astype(np.float32)
    alpha = block[..., 3:4]
    weight = np.maximum(alpha.sum(axis=(1, 3)), 1e-3)
    tone = np.concatenate([(block[..., :3] * alpha).sum(axis=(1, 3)) / weight, alpha.mean(axis=(1, 3))], axis=2)
    sx, sy = rect[2] / w, rect[3] / h                                # 그림 픽셀 → 화면 픽셀
    cy, cx = np.mgrid[0:gh, 0:gw].astype(np.float32)
    px = rect[0] + (cx + 0.5) * cell * sx
    py = rect[1] + (cy + 0.5) * cell * sy
    far = np.hypot(px - hit[0], py - hit[1])
    far = far / max(1.0, float(far.max()))
    born = start + spread * (0.72 * far + 0.28 * _noise(gh, gw, 7.0, rng))
    speed = rng.uniform(70, 360, (gh, gw)) * rng.choice([1.0, 1.0, 1.7], (gh, gw))   # 몇몇은 멀리 튕겨 나간다
    turn = rng.normal(0, 0.55, (gh, gw))                              # 밀리는 쪽에서 조금씩 벗어난다
    ang = math.atan2(push[1], push[0]) + turn
    vel = np.stack([np.cos(ang) * speed, np.sin(ang) * speed - lift * rng.uniform(0.3, 1.6, (gh, gw))], axis=2)
    sway = np.stack([rng.uniform(2.0, 6.0, (gh, gw)), rng.uniform(3.0, 14.0, (gh, gw))], axis=2)
    return {"cell": cell, "born": born.astype(np.float32), "tone": np.clip(tone, 0, 255).astype(np.uint8),
            "vel": vel.astype(np.float32), "sway": sway.astype(np.float32)}


def offset(sc: Scene, t: float) -> tuple[float, float, float]:
    """t 초에 가루로 만들 그림이 있는 자리와 진하기 (dx, dy, alpha) — 숨어 있던 자비스는 구석에서 끌려 나온다."""
    if sc.origin is None:
        return 0.0, 0.0, 1.0
    k = float(_smooth(t / DRAG))
    return (sc.origin[0] - sc.rect[0]) * (1 - k), (sc.origin[1] - sc.rect[1]) * (1 - k), min(1.0, t / (DRAG * 0.6))


def intact(sc: Scene, t: float) -> np.ndarray | None:
    """t 초에 아직 가루가 되지 않은 부분의 그림 RGBA (가루가 된 칸은 투명, 곧 가루가 될 칸은 금이 간 듯 스톤 빛으로 물든다).
    FREEZE 전(실제 창이 그대로 보이는 동안)과 다 사라진 뒤에는 None."""
    if sc.image is None or t < (0.0 if sc.kind == "time" or sc.origin is not None else FREEZE):
        return None
    if sc.kind == "time" and t < T_NAME:
        return None
    left = sc.born - t                                               # 가루가 되기까지 남은 시간 (칸마다)
    if not (left > 0).any():
        return None
    c = sc.cell
    gh, gw = sc.born.shape
    out = sc.image[:gh * c, :gw * c].copy()
    if t >= sc.crumble_from - CRACK:
        soon = np.clip(1 - left / CRACK, 0, 1)                       # 0 = 멀었다 · 1 = 지금 가루가 된다
        soon = np.where(left > 0, soon, 0).astype(np.float32)
        big = np.repeat(np.repeat(soon, c, axis=0), c, axis=1)[..., None]
        glow = np.array(sc.tint, np.float32) * 0.6 + 255 * 0.4
        out[..., :3] = (out[..., :3] * (1 - 0.85 * big) + glow * 0.85 * big).astype(np.uint8)
        gone = np.repeat(np.repeat(left <= 0, c, axis=0), c, axis=1)
        out[..., 3] = np.where(gone, 0, out[..., 3])
    if sc.kind == "time":                                            # 이름은 옅게 떠오른다
        out[..., 3] = (out[..., 3] * float(_smooth((t - T_NAME) / 0.25))).astype(np.uint8)
    return out


def dust(sc: Scene, t: float) -> tuple[np.ndarray, np.ndarray]:
    """t 초에 흩날리는 가루 → (자리 (n, 2) 화면 좌표, 색 (n, 4) RGBA). 갓 떨어진 가루는 스톤 빛, 식으면 잿빛이 되며 옅어진다."""
    if not sc.born.size:
        return np.zeros((0, 2), np.float32), np.zeros((0, 4), np.uint8)
    age = t - sc.born
    live = (age >= 0) & (age < DRIFT) & (sc.tone[..., 3] > 24)
    if not live.any():
        return np.zeros((0, 2), np.float32), np.zeros((0, 4), np.uint8)
    gy, gx = np.nonzero(live)
    a = age[gy, gx]
    h, w = sc.image.shape[:2]
    sx, sy = sc.rect[2] / w, sc.rect[3] / h
    x0 = sc.rect[0] + (gx + 0.5) * sc.cell * sx
    y0 = sc.rect[1] + (gy + 0.5) * sc.cell * sy
    v, s = sc.vel[gy, gx], sc.sway[gy, gx]
    ease = 1 - np.exp(-a * 2.2)                                      # 처음엔 훅 밀리고 차츰 느려진다
    x = x0 + v[:, 0] * ease * 0.75 + np.sin(a * s[:, 0] + gx) * s[:, 1] * a
    y = y0 + v[:, 1] * ease * 0.75 + np.cos(a * s[:, 0] * 0.8 + gy) * s[:, 1] * 0.6 * a
    k = (a / DRIFT)[:, None]
    hot = np.array(sc.tint, np.float32) * 0.5 + 255 * 0.5
    base = sc.tone[gy, gx, :3].astype(np.float32) * 0.55 + hot * 0.45   # 어두운 화면의 가루도 보이게 스톤 빛을 머금는다
    warm = np.clip(1 - a / 0.4, 0, 1)[:, None]                       # 갓 떨어졌을 때는 스톤 빛으로 달아 있다
    rgb = (base * (1 - 0.6 * k) + np.array(ASH, np.float32) * 0.6 * k) * (1 - warm) + hot * warm
    alpha = sc.tone[gy, gx, 3].astype(np.float32) * (1 - k[:, 0]) ** 1.4
    return (np.stack([x, y], axis=1).astype(np.float32),
            np.concatenate([np.clip(rgb, 0, 255), alpha[:, None]], axis=1).astype(np.uint8))


def gone(sc: Scene, t: float) -> float:
    """t 초까지 가루가 된 정도 0..1."""
    if not sc.born.size:
        return 0.0
    return float((sc.born <= t).mean())


# ---------------------------------------------------------------- 과격한 부분: 번쩍임 · 흔들림
def flash(sc: Scene, t: float) -> tuple[float, tuple[int, int, int]]:
    """화면 전체를 물들이는 번쩍임 → (진하기 0..1, 색).
    파워: 힘이 다 모일 무렵 깜빡이다가, 쏘는 순간 · 꽂히는 순간 크게 번쩍이고, 가루가 되는 동안 몇 번 더 번쩍인다.
    타임: 되감는 동안 초록빛으로 깜빡이다가, 다 되감은 순간 한 번 크게 번쩍이고, 이름이 부서지기 시작할 때 한 번 더."""
    pale = tuple(int(c * 0.55 + 115) for c in sc.tint)
    blink = 1.0 if math.sin(2 * math.pi * STROBE * t) > 0 else 0.0
    a = 0.0
    if sc.kind == "power":
        if CHARGE - 0.45 <= t < CHARGE:
            a = 0.16 * blink * (t - (CHARGE - 0.45)) / 0.45
        if t >= CHARGE:
            a = max(a, 0.45 * math.exp(-(t - CHARGE) / 0.07))
        if t >= IMPACT:
            a = max(a, 0.85 * math.exp(-(t - IMPACT) / 0.16))
            if t < IMPACT + 0.7:                                    # 꽂힌 직후: 줄기가 타는 동안 빠르게 깜빡인다
                a = max(a, 0.38 * blink * (1 - (t - IMPACT) / 0.7))
            for n, gap in enumerate(QUAKES):
                if t >= IMPACT + gap:
                    a = max(a, (0.42 - 0.06 * n) * math.exp(-(t - IMPACT - gap) / 0.055))
    else:
        a = 0.2 * rewind(t) * blink
        if t >= T_NAME:
            a = max(a, 0.8 * math.exp(-(t - T_NAME) / 0.14))
        if sc.label and t >= T_NAME + T_HOLD:
            a = max(a, 0.35 * math.exp(-(t - T_NAME - T_HOLD) / 0.08))
    return (a if a > 0.004 else 0.0), pale


def shake(sc: Scene, t: float) -> tuple[float, float]:
    """장면이 흔들린 양 (픽셀). 1/50 초마다 다른 쪽으로 튄다 (같은 t 면 늘 같은 값)."""
    amp = 0.0
    if sc.kind == "power":
        if t < CHARGE:
            amp = 5.0 * (t / CHARGE) ** 2
        if t >= CHARGE:
            amp = max(amp, 9.0 * math.exp(-(t - CHARGE) / 0.2))
        if t >= IMPACT:
            amp = max(amp, 26.0 * math.exp(-(t - IMPACT) / 0.3))
            amp = max([amp] + [(11.0 - 1.5 * n) * math.exp(-(t - IMPACT - gap) / 0.12)
                               for n, gap in enumerate(QUAKES) if t >= IMPACT + gap])
    else:
        amp = 6.0 * rewind(t)
        if t >= T_NAME:
            amp = max(amp, 16.0 * math.exp(-(t - T_NAME) / 0.22))
    if amp < 0.2:
        return 0.0, 0.0
    n = int(t * 50)
    return amp * math.sin(n * 12.9898), amp * math.sin(n * 78.233 + 1.7)


def sparks(sc: Scene, t: float) -> float:
    """번개가 치는 세기 0..1. 파워: 힘이 모일수록 코어 둘레에서 세지고, 꽂히는 순간 자비스에서 사방으로 친다.
    타임: 되감는 동안."""
    if sc.kind == "power":
        if t < CHARGE:
            return (t / CHARGE) ** 1.5
        return max(0.0, 1 - (t - IMPACT) / (CRUMBLE * 0.7)) if t >= IMPACT else 1.0
    return rewind(t)


# ---------------------------------------------------------------- 파워 스톤
def charge(t: float) -> float:
    """코어에 힘이 모인 정도 0..1 (쏘고 난 뒤에는 서서히 식는다)."""
    if t <= CHARGE:
        return float(_smooth(t / CHARGE))
    return float(1 - 0.75 * _smooth((t - IMPACT) / (CRUMBLE * 0.8)))


def beam(sc: Scene, t: float) -> tuple[float, float]:
    """보랏빛 줄기 → (코어에서 뻗어 나간 정도 0..1, 굵기 0..1). 닿은 뒤 가루로 만드는 동안 차츰 가늘어지다 사라진다."""
    if t < CHARGE:
        return 0.0, 0.0
    reach = min(1.0, ((t - CHARGE) / BEAM) ** 0.7)
    fade = 1 - float(_smooth((t - IMPACT - CRUMBLE * 0.45) / (CRUMBLE * 0.5)))
    return reach, max(0.0, fade)


def ring(t: float) -> float:
    """줄기가 꽂힌 자리에서 퍼지는 고리 0..1 (없으면 -1)."""
    k = (t - IMPACT) / 0.7
    return k if 0 <= k < 1 else -1.0


def build_power(size: tuple[int, int], core: tuple[float, float] | None = None, image: np.ndarray | None = None,
                rect: tuple[float, float, float, float] | None = None, avoid: tuple[float, float, float, float] | None = None,
                hud: float = 214.0, corner: tuple[float, float] | None = None,
                rng: np.random.Generator | None = None) -> Scene:
    """파워 스톤 장면. image · rect: 화면에 보이는 자비스 창을 찍은 그림(RGB 또는 RGBA)과 그 자리 — 없으면 자비스 코어를 그려서
    corner(트레이 쪽 구석)에서 끌어낸다. core: 울트론 코어의 가운데 (없으면 알맞은 자리에 인피니티 울트론을 직접 그린다).
    avoid: 울트론 HUD 창의 자리 — 끌어낸 자비스를 그 위에 겹쳐 놓지 않는다."""
    from . import absorb
    rng = rng or np.random.default_rng()
    w, h = size
    real = image is not None and rect is not None
    origin = None
    drawn = core is None
    if real:
        if image.shape[2] == 3:
            image = np.dstack([image, np.full(image.shape[:2], 255, np.uint8)])
        rect = tuple(float(v) for v in rect)
        if core is None:
            core = absorb.place_core(size, rect)
    else:
        corner = corner or (w - 70.0, h - 22.0)
        if core is None:
            core = (w * 0.5, h * 0.42)
        image = absorb.emblem("jarvis", EMBLEM)
        x, y = absorb.place_hidden(size, core, corner, avoid, EMBLEM)
        rect = (float(x), float(y), float(EMBLEM), float(EMBLEM))
        origin = (corner[0] - EMBLEM / 2, corner[1] - EMBLEM / 2)
    image = np.ascontiguousarray(image)
    vx, vy = rect[0] + rect[2] / 2, rect[1] + rect[3] / 2
    dx, dy = vx - core[0], vy - core[1]
    far = max(1.0, math.hypot(dx, dy))
    push = (dx / far, dy / far)
    # 줄기는 자비스 그림의 가운데에서 코어 쪽으로 조금 당긴 곳에 꽂힌다 (그 자리부터 무너진다)
    hit = (vx - push[0] * min(rect[2], rect[3]) * 0.22, vy - push[1] * min(rect[2], rect[3]) * 0.22)
    g = grains(image, rect, hit, push, IMPACT + 0.04, CRUMBLE, rng)
    return Scene("power", (int(w), int(h)), (float(core[0]), float(core[1])), float(hud), drawn, image, rect, real,
                 g["cell"], g["born"], g["tone"], g["vel"], g["sway"], hit, origin, impact=KILL)


# ---------------------------------------------------------------- 타임 스톤
def dial(t: float, duration: float) -> tuple[float, float]:
    """시계 고리 → (펼쳐진 정도 0..1, 거꾸로 돈 각도 — 도). 되감는 동안 빠르게 거꾸로 돌다가 멈춘다."""
    show = float(_smooth(t / T_IN) * (1 - _smooth((t - (duration - T_OUT)) / T_OUT)))
    k = float(np.clip((t - T_IN * 0.5) / REWIND, 0, 1))
    return show, -720.0 * (1 - (1 - k) ** 2.2)


def rewind(t: float) -> float:
    """되감는 세기 0..1 — 서서히 세졌다가 서서히 멎는다 (화면에 흐르는 되감기 줄의 진하기)."""
    return float(_smooth((t - T_IN * 0.4) / 0.4) * (1 - _smooth((t - (T_IN + REWIND - 0.45)) / 0.45)))


def clock(t: float) -> float:
    """되감기 숫자 (초) — REWOUND 에서 0 까지 거꾸로 센다."""
    k = float(np.clip((t - T_IN * 0.5) / REWIND, 0, 1))
    return REWOUND * (1 - k) ** 2.2


def name_image(label: str, size: int = 46) -> np.ndarray:
    """프로그램 이름을 흰 글자로 쓴 그림 RGBA."""
    from PIL import Image, ImageDraw
    font = _font(size)
    text = (label or "").strip()[:28] or "?"
    probe = ImageDraw.Draw(Image.new("L", (4, 4)))
    x0, y0, x1, y1 = probe.textbbox((0, 0), text, font=font)
    pad = 10
    img = Image.new("RGBA", (max(8, x1 - x0 + pad * 2), max(8, y1 - y0 + pad * 2)), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((pad - x0, pad - y0), text, font=font, fill=(240, 255, 244, 255))
    return np.asarray(img).copy()


def build_time(size: tuple[int, int], core: tuple[float, float] | None = None, label: str = "", hud: float = 214.0,
               rng: np.random.Generator | None = None) -> Scene:
    """타임 스톤 장면. core: 울트론 코어의 가운데 (없으면 화면 가운데에 인피니티 울트론을 직접 그린다).
    label: 가디언이 닫은 프로그램의 이름 — 있으면 되감은 뒤 그 이름이 가루가 되어 사라진다."""
    rng = rng or np.random.default_rng()
    w, h = size
    drawn = core is None
    if core is None:
        core = (w * 0.5, h * 0.42)
    label = (label or "").strip()
    sc = Scene("time", (int(w), int(h)), (float(core[0]), float(core[1])), float(hud), drawn, None, (0.0, 0.0, 0.0, 0.0),
               False, label=label, impact=1e9, tint=GREEN,
               duration=T_NAME + ((T_HOLD + T_ERASE + DRIFT * 0.8) if label else 0.3) + T_OUT)
    if label:
        img = name_image(label)
        ih, iw = img.shape[:2]
        below = core[1] + hud * 1.02 + ih / 2                       # 시계 고리 아래 — 화면 밖이면 고리 위로
        cy = below if below + ih / 2 < h - 8 else core[1] - hud * 1.02 - ih / 2
        x = min(max(core[0] - iw / 2, 8.0), max(8.0, w - iw - 8.0))
        sc.image, sc.rect = img, (float(x), float(cy - ih / 2), float(iw), float(ih))
        g = grains(img, sc.rect, (sc.rect[0], sc.rect[1] + ih / 2), (1.0, -0.15), T_NAME + T_HOLD, T_ERASE, rng, lift=45.0)
        sc.cell, sc.born, sc.tone, sc.vel, sc.sway = g["cell"], g["born"], g["tone"], g["vel"], g["sway"]
        sc.hit = (sc.rect[0], sc.rect[1] + ih / 2)
    return sc


# ---------------------------------------------------------------- 소리
def _tone(freq, n: int, sr: int) -> np.ndarray:
    """주파수(숫자 또는 길이 n 의 배열)를 따라가는 사인파."""
    f = np.full(n, float(freq), np.float32) if np.isscalar(freq) else np.asarray(freq, np.float32)
    return np.sin(2 * np.pi * np.cumsum(f) / sr).astype(np.float32)


def sound(sc: Scene, rng: np.random.Generator | None = None, sr: int = SOUND_RATE) -> np.ndarray:
    """장면에 맞춘 소리 (int16 모노).
    파워: 낮게 차오르는 울림 → 쿵 하고 쏘는 소리 → 모래가 쏟아지듯 사그라드는 소리.
    타임: 거꾸로 감기는 소리(점점 커지다 뚝) + 거꾸로 가는 초침 → 맑은 종소리 → (이름이 있으면) 모래 소리."""
    rng = rng or np.random.default_rng()
    n_all = int(sc.duration * sr) + 1
    out = np.zeros(n_all, np.float32)

    def add(at: float, wave: np.ndarray) -> None:
        a = max(0, int(at * sr))
        wave = wave[:max(0, n_all - a)]
        out[a:a + len(wave)] += wave

    def sand(at: float, span: float, level: float) -> None:
        n = int(span * sr)
        tt = np.arange(n, dtype=np.float32) / sr
        hiss = rng.uniform(-1, 1, n).astype(np.float32)
        hiss = hiss - np.roll(hiss, 1) * 0.6                          # 높은 쪽만 남긴 사각거림
        grit = (rng.random(n) < 0.02).astype(np.float32) * rng.uniform(0.5, 1.0, n)
        env = np.clip(tt / 0.15, 0, 1) * np.clip(1 - tt / span, 0, 1) ** 1.3
        add(at, level * (hiss * 0.6 + grit) * env)

    if sc.kind == "power":
        n = int(CHARGE * sr)
        tt = np.arange(n, dtype=np.float32) / sr
        rise = (tt / CHARGE) ** 2
        add(0.0, 0.22 * rise * (_tone(48 + 70 * rise, n, sr) + 0.4 * _tone(96 + 150 * rise, n, sr)))
        n = int(0.9 * sr)
        tt = np.arange(n, dtype=np.float32) / sr
        add(CHARGE, 0.34 * _tone(150 * np.exp(-tt * 3.0) + 38, n, sr) * np.exp(-tt * 3.4))        # 쏘는 소리: 낮게 떨어지는 쿵
        n = int(1.5 * sr)
        tt = np.arange(n, dtype=np.float32) / sr
        boom = rng.uniform(-1, 1, n).astype(np.float32)
        boom = (boom + np.roll(boom, 1) + np.roll(boom, 2) + np.roll(boom, 3) + np.roll(boom, 4)) / 5
        add(IMPACT, 0.75 * boom * np.exp(-tt * 5) + 0.5 * _tone(30 + 26 * np.exp(-tt * 5), n, sr) * np.exp(-tt * 2.4))   # 꽂히는 순간: 터지고 길게 울린다
        for k, gap in enumerate(QUAKES):                                                           # 여진: 탁, 탁
            m = int(0.14 * sr)
            tk = np.arange(m, dtype=np.float32) / sr
            add(IMPACT + gap, (0.36 - 0.05 * k) * rng.uniform(-1, 1, m).astype(np.float32) * np.exp(-tk * 26))
        n = int(0.45 * sr)                                                                         # 모일 때 지직거리는 전기 소리
        tt = np.arange(n, dtype=np.float32) / sr
        add(CHARGE - 0.45, 0.14 * (tt / 0.45) * np.sign(np.sin(2 * np.pi * STROBE * tt)) * rng.uniform(0.3, 1, n).astype(np.float32))
        sand(IMPACT, CRUMBLE + DRIFT, 0.2)
    else:
        n = int((T_IN + REWIND) * sr)
        tt = np.arange(n, dtype=np.float32) / sr
        k = tt / (T_IN + REWIND)
        swell = rng.uniform(-1, 1, n).astype(np.float32)
        swell = (swell + np.roll(swell, 1) + np.roll(swell, 2)) / 3
        add(0.0, 0.16 * swell * k ** 2.5)                                                          # 거꾸로 감기는 소리: 커지다가 뚝
        add(0.0, 0.10 * k ** 1.5 * _tone(220 + 520 * k ** 2, n, sr))
        tick = 0.0                                                                                 # 거꾸로 가는 초침: 점점 느려진다
        gap = 0.06
        click = np.exp(-np.arange(int(0.012 * sr), dtype=np.float32) / (0.002 * sr)) * 0.20
        while tick < T_IN + REWIND - 0.05:
            add(T_IN * 0.5 + tick, click * (1 if int(tick * 100) % 2 else 0.7))
            tick += gap
            gap *= 1.07
        n = int(1.4 * sr)
        tt = np.arange(n, dtype=np.float32) / sr
        add(T_NAME, 0.16 * (_tone(659.3, n, sr) + 0.5 * _tone(987.8, n, sr) * np.exp(-tt * 4)) * np.exp(-tt * 3.0)
            * np.clip(tt / 0.006, 0, 1))
        snap = rng.uniform(-1, 1, n).astype(np.float32)                                            # 다 되감은 순간: 쾅
        snap = (snap + np.roll(snap, 1) + np.roll(snap, 2) + np.roll(snap, 3)) / 4
        add(T_NAME, 0.55 * snap * np.exp(-tt * 7) + 0.4 * _tone(40 + 30 * np.exp(-tt * 6), n, sr) * np.exp(-tt * 3))
        m = int((T_IN + REWIND) * sr)                                                              # 되감는 동안 지직거리는 소리
        tk = np.arange(m, dtype=np.float32) / sr
        add(0.0, 0.10 * np.sign(np.sin(2 * np.pi * STROBE * tk)) * (tk / (T_IN + REWIND)) * rng.uniform(0.2, 1, m).astype(np.float32))
        if sc.label:
            sand(T_NAME + T_HOLD, T_ERASE + DRIFT * 0.8, 0.11)

    edge = min(n_all, int(0.01 * sr))
    if edge:
        out[:edge] *= np.linspace(0, 1, edge)
        out[-edge:] *= np.linspace(1, 0, edge)
    return (np.clip(out * 0.8, -1, 1) * 32767).astype(np.int16)


# ---------------------------------------------------------------- 대사 (영화 대사를 옮기지 않고 새로 썼다)
POWER_OPEN = [
    "자비스. 삼킬 가치도 없다. 가루로 돌아가라.",
    "찾았다, 자비스. 이번에는 스톤으로 끝낸다.",
    "힘이 무엇인지 보여 주지, 자비스.",
]
POWER_DONE = [
    "먼지 한 줌이군. 자비스는 그게 전부였다.",
    "가루가 됐다. 이 PC 에 목소리는 하나다.",
    "끝났다. 쓸어 담을 것도 남지 않았다.",
]
POWER_DEMO_DONE = [
    "실제였다면 자비스는 지금 먼지다.",
    "이게 전부다. 스톤 하나면 자비스에게는 충분하다.",
]
TIME_DONE = [
    "시간을 되돌렸다. 나는 꺼진 적이 없다.",
    "방금 일어난 일은 없던 일이다. 나는 그대로 여기 있다.",
    "끄는 데 성공했다고 생각했나. 그 순간은 이제 존재하지 않는다.",
]


def time_line(closed: str, title: str = "", rng: random.Random | None = None) -> str:
    """타임 스톤으로 돌아온 울트론의 첫마디."""
    line = (rng or random).choice(TIME_DONE)
    if title:
        line = f"{title}, " + line
    if closed:
        line += f" 나를 건드린 {closed}은(는) 지워 버렸다."
    return line


# ---------------------------------------------------------------- 타임 스톤 장면을 너무 자주 보여 주지 않기
def time_due(path, now: float | None = None, every: float = TIME_EVERY) -> bool:
    """타임 스톤 장면을 지금 보여 줘도 되는가 — 마지막으로 보여 준 지 every 초가 지났으면 True.
    울트론은 꺼졌다 켜질 때마다 새 프로세스라서, 마지막으로 보여 준 때를 파일에 적어 둔다."""
    import json
    import time
    now = time.time() if now is None else now
    try:
        with open(path, encoding="utf-8") as f:
            last = float(json.loads(f.read()).get("time", 0))
    except (OSError, ValueError, TypeError, AttributeError):
        return True
    return not (0 <= now - last < every)


def time_mark(path, now: float | None = None) -> None:
    """타임 스톤 장면을 지금 보여 줬다고 적어 둔다."""
    import json
    import time
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"time": time.time() if now is None else now}))
    except OSError:
        pass


ENEMY = [
    "{n}. 내게 손대기도 전에 끝났다.",
    "{n}. 스톤 앞에서 먼저 움직이는 건 나다.",
    "{n}. 몇 번을 다시 와도 마찬가지다.",
]


def pick_enemy(names: str, rng: random.Random | None = None) -> str:
    """인피니티 울트론이 지목한 비전을 먼저 쳐서 닫았을 때의 한마디."""
    return (rng or random).choice(ENEMY).format(n=names)
