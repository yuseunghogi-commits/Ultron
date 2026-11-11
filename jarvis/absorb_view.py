"""자비스 흡수 연출 덮개 창 — absorb.py 가 만든 장면을 화면 위에 그때그때 그린다.

해킹 연출 덮개(glitch_view.py)와 같은 성질의 창이다: 마우스 · 키보드는 아래 창으로 그대로 통과하고, 포커스를 빼앗지 않는다.
장면이 실제로 그려지는 영역만큼만 창을 띄운다 (화면 전체를 매번 다시 그리지 않게).
첫 케이블이 꽂히는 순간 impact 신호를 낸다 — 그때 app.py 가 실제 자비스를 끈다. 조준할 때부터 찍어 둔 자비스 그림이
실제 창을 가리고 있으므로, 창이 꺼지는 모습은 보이지 않고 그림만 잠식되어 빨려 들어간다.
화면 캡처에서 빼지 않는다 — 장면을 녹화할 수 있게 (해킹 연출 덮개와 다른 점).
"""
from __future__ import annotations

import math

import numpy as np
from PySide6.QtCore import QElapsedTimer, QLineF, QPoint, QPointF, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPolygonF, QRadialGradient
from PySide6.QtWidgets import QWidget

from . import absorb as A
from .glitch_view import to_qimage

RED = (255, 45, 63)
HOT = (255, 120, 96)


def _c(rgb, alpha: float) -> QColor:
    return QColor(int(rgb[0]), int(rgb[1]), int(rgb[2]), int(255 * min(max(alpha, 0.0), 1.0)))


