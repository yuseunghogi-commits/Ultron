"""스톤 연출 덮개 창 — stones.py 가 만든 장면(파워 스톤 · 타임 스톤)을 매 순간 그린다.

흡수 연출 덮개(absorb_view.py)와 같은 성질의 창이다: 마우스 · 키보드는 아래 창으로 그대로 통과하고, 포커스를 빼앗지 않는다.
화면 전체를 덮지만 그리는 곳 말고는 투명해서 아래의 실제 화면이 그대로 보인다.

  파워 스톤  코어에 보랏빛이 모이고 → 줄기가 자비스에 꽂히고 → 자비스 화면이 맞은 자리부터 가루가 되어 흩날린다.
            (찍어 둔 자비스 그림이 실제 창을 가린 뒤에만 impact 신호를 낸다 — 그때 app.py 가 실제 자비스를 끈다.)
  타임 스톤  코어 둘레에 초록 시계 고리가 거꾸로 돌고 되감기 줄이 위로 흐른다 → 닫힌 프로그램의 이름이 가루가 된다.
두 장면 다 과격하다: 화면 전체가 번쩍이고(S.flash), 장면이 흔들리고(S.shake), 번개가 친다 (stones.py 머리말 참고).
"""
from __future__ import annotations

import math

import numpy as np
from PySide6.QtCore import QElapsedTimer, QPoint, QPointF, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPolygonF, QRadialGradient
from PySide6.QtWidgets import QWidget

from . import stones as S
from .glitch_view import to_qimage
from .revive_view import _c, _pen, _qt_arc, bolt, draw_bolt, pt


def _col(rgb: tuple[int, int, int]) -> QColor:
    return QColor(int(rgb[0]), int(rgb[1]), int(rgb[2]))


def _light(p: QPainter, cx: float, cy: float, r: float, col: QColor, a: float) -> None:
    """빛무리 — 가운데가 밝고 바깥으로 사라진다 (빛을 더해 그린다)."""
    if a <= 0 or r <= 0:
        return
    g = QRadialGradient(QPointF(cx, cy), r)
    g.setColorAt(0.0, _c(col, a))
    g.setColorAt(0.4, _c(col, a * 0.38))
    g.setColorAt(1.0, _c(col, 0.0))
    p.save()
    p.setCompositionMode(QPainter.CompositionMode_Plus)
    p.setRenderHint(QPainter.Antialiasing, False)
    p.setPen(Qt.NoPen)
    p.setBrush(g)
    p.drawEllipse(QPointF(cx, cy), r, r)
    p.restore()


def _halo_ring(p: QPainter, cx: float, cy: float, r: float, width: float, col: QColor, a: float) -> None:
    """가는 빛 고리 (선으로 그리는 것보다 부드럽고 빠르다)."""
    if a <= 0 or r <= 1:
        return
    edge = r + width
    g = QRadialGradient(QPointF(cx, cy), edge)
    g.setColorAt(max(0.0, (r - width) / edge), _c(col, 0.0))
    g.setColorAt(r / edge, _c(col, a))
    g.setColorAt(1.0, _c(col, 0.0))
    p.save()
    p.setCompositionMode(QPainter.CompositionMode_Plus)
    p.setRenderHint(QPainter.Antialiasing, False)
    p.setPen(Qt.NoPen)
    p.setBrush(g)
    p.drawEllipse(QPointF(cx, cy), edge, edge)
    p.restore()


class Assets:
    """장면마다 한 번 만들어 두는 것들."""

    def __init__(self, scene: S.Scene) -> None:
        self.code = QFont("Consolas")
        self.code.setStyleHint(QFont.Monospace)
        self.code.setBold(True)
        self.code.setPixelSize(max(15, int(scene.hud * 0.085)))


