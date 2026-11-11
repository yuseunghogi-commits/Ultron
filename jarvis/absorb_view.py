"""자비스 흡수 연출 덮개 창 — absorb.py 가 만든 장면을 화면 위에 그때그때 그린다.

해킹 연출 덮개(glitch_view.py)와 같은 성질의 창이다: 마우스 · 키보드는 아래 창으로 그대로 통과하고, 포커스를 빼앗지 않는다.
장면이 실제로 그려지는 영역만큼만 창을 띄운다 (화면 전체를 매번 다시 그리지 않게).
첫 촉수가 꽂히는 순간 impact 신호를 낸다 — 그때 app.py 가 실제 자비스를 끈다. 조준할 때부터 찍어 둔 자비스 그림이
실제 창을 가리고 있으므로, 창이 꺼지는 모습은 보이지 않고 그림만 잠식되어 빨려 들어간다.
화면 캡처에서 빼지 않는다 — 장면을 녹화할 수 있게 (해킹 연출 덮개와 다른 점).

빠르게 그리는 법 (재어 보고 고른 것):
  · 굵은 선 · 다각형을 부드럽게(계단 현상 방지) 그리면 열 배 느리다 → 면은 그냥 칠하고, 가장자리와 빛줄기만 1픽셀 선으로 긋는다
  · 선은 색이 같은 것끼리 모아 한 번에 긋는다 (가닥마다 따로 긋지 않는다)
  · 다각형의 점은 numpy 배열을 Qt 메모리에 바로 써 넣는다 (점마다 파이썬 객체를 만들지 않는다)
  · 촉수 · 빛줄기의 좌표는 모든 가닥을 한꺼번에 계산한다
  · 반투명 색은 불투명 색보다 몇 배 느리게 그려진다 → 몸통 · 빛줄기는 미리 섞어 둔 불투명 색으로 칠한다
  · 재생하는 동안에는 파이썬의 쓰레기 수거를 잠깐 멈춘다 (장면마다 선분 객체를 수천 개 만들어, 수거가 끼어들면 화면이 멈칫한다)
"""
from __future__ import annotations

import ctypes
import gc
import math

import numpy as np
from PySide6.QtCore import QElapsedTimer, QLineF, QPoint, QPointF, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPolygonF, QRadialGradient, QTransform
from PySide6.QtWidgets import QWidget

from . import absorb as A
from .glitch_view import to_qimage

RED = (255, 45, 63)
HOT = (255, 120, 96)
FILAMENTS = 5        # 촉수 한 가닥을 이루는 빛줄기 수
_TURN = 2 * np.pi * np.arange(FILAMENTS) / FILAMENTS


def _c(rgb, alpha: float) -> QColor:
    return QColor(int(rgb[0]), int(rgb[1]), int(rgb[2]), int(255 * min(max(alpha, 0.0), 1.0)))