def _s(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


class Assets:
    """장면마다 한 번 만들어 두는 Qt 그림 · 자리 · 글꼴."""

    def __init__(self, sc: A.Scene) -> None:
        fmt = QImage.Format_ARGB32_Premultiplied
        self.stages = [to_qimage(s).convertToFormat(fmt) for s in sc.stages]
        k = sc.stages[0].shape[1] / sc.rect[2]
        self.src = [QRectF(x * k, y * k, w * k, h * k) for x, y, w, h in sc.cells]
        self.tint = [(r, g, b) for r, g, b in sc.tint]
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
    vx, vy, va = A.victim_at(sc, t)
    fade = min(1.0, max(0.0, (sc.duration - t) / 0.45))             # 끝날 때는 전체가 스르르 사라진다
    state = A.pieces(sc, t)
    lap("state")
    _victim(p, sc, a, t, vx, vy, va, state)
    lap("victim")
    p.setRenderHint(QPainter.Antialiasing)
    _brackets(p, sc, t, vx, vy)
    lap("brackets")
    _cables(p, sc, t)
    lap("cables")
    _pieces(p, sc, a, state)
    lap("pieces")
    _core(p, sc, a, t, fade)
    lap("core")
    _labels(p, sc, a, t, vx, vy, fade)
    lap("labels")


def _victim(p: QPainter, sc: A.Scene, a: Assets, t: float, vx: float, vy: float, va: float, state: dict) -> None:
    """자비스 그림: 잠식되는 동안은 단계 그림을 겹쳐 그리고, 흡수가 시작되면 아직 남은 조각만 그린다."""
    if va <= 0:
        return
    w, h = sc.rect[2], sc.rect[3]
    p.setRenderHint(QPainter.Antialiasing, False)                     # 조각 사이에 실금이 보이지 않게
    if t < A.DRAIN:
        k = A.infection(sc, t) * A.STAGES
        i = min(int(k), A.STAGES)
        whole = QRectF(vx, vy, w, h)
        p.setOpacity(va)
        p.drawImage(whole, a.stages[i])
        if i < A.STAGES and k - i > 0.01:
            p.setOpacity(va * (k - i))
            p.drawImage(whole, a.stages[i + 1])
        p.setOpacity(1.0)
        return
    last = a.stages[-1]
    ox, oy = round(vx), round(vy)
    for j in np.nonzero(state["phase"] == 0)[0]:
        x, y, cw, ch = sc.cells[j]
        # 떠나기 직전의 조각은 바르르 떤다
        shake = 1.6 * math.sin(t * 90 + j * 1.7) if sc.leave[j] - t < 0.16 else 0.0
        p.drawImage(QRectF(ox + x + shake, oy + y, cw, ch), last, a.src[j])


def _brackets(p: QPainter, sc: A.Scene, t: float, vx: float, vy: float) -> None:
    """조준 꺾쇠: 넓게 벌어졌다가 자비스 둘레로 좁혀 든다. 흡수가 시작되면 사라진다."""
    alpha = _s(t / 0.25) * (1 - _s((t - A.DRAIN) / 0.4))
    if alpha <= 0.01:
        return
    gap = 6 + 44 * (1 - _s(t / A.LOCK))
    x, y, w, h = vx - gap, vy - gap, sc.rect[2] + 2 * gap, sc.rect[3] + 2 * gap
    arm = min(34.0, w / 4, h / 4)
    p.setPen(QPen(_c(RED, 0.92 * alpha), 2))
    for cx, cy, dx, dy in ((x, y, 1, 1), (x + w, y, -1, 1), (x, y + h, 1, -1), (x + w, y + h, -1, -1)):
        p.drawPolyline(QPolygonF([QPointF(cx + dx * arm, cy), QPointF(cx, cy), QPointF(cx, cy + dy * arm)]))
    scan = (t - 0.12) / (A.IMPACT - 0.16)                             # 자비스를 위에서 아래로 한 번 훑는 선
    if 0 < scan < 1:
        sy = vy + sc.rect[3] * scan
        p.setPen(QPen(_c(RED, 0.75 * math.sin(math.pi * scan)), 1.4))
        p.drawLine(QLineF(vx - 4, sy, vx + sc.rect[2] + 4, sy))


def _thin(rgb, alpha: float) -> QPen:
    """부드럽게 그려지는 가는 선 (화면 배율과 상관없이 1픽셀 — 이 굵기만 빠르게 그려진다)."""
    pen = QPen(_c(rgb, alpha), 1.0)
    pen.setCosmetic(True)
    return pen


def _segments(pts: np.ndarray) -> list[QLineF]:
    return [QLineF(x0, y0, x1, y1) for x0, y0, x1, y1 in np.hstack([pts[:-1], pts[1:]]).tolist()]


def _ring(p: QPainter, cx: float, cy: float, r: float, start: float = 0.0, span: float = 360.0) -> None:
    """원(또는 호)을 지금의 펜으로 — 가는 선분 여러 개로 그린다 (굵은 원호를 긋는 것보다 훨씬 빠르다)."""
    a = np.radians(np.linspace(start, start + span, max(8, int(abs(span) / 7.5))))
    p.drawLines(_segments(np.column_stack([cx + r * np.cos(a), cy - r * np.sin(a)])))


def _cables(p: QPainter, sc: A.Scene, t: float) -> None:
    """케이블: 코어 쪽은 굵고 끝은 가는 검은 강철 띠 + 붉은 속 + 달아오른 심지, 등뼈 같은 마디, 흐르는 빛,
    꽂히기 전의 날카로운 촉, 꽂힌 자리의 충격 고리.
    띠는 계단 현상 방지 없이 빠르게 칠하고, 가장자리에만 부드러운 가는 선을 덧그린다 (전부 부드럽게 칠하면 열 배 느리다)."""
    lines = A.cables(sc, t, n=26)
    ext = A.extent(sc, t)
    pulse = 0.72 + 0.28 * math.sin(t * 14)
    inward = t >= A.DRAIN                                             # 흡수 중에는 빛이 코어 쪽으로 흐른다
    dark, blood = _c((9, 2, 4), 1.0), _c((140, 13, 28), 1.0)
    for i, pts in enumerate(lines):
        k = len(pts)
        if k < 2:
            continue
        d = np.gradient(pts, axis=0)
        nrm = np.column_stack([-d[:, 1], d[:, 0]])
        nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-6)
        taper = 1 - 0.58 * np.linspace(0, 1, k)
        aura = nrm * (15.0 * taper)[:, None]
        outer = nrm * (8.6 * taper)[:, None]
        inner = nrm * (4.8 * taper)[:, None]
        p.setRenderHint(QPainter.Antialiasing, False)
        p.setPen(Qt.NoPen)
        for side, brush in ((aura, _c(RED, 0.13)), (outer, dark), (inner, blood)):
            p.setBrush(brush)
            p.drawPolygon(QPolygonF([QPointF(x, y) for x, y in np.vstack([pts + side, (pts - side)[::-1]]).tolist()]))
        p.setPen(QPen(dark, 2.4, Qt.SolidLine, Qt.FlatCap))           # 마디
        p.drawLines([QLineF(x0, y0, x1, y1) for x0, y0, x1, y1 in np.hstack([pts[1::2] + inner[1::2], pts[1::2] - inner[1::2]]).tolist()])
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(_thin((9, 2, 4), 0.9))                               # 가장자리를 부드럽게
        p.drawLines(_segments(pts + outer) + _segments(pts - outer))
        core = nrm * (1.3 * taper)[:, None]                           # 달아오른 심지
        p.setPen(_thin((255, 104, 90), 0.55 + 0.45 * pulse))
        p.drawLines(_segments(pts + core) + _segments(pts - core))
        p.setPen(Qt.NoPen)
        if ext[i] >= 0.999 or t >= A.RETRACT:                         # 다 뻗은 뒤: 케이블을 따라 흐르는 빛
            for j in range(3):
                u = (t * 1.5 + j / 3 + i * 0.13) % 1
                x, y = pts[int((1 - u if inward else u) * (k - 1))]
                p.setBrush(_c(HOT, 0.32))
                p.drawEllipse(QPointF(float(x), float(y)), 9.5, 9.5)
                p.setBrush(_c((255, 214, 200), 0.95))
                p.drawEllipse(QPointF(float(x), float(y)), 3.2, 3.2)
        else:                                                         # 뻗는 중: 날카로운 촉
            ux, uy = -nrm[-1][1], nrm[-1][0]
            if (pts[-1] - pts[-2]) @ (ux, uy) < 0:
                ux, uy = -ux, -uy
            tx, ty = float(pts[-1][0]), float(pts[-1][1])
            p.setBrush(_c((255, 150, 130), 1.0))
            p.drawPolygon(QPolygonF([QPointF(tx + ux * 30, ty + uy * 30), QPointF(tx - uy * 6.5, ty + ux * 6.5),
                                     QPointF(tx + uy * 6.5, ty - ux * 6.5)]))
        since = t - (sc.t0[i] + A.REACH)                              # 꽂힌 자리
        if since >= 0 and t < A.RETRACT:
            hx, hy = float(pts[-1][0]), float(pts[-1][1])
            g = QRadialGradient(QPointF(hx, hy), 17)
            g.setColorAt(0, _c((255, 150, 120), 0.85 * pulse))
            g.setColorAt(1, _c(RED, 0.0))
            p.setBrush(g)
            p.drawEllipse(QPointF(hx, hy), 17, 17)
            if since < 0.36:                                          # 충격 고리
                r = 6 + 46 * _s(since / 0.36)
                p.setPen(_thin(HOT, 0.9 * (1 - since / 0.36)))
                _ring(p, hx, hy, r)
                _ring(p, hx, hy, r + 1.2)
                p.setPen(Qt.NoPen)
    p.setBrush(Qt.NoBrush)