# ---------------------------------------------------------------- 함께 쓰는 그림
def draw_core(p: QPainter, sc: S.Scene, t: float) -> None:
    """울트론 HUD 가 이 화면에 없을 때: 인피니티 울트론을 코어 자리에 직접 그린다 (옅게 나타났다가 끝에 옅어진다)."""
    if not sc.core_drawn:
        return
    from . import infinity
    alpha = min(1.0, t / 0.4) * min(1.0, max(0.0, (sc.duration - t) / 0.4))
    if alpha <= 0:
        return
    unit = sc.hud / infinity.BOX
    p.save()
    p.translate(sc.core[0], sc.core[1])
    p.scale(unit, unit)
    p.setOpacity(alpha)
    infinity.paint(p, t)
    p.restore()


def draw_victim(p: QPainter, sc: S.Scene, t: float) -> bool:
    """아직 가루가 되지 않은 부분 (자비스 화면 · 프로그램 이름). 그렸으면 True."""
    img = S.intact(sc, t)
    if img is None:
        return False
    dx, dy, alpha = S.offset(sc, t)
    h, w = sc.image.shape[:2]
    ih, iw = img.shape[:2]
    x, y, rw, rh = sc.rect
    p.save()
    p.setOpacity(alpha)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.drawImage(QRectF(x + dx, y + dy, rw * iw / w, rh * ih / h), to_qimage(img))
    p.restore()
    return True


def draw_dust(p: QPainter, sc: S.Scene, t: float) -> None:
    """흩날리는 가루 — 알갱이 크기의 낮은 해상도 그림에 찍어 늘여 그린다 (알갱이 수만 개를 하나하나 그리지 않는다)."""
    pos, col = S.dust(sc, t)
    if not len(pos):
        return
    w, h = sc.size
    c = float(max(2, sc.cell))
    keep = (pos[:, 0] >= 0) & (pos[:, 0] < w) & (pos[:, 1] >= 0) & (pos[:, 1] < h)
    pos, col = pos[keep], col[keep]
    if not len(pos):
        return
    x0, y0 = math.floor(pos[:, 0].min() / c) * c, math.floor(pos[:, 1].min() / c) * c
    ix = ((pos[:, 0] - x0) / c).astype(np.int32)
    iy = ((pos[:, 1] - y0) / c).astype(np.int32)
    bw, bh = int(ix.max()) + 1, int(iy.max()) + 1
    buf = np.zeros((bh, bw, 4), np.uint8)
    a = col[:, 3:4].astype(np.float32) / 255
    buf[iy, ix, :3] = (col[:, :3] * a).astype(np.uint8)            # 미리 곱한 색 (투명도가 곱해진 색)
    buf[iy, ix, 3] = col[:, 3]
    img = QImage(buf.data, bw, bh, bw * 4, QImage.Format_RGBA8888_Premultiplied)
    p.save()
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.drawImage(QRectF(x0, y0, bw * c, bh * c), img)
    p.restore()


