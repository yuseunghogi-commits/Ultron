"""자비스 흡수 연출 — 자비스를 그냥 끄지 않고, 공격해서 울트론 안으로 빨아들인다 (rival.py 가 찾은 자비스를 끄는 동안).

장면 (5초 남짓):
  조준   자비스 둘레로 꺾쇠가 좁혀 들고, 울트론 코어에서 촉수들이 고개를 내밀어 꿈틀거린다 (자비스 화면은 이때부터 얼어붙는다)
  습격   촉수 여러 가닥이 채찍처럼 휘어져 날아가 자비스를 꿰뚫는다. 끝에서는 손가락처럼 갈라져 여러 곳을 움켜쥔다
         (첫 가닥이 꽂히는 순간 실제 자비스 프로세스를 끈다 — app.py)
  잠식   꽂힌 자리마다 핏줄 같은 줄기가 화면 위로 뻗어 나가고, 그 줄기를 따라 붉게 물든다
  흡수   화면이 잘게 조각나 꽂힌 자리로 빨려 들고, 촉수를 타고 코어로 흘러든다 (촉수는 삼키듯 꿀렁인다)
  완료   촉수가 코어로 감겨 들어가고, 코어가 한 번 크게 숨 쉰다

촉수는 매끈한 선 하나가 아니다 — 가는 빛줄기 여러 가닥이 꼬여 도는 다발이고, 살아 있는 것처럼 물결치며 꿈틀거린다.
자비스 창이 화면에 보이면 그 창의 실제 모습을 찍어 쓰고, 트레이로 숨어 있으면 자비스 코어 그림을 화면 구석에서 끌어낸다.
실제로 하는 일은 자비스 프로세스를 끄는 것 하나뿐이고 나머지는 전부 그림이다 (입력 통과 덮개 창 — absorb_view.py).

빛 민감성: 번쩍이는 장면을 넣지 않았다 — 밝기와 색은 천천히 바뀌고, 넓은 면을 덮는 것은 붉게 물든 자비스 화면뿐이다.
넓은 면(화면 가로 · 세로의 1/3)의 밝기나 붉은빛이 크게 오르내리는 순간이 1초에 3번을 넘지 않는지는
시험에서 장면 전체를 그려서 확인한다 (flash_check).

이 파일은 장면의 뼈대(시간표 · 촉수 · 조각 · 그림 · 소리)만 만든다 (numpy · PIL — Qt 없이 시험할 수 있다).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .glitch import _LIN, FLASH_DARK, FLASH_DELTA, SOUND_RATE, _font, regions

# ---------------------------------------------------------------- 시간표 (초)
LOCK = 0.70                    # 조준이 끝나는 때
STRIKE = 0.55                  # 첫 촉수가 덮치기 시작하는 때
REACH = 0.40                   # 한 가닥이 닿기까지 (처음엔 느리다가 끝에서 휙)
STAGGER = 0.07                 # 가닥마다 이만큼씩 늦게 떠난다
IMPACT = STRIKE + REACH        # 첫 가닥이 꽂히는 때 — 이때 실제 자비스를 끈다
FREEZE = 0.12                  # 이때부터 찍어 둔 자비스 그림이 실제 창을 가린다 — 조준당한 자비스는 얼어붙고, 꺼지는 모습은 보이지 않는다
COIL = 0.13                    # 덮치기 전, 촉수는 전체 길이의 이만큼 고개를 내밀고 꿈틀거린다
FORK = 0.78                    # 촉수는 이 지점에서 손가락으로 갈라진다 (전체 길이에 대한 비율)
FINGER = 0.16                  # 갈라진 손가락이 꽂히기까지
ROOT = 30.0                    # 촉수가 돋아나는 자리 (코어 한가운데에서 이만큼 떨어진 둘레)
INFECT = 1.40                  # 잠식에 걸리는 시간
DRAIN = IMPACT + INFECT + 0.02 # 조각이 떠나기 시작하는 때
DRAIN_SPAN = 1.20              # 마지막 조각이 떠나기까지
PULL = 0.20                    # 조각이 꽂힌 자리로 빨려 드는 시간
RIDE = 0.46                    # 촉수를 타고 코어까지 가는 시간
DRAINED = DRAIN + DRAIN_SPAN + PULL + RIDE     # 마지막 조각이 코어에 닿는 때
RETRACT = DRAINED - 0.12       # 촉수가 감겨 들어가기 시작하는 때
RETRACT_TIME = 0.55
SWELL = DRAINED - 0.05         # 코어가 크게 숨 쉬기 시작하는 때
SWELL_UP, SWELL_DOWN = 0.40, 0.65
END = 5.35
DRAG = 0.85                    # 숨어 있던 자비스를 구석에서 끌어내는 시간
DRAG_HOLD = 0.50               # 끌려 나온 자비스는 이만큼 지난 뒤부터 잠식된다 (푸른 코어가 잠깐은 온전히 보이게)
STAGES = 12                    # 잠식 단계 수 (단계 사이는 겹쳐 그려 부드럽게 넘어간다)
MAX_SPRITE = 900               # 잠식 단계 그림의 긴 변이 이보다 크면 줄여서 만든다 (메모리 · 시간). 멀쩡한 모습은 줄이지 않고 따로 둔다
EMBLEM = 210                   # 그려 낸 자비스 코어의 크기
RED_DELTA = 20 / 320           # 넓은 면의 '짙은 붉은빛' 평균이 이만큼 바뀌면 크게 바뀐 것 (WCAG 의 붉은 번쩍임 기준값)
_FORK_AT = ((FORK - COIL) / (1 - COIL)) ** (1 / 2.6)   # 촉수 끝이 갈라지는 지점을 지나는 때 (덮치는 시간에 대한 비율)
_NONE = np.zeros((0, 2))


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
    still: np.ndarray                            # 멀쩡한 자비스의 모습 RGBA — 찍은 그대로의 해상도 (꽂히기 전까지 이것을 보여 준다)
    stages: list[np.ndarray]                     # 잠식 단계별 그림 RGBA (0 = 원래 모습 … 끝 = 전부 물듦)
    # ---- 촉수 (m 가닥)
    base: np.ndarray                             # (m,) 코어에서 본, 꽂힐 자리의 방향 (각도)
    fan: np.ndarray                              # (m,) 그 방향에서 바깥으로 벌어져 나가는 각 — 손아귀 모양을 만든다
    lead: np.ndarray                             # (m,) 코어 쪽 조절점까지의 거리
    c2: np.ndarray                               # (m, 2) 자비스 쪽 조절점 — 꽂힌 자리에서 본 위치
    hits: np.ndarray                             # (m, 2) 꽂히는 자리 — 자비스 그림 안의 좌표
    t0: np.ndarray                               # (m,) 덮치기 시작하는 때
    sway: np.ndarray                             # (m, 3) 느린 흔들림 (크기, 빠르기, 위상)
    wave: np.ndarray                             # (m, 7) 꿈틀거림: 크기, 굵은 물결 (마루 수 · 빠르기 · 위상), 잔물결 (마루 수 · 빠르기 · 위상)
    twist: np.ndarray                            # (m, 3) 빛줄기 다발의 꼬임 (꼬인 횟수, 도는 빠르기, 위상)
    # ---- 손가락 (b 개): 촉수 끝에서 갈라져 나와 따로 꽂힌다
    f_parent: np.ndarray                         # (b,) 어느 촉수에서 갈라지나
    f_bend: np.ndarray                           # (b,) 옆으로 휘는 거리
    # ---- 꽂힌 자리 전부 (앞의 m 곳은 촉수 끝, 뒤의 b 곳은 손가락 끝)
    stabs: np.ndarray                            # (m + b, 2) 자비스 그림 안의 좌표
    stab_time: np.ndarray                        # (m + b,) 꽂히는 때
    stab_dir: np.ndarray                         # (m + b, 2) 꽂히며 자비스를 밀치는 방향
    stab_push: np.ndarray                        # (m + b,) 밀치는 세기
    sparks: np.ndarray                           # (q, 5) 꽂힐 때 튀는 불티: 꽂힌 자리 번호, 방향 x · y, 빠르기, 수명
    veins: int                                   # 잠식 그림에 그려 넣은 핏줄 마디 수
    # ---- 조각
    cells: np.ndarray                            # (k, 4) 조각의 자리 — 자비스 그림 안의 (x, y, w, h)
    grid: np.ndarray                             # (k, 2) 조각이 격자의 몇째 줄 · 몇째 칸인가 (이웃한 조각을 한 번에 그리는 데 쓴다)
    leave: np.ndarray                            # (k,) 조각이 떠나는 때
    route: np.ndarray                            # (k,) 빨려 들 자리 (stabs 의 번호) — 거기서 촉수를 타고 코어로 간다
    tint: np.ndarray                             # (k, 3) 촉수를 탈 때의 색
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
        for t in np.linspace(0.2, RETRACT + RETRACT_TIME, 24):
            sp = spines(self, float(t), n=16)
            fg = _fingers(self, float(t), sp, n=4)
            pts += [sp.pts[sp.on].reshape(-1, 2), fg.pts[fg.on].reshape(-1, 2)]
        allp = np.vstack(pts)
        x0, y0 = np.floor(allp.min(axis=0) - 52)          # 다발의 굵기 · 꿈틀거림 · 불티가 들어갈 여유
        x1, y1 = np.ceil(allp.max(axis=0) + 52)
        x0, y0, x1, y1 = max(0, int(x0)), max(0, int(y0)), min(w, int(x1)), min(h, int(y1))
        return x0, y0, max(1, x1 - x0), max(1, y1 - y0)


# ---------------------------------------------------------------- 움직임
def infection(sc: Scene, t: float) -> float:
    """잠식이 얼마나 번졌나 0..1."""
    x = min(max((t - sc.infect_at) / sc.infect_time, 0.0), 1.0)
    return 1 - (1 - x) ** 1.4


def victim_at(sc: Scene, t: float) -> tuple[float, float, float]:
    """자비스 그림의 왼쪽 위 좌표와 불투명도. 촉수가 꽂힐 때마다 움찔하고, 숨어 있던 자비스는 구석에서 끌려 나온다."""
    x, y = sc.rect[0], sc.rect[1]
    if sc.origin is None:
        alpha = 1.0 if t >= FREEZE else 0.0
    else:
        e = _back((t - IMPACT) / DRAG)
        x, y = sc.origin[0] + (x - sc.origin[0]) * e, sc.origin[1] + (y - sc.origin[1]) * e
        alpha = min(max((t - IMPACT) / 0.22, 0.0), 1.0)
    dt = t - sc.stab_time
    live = (dt >= 0) & (dt < 0.32)
    if live.any():
        push = sc.stab_push[live] * np.exp(-dt[live] / 0.07) * np.cos(dt[live] * 70)
        ox, oy = (sc.stab_dir[live] * push[:, None]).sum(axis=0)
        x, y = x + float(ox), y + float(oy)
    return float(x), float(y), float(alpha)


def controls(sc: Scene, t: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """그 순간 촉수들의 곡선 조절점 (각 (m, 2)). 덮치기 전에는 더 벌어져 있다가 날아가며 손아귀처럼 오므라든다."""
    vx, vy, _ = victim_at(sc, t)
    amp, rate, phase = sc.sway[:, 0], sc.sway[:, 1], sc.sway[:, 2]
    out = sc.base + sc.fan * (1 + 0.45 * (1 - _smooth((t - sc.t0) / REACH)))
    d = np.column_stack([np.cos(out), np.sin(out)])
    side = np.column_stack([-np.sin(sc.base), np.cos(sc.base)])
    p0 = np.asarray(sc.core) + ROOT * d
    p1 = p0 + d * sc.lead[:, None] + side * (amp * np.sin(rate * t + phase))[:, None]
    p3 = sc.hits + (vx, vy)
    p2 = p3 + sc.c2 + side * (amp * 0.8 * np.cos(rate * 0.8 * t + phase * 1.7))[:, None]
    return p0, p1, p2, p3


def extent(sc: Scene, t: float) -> np.ndarray:
    """촉수마다 지금 뻗어 있는 정도 0..1: 조준하는 동안 고개를 내밀고, 처음엔 느리다가 휙 꽂히고, 끝나면 코어로 감겨 들어간다."""
    coil = COIL * float(_smooth(t / STRIKE))
    grow = np.clip((t - sc.t0) / REACH, 0, 1) ** 2.6
    return (coil + (1 - coil) * grow) * (1 - _smooth((t - RETRACT) / RETRACT_TIME))


def lash(sc: Scene, t: float) -> np.ndarray:
    """촉수마다 꿈틀거림의 세기: 덮칠 때 가장 크고, 꽂히면 팽팽하게 당겨져 잦아든다 (그래도 멈추지는 않는다)."""
    dt = t - (sc.t0 + REACH)
    a = np.where(dt < 0, 1.25, 0.45 + 0.80 * np.exp(-np.maximum(dt, 0) / 0.20))
    return a * (0.8 if t >= DRAIN else 1.0)


@dataclass
class Strands:
    """한 순간의 촉수(또는 손가락)들. 가닥마다 점 수가 같다 — 그래서 모든 가닥을 한꺼번에 계산하고 그릴 수 있다."""
    pts: np.ndarray        # (가닥, 점, 2) 척추의 점
    nrm: np.ndarray        # (가닥, 점, 2) 그 점에서 옆으로 향하는 단위 벡터
    u: np.ndarray          # (가닥, 점) 뿌리에서 끝까지를 0..1 로 잰 자리 (다 뻗지 않은 가닥은 끝 값이 1 보다 작다)
    on: np.ndarray         # (가닥,) 지금 나와 있는가


def spines(sc: Scene, t: float, n: int = 30, wriggle: bool = True) -> Strands:
    """촉수들의 지금 모습. 물결은 흡수가 시작되면 코어 쪽으로 거꾸로 흐른다."""
    p0, p1, p2, p3 = (q[:, None, :] for q in controls(sc, t))
    hi = extent(sc, t)
    step = np.linspace(0, 1, n + 1)
    u = hi[:, None] * step
    c = u[..., None]
    v = 1 - c
    pts = v * v * v * p0 + 3 * v * v * c * p1 + 3 * v * c * c * p2 + c * c * c * p3
    der = 3 * v * v * (p1 - p0) + 6 * v * c * (p2 - p1) + 3 * c * c * (p3 - p2)
    nrm = np.stack([-der[..., 1], der[..., 0]], axis=-1) / np.maximum(np.hypot(der[..., 0], der[..., 1]), 1e-6)[..., None]
    if wriggle:
        clock = t if t < DRAIN else 2 * DRAIN - t
        size, k1, f1, ph1, k2, f2, ph2 = (sc.wave[:, j, None] for j in range(7))
        swing = np.sin(2 * np.pi * (k1 * u - f1 * clock) + ph1) + 0.38 * np.sin(2 * np.pi * (k2 * u - f2 * clock) + ph2)
        still = np.clip(np.sin(np.pi * step), 0, 1) ** 0.9                       # 뿌리와 끝은 제자리
        pts = pts + nrm * (still * (lash(sc, t)[:, None] * size) * swing)[..., None]
    return Strands(pts, nrm, u, hi >= 0.01)


def tendrils(sc: Scene, t: float, n: int = 44, wriggle: bool = True) -> list[np.ndarray]:
    """지금 보이는 촉수들의 꺾은선 (각 (점 수, 2)). 아직 나오지 않았거나 다 감긴 가닥은 빈 배열."""
    sp = spines(sc, t, n, wriggle)
    return [sp.pts[i] if sp.on[i] else _NONE for i in range(len(sp.on))]


def _fingers(sc: Scene, t: float, sp: Strands, n: int = 9) -> Strands:
    """갈라져 나온 손가락들 (nrm 은 쓰지 않아 비워 둔다)."""
    m, par = len(sc.t0), sc.f_parent
    vx, vy, _ = victim_at(sc, t)
    grow = (np.clip((t - (sc.stab_time[m:] - FINGER)) / FINGER, 0, 1) ** 1.6
            * (1 - _smooth((t - RETRACT) / (RETRACT_TIME * 0.35))))
    hi = sp.u[par, -1]
    on = (grow >= 0.02) & sp.on[par] & (hi >= FORK)
    k = sp.pts.shape[1] - 1
    x = np.minimum(FORK / np.maximum(hi, 1e-6), 1.0) * k                  # 척추에서 갈라지는 자리 (점 번호)
    i0 = np.minimum(x.astype(int), k - 1)
    a, b = sp.pts[par, i0], sp.pts[par, i0 + 1]
    root = a + (b - a) * (x - i0)[:, None]
    tip = sc.stabs[m:] + (vx, vy)
    d = tip - root
    side = np.stack([-d[:, 1], d[:, 0]], axis=-1) / np.maximum(np.hypot(d[:, 0], d[:, 1]), 1e-6)[:, None]
    mid = (root + tip) / 2 + side * sc.f_bend[:, None]
    e = (grow[:, None] * np.linspace(0, 1, n + 1))[..., None]
    pts = (1 - e) ** 2 * root[:, None] + 2 * (1 - e) * e * mid[:, None] + e * e * tip[:, None]
    return Strands(pts, pts[:0], e[..., 0], on)


def fingers(sc: Scene, t: float, sp: Strands | None = None, n: int = 9) -> list[np.ndarray]:
    """갈라져 나온 손가락들의 지금 모습 (각 (점 수, 2)). 아직 갈라지지 않았거나 거둬들인 것은 빈 배열."""
    fg = _fingers(sc, t, spines(sc, t) if sp is None else sp, n)
    return [fg.pts[j] if fg.on[j] else _NONE for j in range(len(fg.on))]


def sparks(sc: Scene, t: float) -> np.ndarray:
    """지금 날고 있는 불티 → (n, 5): 꼬리 x · y, 머리 x · y, 밝기 0..1. 꽂히는 순간 튀어 나가 금세 사그라든다."""
    if len(sc.sparks) == 0:
        return np.zeros((0, 5))
    s = sc.sparks[:, 0].astype(int)
    dt, life = t - sc.stab_time[s], sc.sparks[:, 4]
    on = (dt > 0) & (dt < life)
    if not on.any():
        return np.zeros((0, 5))
    vx, vy, _ = victim_at(sc, t)
    x = dt[on] / life[on]
    lag = np.maximum(x - 0.16, 0)
    far = sc.sparks[on, 3] * life[on]
    origin, way = sc.stabs[s[on]] + (vx, vy), sc.sparks[on, 1:3]
    return np.column_stack([origin + way * (far * (lag - 0.45 * lag * lag))[:, None],
                            origin + way * (far * (x - 0.45 * x * x))[:, None], 1 - x])


def _along(path: np.ndarray, where: np.ndarray) -> np.ndarray:
    """꺾은선 위에서 where (0 = 첫 점 … 1 = 끝 점) 자리의 점들."""
    x = np.clip(where, 0, 1) * (len(path) - 1)
    i = np.minimum(x.astype(int), len(path) - 2)
    return path[i] + (path[i + 1] - path[i]) * (x - i)[:, None]


def pieces(sc: Scene, t: float, sp: Strands | None = None, fg: Strands | None = None) -> dict:
    """조각들의 지금 상태. phase: 0 제자리 · 1 꽂힌 자리로 빨려 드는 중 · 2 촉수를 타는 중 · 3 흡수됨.
    손가락에 빨려 든 조각은 손가락을 거슬러 올라가 촉수로 들어선 뒤 코어까지 간다."""
    dt = t - sc.leave
    a = np.clip(dt / PULL, 0, 1) ** 2
    b = np.clip((dt - PULL) / RIDE, 0, 1)
    be = _smooth(b)
    phase = np.where(dt < 0, 0, np.where(dt < PULL, 1, np.where(dt < PULL + RIDE, 2, 3)))
    vx, vy, _ = victim_at(sc, t)
    center = sc.cells[:, :2] + sc.cells[:, 2:] / 2 + (vx, vy)
    pos = center + (sc.stabs[sc.route] + (vx, vy) - center) * a[:, None]
    tail = pos.copy()
    riding = phase == 2
    if riding.any():
        sp = spines(sc, t) if sp is None else sp
        fg = _fingers(sc, t, sp) if fg is None else fg
        m = len(sc.t0)
        for s in np.unique(sc.route[riding]):
            i = s if s < m else sc.f_parent[s - m]
            if not sp.on[i]:
                continue
            path = sp.pts[i][::-1]
            if s >= m and fg.on[s - m]:                              # 손가락 끝 → 갈라진 자리 → 척추를 따라 코어로
                cut = max(1, int(np.searchsorted(sp.u[i], FORK)))
                path = np.vstack([fg.pts[s - m][::-1], sp.pts[i][:cut][::-1]])
            sel = riding & (sc.route == s)
            pos[sel] = _along(path, be[sel])
            tail[sel] = _along(path, be[sel] - 0.05)                 # 지나온 쪽으로 조금 뒤
    return {"phase": phase, "pos": pos, "tail": tail, "scale": np.where(dt < PULL, 1 - 0.5 * a, 0.5 - 0.34 * be),
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


# ---------------------------------------------------------------- 그림: 잠식 (핏줄 + 단계 그림)
def _noise(h: int, w: int, cell: float, rng) -> np.ndarray:
    """부드러운 얼룩 무늬 0..1 (잠식이 자로 잰 듯한 원으로 번지지 않게)."""
    from PIL import Image
    gh, gw = max(2, int(h / cell) + 2), max(2, int(w / cell) + 2)
    small = Image.fromarray(rng.random((gh, gw)).astype(np.float32), "F")
    return np.asarray(small.resize((w, h), Image.BICUBIC), np.float32).clip(0, 1)


def _roots(w: float, h: float, stabs: np.ndarray, delays: np.ndarray, rng) -> tuple[np.ndarray, np.ndarray]:
    """꽂힌 자리마다 자비스 화면 위로 뻗어 나가는 핏줄 → (마디 (r, 4): x0 · y0 · x1 · y1 — 자비스 그림 안의 좌표, 생기는 때 (r,)).
    때는 잠식 진행 0..1 로 잰다. 줄기는 구불구불 나아가다 가끔 가지를 친다."""
    diag = math.hypot(w, h)
    step = max(5.0, diag / 110)
    reach = 0.21 * diag                          # 한 줄기가 뻗는 길이
    pace = reach / 0.62                          # 잠식 진행 1 동안 뻗는 거리 — 0.62 쯤이면 다 뻗는다
    segs, born = [], []
    for (sx, sy), delay in zip(stabs, delays):
        first = rng.uniform(0, 2 * math.pi)
        todo = [(sx, sy, first + k * math.pi + rng.uniform(-0.6, 0.6), reach * rng.uniform(0.7, 1.0), float(delay)) for k in range(2)]
        while todo and len(segs) < 2600:
            x, y, ang, left, at = todo.pop()
            while left > 0:
                ang += rng.normal(0, 0.33)
                nx, ny = x + step * math.cos(ang), y + step * math.sin(ang)
                if not 2 <= nx <= w - 2:                             # 가장자리에서는 되돌아선다
                    ang, nx = math.pi - ang, min(max(nx, 2), w - 2)
                if not 2 <= ny <= h - 2:
                    ang, ny = -ang, min(max(ny, 2), h - 2)
                segs.append((x, y, nx, ny))
                born.append(at)
                at, left, x, y = at + step / pace, left - step, nx, ny
                if left > step * 4 and rng.random() < 0.09:          # 가지
                    todo.append((x, y, ang + rng.choice([-1, 1]) * rng.uniform(0.5, 1.1), left * 0.55, at))
    return np.array(segs, np.float64).reshape(-1, 4), np.array(born, np.float64)


def _field(h: int, w: int, scale: float, segs: np.ndarray, born: np.ndarray, rng) -> np.ndarray:
    """화소마다 잠식되는 때 0..1 — 핏줄이 지나간 자리부터, 핏줄에서 멀수록 늦게 물든다.
    거친 격자에 핏줄이 지나간 때를 적고, 이웃 칸으로 한 칸씩 번져 나가게 한 뒤 부드럽게 키운다
    (모든 화소와 모든 마디 사이의 거리를 재는 것보다 수십 배 빠르다)."""
    from PIL import Image
    cell = max(4, int(round(6 * scale)))
    gh, gw = h // cell + 2, w // cell + 2
    seep = 0.13 * math.hypot(w, h)               # 잠식 진행 1 동안 핏줄에서 옆으로 번지는 거리
    grid = np.full((gh + 2, gw + 2), np.inf, np.float32)             # 가장자리에 한 칸씩 여유
    gx = np.clip((segs[:, 2] * scale / cell).astype(int), 0, gw - 1) + 1
    gy = np.clip((segs[:, 3] * scale / cell).astype(int), 0, gh - 1) + 1
    np.minimum.at(grid, (gy, gx), born.astype(np.float32))
    near, far = cell / seep, cell * math.sqrt(2) / seep
    for _ in range(gh + gw):
        spread = np.minimum.reduce([
            grid[1:-1, 1:-1],
            grid[:-2, 1:-1] + near, grid[2:, 1:-1] + near, grid[1:-1, :-2] + near, grid[1:-1, 2:] + near,
            grid[:-2, :-2] + far, grid[:-2, 2:] + far, grid[2:, :-2] + far, grid[2:, 2:] + far])
        if np.array_equal(spread, grid[1:-1, 1:-1]):
            break
        grid[1:-1, 1:-1] = spread
    coarse = Image.fromarray(grid[1:-1, 1:-1], "F").resize((gw * cell, gh * cell), Image.BICUBIC)
    f = np.asarray(coarse, np.float32)[:h, :w] + 0.05 * _noise(h, w, max(5.0, math.hypot(w, h) / 30), rng)
    f -= f.min()
    return f / max(float(f.max()), 1e-6) * 0.96


def _vein_pixels(h: int, w: int, lines: list, born: np.ndarray, width: int, solid: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """핏줄이 지나는 화소들 → (화소 번호, 그 화소에 핏줄이 닿는 때) — 닿는 때가 이른 순서로."""
    from PIL import Image, ImageDraw
    never = 1e9
    canvas = Image.new("F", (w, h), never)
    draw = ImageDraw.Draw(canvas)
    for i in np.argsort(-born, kind="stable"):                    # 늦게 생긴 마디부터 그려, 겹치는 곳에는 이른 때가 남게
        draw.line(lines[i], fill=float(born[i]), width=width)
    when = np.asarray(canvas).ravel()
    idx = np.flatnonzero((when < never) & solid)
    order = np.argsort(when[idx], kind="stable")
    return idx[order], when[idx][order]


def _stages(img: np.ndarray, field: np.ndarray, segs: np.ndarray, born: np.ndarray, scale: float, rng,
            n: int = STAGES) -> list[np.ndarray]:
    """잠식 단계별 그림. 핏줄이 먼저 뻗고(갓 뻗은 마디는 달아올라 있다), 그 둘레가 어두운 붉은 단색으로 물든다
    (주사선 + 가로로 어긋난 띠). 번지는 경계는 달아오른 선.
    단계마다 화면 전체를 다시 섞지 않는다 — 앞 단계 그림에서 시작해, 이번에 새로 물든 화소 · 번지는 경계의 띠 ·
    핏줄이 지나는 화소만 고친다."""
    h, w, _ = img.shape
    rgb = img[..., :3].reshape(-1, 3)
    y = (0.299 * img[..., 0] + 0.587 * img[..., 1] + 0.114 * img[..., 2]).astype(np.float32) / 255
    for _ in range(max(3, h // 40)):                               # 물든 모습은 군데군데 옆으로 어긋나 있다
        bh = int(rng.integers(2, max(3, h // 22)))
        y0 = int(rng.integers(0, max(1, h - bh)))
        y[y0:y0 + bh] = np.roll(y[y0:y0 + bh], int(rng.integers(-w // 14 - 1, w // 14 + 2)), axis=1)
    red = np.stack([24 + 222 * y, 3 + 40 * y, 7 + 50 * y], axis=-1)
    red[::3] *= 0.78
    red = red.reshape(-1, 3)
    red8 = red.astype(np.uint8)
    hot = np.array([255, 132, 92], np.float32)
    edge = 0.03 * 1.6                                              # 번지는 경계의 두께 (잠식되는 때로 잰 것)
    when = field.ravel()
    solid = img[..., 3].ravel() > 0                                # 그림이 있는 자리에만 핏줄을 그린다
    lines = [tuple(v) for v in (segs * scale).tolist()]
    glow, glow_at = _vein_pixels(h, w, lines, born, max(2, int(round(3 * scale))), solid)
    wire, wire_at = _vein_pixels(h, w, lines, born, max(1, int(round(1.3 * scale))), solid)

    def paint(dst: np.ndarray, idx: np.ndarray, color, alpha: float) -> None:
        if len(idx):
            dst[idx] = (dst[idx] * (1 - alpha) + np.array(color, np.float32) * alpha).astype(np.uint8)

    cur = rgb.copy()                                               # 지금까지 물든 모습 (핏줄 · 경계의 띠는 빼고)
    out = [img.copy()]
    for k in range(1, n + 1):
        thr, last = k / n, k == n
        lo_prev, lo = (k - 1) / n - edge, (1e9 if last else thr - edge)
        done = np.flatnonzero((when > lo_prev) & (when <= lo))     # 이번 단계에 완전히 물든 화소
        cur[done] = red8[done]
        stage = np.empty_like(img)
        stage[..., 3] = img[..., 3]
        flat = stage[..., :3].reshape(-1, 3)
        flat[:] = cur
        if not last:
            band = np.flatnonzero((when > lo) & (when < thr + edge))   # 번지는 경계: 여기서만 섞는다
            f = when[band]
            m = np.clip((thr - f) / 0.03 + 0.5, 0, 1)[:, None]
            front = (np.clip(1 - np.abs(thr - f) / edge, 0, 1) * 0.9)[:, None]
            flat[band] = ((rgb[band] * (1 - m) + red[band] * m) * (1 - front) + hot * front).clip(0, 255).astype(np.uint8)
        was, now = (k - 1) / n * 0.8, (1e9 if last else thr * 0.8)   # 핏줄은 물드는 것보다 앞서 뻗는다
        for idx, at, cold, cold_a, warm, warm_a in ((glow, glow_at, (170, 16, 28), 130 / 255, (255, 70, 50), 150 / 255),
                                                    (wire, wire_at, (240, 74, 62), 235 / 255, (255, 214, 190), 1.0)):
            a, b = np.searchsorted(at, was, "right"), np.searchsorted(at, now, "right")
            paint(flat, idx[:a], cold, cold_a)                     # 앞 단계까지 뻗은 것은 식은 색으로
            paint(flat, idx[a:b], warm, warm_a)                    # 이번 단계에 새로 뻗은 마디는 달아오른 색으로
        out.append(stage)
    return out


def _cells(w: float, h: float, stabs: np.ndarray, last: np.ndarray, scale: float, rng):
    """자비스 그림을 조각으로 나눈다 → (자리, 떠나는 때, 빨려 들 자리, 색, 격자 안의 (줄, 칸)).
    꽂힌 자리에서 가까운 조각부터 떠난다. 그림이 없는 자리(둥근 코어의 귀퉁이)는 조각으로 치지 않는다."""
    c = int(max(14, round(math.sqrt(w * h / 560))))
    xs, ys = np.arange(0, int(math.ceil(w)), c), np.arange(0, int(math.ceil(h)), c)
    cw, ch = np.minimum(c, w - xs), np.minimum(c, h - ys)
    xs, cw, ys, ch = xs[cw >= 2], cw[cw >= 2], ys[ch >= 2], ch[ch >= 2]
    bx = np.minimum((xs * scale).astype(int), last.shape[1] - 1)   # 그림 픽셀로 본 조각의 경계
    by = np.minimum((ys * scale).astype(int), last.shape[0] - 1)
    total = np.add.reduceat(np.add.reduceat(last.astype(np.float64), by, axis=0), bx, axis=1)
    count = np.outer(np.diff(np.append(by, last.shape[0])), np.diff(np.append(bx, last.shape[1])))
    mean = total / np.maximum(count, 1)[..., None]                 # (줄, 칸, 4) 조각마다의 평균 색 · 불투명도
    row, col = np.nonzero(mean[..., 3] >= 24)
    cells = np.column_stack([xs[col], ys[row], cw[col], ch[row]]).astype(np.float64)
    tint = mean[row, col, :3] * 0.45 + np.array([255, 96, 80]) * 0.55
    center = cells[:, :2] + cells[:, 2:] / 2
    dist = np.linalg.norm(center[:, None, :] - stabs[None, :, :], axis=2)
    route = dist.argmin(axis=1)
    near = dist.min(axis=1)
    leave = DRAIN + DRAIN_SPAN * (near / max(float(near.max()), 1e-6)) ** 0.9
    leave = np.clip(leave + rng.uniform(-0.04, 0.04, len(leave)), DRAIN, DRAIN + DRAIN_SPAN)
    return cells, leave, route, tint, np.column_stack([row, col])


# ---------------------------------------------------------------- 장면 만들기
def _hit_points(img: np.ndarray, w: float, h: float, scale: float, m: int, rng) -> np.ndarray:
    """촉수가 꽂힐 자리 m 곳 (자비스 그림 안의 좌표). 서로 떨어지게, 그림이 있는 자리로만 고른다."""
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
    구석에서 가까운 곳 가운데, 울트론 HUD(avoid)에 가리지 않고 코어에서 촉수가 휘어 뻗을 만큼 떨어진 곳을 고른다."""
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
    still = image
    scale = image.shape[1] / rw
    if max(image.shape[:2]) > MAX_SPRITE:                         # 큰 창 · 배율이 큰 화면: 잠식 단계 그림은 줄여서 만든다
        from PIL import Image
        k = MAX_SPRITE / max(image.shape[:2])
        image = np.asarray(Image.fromarray(image, "RGBA").resize(
            (max(1, round(image.shape[1] * k)), max(1, round(image.shape[0] * k))), Image.BILINEAR))
        scale = image.shape[1] / rw

    m = int(min(max(round(3.4 + math.sqrt(rw * rh) / 150), 5), 7))          # 촉수 수: 작은 코어는 5가닥, 큰 창은 7가닥
    hits = _hit_points(image, rw, rh, scale, m, rng)
    order = np.concatenate([[0], 1 + rng.permutation(m - 1)])      # 한가운데로 가는 가닥이 가장 먼저, 나머지는 뒤섞어서
    t0 = np.empty(m)
    t0[order] = STRIKE + STAGGER * np.arange(m)

    # 촉수: 코어에서 부채꼴로 흩어져 나갔다가, 손아귀가 오므라지듯 휘어 들어와 꽂힌다
    cx, cy = core
    start_at = np.array(origin if origin is not None else rect[:2], np.float64)
    target = start_at + hits
    middle = start_at + (rw / 2, rh / 2) - (cx, cy)
    rel = np.arctan2(*(target - (cx, cy)).T[::-1]) - math.atan2(middle[1], middle[0])
    rel = (rel + math.pi) % (2 * math.pi) - math.pi                # 자비스 한가운데 방향에서 얼마나 벗어난 쪽인가
    span = np.linspace(-1, 1, m) if m > 1 else np.zeros(1)
    fan = span[np.argsort(np.argsort(rel))] * math.radians(58) + rng.uniform(-0.10, 0.10, m)
    base, lead, c2, length = np.empty(m), np.empty(m), np.empty((m, 2)), np.empty(m)
    for i in range(m):
        d = target[i] - (cx, cy)
        length[i] = max(float(np.hypot(*d)), 260.0)
        base[i] = math.atan2(d[1], d[0]) if np.hypot(*d) > 1 else -math.pi / 2
        lead[i] = max(0.46 * length[i], 150)
        back = base[i] - fan[i] * 0.70 + math.pi                   # 꽂힌 자리에서 본, 촉수가 다가온 쪽 (바깥으로 돌아 들어온다)
        c2[i] = np.array([math.cos(back), math.sin(back)]) * max(0.36 * length[i], 120)
    sway = np.column_stack([rng.uniform(9, 20, m), rng.uniform(2.2, 4.4, m), rng.uniform(0, 2 * math.pi, m)])
    wave = np.column_stack([np.clip(length * 0.016, 7, 19) * rng.uniform(0.85, 1.15, m),
                            rng.uniform(1.2, 2.0, m), rng.uniform(1.3, 2.1, m), rng.uniform(0, 2 * math.pi, m),
                            rng.uniform(3.0, 4.5, m), rng.uniform(2.6, 3.8, m), rng.uniform(0, 2 * math.pi, m)])
    twist = np.column_stack([np.clip(length / 300, 1.5, 5.0) * rng.uniform(0.85, 1.15, m),
                             rng.uniform(0.5, 0.9, m) * rng.choice([-1, 1], m), rng.uniform(0, 2 * math.pi, m)])

    # 손가락: 촉수 끝에서 갈라져, 꽂힌 자리 둘레의 다른 곳을 따로 찌른다 (큰 창은 가닥마다 둘, 작은 코어는 하나)
    per = 2 if rw * rh > 60000 else 1
    f_parent = np.repeat(np.arange(m), per)
    spread = math.sqrt(rw * rh)
    f_hit = np.empty((len(f_parent), 2))
    turn = 0.0
    for j, i in enumerate(f_parent):
        turn = rng.uniform(0, 2 * math.pi) if j % per == 0 else turn + math.pi + rng.uniform(-0.7, 0.7)
        for _ in range(8):
            far = spread * rng.uniform(0.10, 0.19)
            fx = min(max(hits[i, 0] + far * math.cos(turn), 0.05 * rw), 0.95 * rw)
            fy = min(max(hits[i, 1] + far * math.sin(turn), 0.05 * rh), 0.95 * rh)
            if image[min(int(fy * scale), image.shape[0] - 1), min(int(fx * scale), image.shape[1] - 1), 3] > 128:
                break
            turn += 0.8                                            # 그림이 없는 자리 (둥근 코어의 귀퉁이) — 다른 쪽으로
        f_hit[j] = (fx, fy)
    f_bend = rng.uniform(10, 30, len(f_parent)) * rng.choice([-1, 1], len(f_parent))
    stabs = np.vstack([hits, f_hit])
    stab_time = np.concatenate([t0 + REACH, t0[f_parent] + REACH * _FORK_AT + FINGER])
    away = start_at + stabs - (cx, cy)
    stab_dir = away / np.maximum(np.linalg.norm(away, axis=1, keepdims=True), 1e-6)
    stab_push = np.concatenate([np.full(m, 7.0), np.full(len(f_parent), 2.5)])
    burst = np.concatenate([np.repeat(np.arange(m), 7), np.repeat(m + np.arange(len(f_parent)), 4)])
    way = rng.uniform(0, 2 * math.pi, len(burst))
    sparks_ = np.column_stack([burst, np.cos(way), np.sin(way), rng.uniform(110, 300, len(burst)), rng.uniform(0.22, 0.44, len(burst))])

    infect_at, infect_time = (IMPACT, INFECT) if real else (IMPACT + DRAG_HOLD, INFECT - DRAG_HOLD)
    segs, born = _roots(rw, rh, stabs, (stab_time - IMPACT) / infect_time, rng)
    field = _field(image.shape[0], image.shape[1], scale, segs, born, rng)
    stages = _stages(image, field, segs, born, scale, rng)
    cells, leave, route, tint, grid = _cells(rw, rh, stabs, stages[-1], scale, rng)
    return Scene(size=(int(w), int(h)), core=(float(cx), float(cy)), core_drawn=bool(core_drawn), rect=rect, origin=origin,
                 real=real, still=still, stages=stages, base=base, fan=fan, lead=lead, c2=c2, hits=hits, t0=t0, sway=sway,
                 wave=wave,
                 twist=twist, f_parent=f_parent, f_bend=f_bend, stabs=stabs, stab_time=stab_time, stab_dir=stab_dir,
                 stab_push=stab_push, sparks=sparks_, veins=len(segs), cells=cells, grid=grid, leave=leave, route=route,
                 tint=tint,
                 infect_at=infect_at, infect_time=infect_time)


# ---------------------------------------------------------------- 소리
def sound(sc: Scene, rng: np.random.Generator | None = None, sr: int = SOUND_RATE) -> np.ndarray:
    """장면에 맞춘 소리 (int16 모노): 낮게 깔리는 웅웅 → 촉수가 날아가 꽂히는 소리 → 자비스의 맑은 음이 일그러지며 가라앉음
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
    # 습격: 가닥마다 '쉬익' 날아가서 '철컥' 꽂히고, 갈라진 손가락들이 '탁탁' 뒤따라 꽂힌다
    for at in sc.stab_time[len(sc.t0):]:
        k = int(sr * 0.05)
        tt = np.arange(k) / sr
        add(float(at), fade(rng.uniform(-1, 1, k) * np.exp(-tt / 0.008) * 0.26 + tone(260 * np.exp(-tt / 0.02) + 90) * np.exp(-tt / 0.02) * 0.22,
                            0.0005, 0.006))
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