def _pieces(p: QPainter, sc: A.Scene, a: Assets, state: dict) -> None:
    """떠난 조각: 꿰뚫린 자리로 빨려 드는 동안은 그림 조각이 빙글 돌며 작아지고 달아오른다.
    케이블을 타는 동안은 밝은 빛줄기가 되어 코어로 흐른다."""
    phase, pos, tail, scale, alpha = state["phase"], state["pos"], state["tail"], state["scale"], state["alpha"]
    last = a.stages[-1]
    p.setRenderHint(QPainter.Antialiasing, False)
    for j in np.nonzero(phase == 1)[0]:
        cw, ch = sc.cells[j, 2] * scale[j], sc.cells[j, 3] * scale[j]
        gone = 2 * (1 - scale[j])                                      # 0 → 1 (꿰뚫린 자리에 다다를수록)
        box = QRectF(-cw / 2, -ch / 2, cw, ch)
        p.save()
        p.translate(pos[j, 0], pos[j, 1])
        p.rotate(((j * 37) % 100 - 50) * 3.2 * gone)
        p.drawImage(box, last, a.src[j])
        p.fillRect(box, _c(HOT, 0.55 * gone))
        p.restore()
    riding = np.nonzero(phase == 2)[0]
    if len(riding):
        streaks = np.hstack([tail[riding], pos[riding]])
        fresh = alpha[riding] > 0.5                                    # 코어에 거의 다 온 것은 옅게
        for rows, rgb, al, width in ((streaks[fresh], HOT, 0.92, 6.4), (streaks[~fresh], HOT, 0.42, 4.6)):
            if len(rows):
                p.setPen(QPen(_c(rgb, al), width, Qt.SolidLine, Qt.FlatCap))
                p.drawLines([QLineF(*r) for r in rows.tolist()])
        p.setRenderHint(QPainter.Antialiasing, True)
        if fresh.any():
            p.setPen(_thin((255, 236, 224), 0.95))                     # 빛줄기의 밝은 심지
            p.drawLines([QLineF(*r) for r in streaks[fresh].tolist()])
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(Qt.NoPen)