# ---------------------------------------------------------------- 파워 스톤
def paint_power(p: QPainter, sc: S.Scene, a: Assets, t: float) -> None:
    violet = _col(sc.tint)
    cx, cy = sc.core
    d = sc.hud
    draw_core(p, sc, t)
    draw_victim(p, sc, t)
    draw_dust(p, sc, t)
    p.setRenderHint(QPainter.Antialiasing)

    # 번개: 힘이 모이는 동안 코어 둘레에서 지직거리고, 꽂히는 순간부터는 자비스에서 사방으로 친다 (1/20 초마다 모양이 바뀐다)
    k = S.sparks(sc, t)
    if k > 0.05:
        tick = int(t * 20)
        p.save()
        p.setCompositionMode(QPainter.CompositionMode_Plus)
        if t < S.IMPACT:
            for n in range(2 + int(5 * k)):
                rng = np.random.default_rng(tick * 113 + n)
                a0, a1 = float(rng.uniform(0, 360)), float(rng.uniform(40, 150))
                p0, p1 = pt(a0, d * 0.5), pt(a0 + a1, d * float(rng.uniform(0.55, 0.6 + 0.9 * k)))
                draw_bolt(p, bolt((cx + p0.x(), cy + p0.y()), (cx + p1.x(), cy + p1.y()), tick * 911 + n, 0.3, 4), violet, k, 0.7)
        else:
            hx, hy = sc.hit
            for n in range(3 + int(6 * k)):
                rng = np.random.default_rng(tick * 127 + n)
                far = pt(float(rng.uniform(0, 360)), float(rng.uniform(90, 150 + 300 * k)))
                draw_bolt(p, bolt((hx, hy), (hx + far.x(), hy + far.y()), tick * 719 + n, 0.24), violet, k, 0.9)
        p.restore()

    # 코어에 모이는 힘: 보랏빛이 차오르고, 둘레에서 빛줄기가 코어로 빨려 든다
    c = S.charge(t)
    fade = min(1.0, max(0.0, (sc.duration - t) / 0.5))
    if c > 0 and fade > 0:
        throb = 0.9 + 0.1 * math.sin(t * 17)
        _light(p, cx, cy, d * (0.30 + 0.42 * c), violet, 0.6 * c * throb * fade)
        _light(p, cx, cy, d * 0.16 * c, QColor(255, 255, 255), 0.55 * c * fade)
        _halo_ring(p, cx, cy, d * (0.62 - 0.12 * c), 5, violet, 0.5 * c * fade)
        if t < S.CHARGE + 0.1:
            p.save()
            p.setCompositionMode(QPainter.CompositionMode_Plus)
            for i in range(14):
                ph = (t * 1.5 + i * 0.37) % 1.0
                ang = i * 360 / 14 + 40 * ph + 23 * (i % 3)
                r1 = d * (0.95 - 0.72 * ph)
                p.setPen(_pen(_c(violet.lighter(130), 0.8 * c * math.sin(math.pi * ph)), 2.2, Qt.RoundCap))
                p.drawLine(QPointF(cx, cy) + pt(ang, r1), QPointF(cx, cy) + pt(ang - 6, r1 - d * 0.10))
            p.restore()

    # 줄기: 코어 → 자비스. 가운데는 하얗고 가장자리는 보랏빛, 살짝 떨린다
    reach, thick = S.beam(sc, t)
    if reach > 0 and thick > 0:
        hx, hy = sc.hit
        tip = QPointF(cx + (hx - cx) * reach, cy + (hy - cy) * reach)
        thick *= 0.88 + 0.12 * math.sin(t * 47)
        p.save()
        p.setCompositionMode(QPainter.CompositionMode_Plus)
        for width, alpha, col in ((54, 0.16, violet), (30, 0.3, violet), (14, 0.6, violet.lighter(120)),
                                  (5, 0.95, QColor(255, 255, 255))):
            p.setPen(_pen(_c(col, alpha * min(1.0, thick * 1.3)), width * thick, Qt.RoundCap))
            p.drawLine(QPointF(cx, cy), tip)
        tick = int(t * 24)                                              # 줄기를 감고 도는 번개 두 가닥
        for n in range(2):
            draw_bolt(p, bolt((cx, cy), (tip.x(), tip.y()), tick * 389 + n, 0.07, 5), violet.lighter(130), thick, 0.8)
        p.restore()
        if reach >= 1.0:
            _light(p, hx, hy, 54 * thick, violet.lighter(130), 0.7 * thick)
            _light(p, hx, hy, 18 * thick, QColor(255, 255, 255), 0.8 * thick)

    # 꽂힌 자리에서 퍼지는 고리 (가늘다 — 화면 밝기는 거의 그대로)
    k = S.ring(t)
    if k >= 0:
        _halo_ring(p, sc.hit[0], sc.hit[1], 24 + 170 * (1 - (1 - k) ** 2), 5, violet.lighter(130), 0.6 * (1 - k) ** 1.5)


