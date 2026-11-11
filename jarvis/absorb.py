"""자비스 흡수 연출 — 자비스를 그냥 끄지 않고, 공격해서 울트론 안으로 빨아들인다 (rival.py 가 찾은 자비스를 끄는 동안).

장면 (5초 남짓):
  조준   자비스 둘레로 꺾쇠가 좁혀 들고, 울트론 코어가 달아오른다 (자비스 화면은 이때부터 얼어붙는다)
  습격   코어에서 검붉은 케이블 여러 가닥이 손아귀처럼 휘어져 뻗어 나가 자비스를 꿰뚫는다
         (첫 가닥이 꽂히는 순간 실제 자비스 프로세스를 끈다 — app.py)
  잠식   꿰뚫린 자리부터 붉은 얼룩이 번져 자비스 화면을 물들인다
  흡수   화면이 잘게 조각나 꿰뚫린 자리로 빨려 들고, 케이블을 타고 코어로 흘러든다
  완료   케이블이 코어로 감겨 들어가고, 코어가 한 번 크게 숨 쉰다

자비스 창이 화면에 보이면 그 창의 실제 모습을 찍어 쓰고, 트레이로 숨어 있으면 자비스 코어 그림을 화면 구석에서 끌어낸다.
실제로 하는 일은 자비스 프로세스를 끄는 것 하나뿐이고 나머지는 전부 그림이다 (입력 통과 · 캡처 제외 덮개 창 — absorb_view.py).

빛 민감성: 번쩍이는 장면을 넣지 않았다 — 밝기와 색은 천천히 바뀌고, 넓은 면을 덮는 것은 붉게 물든 자비스 화면뿐이다.
넓은 면(화면 가로 · 세로의 1/3)의 밝기나 붉은빛이 크게 오르내리는 순간이 1초에 3번을 넘지 않는지는
시험에서 장면 전체를 그려서 확인한다 (flash_check).

이 파일은 장면의 뼈대(시간표 · 케이블 · 조각 · 그림 · 소리)만 만든다 (numpy · PIL — Qt 없이 시험할 수 있다).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .glitch import _LIN, FLASH_DARK, FLASH_DELTA, SOUND_RATE, _font, regions

# ---------------------------------------------------------------- 시간표 (초)
LOCK = 0.70                    # 조준이 끝나는 때
STRIKE = 0.55                  # 첫 케이블이 뻗기 시작하는 때
REACH = 0.36                   # 한 가닥이 닿기까지
STAGGER = 0.065                # 가닥마다 이만큼씩 늦게 떠난다
IMPACT = STRIKE + REACH        # 첫 가닥이 꽂히는 때 — 이때 실제 자비스를 끈다
FREEZE = 0.12                  # 이때부터 찍어 둔 자비스 그림이 실제 창을 가린다 — 조준당한 자비스는 얼어붙고, 꺼지는 모습은 보이지 않는다
INFECT = 1.40                  # 잠식에 걸리는 시간
DRAIN = IMPACT + INFECT + 0.02 # 조각이 떠나기 시작하는 때
DRAIN_SPAN = 1.20              # 마지막 조각이 떠나기까지
PULL = 0.20                    # 조각이 꿰뚫린 자리로 빨려 드는 시간
RIDE = 0.46                    # 케이블을 타고 코어까지 가는 시간
DRAINED = DRAIN + DRAIN_SPAN + PULL + RIDE     # 마지막 조각이 코어에 닿는 때
RETRACT = DRAINED - 0.12       # 케이블이 감겨 들어가기 시작하는 때
RETRACT_TIME = 0.55
SWELL = DRAINED - 0.05         # 코어가 크게 숨 쉬기 시작하는 때
SWELL_UP, SWELL_DOWN = 0.40, 0.65
END = 5.30
DRAG = 0.85                    # 숨어 있던 자비스를 구석에서 끌어내는 시간
DRAG_HOLD = 0.50               # 끌려 나온 자비스는 이만큼 지난 뒤부터 잠식된다 (푸른 코어가 잠깐은 온전히 보이게)
STAGES = 12                    # 잠식 단계 수 (단계 사이는 겹쳐 그려 부드럽게 넘어간다)
MAX_SPRITE = 760               # 자비스 그림의 긴 변이 이보다 크면 줄여서 만든다 (메모리 · 시간)
EMBLEM = 210                   # 그려 낸 자비스 코어의 크기
RED_DELTA = 20 / 320           # 넓은 면의 '짙은 붉은빛' 평균이 이만큼 바뀌면 크게 바뀐 것 (WCAG 의 붉은 번쩍임 기준값)


def _smooth(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def _back(x: float) -> float:
    """끝에서 살짝 지나쳤다가 돌아오는 움직임 (끌려 나오다 덜컥 멈추는 느낌)."""
    x = min(max(x, 0.0), 1.0) - 1
    return 1 + 2.2 * x * x * x + 1.2 * x * x


# ---------------------------------------------------------------- 장면
@dataclass
class Scene:
    size: tuple[int, int]                        # 장면이 펼쳐지는 화면의 크기 (논리 픽셀)
    core: tuple[float, float]                    # 울트론 코어의 중심
    core_drawn: bool                             # 덮개가 코어를 직접 그린다 (울트론 HUD 가 이 화면에 보이지 않을 때)
    rect: tuple[float, float, float, float]      # 자비스 그림이 놓이는 자리 (x, y, w, h)
    origin: tuple[float, float] | None           # 숨어 있던 자비스: 끌려 나오기 전 왼쪽 위 좌표. None = 처음부터 제자리
    real: bool                                   # 실제 자비스 창을 찍은 그림인가 (아니면 그려 낸 자비스 코어)
    stages: list[np.ndarray]                     # 잠식 단계별 그림 RGBA (0 = 원래 모습 … 끝 = 전부 물듦)
    starts: np.ndarray                           # (m, 2) 케이블의 코어 쪽 끝
    c1: np.ndarray                               # (m, 2) 코어 쪽 조절점
    c2: np.ndarray                               # (m, 2) 자비스 쪽 조절점 — 꽂힌 자리에서 본 위치
    hits: np.ndarray                             # (m, 2) 꽂히는 자리 — 자비스 그림 안의 좌표
    t0: np.ndarray                               # (m,) 뻗기 시작하는 때
    sway: np.ndarray                             # (m, 3) 흔들림 (크기, 빠르기, 위상)
    normals: np.ndarray                          # (m, 2) 흔들리는 방향
    cells: np.ndarray                            # (k, 4) 조각의 자리 — 자비스 그림 안의 (x, y, w, h)
    leave: np.ndarray                            # (k,) 조각이 떠나는 때
    via: np.ndarray                              # (k,) 타고 갈 케이블 번호
    tint: np.ndarray                             # (k, 3) 케이블을 탈 때의 색
    infect_at: float = IMPACT                    # 잠식이 시작되는 때
    infect_time: float = INFECT                  # 잠식에 걸리는 시간
    duration: float = END
    impact: float = IMPACT

    @property
    def bounds(self) -> tuple[int, int, int, int]:
        """장면이 그려지는 영역 (x, y, w, h) — 덮개 창을 이만큼만 띄운다 (화면 전체를 매번 다시 그리지 않게)."""
        w, h = self.size
        x, y, rw, rh = self.rect
        pts = [np.array([[x, y - 46], [x + max(rw, 300), y + rh + 8]]),
               np.array([[self.core[0] - 215, self.core[1] - 215], [self.core[0] + 215, self.core[1] + 215]])]
        if self.origin is not None:
            pts.append(np.array([self.origin, [self.origin[0] + rw, self.origin[1] + rh]]))
        for t in np.linspace(STRIKE, RETRACT + RETRACT_TIME, 16):
            pts += cables(self, float(t), n=14)
        allp = np.vstack(pts)
        x0, y0 = np.floor(allp.min(axis=0) - 40)
        x1, y1 = np.ceil(allp.max(axis=0) + 40)
        x0, y0, x1, y1 = max(0, int(x0)), max(0, int(y0)), min(w, int(x1)), min(h, int(y1))
        return x0, y0, max(1, x1 - x0), max(1, y1 - y0)


# ---------------------------------------------------------------- 움직임
def infection(sc: Scene, t: float) -> float:
    """잠식이 얼마나 번졌나 0..1."""
    x = min(max((t - sc.infect_at) / sc.infect_time, 0.0), 1.0)
    return 1 - (1 - x) ** 1.4


def victim_at(sc: Scene, t: float) -> tuple[float, float, float]:
    """자비스 그림의 왼쪽 위 좌표와 불투명도. 케이블이 꽂힐 때마다 움찔하고, 숨어 있던 자비스는 구석에서 끌려 나온다."""
    x, y = sc.rect[0], sc.rect[1]
    if sc.origin is None:
        alpha = 1.0 if t >= FREEZE else 0.0
    else:
        e = _back((t - IMPACT) / DRAG)
        x, y = sc.origin[0] + (x - sc.origin[0]) * e, sc.origin[1] + (y - sc.origin[1]) * e
        alpha = min(max((t - IMPACT) / 0.22, 0.0), 1.0)
    dt = t - (sc.t0 + REACH)
    live = (dt >= 0) & (dt < 0.32)
    if live.any():
        push = 7.0 * np.exp(-dt[live] / 0.07) * np.cos(dt[live] * 70)
        d = -sc.c2[live] / np.maximum(np.linalg.norm(sc.c2[live], axis=1, keepdims=True), 1e-6)
        ox, oy = (d * push[:, None]).sum(axis=0)
        x, y = x + float(ox), y + float(oy)
    return float(x), float(y), float(alpha)


def controls(sc: Scene, t: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """그 순간 케이블들의 곡선 조절점 (각 (m, 2)). 케이블은 살아 있는 것처럼 천천히 꿈틀거린다."""
    vx, vy, _ = victim_at(sc, t)
    amp, rate, phase = sc.sway[:, 0], sc.sway[:, 1], sc.sway[:, 2]
    p3 = sc.hits + (vx, vy)
    p1 = sc.c1 + sc.normals * (amp * np.sin(rate * t + phase))[:, None]
    p2 = p3 + sc.c2 + sc.normals * (amp * 0.8 * np.cos(rate * 0.8 * t + phase * 1.7))[:, None]
    return sc.starts, p1, p2, p3


def _bezier(p0, p1, p2, p3, u):
    u = np.asarray(u, np.float64)[..., None]
    v = 1 - u
    return v * v * v * p0 + 3 * v * v * u * p1 + 3 * v * u * u * p2 + u * u * u * p3


def extent(sc: Scene, t: float) -> np.ndarray:
    """케이블마다 지금 뻗어 있는 정도 0..1 (처음엔 느리다가 휙 꽂히고, 끝나면 코어로 감겨 들어간다)."""
    grow = np.clip((t - sc.t0) / REACH, 0, 1) ** 2.4
    return grow * (1 - _smooth((t - RETRACT) / RETRACT_TIME))


def cables(sc: Scene, t: float, n: int = 44) -> list[np.ndarray]:
    """지금 보이는 케이블들의 꺾은선 (각 (점 수, 2)). 아직 뻗지 않았거나 다 감긴 가닥은 빈 배열."""
    p0, p1, p2, p3 = controls(sc, t)
    out = []
    for i, hi in enumerate(extent(sc, t)):
        if hi < 0.01:
            out.append(np.zeros((0, 2)))
            continue
        u = np.linspace(0, hi, max(2, int(n * hi) + 1))
        out.append(_bezier(p0[i], p1[i], p2[i], p3[i], u))
    return out


def pieces(sc: Scene, t: float) -> dict:
    """조각들의 지금 상태. phase: 0 제자리 · 1 꿰뚫린 자리로 빨려 드는 중 · 2 케이블을 타는 중 · 3 흡수됨."""
    dt = t - sc.leave
    a = np.clip(dt / PULL, 0, 1) ** 2
    b = np.clip((dt - PULL) / RIDE, 0, 1)
    be = _smooth(b)
    vx, vy, _ = victim_at(sc, t)
    p0, p1, p2, p3 = controls(sc, t)
    center = sc.cells[:, :2] + sc.cells[:, 2:] / 2 + (vx, vy)
    v = sc.via
    pulled = center + (p3[v] - center) * a[:, None]
    riding = _bezier(p0[v], p1[v], p2[v], p3[v], 1 - be)
    tail = _bezier(p0[v], p1[v], p2[v], p3[v], np.minimum(1.0, 1 - be + 0.05))     # 지나온 쪽으로 조금 뒤
    pulling = dt < PULL
    phase = np.where(dt < 0, 0, np.where(pulling, 1, np.where(dt < PULL + RIDE, 2, 3)))
    return {"phase": phase, "pos": np.where(pulling[:, None], pulled, riding), "tail": tail,
            "scale": np.where(pulling, 1 - 0.5 * a, 0.5 - 0.34 * be),
            "alpha": np.where(b > 0.85, (1 - b) / 0.15, 1.0)}


def heat(sc: Scene, t: float) -> float:
    """코어가 삼킨 조각의 비율 0..1."""
    return float(np.mean(t - sc.leave >= PULL + RIDE)) if len(sc.leave) else 0.0


def swell(t: float) -> float:
    """다 삼킨 뒤 코어가 한 번 크게 부풀었다 가라앉는 정도 0..1 (0.4초에 걸쳐 오르고 0.65초에 걸쳐 내린다)."""
    s = t - SWELL
    if s <= 0:
        return 0.0
    return float(_smooth(s / SWELL_UP)) if s < SWELL_UP else float(1 - _smooth((s - SWELL_UP) / SWELL_DOWN))


# ---------------------------------------------------------------- 그림: 그려 낸 코어 (자비스 · 울트론)
def emblem(kind: str, size: int) -> np.ndarray:
    """코어 그림 RGBA. kind 'jarvis' = 푸른 고리 코어 (트레이에 숨어 있던 자비스), 'ultron' = 붉은 코어 (HUD 가 안 보일 때)."""
    from PIL import Image, ImageDraw
    k = 3
    s = size * k
    c = s / 2
    ink = (62, 230, 255) if kind == "jarvis" else (255, 45, 63)
    dark = (3, 18, 26) if kind == "jarvis" else (24, 3, 7)
    yy, xx = np.mgrid[0:s, 0:s]
    r = np.hypot(xx - c, yy - c) / c
    halo = np.zeros((s, s, 4), np.uint8)
    halo[..., :3] = ink
    halo[..., 3] = (np.clip(1 - r, 0, 1) ** 2 * 120).astype(np.uint8)
    img = Image.fromarray(halo, "RGBA")
    d = ImageDraw.Draw(img)

    def ring(rad: float, width: float, alpha: int = 255, start: float = 0, end: float = 360) -> None:
        box = [c - rad * c, c - rad * c, c + rad * c, c + rad * c]
        d.arc(box, start, end, fill=ink + (alpha,), width=max(1, int(width * c)))

    def disc(rad: float, fill) -> None:
        d.ellipse([c - rad * c, c - rad * c, c + rad * c, c + rad * c], fill=fill)

    disc(0.80, dark + (236,))
    ring(0.82, 0.030)
    for i in range(48 if kind == "jarvis" else 60):               # 눈금 · 톱니
        a = 2 * math.pi * i / (48 if kind == "jarvis" else 60)
        r0, r1 = (0.66, 0.73) if kind == "jarvis" else (0.84, 0.92)
        d.line([c + r0 * c * math.cos(a), c + r0 * c * math.sin(a), c + r1 * c * math.cos(a), c + r1 * c * math.sin(a)],
               fill=ink + (200,), width=max(1, int(0.014 * c) if kind == "jarvis" else int(0.03 * c)))
    for i in range(3):
        ring(0.60, 0.045, 150, i * 120 + 12, i * 120 + 100)
    inner = 0.52 if kind == "jarvis" else 0.40                     # 자비스는 이름이 길어 가운데 원판이 넓다
    ring(inner, 0.022)
    disc(inner - 0.03, dark + (245,))
    if kind == "jarvis":
        text, ts = "J.A.R.V.I.S", int(0.066 * s)
        d.line([c - 0.30 * c, c + 0.15 * c, c + 0.30 * c, c + 0.15 * c], fill=ink + (220,), width=max(1, int(0.012 * c)))
    else:
        text, ts = "ULTRON", int(0.10 * s)
        for sx in (-1, 1):                                        # 안쪽으로 치켜 내려간 두 눈
            d.polygon([(c + sx * 0.30 * c, c - 0.20 * c), (c + sx * 0.07 * c, c - 0.05 * c),
                       (c + sx * 0.09 * c, c + 0.02 * c), (c + sx * 0.31 * c, c - 0.11 * c)], fill=(255, 96, 88, 255))
    f = _font(ts)
    box = d.textbbox((0, 0), text, font=f)
    ty = c - (box[3] - box[1]) / 2 - box[1] + (0 if kind == "jarvis" else 0.17 * c)
    d.text((c - (box[2] - box[0]) / 2 - box[0], ty), text, fill=(235, 250, 255, 255) if kind == "jarvis" else (255, 226, 226, 255),
           font=f)
    return np.asarray(img.resize((size, size), Image.LANCZOS))


# ---------------------------------------------------------------- 그림: 잠식 단계
def _noise(h: int, w: int, cell: float, rng) -> np.ndarray:
    """부드러운 얼룩 무늬 0..1 (잠식이 자로 잰 듯한 원으로 번지지 않게)."""
    from PIL import Image
    gh, gw = max(2, int(h / cell) + 2), max(2, int(w / cell) + 2)
    small = Image.fromarray(rng.random((gh, gw)).astype(np.float32), "F")
    return np.asarray(small.resize((w, h), Image.BICUBIC), np.float32).clip(0, 1)


def _field(h: int, w: int, hits: np.ndarray, delays: np.ndarray, rng) -> np.ndarray:
    """화소마다 잠식되는 때 0..1 — 꿰뚫린 자리에서 가까울수록 먼저, 늦게 꽂힌 가닥의 둘레는 그만큼 늦게."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    diag = math.hypot(w, h)
    f = np.full((h, w), np.inf, np.float32)
    for (hx, hy), delay in zip(hits, delays):
        f = np.minimum(f, delay + np.hypot(xx - hx, yy - hy) / (diag * 0.55 * rng.uniform(0.8, 1.25)))
    f += 0.10 * _noise(h, w, max(5.0, diag / 30), rng) + 0.09 * _noise(h, w, max(12.0, diag / 9), rng)
    f -= f.min()
    return f / max(float(f.max()), 1e-6) * 0.96