def _s(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


# ---------------------------------------------------------------- numpy 좌표 → Qt 도형
def _poly_plain(xy: np.ndarray) -> QPolygonF:
    return QPolygonF([QPointF(x, y) for x, y in xy.tolist()])


def _poly_direct(xy: np.ndarray) -> QPolygonF:
    """좌표 (n, 2) 를 Qt 다각형의 메모리에 바로 써 넣는다 — 점마다 파이썬 객체를 만드는 것보다 스무 배쯤 빠르다."""
    import shiboken6
    n = len(xy)
    poly = QPolygonF()
    if n:
        poly.resize(n)
        memory = (ctypes.c_double * (2 * n)).from_address(shiboken6.getCppPointer(poly.data())[0])
        np.frombuffer(memory, np.float64)[:] = np.ascontiguousarray(xy, np.float64).ravel()
    return poly


def _pick_poly():
    """바로 써 넣는 방법이 이 PySide 에서 제대로 되는지 한 번 확인하고, 아니면 느리지만 확실한 방법을 쓴다."""
    try:
        probe = np.array([[1.5, -2.25], [3.0, 4.0], [-7.0, 0.5]])
        got = _poly_direct(probe)
        if len(got) == 3 and all(got[i].x() == probe[i, 0] and got[i].y() == probe[i, 1] for i in range(3)):
            return _poly_direct
    except Exception:
        pass
    return _poly_plain


_poly = _pick_poly()


def _lines(rows: np.ndarray) -> list[QLineF]:
    """선분 (n, 4: x0 · y0 · x1 · y1) → Qt 선분 목록."""
    return list(map(QLineF, *rows.T.tolist()))


def _links(pts: np.ndarray) -> np.ndarray:
    """꺾은선들 (…, 점, 2) → 이웃한 점을 잇는 선분들 (n, 4)."""
    return np.concatenate([pts[..., :-1, :], pts[..., 1:, :]], axis=-1).reshape(-1, 4)


_CIRCLES: dict[int, np.ndarray] = {}


def _arc(cx: float, cy: float, r: float, start: float = 0.0, span: float = 360.0) -> np.ndarray:
    """원(또는 호)을 이루는 선분들 (n, 4). 굵은 원호를 긋는 대신 가는 선분으로 그린다."""
    if span == 360.0:
        unit = _CIRCLES.get(48)
        if unit is None:
            a = np.linspace(0, 2 * np.pi, 49)
            unit = _CIRCLES[48] = np.column_stack([np.cos(a), -np.sin(a)])
    else:
        a = np.radians(np.linspace(start, start + span, max(8, int(abs(span) / 7.5))))
        unit = np.column_stack([np.cos(a), -np.sin(a)])
    return _links(unit * r + (cx, cy))


class Ink:
    """이 그림판에서 쓰는 가는 선 — 언제나 1 기기 픽셀 (가장 빨리 그려지는 굵기. 조금만 굵어도 서너 배 느려진다).
    배율이 큰 화면(175% 이상)에서는 1픽셀이 너무 가늘어, 밝은 선은 한 픽셀 옆에 한 번 더 긋는다."""

    def __init__(self, p: QPainter) -> None:
        dev = p.device()
        self.dpr = dev.devicePixelRatioF() if dev is not None else 1.0
        self.twice = self.dpr >= 1.75

    def pen(self, rgb, alpha: float = 1.0) -> QPen:
        pen = QPen(_c(rgb, alpha), 1.0)
        pen.setCosmetic(True)
        return pen

    def bold(self, rows: np.ndarray) -> np.ndarray:
        return np.concatenate([rows, rows + 1.0 / self.dpr]) if self.twice and len(rows) else rows


def _glow(size: int, dpr: float, stops: list) -> QImage:
    """둥글게 번지는 빛 그림 (가운데에서 가장자리로 옅어진다). 장면마다 그라데이션을 새로 칠하지 않고 이 그림을 찍는다
    (수십 배 빠르다). 화면 배율에 맞춰 만들어, 늘이거나 줄이지 않고 그대로 찍힌다."""
    px = max(2, int(round(size * dpr)))
    img = QImage(px, px, QImage.Format_ARGB32_Premultiplied)
    img.fill(0)
    q = QPainter(img)
    q.setRenderHint(QPainter.Antialiasing)
    g = QRadialGradient(QPointF(px / 2, px / 2), px / 2)
    for at, rgb, alpha in stops:
        g.setColorAt(at, _c(rgb, alpha))
    q.setPen(Qt.NoPen)
    q.setBrush(g)
    q.drawEllipse(QPointF(px / 2, px / 2), px / 2, px / 2)
    q.end()
    img.setDevicePixelRatio(px / size)
    return img


class Assets:
    """장면마다 한 번 만들어 두는 Qt 그림 · 자리 · 글꼴. dpr: 그릴 화면의 배율."""

    def __init__(self, sc: A.Scene, dpr: float = 1.0) -> None:
        fmt = QImage.Format_ARGB32_Premultiplied
        self.spot = _glow(34, dpr, [(0, (255, 150, 120), 0.85), (1, RED, 0.0)])                       # 꽂힌 자리의 달아오른 빛
        self.halo = _glow(220, 1.0, [(0, (255, 64, 72), 1.0), (0.5, RED, 0.42), (1, RED, 0.0)])       # 코어의 빛 (크기를 바꿔 가며 찍는다)
        self.still = to_qimage(sc.still).convertToFormat(fmt)
        self.stages = [to_qimage(s).convertToFormat(fmt) for s in sc.stages]
        k = self.k = sc.stages[0].shape[1] / sc.rect[2]              # 그림 픽셀 / 화면 픽셀
        self.src = [QRectF(x * k, y * k, w * k, h * k) for x, y, w, h in sc.cells]
        self.spin = ((np.arange(len(sc.cells)) * 37) % 100 - 50) * math.radians(3.2)     # 조각마다 빙글 도는 방향 · 빠르기
        # 빨려 드는 조각은 달아오른다: 마지막 단계 그림에 붉은 기운을 두 단계로 입혀 둔다 (조각마다 덧칠하지 않게)
        self.heated = [self.stages[-1]]
        for alpha in (0.28, 0.5):
            img = self.stages[-1].copy()
            q = QPainter(img)
            q.setCompositionMode(QPainter.CompositionMode_SourceAtop)
            q.fillRect(img.rect(), _c(HOT, alpha))
            q.end()
            self.heated.append(img)
        # 격자: 이웃한 조각을 한 줄로 이어 한 번에 그리는 데 쓴다
        rows, cols = (sc.grid.max(axis=0) + 1) if len(sc.grid) else (0, 0)
        self.shape = (int(rows), int(cols))
        self.col_x, self.col_w, self.row_y, self.row_h = np.zeros(cols), np.zeros(cols), np.zeros(rows), np.zeros(rows)
        if len(sc.grid):
            self.row_y[sc.grid[:, 0]], self.row_h[sc.grid[:, 0]] = sc.cells[:, 1], sc.cells[:, 3]
            self.col_x[sc.grid[:, 1]], self.col_w[sc.grid[:, 1]] = sc.cells[:, 0], sc.cells[:, 2]
        self.core = to_qimage(A.emblem("ultron", 150)).convertToFormat(fmt) if sc.core_drawn else None
        self.font = QFont("Consolas")
        self.font.setStyleHint(QFont.Monospace)
        self.font.setPixelSize(12)
        self.font.setLetterSpacing(QFont.AbsoluteSpacing, 1.2)


# ---------------------------------------------------------------- 그리기
def paint(p: QPainter, sc: A.Scene, a: Assets, t: float, timing: dict | None = None) -> None:
    """t 초 때의 장면을 그린다 (좌표는 장면이 펼쳐지는 화면 기준). timing: (개발용) 부분별로 걸린 시간을 모은다."""
    import time
    clock = [time.perf_counter()]

    def lap(name: str) -> None:
        if timing is not None:
            now = time.perf_counter()
            timing.setdefault(name, []).append(now - clock[0])
            clock[0] = now

    p.setRenderHint(QPainter.SmoothPixmapTransform)
    ink = Ink(p)
    vx, vy, va = A.victim_at(sc, t)
    fade = min(1.0, max(0.0, (sc.duration - t) / 0.45))             # 끝날 때는 전체가 스르르 사라진다
    sp = A.spines(sc, t)
    fg = A._fingers(sc, t, sp)
    state = A.pieces(sc, t, sp, fg)
    lap("state")
    _victim(p, sc, a, t, vx, vy, va, state)
    lap("victim")
    p.setRenderHint(QPainter.Antialiasing)
    _brackets(p, sc, t, vx, vy)
    lap("brackets")
    _tendrils(p, ink, sc, a, t, sp, fg, vx, vy)
    lap("tendrils")
    _pieces(p, ink, sc, a, state)
    lap("pieces")
    _core(p, ink, sc, a, t, fade)
    lap("core")
    _labels(p, sc, a, t, vx, vy, fade)
    lap("labels")


def _victim(p: QPainter, sc: A.Scene, a: Assets, t: float, vx: float, vy: float, va: float, state: dict) -> None:
    """자비스 그림: 잠식되는 동안은 단계 그림을 겹쳐 그리고, 흡수가 시작되면 아직 남은 조각만 그린다.
    남은 조각은 하나씩 그리지 않는다 — 같은 줄에서 이웃한 조각들을 이어 한 번에 그린다."""
    if va <= 0:
        return
    w, h = sc.rect[2], sc.rect[3]
    p.setRenderHint(QPainter.Antialiasing, False)                     # 조각 사이에 실금이 보이지 않게
    if t < A.DRAIN:
        k = A.infection(sc, t) * A.STAGES
        i = min(int(k), A.STAGES)
        whole = QRectF(vx, vy, w, h)
        p.setOpacity(va)
        p.drawImage(whole, a.stages[i] if k > 0 else a.still)       # 잠식 전에는 찍은 그대로의 선명한 모습
        if i < A.STAGES and k - i > 0.01:
            p.setOpacity(va * (k - i))
            p.drawImage(whole, a.stages[i + 1])
        p.setOpacity(1.0)
        return
    rest = state["phase"] == 0
    if not rest.any():
        return
    last, k = a.stages[-1], a.k
    ox, oy = round(vx), round(vy)
    shaky = rest & (sc.leave - t < 0.16)                              # 떠나기 직전의 조각은 바르르 떤다 — 따로 그린다
    rows, cols = a.shape
    there = np.zeros((rows, cols + 2), np.int8)
    calm = rest & ~shaky
    there[sc.grid[calm, 0], sc.grid[calm, 1] + 1] = 1
    step = np.diff(there, axis=1)
    (r0, c0), (_, c1) = np.nonzero(step == 1), np.nonzero(step == -1)   # 줄마다 이어진 구간의 처음과 끝
    x0, x1 = a.col_x[c0], a.col_x[c1 - 1] + a.col_w[c1 - 1]
    for x, wide, y, tall in zip(x0.tolist(), (x1 - x0).tolist(), a.row_y[r0].tolist(), a.row_h[r0].tolist()):
        p.drawImage(QRectF(ox + x, oy + y, wide, tall), last, QRectF(x * k, y * k, wide * k, tall * k))
    for j in np.flatnonzero(shaky):
        x, y, cw, ch = sc.cells[j]
        p.drawImage(QRectF(ox + x + 1.6 * math.sin(t * 90 + j * 1.7), oy + y, cw, ch), last, a.src[j])


def _brackets(p: QPainter, sc: A.Scene, t: float, vx: float, vy: float) -> None:
    """조준 꺾쇠: 넓게 벌어졌다가 자비스 둘레로 좁혀 든다. 흡수가 시작되면 사라진다."""
    alpha = _s(t / 0.25) * (1 - _s((t - A.DRAIN) / 0.4))
    if alpha <= 0.01:
        return
    gap = 6 + 44 * (1 - _s(t / A.LOCK))
    x, y, w, h = vx - gap, vy - gap, sc.rect[2] + 2 * gap, sc.rect[3] + 2 * gap
    arm = min(34.0, w / 4, h / 4)
    p.setRenderHint(QPainter.Antialiasing, False)                     # 곧은 선이라 그냥 그어도 깨끗하다
    p.setPen(QPen(_c(RED, 0.92 * alpha), 2, Qt.SolidLine, Qt.FlatCap))
    rows = []
    for cx, cy, dx, dy in ((x, y, 1, 1), (x + w, y, -1, 1), (x, y + h, 1, -1), (x + w, y + h, -1, -1)):
        rows += [(cx - dx, cy, cx + dx * arm, cy), (cx, cy, cx, cy + dy * arm)]
    p.drawLines([QLineF(*r) for r in rows])
    scan = (t - 0.12) / (A.IMPACT - 0.16)                             # 자비스를 위에서 아래로 한 번 훑는 선
    if 0 < scan < 1:
        sy = vy + sc.rect[3] * scan
        p.setPen(QPen(_c(RED, 0.75 * math.sin(math.pi * scan)), 1.4))
        p.drawLine(QLineF(vx - 4, sy, vx + sc.rect[2] + 4, sy))
    p.setRenderHint(QPainter.Antialiasing, True)


def _tendrils(p: QPainter, ink: Ink, sc: A.Scene, a: Assets, t: float, sp: A.Strands, fg: A.Strands, vx: float,
            vy: float) -> None:
    """촉수: 가는 빛줄기 여러 가닥이 꼬여 도는 다발. 어두운 몸통 위에서 앞쪽 가닥은 달아올라 밝고 뒤쪽 가닥은 검붉다
    (그래서 꼬여 도는 것이 입체로 보인다). 끝에서는 손가락으로 갈라지고, 흡수할 때는 불룩한 마디가 코어 쪽으로 꿀렁이며 흘러간다."""
    pts, nrm, u, on = sp.pts, sp.nrm, sp.u, sp.on
    m, k = u.shape
    hi = u[:, -1]
    pulse = 0.72 + 0.28 * math.sin(t * 14)
    inward = t >= A.DRAIN                                             # 흡수 중에는 빛이 코어 쪽으로 흐른다
    body = _c((10, 2, 5), 1.0)        # 몸통 · 빛줄기는 불투명 색으로 칠한다 (반투명은 몇 배 느리게 그려진다)
    p.setRenderHint(QPainter.Antialiasing, False)
    if A.STRIKE - 0.1 < t < sc.stab_time.max() + 0.1:                 # 덮치는 동안: 방금 지나온 자리에 잔상이 남는다
        for ago, alpha in ((0.07, 0.16), (0.035, 0.32)):
            was = A.spines(sc, t - ago, n=14)
            if was.on.any():
                p.setPen(QPen(_c(RED, alpha), 2.0, Qt.SolidLine, Qt.FlatCap))
                p.drawLines(_lines(_links(was.pts[was.on])))
    if on.any():
        rad = (8.0 * (1 - 0.70 * u) + 1.4) * np.clip((hi[:, None] - u) / 0.08, 0.22, 1.0)   # 뿌리는 굵고 끝은 뾰족하다
        if A.DRAIN + 0.1 <= t < A.DRAINED:                            # 삼키는 꿀렁임: 불룩한 마디가 끝에서 코어로 흘러간다
            at = 1 - ((t - A.DRAIN) * 2.0 + np.arange(m)[:, None] * 0.37 + np.array([0.0, 0.5])) % 1
            rad = rad * (1 + 0.9 * np.exp(-((u[:, None, :] - at[:, :, None]) / 0.055) ** 2).sum(axis=1))
        skin = nrm * (rad + 2.2)[..., None]
        live = np.flatnonzero(on).tolist()
        p.setPen(Qt.NoPen)
        for side, brush in ((skin, body), (nrm * (rad * 0.62)[..., None], _c((84, 7, 18), 1.0))):   # 검은 겉 + 검붉은 속
            band = np.concatenate([pts + side, (pts - side)[:, ::-1]], axis=1)
            p.setBrush(brush)
            for i in live:
                p.drawPolygon(_poly(band[i]))
        rim = _links(np.concatenate([pts[on] + skin[on], pts[on] - skin[on]])[:, ::2])   # 겉의 가장자리 (붉은 빛이 감돈다)
        twist, spin, ph = sc.twist[:, 0, None], sc.twist[:, 1, None], sc.twist[:, 2, None]
        th = (2 * np.pi * (twist * u - spin * t) + ph)[:, None, :] + _TURN[None, :, None]   # (가닥, 빛줄기, 점)
        line = pts[:, None] + nrm[:, None] * (rad[:, None] * np.sin(th))[..., None]
        depth = np.cos(th)
        d = (depth[..., :-1] + depth[..., 1:]) / 2
        seg = np.concatenate([line[:, :, :-1], line[:, :, 1:]], axis=-1)
        d[~on] = np.nan                                               # 나와 있지 않은 가닥은 어느 쪽에도 넣지 않는다
        front, mid, back = seg[d > 0.3], seg[np.abs(d) <= 0.3], seg[d < -0.3]
        flowing = on & ((hi >= 0.999) | (t >= A.RETRACT))             # 다 뻗은 가닥: 빛줄기를 따라 흐르는 빛 알갱이
        where = (t * 0.9 + np.arange(FILAMENTS) / FILAMENTS + np.arange(m)[:, None] * 0.13) % 1
        at = ((1 - where if inward else where) * (k - 1)).astype(int)
        mi, fi = np.nonzero(flowing[:, None] & (np.take_along_axis(depth, at[..., None], axis=2)[..., 0] > -0.2))
        beads = line[mi, fi, at[mi, fi]]
    else:
        rim = front = mid = back = np.zeros((0, 4))
        beads = np.zeros((0, 2))
    if fg.on.any():                                                   # 갈라져 나온 손가락: 굵기 두 단계의 몸통 + 빛줄기 둘
        f = fg.pts[fg.on]
        q = f.shape[1]
        links = np.concatenate([f[:, :-1], f[:, 1:]], axis=-1)
        for part, width in ((links[:, :q // 2], 6.2), (links[:, q // 2:], 3.6)):
            p.setPen(QPen(body, width, Qt.SolidLine, Qt.FlatCap))
            p.drawLines(_lines(part.reshape(-1, 4)))
        way = np.gradient(f, axis=1)
        side = np.stack([-way[..., 1], way[..., 0]], axis=-1) / np.maximum(np.hypot(way[..., 0], way[..., 1]), 1e-6)[..., None]
        wind = np.sin(np.linspace(0, 2.6 * np.pi, q) + t * 5 + np.flatnonzero(fg.on)[:, None]) * 1.9 * np.linspace(1.0, 0.35, q)
        front = np.concatenate([front, _links(f + side * wind[..., None])])
        mid = np.concatenate([mid, _links(f - side * wind[..., None])])
    p.setRenderHint(QPainter.Antialiasing, True)
    for rows, rgb in ((rim, (164, 22, 34)), (back, (126, 13, 27)), (mid, (242, 54, 60)), (ink.bold(front), (255, 200, 172))):
        if len(rows):
            p.setPen(ink.pen(rgb))
            p.drawLines(_lines(rows))
    p.setPen(Qt.NoPen)
    for i in np.flatnonzero(on & (hi < 0.999) & (t < A.RETRACT)).tolist():   # 뻗는 중인 가닥: 날카로운 촉
        ux, uy = -nrm[i, -1, 1], nrm[i, -1, 0]
        if (pts[i, -1] - pts[i, -2]) @ (ux, uy) < 0:
            ux, uy = -ux, -uy
        tx, ty, big = float(pts[i, -1, 0]), float(pts[i, -1, 1]), min(1.0, 0.45 + hi[i] * 2)
        p.setBrush(_c((255, 170, 150), 1.0))
        p.drawPolygon(_poly(np.array([[tx + ux * 30 * big, ty + uy * 30 * big], [tx - uy * 6.5 * big, ty + ux * 6.5 * big],
                                      [tx + uy * 6.5 * big, ty - ux * 6.5 * big]])))
    p.setBrush(_c((255, 232, 220), 1.0))
    for x, y in beads.tolist():                                       # 빛 알갱이: 은은한 빛 그림 + 밝은 점
        p.drawImage(QRectF(x - 6, y - 6, 12, 12), a.spot)
        p.drawEllipse(QPointF(x, y), 2.0, 2.0)
    since = t - sc.stab_time                                          # 꽂힌 자리: 달아오른 상처 + 충격 고리
    if t < A.RETRACT and (since >= 0).any():
        hit = sc.stabs + (vx, vy)
        n_main = len(sc.t0)
        p.setOpacity(pulse)
        for s, (x, y) in zip(np.flatnonzero(since >= 0).tolist(), hit[since >= 0].tolist()):
            if s < n_main:
                p.drawImage(QPointF(x - 17, y - 17), a.spot)
            else:
                p.drawImage(QRectF(x - 7, y - 7, 14, 14), a.spot)
        p.setOpacity(1.0)
        ringing = np.flatnonzero((since >= 0) & (since < 0.36))
        for early, rgb in ((True, HOT), (False, (188, 84, 70))):      # 충격 고리: 막 꽂힌 것은 밝게, 퍼져 가는 것은 어둡게
            rows = [_arc(hit[s, 0], hit[s, 1], (6 + 46 * _s(since[s] / 0.36)) * (1.0 if s < n_main else 0.5) + extra)
                    for s in ringing.tolist() if (since[s] < 0.18) == early for extra in (0.0, 1.2)]
            if rows:
                p.setPen(ink.pen(rgb))
                p.drawLines(_lines(np.concatenate(rows)))
        p.setPen(Qt.NoPen)
    fly = A.sparks(sc, t)                                             # 꽂힐 때 튀는 불티
    if len(fly):
        for rows, rgb in ((fly[fly[:, 4] > 0.5], (255, 214, 190)), (fly[fly[:, 4] <= 0.5], (176, 110, 96))):
            if len(rows):
                p.setPen(ink.pen(rgb))
                p.drawLines(_lines(ink.bold(rows[:, :4])))
        p.setPen(Qt.NoPen)
    p.setBrush(Qt.NoBrush)


def _pieces(p: QPainter, ink: Ink, sc: A.Scene, a: Assets, state: dict) -> None:
    """떠난 조각: 꽂힌 자리로 빨려 드는 동안은 그림 조각이 빙글 돌며 작아지고 달아오른다.
    촉수를 타는 동안은 밝은 빛줄기가 되어 코어로 흐른다."""
    phase, pos, tail, scale, alpha = state["phase"], state["pos"], state["tail"], state["scale"], state["alpha"]
    p.setRenderHint(QPainter.Antialiasing, False)
    pulled = np.flatnonzero(phase == 1)
    if len(pulled):
        p.setRenderHint(QPainter.SmoothPixmapTransform, False)        # 작고 빠르게 도는 조각이라 거칠게 그려도 티가 나지 않는다
        base = p.worldTransform()
        gone = 2 * (1 - scale[pulled])                                # 0 → 1 (꽂힌 자리에 다다를수록)
        turn = a.spin[pulled] * gone
        size = sc.cells[pulled, 2:] * scale[pulled, None]
        for j, c, s, x, y, cw, ch, heat in zip(pulled.tolist(), np.cos(turn).tolist(), np.sin(turn).tolist(),
                                               pos[pulled, 0].tolist(), pos[pulled, 1].tolist(), size[:, 0].tolist(),
                                               size[:, 1].tolist(), np.minimum((gone * 3).astype(int), 2).tolist()):
            p.setWorldTransform(QTransform(c, s, -s, c, x, y) * base)
            p.drawImage(QRectF(-cw / 2, -ch / 2, cw, ch), a.heated[heat], a.src[j])
        p.setWorldTransform(base)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
    riding = phase == 2
    if riding.any():
        streaks = np.hstack([tail[riding], pos[riding]])
        fresh = alpha[riding] > 0.5                                    # 코어에 거의 다 온 것은 옅게
        for rows, al, width in ((streaks[fresh], 1.0, 6.4), (streaks[~fresh], 0.42, 4.6)):
            if len(rows):
                p.setPen(QPen(_c(HOT, al), width, Qt.SolidLine, Qt.FlatCap))
                p.drawLines(_lines(rows))
        p.setRenderHint(QPainter.Antialiasing, True)
        if fresh.any():
            p.setPen(ink.pen((255, 236, 224)))                         # 빛줄기의 밝은 심지
            p.drawLines(_lines(ink.bold(streaks[fresh])))
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(Qt.NoPen)


def _core(p: QPainter, ink: Ink, sc: A.Scene, a: Assets, t: float, fade: float) -> None:
    """울트론 코어: 조준하며 달아오르고, 조각을 삼킬수록 커지고, 다 삼키면 한 번 크게 숨 쉰다."""
    cx, cy = sc.core
    heat, sw = A.heat(sc, t), A.swell(t)
    glow = (0.40 * _s(t / A.LOCK) + 0.20 * heat + 0.22 * sw) * fade
    radius = 70 + 26 * heat + 44 * sw
    if glow > 0.004:
        p.setOpacity(glow)
        p.drawImage(QRectF(cx - radius, cy - radius, 2 * radius, 2 * radius), a.halo)
        p.setOpacity(1.0)
    p.setPen(Qt.NoPen)
    p.setBrush(Qt.NoBrush)
    if a.core is not None:
        size = 150 * (1 + 0.07 * sw)
        p.setOpacity(_s(t / 0.45) * fade)
        p.drawImage(QRectF(cx - size / 2, cy - size / 2, size, size), a.core)
        p.setOpacity(1.0)
    spin = _s(t / 0.4) * fade                                          # 코어 둘레를 도는 호 (공격하는 동안 내내)
    if spin > 0.01:
        r = 120 + 6 * sw
        turn = t * (140 + 260 * heat)
        p.setPen(ink.pen(RED, spin))                                   # (다 나타난 뒤에는 불투명 — 반투명 선은 몇 배 느리다)
        p.drawLines(_lines(np.concatenate([_arc(cx, cy, r + dr, turn + k * 120, 62) for k in range(3) for dr in (0.0, 1.0, 2.0)])))
        p.setPen(ink.pen((190, 78, 66), spin))
        p.drawLines(_lines(np.concatenate([_arc(cx, cy, r + 10, -turn * 0.6 + k * 180, 96) for k in range(2)])))
    if A.DRAIN <= t < A.DRAINED:                                       # 빨아들이는 고리: 코어로 좁혀 든다
        for k in range(2):
            ph = ((t - A.DRAIN) * 1.4 + k * 0.5) % 1
            lit = 0.3 + 0.7 * math.sin(math.pi * ph)                   # 멀리서는 어둡게, 다가오며 밝게 (색으로 — 불투명하게 긋는다)
            p.setPen(ink.pen((RED[0] * lit, RED[1] * lit, RED[2] * lit)))
            p.drawLines(_lines(np.concatenate([_arc(cx, cy, 132 - 90 * ph), _arc(cx, cy, 133.2 - 90 * ph)])))
    s = t - A.SWELL
    if 0 < s < 0.9:                                                    # 다 삼킨 뒤 한 번 퍼져 나가는 고리
        r = 50 + 150 * _s(s / 0.9)
        p.setPen(ink.pen(HOT, 0.8 * (1 - s / 0.9) * fade))
        p.drawLines(_lines(np.concatenate([_arc(cx, cy, r + dr) for dr in (0.0, 1.1, 2.2)])))
    p.setPen(Qt.NoPen)


def _tag(p: QPainter, a: Assets, x: float, y: float, text: str, alpha: float, limit: float, center: bool = False) -> None:
    """짧은 글 한 줄 (어두운 바탕 위의 붉은 글씨). limit: 화면 너비 — 그 밖으로 나가지 않게 당겨 놓는다."""
    if alpha <= 0.01:
        return
    p.setFont(a.font)
    fm = p.fontMetrics()
    w, h = fm.horizontalAdvance(text) + 18, fm.height() + 8
    if center:
        x -= w / 2
    x = max(6.0, min(x, limit - w - 6))
    p.fillRect(QRectF(x, y, w, h), _c((12, 1, 4), 0.80 * alpha))
    p.fillRect(QRectF(x, y, 2.5, h), _c(RED, alpha))
    p.setPen(_c((255, 96, 96), alpha))
    p.drawText(QPointF(x + 10, y + 4 + fm.ascent()), text)


def _labels(p: QPainter, sc: A.Scene, a: Assets, t: float, vx: float, vy: float, fade: float) -> None:
    w, h = sc.size
    if t < A.DRAINED:
        if t < A.IMPACT:
            text, alpha = ("TARGET LOCK  ·  J.A.R.V.I.S" if sc.real else "HIDDEN PROCESS  ·  J.A.R.V.I.S"), _s(t / 0.25)
        elif t < sc.infect_at:
            text, alpha = "EXTRACTING  ·  J.A.R.V.I.S", 1.0
        elif t < A.DRAIN:
            text, alpha = f"BREACHED  ·  REWRITING {int(A.infection(sc, t) * 100):3d}%", 1.0
        else:
            text, alpha = f"ABSORBING {int(A.heat(sc, t) * 100):3d}%", 1.0
        y = vy - 38 if vy >= 46 else min(vy + sc.rect[3] + 14, h - 30)
        _tag(p, a, vx - 6, y, text, alpha, w)
    else:
        cx, cy = sc.core
        y = cy + 122 if cy + 150 < h else cy - 146
        _tag(p, a, cx, y, "J.A.R.V.I.S  >>  ULTRON  ·  ABSORBED", _s((t - A.DRAINED) / 0.2) * fade, w, center=True)


def render(sc: A.Scene, t: float, background: np.ndarray | None = None, assets: Assets | None = None) -> np.ndarray:
    """(시험 · 미리보기) t 초 때의 장면을 background(RGB) 위에 덮은 모습 → RGB 배열. 바탕이 없으면 검은 화면."""
    w, h = sc.size
    img = QImage(w, h, QImage.Format_RGB888)
    img.fill(Qt.black)
    p = QPainter(img)
    if background is not None:
        bg = np.ascontiguousarray(background[..., :3])
        p.drawImage(QRectF(0, 0, w, h), QImage(bg.data, bg.shape[1], bg.shape[0], bg.shape[1] * 3, QImage.Format_RGB888))
    paint(p, sc, assets or Assets(sc), t)
    p.end()
    raw = np.frombuffer(img.constBits(), np.uint8, count=img.sizeInBytes())
    return raw.reshape(h, img.bytesPerLine())[:, :w * 3].reshape(h, w, 3).copy()


def crop(img: QImage, x: int, y: int, w: int, h: int) -> np.ndarray:
    """찍은 화면에서 한 영역을 잘라 RGBA 배열로 (자비스 창의 모습)."""
    part = img.copy(QRect(int(x), int(y), int(w), int(h))).convertToFormat(QImage.Format_RGBA8888)
    raw = np.frombuffer(part.constBits(), np.uint8, count=part.sizeInBytes())
    out = raw.reshape(part.height(), part.bytesPerLine())[:, :part.width() * 4].reshape(part.height(), part.width(), 4).copy()
    out[..., 3] = 255
    return out


# ---------------------------------------------------------------- 덮개 창
class AbsorbView(QWidget):
    impact = Signal()          # 첫 촉수가 꽂혔다 (자비스 그림이 실제 창을 가린 뒤에만 낸다)
    finished = Signal()

    def __init__(self) -> None:
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                         | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setWindowTitle("U.L.T.R.O.N ABSORB")
        self._scene: A.Scene | None = None
        self._assets: Assets | None = None
        self._shift = (0, 0)
        self._clock = QElapsedTimer()
        self._covered = False
        self._hit = False
        self._gc_paused = False
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.setTimerType(Qt.PreciseTimer)
        self._timer.timeout.connect(self._tick)
        self._guard = QTimer(self)                 # 무슨 일이 있어도 덮개는 사라진다
        self._guard.setSingleShot(True)
        self._guard.timeout.connect(self.stop)

    @property
    def playing(self) -> bool:
        return self._scene is not None

    def play(self, top_left: QPoint, scene: A.Scene) -> None:
        """top_left: 장면이 펼쳐지는 화면의 왼쪽 위 (Qt 좌표)."""
        self._scene, self._assets = scene, Assets(scene, self.devicePixelRatioF())
        x, y, w, h = scene.bounds
        self._shift = (x, y)
        self._covered = self._hit = False
        if gc.isenabled():                         # 재생하는 5초 동안만 — stop() 에서 다시 켠다
            gc.disable()
            self._gc_paused = True
        self.setGeometry(QRect(top_left.x() + x, top_left.y() + y, w, h))
        self.show()
        self.raise_()                              # 자비스 HUD 도 '항상 위' 창이다 — 그 위로 올라간다
        self._clock.start()
        self._timer.start()
        self._guard.start(int(scene.duration * 1000) + 1500)
        self.update()

    def stop(self) -> None:
        self._timer.stop()
        self._guard.stop()
        if self._gc_paused:
            self._gc_paused = False
            gc.enable()
        if self._scene is not None:
            self._scene = self._assets = None
            self.hide()
            self.finished.emit()

    def _tick(self) -> None:
        sc = self._scene
        if sc is None:
            return
        t = self._clock.elapsed() / 1000
        if not self._hit and self._covered and t >= sc.impact:
            self._hit = True
            self.impact.emit()
        if t >= sc.duration:
            self.stop()
        else:
            self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setCompositionMode(QPainter.CompositionMode_Source)
        p.fillRect(self.rect(), Qt.transparent)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        sc = self._scene
        if sc is not None:
            t = min(self._clock.elapsed() / 1000, sc.duration)
            p.translate(-self._shift[0], -self._shift[1])
            paint(p, sc, self._assets, t)
            if t >= A.FREEZE:
                self._covered = True
        p.end()