# ---------------------------------------------------------------- 타임 스톤
def paint_time(p: QPainter, sc: S.Scene, a: Assets, t: float) -> None:
    green = _col(sc.tint)
    w, h = sc.size
    cx, cy = sc.core
    d = sc.hud
    show, ang = S.dial(t, sc.duration)
    draw_core(p, sc, t)
    p.setRenderHint(QPainter.Antialiasing)

    # 되감기 줄: 초록 줄과 굵은 띠가 화면을 타고 위로 쏟아져 흐른다 (비디오테이프를 되감을 때처럼)
    s = S.rewind(t)
    if s > 0:
        p.save()
        p.setCompositionMode(QPainter.CompositionMode_Plus)
        p.setPen(Qt.NoPen)
        tick = int(t * 30)
        for i in range(5):                                              # 굵은 띠: 1/30 초마다 자리가 튄다
            rng = np.random.default_rng(tick * 97 + i)
            band = h * float(rng.uniform(0.02, 0.09))
            y = (h * float(rng.uniform(0, 1)) - t * h * 1.6) % h
            p.setBrush(_c(green, float(rng.uniform(0.10, 0.26)) * s))
            p.drawRect(QRectF(0, y, w, band))
        for i in range(18):
            frac = (i / 18 + t * 1.5 + 0.13 * math.sin(i * 2.4)) % 1.0
            y = h * (1 - frac)
            p.setBrush(_c(green, 0.22 * s))
            p.drawRect(QRectF(0, y, w, 2))
            seg = w * (0.12 + 0.2 * ((i * 37) % 10) / 10)               # 줄마다 한 토막은 더 밝다 (테이프가 튀는 느낌)
            x = (w * ((i * 53) % 17) / 17 + t * 900 * (1 if i % 2 else -1)) % w
            p.setBrush(_c(green.lighter(150), 0.5 * s))
            p.drawRect(QRectF(x, y - 1, seg, 3))
        p.restore()

    if s > 0.05:                                                        # 시계 고리에서 튀는 초록 번개
        tick = int(t * 20)
        p.save()
        p.setCompositionMode(QPainter.CompositionMode_Plus)
        for n in range(2 + int(4 * s)):
            rng = np.random.default_rng(tick * 139 + n)
            a0 = float(rng.uniform(0, 360))
            p0, p1 = pt(a0, d * 0.86), pt(a0 + float(rng.uniform(-30, 30)), d * float(rng.uniform(1.2, 2.4)))
            draw_bolt(p, bolt((cx + p0.x(), cy + p0.y()), (cx + p1.x(), cy + p1.y()), tick * 523 + n, 0.22), green, s, 0.8)
        p.restore()

    if show > 0:
        r1, r2, r3 = d * 0.60, d * 0.72, d * 0.86
        _light(p, cx, cy, r3 * 1.3, green, 0.20 * show)
        p.save()
        p.translate(cx, cy)
        p.setBrush(Qt.NoBrush)
        # 안쪽 고리: 눈금 60개 (시계 문자판) — 거꾸로 돈다
        p.save()
        p.rotate(ang)
        p.setPen(_pen(_c(green, 0.75 * show), 1.4))
        p.drawEllipse(QPointF(0, 0), r1, r1)
        for i in range(60):
            big = i % 5 == 0
            p.setPen(_pen(_c(green.lighter(140) if big else green, (0.95 if big else 0.6) * show), 2.6 if big else 1.2))
            p.drawLine(pt(i * 6, r1), pt(i * 6, r1 + d * (0.05 if big else 0.028)))
        p.restore()
        # 가운데 고리: 굵은 토막 12개 — 반대로 돈다
        p.save()
        p.rotate(-ang * 0.5)
        p.setPen(_pen(_c(green.lighter(125), 0.85 * show), d * 0.022))
        for i in range(12):
            _qt_arc(p, r2, i * 30, 13 * show)
        p.restore()
        # 바깥 고리: 긴 호 셋 + 점선 — 천천히 거꾸로
        p.save()
        p.rotate(ang * 0.3)
        dash = _pen(_c(green, 0.5 * show), 1.2)
        dash.setDashPattern([2, 6])
        p.setPen(dash)
        p.drawEllipse(QPointF(0, 0), r3, r3)
        p.setPen(_pen(_c(green.lighter(140), 0.9 * show), 3))
        for i in range(3):
            _qt_arc(p, r3, i * 120, 74 * show)
        p.restore()
        # 거꾸로 달리는 바늘: 안쪽 고리 위의 밝은 쐐기와 그 뒤로 끌리는 빛
        hand = ang * 2 - 90
        for n in range(9):
            p.setPen(_pen(_c(green.lighter(160), (1 - n / 9) ** 2 * show), 4.5 - n * 0.3))
            _qt_arc(p, r1 - 5, hand + n * 7, 7)
        tip = pt(hand, r1 - 5)
        p.setPen(Qt.NoPen)
        p.setBrush(_c(QColor(255, 255, 255), show))
        p.drawPolygon(QPolygonF([tip + pt(hand, 9), tip + pt(hand + 120, 6), tip + pt(hand - 120, 6)]))
        p.restore()

        # 되감기 표시: ◀◀ 와 거꾸로 세는 시간 (끝나면 TIMELINE RESTORED)
        top = cy - r3 - d * 0.20
        if top < 20:
            top = cy + r3 + d * 0.10 + (sc.rect[3] + 12 if sc.label else 0)
        done = t >= S.T_NAME
        text = "TIMELINE RESTORED" if done else f"REWIND  -{S.clock(t):05.2f} s"
        p.setFont(a.code)
        fm = p.fontMetrics()
        tw = fm.horizontalAdvance(text)
        mark = 0 if done else fm.height() * 1.5
        x = cx - (tw + mark) / 2
        if not done:
            p.setPen(Qt.NoPen)
            p.setBrush(_c(green.lighter(150), show))
            mh = fm.height() * 0.62
            for j in range(2):
                bx = x + j * mh * 0.75
                p.drawPolygon(QPolygonF([QPointF(bx, top + fm.height() / 2), QPointF(bx + mh * 0.7, top + fm.height() / 2 - mh / 2),
                                         QPointF(bx + mh * 0.7, top + fm.height() / 2 + mh / 2)]))
        p.setPen(_c(QColor(0, 0, 0), 0.7 * show))
        p.drawText(QPointF(x + mark + 1.5, top + fm.ascent() + 1.5), text)
        p.setPen(_c(green.lighter(150), show))
        p.drawText(QPointF(x + mark, top + fm.ascent()), text)

    draw_victim(p, sc, t)                                               # 닫힌 프로그램의 이름 → 가루
    draw_dust(p, sc, t)