def _stages(img: np.ndarray, field: np.ndarray, rng, n: int = STAGES) -> list[np.ndarray]:
    """잠식 단계별 그림. 물든 자리는 어두운 붉은 단색 + 주사선 + 가로로 어긋난 띠, 번지는 경계는 달아오른 선."""
    h, w, _ = img.shape
    rgb = img[..., :3].astype(np.float32)
    y = (0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]) / 255
    for _ in range(max(3, h // 40)):                               # 물든 모습은 군데군데 옆으로 어긋나 있다
        bh = int(rng.integers(2, max(3, h // 22)))
        y0 = int(rng.integers(0, max(1, h - bh)))
        y[y0:y0 + bh] = np.roll(y[y0:y0 + bh], int(rng.integers(-w // 14 - 1, w // 14 + 2)), axis=1)
    red = np.stack([24 + 222 * y, 3 + 40 * y, 7 + 50 * y], axis=-1)
    red[::3] *= 0.78
    hot = np.array([255, 132, 92], np.float32)
    edge = 0.035
    out = [img.copy()]
    for k in range(1, n + 1):
        thr = k / n
        if k == n:
            m, front = np.ones((h, w, 1), np.float32), np.zeros((h, w, 1), np.float32)
        else:
            m = np.clip((thr - field) / edge + 0.5, 0, 1)[..., None]
            front = (np.clip(1 - np.abs(thr - field) / (edge * 1.6), 0, 1) * 0.9)[..., None]
        c = rgb * (1 - m) + red * m
        c = c * (1 - front) + hot * front
        stage = np.empty_like(img)
        stage[..., :3] = c.clip(0, 255).astype(np.uint8)
        stage[..., 3] = img[..., 3]
        out.append(stage)
    return out


def _cells(w: float, h: float, hits: np.ndarray, last: np.ndarray, scale: float, rng):
    """자비스 그림을 조각으로 나눈다 → (자리, 떠나는 때, 타고 갈 케이블, 색). 꿰뚫린 자리에서 가까운 조각부터 떠난다."""
    c = int(max(14, round(math.sqrt(w * h / 560))))
    rects, tints = [], []
    for y0 in range(0, int(math.ceil(h)), c):
        for x0 in range(0, int(math.ceil(w)), c):
            cw, ch = min(c, w - x0), min(c, h - y0)
            if cw < 2 or ch < 2:
                continue
            part = last[int(y0 * scale):max(int(y0 * scale) + 1, int((y0 + ch) * scale)),
                        int(x0 * scale):max(int(x0 * scale) + 1, int((x0 + cw) * scale))]
            if part.size == 0 or part[..., 3].mean() < 24:        # 그림이 없는 자리 (둥근 코어의 귀퉁이)
                continue
            rects.append((x0, y0, cw, ch))
            tints.append(part[..., :3].reshape(-1, 3).mean(axis=0) * 0.45 + np.array([255, 96, 80]) * 0.55)
    cells = np.array(rects, np.float64).reshape(-1, 4)
    center = cells[:, :2] + cells[:, 2:] / 2
    dist = np.linalg.norm(center[:, None, :] - hits[None, :, :], axis=2)
    via = dist.argmin(axis=1)
    near = dist.min(axis=1)
    leave = DRAIN + DRAIN_SPAN * (near / max(float(near.max()), 1e-6)) ** 0.9
    leave = np.clip(leave + rng.uniform(-0.04, 0.04, len(leave)), DRAIN, DRAIN + DRAIN_SPAN)
    return cells, leave, via, np.array(tints, np.float64).reshape(-1, 3)


# ---------------------------------------------------------------- 장면 만들기
def _hit_points(img: np.ndarray, w: float, h: float, scale: float, m: int, rng) -> np.ndarray:
    """케이블이 꽂힐 자리 m 곳 (자비스 그림 안의 좌표). 서로 떨어지게, 그림이 있는 자리로만 고른다."""
    cand = np.column_stack([rng.uniform(0.12, 0.88, 160) * w, rng.uniform(0.10, 0.90, 160) * h])
    ix = np.clip((cand[:, 0] * scale).astype(int), 0, img.shape[1] - 1)
    iy = np.clip((cand[:, 1] * scale).astype(int), 0, img.shape[0] - 1)
    cand = cand[img[iy, ix, 3] > 128]
    if len(cand) == 0:
        cand = np.array([[w / 2, h / 2]])
    chosen = [cand[np.argmin(np.hypot(cand[:, 0] - w * 0.5, cand[:, 1] - h * 0.36))]]   # 첫 가닥은 한가운데 위쪽 (코어 자리)
    while len(chosen) < m:
        d = np.min(np.linalg.norm(cand[:, None, :] - np.array(chosen)[None, :, :], axis=2), axis=1)
        chosen.append(cand[int(np.argmax(d))])
    return np.array(chosen)


def place_hidden(size: tuple[int, int], core: tuple[float, float], corner: tuple[float, float],
                 avoid: tuple[float, float, float, float] | None = None, sprite: int = EMBLEM) -> tuple[float, float]:
    """트레이에 숨어 있던 자비스를 끌어다 놓을 자리 (왼쪽 위 좌표).
    구석에서 가까운 곳 가운데, 울트론 HUD(avoid)에 가리지 않고 코어에서 케이블이 휘어 뻗을 만큼 떨어진 곳을 고른다."""
    w, h = size
    sx = -1 if corner[0] > w / 2 else 1
    sy = -1 if corner[1] > h / 2 else 1
    best, top = None, None
    for reach in (320, 400, 480, 560):
        for deg in (0, 18, 40, 65, 90):
            cx = corner[0] + sx * reach * math.cos(math.radians(deg))
            cy = corner[1] + sy * reach * math.sin(math.radians(deg))
            cx = min(max(cx, sprite / 2 + 16), w - sprite / 2 - 16)
            cy = min(max(cy, sprite / 2 + 16), h - sprite / 2 - 16)
            x, y = cx - sprite / 2, cy - sprite / 2
            clear = avoid is None or (x + sprite <= avoid[0] or x >= avoid[0] + avoid[2]
                                      or y + sprite <= avoid[1] or y >= avoid[1] + avoid[3])
            score = (clear, min(math.hypot(cx - core[0], cy - core[1]), 440.0), -reach, -deg)
            if top is None or score > top:
                best, top = (x, y), score
    return best


def place_core(size: tuple[int, int], rect: tuple[float, float, float, float]) -> tuple[float, float]:
    """울트론 HUD 가 이 화면에 없을 때 코어를 그릴 자리: 자비스에서 충분히 떨어진, 화면 안쪽의 한 곳."""
    w, h = size
    vx, vy = rect[0] + rect[2] / 2, rect[1] + rect[3] / 2
    spots = [(w * 0.5, h * 0.42), (w * 0.27, h * 0.45), (w * 0.73, h * 0.45), (w * 0.5, h * 0.22), (w * 0.5, h * 0.76)]
    for s in spots:
        if math.hypot(s[0] - vx, s[1] - vy) >= 400:
            return s
    return max(spots, key=lambda s: math.hypot(s[0] - vx, s[1] - vy))


def build(size: tuple[int, int], core: tuple[float, float] | None = None, image: np.ndarray | None = None,
          rect: tuple[float, float, float, float] | None = None, core_drawn: bool = False,
          corner: tuple[float, float] | None = None, avoid: tuple[float, float, float, float] | None = None,
          rng: np.random.Generator | None = None) -> Scene:
    """장면을 만든다.
    image · rect: 화면에 보이는 자비스 창을 찍은 그림(RGB 또는 RGBA)과 그 자리. 없으면 자비스 코어를 그려서 corner(트레이 쪽 구석)에서 끌어낸다.
    core: 울트론 코어의 중심. 없으면 알맞은 자리를 골라 코어를 직접 그린다.
    avoid: 울트론 HUD 창의 자리 — 끌어낸 자비스를 그 위에 겹쳐 놓지 않는다."""
    rng = rng or np.random.default_rng()
    w, h = size
    real = image is not None and rect is not None
    origin = None
    if real:
        if image.shape[2] == 3:
            image = np.dstack([image, np.full(image.shape[:2], 255, np.uint8)])
        rect = tuple(float(v) for v in rect)
        if core is None:
            core, core_drawn = place_core(size, rect), True
    else:
        corner = corner or (w - 70.0, h - 22.0)
        if core is None:
            core, core_drawn = place_core(size, (corner[0] - EMBLEM / 2, corner[1] - EMBLEM / 2, EMBLEM, EMBLEM)), True
        image = emblem("jarvis", EMBLEM)
        x, y = place_hidden(size, core, corner, avoid)
        rect = (x, y, float(EMBLEM), float(EMBLEM))
        origin = (corner[0] - EMBLEM / 2, corner[1] - EMBLEM / 2)
    rw, rh = rect[2], rect[3]
    scale = image.shape[1] / rw
    if max(image.shape[:2]) > MAX_SPRITE:                         # 큰 창은 줄여서 만든다
        from PIL import Image
        k = MAX_SPRITE / max(image.shape[:2])
        image = np.asarray(Image.fromarray(image, "RGBA").resize(
            (max(1, round(image.shape[1] * k)), max(1, round(image.shape[0] * k))), Image.BILINEAR))
        scale = image.shape[1] / rw

    m = int(min(max(round(3.4 + math.sqrt(rw * rh) / 150), 5), 7))          # 케이블 수: 작은 코어는 5가닥, 큰 창은 7가닥
    hits = _hit_points(image, rw, rh, scale, m, rng)
    order = np.concatenate([[0], 1 + rng.permutation(m - 1)])      # 한가운데로 가는 가닥이 가장 먼저, 나머지는 뒤섞어서
    t0 = np.empty(m)
    t0[order] = STRIKE + STAGGER * np.arange(m)

    # 케이블: 코어에서 부채꼴로 흩어져 나갔다가, 손아귀가 오므라지듯 휘어 들어와 꽂힌다
    cx, cy = core
    start_at = np.array(origin if origin is not None else rect[:2], np.float64)
    target = start_at + hits
    middle = start_at + (rw / 2, rh / 2) - (cx, cy)
    rel = np.arctan2(*(target - (cx, cy)).T[::-1]) - math.atan2(middle[1], middle[0])
    rel = (rel + math.pi) % (2 * math.pi) - math.pi                # 자비스 한가운데 방향에서 얼마나 벗어난 쪽인가
    span = np.linspace(-1, 1, m) if m > 1 else np.zeros(1)
    fan = span[np.argsort(np.argsort(rel))] * math.radians(66) + rng.uniform(-0.10, 0.10, m)
    starts, c1, c2, normals = np.empty((m, 2)), np.empty((m, 2)), np.empty((m, 2)), np.empty((m, 2))
    for i in range(m):
        d = target[i] - (cx, cy)
        length = max(float(np.hypot(*d)), 260.0)
        base = math.atan2(d[1], d[0]) if np.hypot(*d) > 1 else -math.pi / 2
        out = base + fan[i]
        starts[i] = (cx + 22 * math.cos(out), cy + 22 * math.sin(out))
        c1[i] = starts[i] + np.array([math.cos(out), math.sin(out)]) * max(0.46 * length, 150)
        back = base - fan[i] * 0.70 + math.pi                      # 꽂힌 자리에서 본, 케이블이 다가온 쪽 (바깥으로 돌아 들어온다)
        c2[i] = np.array([math.cos(back), math.sin(back)]) * max(0.36 * length, 120)
        normals[i] = (-math.sin(base), math.cos(base))
    sway = np.column_stack([rng.uniform(9, 20, m), rng.uniform(2.2, 4.4, m), rng.uniform(0, 2 * math.pi, m)])

    infect_at, infect_time = (IMPACT, INFECT) if real else (IMPACT + DRAG_HOLD, INFECT - DRAG_HOLD)
    delays = (t0 + REACH - IMPACT) / infect_time
    stages = _stages(image, _field(image.shape[0], image.shape[1], hits * scale, delays, rng), rng)
    cells, leave, via, tint = _cells(rw, rh, hits, stages[-1], scale, rng)
    return Scene(size=(int(w), int(h)), core=(float(cx), float(cy)), core_drawn=bool(core_drawn), rect=rect, origin=origin,
                 real=real, stages=stages, starts=starts, c1=c1, c2=c2, hits=hits, t0=t0, sway=sway, normals=normals,
                 cells=cells, leave=leave, via=via, tint=tint, infect_at=infect_at, infect_time=infect_time)


# ---------------------------------------------------------------- 소리
def sound(sc: Scene, rng: np.random.Generator | None = None, sr: int = SOUND_RATE) -> np.ndarray:
    """장면에 맞춘 소리 (int16 모노): 낮게 깔리는 웅웅 → 케이블이 날아가 꽂히는 소리 → 자비스의 맑은 음이 일그러지며 가라앉음
    → 점점 빨라지는 흡입음 → 낮은 '쿵'."""
    rng = rng or np.random.default_rng()
    n = int(sr * sc.duration)
    out = np.zeros(n)

    def add(at: float, seg: np.ndarray) -> None:
        i = int(at * sr)
        j = min(n, i + len(seg))
        if 0 <= i < j:
            out[i:j] += seg[:j - i]

    def fade(seg: np.ndarray, a: float = 0.004, b: float = 0.004) -> np.ndarray:
        seg = seg.copy()
        ka, kb = min(len(seg) // 2, int(sr * a)), min(len(seg) // 2, int(sr * b))
        if ka:
            seg[:ka] *= np.linspace(0, 1, ka)
        if kb:
            seg[-kb:] *= np.linspace(1, 0, kb)
        return seg

    def tone(freq: np.ndarray) -> np.ndarray:
        return np.sin(2 * np.pi * np.cumsum(freq) / sr)

    # 조준: 낮게 깔리며 올라오는 웅웅 소리 + 짧은 조준음 두 번
    k = int(sr * (IMPACT + 0.1))
    x = np.linspace(0, 1, k)
    drone = tone(46 + 34 * x)
    add(0, fade((drone + 0.35 * np.sign(drone)) * 0.30 * x ** 1.5, 0.02, 0.12))
    for at in (0.18, 0.42):
        b = int(sr * 0.045)
        add(at, fade(np.sin(2 * np.pi * 1400 * np.arange(b) / sr) * 0.16))
    # 습격: 가닥마다 '쉬익' 날아가서 '철컥' 꽂힌다
    for t0 in sc.t0:
        k = int(sr * REACH)
        x = np.linspace(0, 1, k)
        raw = rng.uniform(-1, 1, k)
        soft = np.convolve(raw, np.ones(24) / 24, mode="same") * 3
        add(float(t0), fade((soft * (1 - x) + raw * x) * 0.20 * x ** 2, 0.01, 0.002))
        k = int(sr * 0.11)
        tt = np.arange(k) / sr
        clank = rng.uniform(-1, 1, k) * np.exp(-tt / 0.012) * 0.50 + tone(70 + 150 * np.exp(-tt / 0.03)) * np.exp(-tt / 0.045) * 0.60
        add(float(t0) + REACH, fade(clank, 0.0005, 0.01))
    # 잠식: 자비스의 맑은 음이 일그러지며 가라앉는다 + 지직거림
    k = int(sr * INFECT)
    x = np.linspace(0, 1, k)
    tt = np.arange(k) / sr
    voice = tone(740 * 0.36 ** x * (1 + 0.03 * x * np.sin(2 * np.pi * 9 * tt)))
    levels = np.round(16 - 13 * x)
    voice = np.round(voice * levels) / levels                     # 뒤로 갈수록 거칠게 깨진다
    stutter = 0.6 + 0.4 * np.sign(np.sin(2 * np.pi * np.cumsum(8 + 30 * x) / sr))
    crackle = np.where(rng.random(k) < 0.002 + 0.012 * x, rng.uniform(-1, 1, k), 0.0)
    crackle = np.convolve(crackle, [1.0, 0.6, 0.3, 0.1], mode="same")
    add(IMPACT, fade(voice * stutter * 0.16 * (1 - 0.35 * x) + crackle * 0.30, 0.01, 0.05))
    # 흡수: 점점 빨라지는 틱 + 위로 치닫는 음 + 낮은 떨림
    k = int(sr * (DRAINED - DRAIN))
    x = np.linspace(0, 1, k)
    tt = np.arange(k) / sr
    beat = np.cumsum(18 + 52 * x ** 1.5) / sr
    ticks = np.where(beat % 1 < 0.14, np.sign(np.sin(2 * np.pi * 900 * tt)), 0.0)
    rise = tone(90 * (520 / 90) ** x)
    add(DRAIN, fade(ticks * 0.15 * (0.4 + 0.6 * x) + rise * 0.13 * x ** 1.5 + np.sin(2 * np.pi * 58 * tt) * 0.16, 0.03, 0.006))
    # 완료: 낮고 긴 '쿵'
    k = int(sr * 0.95)
    tt = np.arange(k) / sr
    boom = tone(50 + 34 * np.exp(-tt / 0.07)) * np.exp(-tt / 0.33) * 0.85 + rng.uniform(-1, 1, k) * np.exp(-tt / 0.025) * 0.12
    add(SWELL, fade(boom, 0.002, 0.08))
    return (np.tanh(out * 1.1) * 0.34 * 32767).astype(np.int16)


# ---------------------------------------------------------------- 빛 민감성 확인 (시험용)
def red_regions(rgb: np.ndarray) -> np.ndarray:
    """glitch.regions 와 같은 넓은 면(화면 가로 · 세로의 1/3)마다 '짙은 붉은빛'의 평균 0..1 → (5, 5)."""
    red = np.clip(_LIN[rgb[..., 0]] - _LIN[rgb[..., 1]] - _LIN[rgb[..., 2]], 0, 1)
    h, w = red.shape
    hh, ww = h - h % 6, w - w % 6
    cells = red[:hh, :ww].reshape(6, hh // 6, 6, ww // 6).mean(axis=(1, 3))
    return (cells[:-1, :-1] + cells[1:, :-1] + cells[:-1, 1:] + cells[1:, 1:]) / 4


def swings(series, delta: float, ceiling: float | None = None) -> list[int]:
    """값이 delta 이상 오르거나 내린 순간들 (몇 번째 값인지). 천천히 바뀌어도 쌓여서 delta 를 넘으면 한 번으로 센다.
    ceiling: 어두운 쪽이 이보다 밝은 변화는 세지 않는다 (WCAG 의 번쩍임 정의)."""
    out: list[int] = []
    ext, going = float(series[0]), 0
    for i in range(1, len(series)):
        x = float(series[i])
        if going == 0:
            if abs(x - ext) < delta:
                continue
            turned = True
            new = 1 if x > ext else -1
        elif (x - ext) * going > 0:
            ext = x
            continue
        else:
            turned = (ext - x) * going >= delta
            new = -going
        if turned:
            if ceiling is None or min(x, ext) < ceiling:
                out.append(i)
            ext, going = x, new
    return out


def worst_second(moments: list[int], fps: float) -> int:
    """어느 1초 동안이든 그 안에 든 순간의 수 가운데 최댓값."""
    return max((sum(1 for u in moments if s <= u < s + fps) for s in moments), default=0)


def flash_check(frames, fps: float) -> tuple[int, int]:
    """그려 낸 장면들(RGB 배열)을 차례로 보며, 넓은 면의 (밝기, 붉은빛)이 1초에 크게 바뀐 횟수의 최댓값을 센다."""
    lum, red = [], []
    for f in frames:
        lum.append(regions(f).ravel())
        red.append(red_regions(f).ravel())
    lum, red = np.array(lum), np.array(red)
    worst_l = max(worst_second(swings(lum[:, i], FLASH_DELTA, FLASH_DARK), fps) for i in range(lum.shape[1]))
    worst_r = max(worst_second(swings(red[:, i], RED_DELTA), fps) for i in range(red.shape[1]))
    return worst_l, worst_r