def _core(p: QPainter, sc: A.Scene, a: Assets, t: float, fade: float) -> None:
    """울트론 코어: 조준하며 달아오르고, 조각을 삼킬수록 커지고, 다 삼키면 한 번 크게 숨 쉰다."""
    cx, cy = sc.core
    c = QPointF(cx, cy)
    heat, sw = A.heat(sc, t), A.swell(t)
    glow = (0.40 * _s(t / A.LOCK) + 0.20 * heat + 0.22 * sw) * fade
    radius = 70 + 26 * heat + 44 * sw
    g = QRadialGradient(c, radius)
    g.setColorAt(0, _c((255, 64, 72), glow))
    g.setColorAt(0.5, _c(RED, glow * 0.42))
    g.setColorAt(1, _c(RED, 0.0))
    p.setPen(Qt.NoPen)
    p.setBrush(g)
    p.drawEllipse(c, radius, radius)
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
        p.setPen(_thin(RED, 0.85 * spin))
        for k in range(3):
            for dr in (0.0, 1.0, 2.0):
                _ring(p, cx, cy, r + dr, turn + k * 120, 62)
        p.setPen(_thin(HOT, 0.55 * spin))
        for k in range(2):
            _ring(p, cx, cy, r + 10, -turn * 0.6 + k * 180, 96)
    if A.DRAIN <= t < A.DRAINED:                                       # 빨아들이는 고리: 코어로 좁혀 든다
        for k in range(2):
            ph = ((t - A.DRAIN) * 1.4 + k * 0.5) % 1
            p.setPen(_thin(RED, 0.7 * math.sin(math.pi * ph)))
            _ring(p, cx, cy, 132 - 90 * ph)
            _ring(p, cx, cy, 133.2 - 90 * ph)
    s = t - A.SWELL
    if 0 < s < 0.9:                                                    # 다 삼킨 뒤 한 번 퍼져 나가는 고리
        r = 50 + 150 * _s(s / 0.9)
        p.setPen(_thin(HOT, 0.8 * (1 - s / 0.9) * fade))
        for dr in (0.0, 1.1, 2.2):
            _ring(p, cx, cy, r + dr)
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
    impact = Signal()          # 첫 케이블이 꽂혔다 (자비스 그림이 실제 창을 가린 뒤에만 낸다)
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
        self._scene, self._assets = scene, Assets(scene)
        x, y, w, h = scene.bounds
        self._shift = (x, y)
        self._covered = self._hit = False
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