def paint(p: QPainter, sc: S.Scene, a: Assets, t: float) -> None:
    """t 초 때의 장면 (화면 좌표). 투명하게 남긴 곳으로는 아래의 실제 화면이 보인다."""
    p.save()
    alpha, tint = S.flash(sc, t)
    if alpha > 0:                                                       # 화면 전체가 스톤의 색으로 번쩍인다
        p.fillRect(QRectF(0, 0, sc.size[0], sc.size[1]), _c(_col(tint), alpha))
    dx, dy = S.shake(sc, t)
    p.translate(dx, dy)                                                 # 장면이 흔들린다
    if sc.kind == "power":
        paint_power(p, sc, a, t)
    else:
        paint_time(p, sc, a, t)
    p.restore()


def render(sc: S.Scene, t: float, background: np.ndarray | None = None, assets: Assets | None = None) -> np.ndarray:
    """(시험 · 미리보기) t 초 때의 장면을 background(RGB, 실제 화면 대신) 위에 덮은 모습 → RGB 배열."""
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


# ---------------------------------------------------------------- 덮개 창
class StoneView(QWidget):
    impact = Signal()          # 줄기가 꽂혔다 (자비스 그림이 실제 창을 가린 뒤에만 낸다) — 타임 스톤 장면에서는 내지 않는다
    finished = Signal()

    def __init__(self) -> None:
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                         | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setWindowTitle("U.L.T.R.O.N STONE")
        self._scene: S.Scene | None = None
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

    def play(self, top_left: QPoint, scene: S.Scene) -> None:
        """top_left: 장면이 펼쳐지는 화면의 왼쪽 위 (Qt 좌표)."""
        self._scene, self._assets = scene, Assets(scene)
        x, y, w, h = scene.bounds
        self._shift = (x, y)
        self._covered = self._hit = False
        self.setGeometry(QRect(top_left.x() + x, top_left.y() + y, w, h))
        self.show()
        self.raise_()                              # 자비스 HUD · 울트론 HUD 도 '항상 위' 창이다 — 그 위로 올라간다
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
            if t >= S.FREEZE:
                self._covered = True
        p.end()
