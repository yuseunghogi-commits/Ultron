"""부활 연출 덮개 창 — revive.py 가 만든 재료 · 사건 목록으로 장면을 매 순간 그린다.

해킹 연출 덮개(glitch_view.py)와 같은 성질의 창이다: 마우스 · 키보드는 아래 창으로 그대로 통과하고, 포커스를 빼앗지 않으며,
화면 캡처에는 찍히지 않는다 (app.py 가 설정).

해킹 단계는 찍어 둔 실제 화면을 빨강 층 · 청록 층으로 나눠 반대쪽으로 밀어 겹쳐 그린다(색 번짐) — 그 위에 그 순간 일어나고 있는
찢김 · 블록 · 얼룩 · 해킹 글자를 얹는다. 화면이 다 바뀌는 큰 그림을 미리 만들어 두지 않으므로 메모리를 거의 쓰지 않는다.

울트론 코어는 HUD 의 엠블럼(ui/Emblem.qml)과 같은 모양 · 색 · 좌표(440 단위, 가운데 0,0)로 직접 그린다 —
눈이 먼저 옅게 떠올라 진해지고, 원판 → 안쪽 링 → 강철 호 · 칼날 → 눈금 → 톱니 → 육각 꺾쇠 → 이름 순으로 안쪽부터 나타난다.
다 나타나면 검은 바탕이 걷히며 그 자리에서 HUD 크기로 줄어들고(handoff 신호 — app.py 가 실제 HUD 를 그 자리에 띄운다),
HUD 와 겹친 채 옅어진다.

인피니티 울트론으로 되살아나는 장면(scene.infinity)이면 코어 자리에 infinity.py 의 모습을 그린다 — 눈 → 원판 · 링 · 칼날 →
스톤 여섯이 하나씩 → 바깥 링 · 가시 · 이름. 멈춘 그림 한 장으로 바꾸지 않고 끝까지 살아 움직이는 채로 줄어든다 (스톤이 맥박 친다).
"""
from __future__ import annotations

import math

import numpy as np
from PySide6.QtCore import QElapsedTimer, QPointF, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QLinearGradient, QPainter, QPen, QPolygonF, QRadialGradient
from PySide6.QtWidgets import QWidget

from . import revive as R
from .glitch_view import to_qimage

ACC = QColor(255, 45, 63)
RING = QColor(255, 75, 85)
RING_HOT = RING.lighter(110)
BAND = QColor(200, 20, 31)
STEEL = QColor(195, 202, 211)
EYE_HOT = QColor(255, 200, 201)
EYE_MID = ACC.lighter(125)
CORE_SIZE = 0.56           # 코어 지름 = 화면 짧은 변 × 이것
EYE_OUTLINE = [(78, -54), (44, -47), (14, -31), (20, -17), (48, -29), (75, -41), (78, -54)]   # 오른쪽 눈 (Emblem.qml)


def _c(c: QColor, a: float) -> QColor:
    q = QColor(c)
    q.setAlphaF(max(0.0, min(1.0, a)))
    return q


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def ease(x: float) -> float:
    x = _clamp(x)
    return 1 - (1 - x) ** 3


def smooth(x: float) -> float:
    """처음과 끝이 완만한 곡선 — 단계가 넘어갈 때 첫 순간 밝기가 확 바뀌지 않게 (빛에 민감한 사람)."""
    x = _clamp(x)
    return x * x * (3 - 2 * x)


def stage(k: float, a: float, b: float) -> float:
    return ease((k - a) / max(1e-6, b - a))


def pt(deg: float, r: float) -> QPointF:
    a = math.radians(deg)
    return QPointF(math.cos(a) * r, math.sin(a) * r)


def _mix(a: QPointF, b: QPointF, k: float) -> QPointF:
    return QPointF(a.x() + (b.x() - a.x()) * k, a.y() + (b.y() - a.y()) * k)


def _arc(r: float, start: float, sweep: float, steps: int = 48) -> QPolygonF:
    n = max(2, int(steps * abs(sweep) / 360) + 2)
    return QPolygonF([pt(start + sweep * i / (n - 1), r) for i in range(n)])


# ---------------------------------------------------------------- 단계별 값 (시험하기 쉽게 따로)
def fade_in(k: float, a: float, b: float) -> float:
    """k 가 a → b 로 가는 동안 옅게 시작해 점점 진해진다 (처음과 끝이 완만)."""
    return smooth((k - a) / max(1e-6, b - a))


def eye_light(k: float) -> float:
    """눈의 진하기 (눈 단계 진행 k 0..1) — 아주 옅게 떠올라 천천히 진해진다."""
    return smooth(k) ** 1.15


def eye_open(k: float) -> float:
    """눈꺼풀: 반쯤 뜬 채로 떠올라 진해지면서 끝까지 뜬다."""
    return 0.55 + 0.45 * smooth((k - 0.25) / 0.75)


def reveal(f: float) -> dict[str, float]:
    """코어가 나타나는 정도 (코어 단계 진행 f 0..1) — 안쪽부터 바깥으로, 하나하나 옅게 시작해 진해진다."""
    return {"glow": fade_in(f, 0.0, 0.9), "disc": fade_in(f, 0.0, 0.45), "inner": fade_in(f, 0.05, 0.5),
            "steel": fade_in(f, 0.2, 0.6), "band": fade_in(f, 0.15, 0.7), "ticks": fade_in(f, 0.3, 0.8),
            "saw": fade_in(f, 0.35, 0.88), "hex": fade_in(f, 0.45, 0.95), "word": fade_in(f, 0.6, 1.0)}


def _lerp(a: float, b: float, k: float) -> float:
    return a + (b - a) * k


def infinity_parts(name: str, k: float) -> dict:
    """인피니티 울트론의 부분별로 나타난 정도 (단계 이름 · 그 단계 안에서의 진행 k) — infinity.paint 의 cv.
    eyes: 눈만 → inner: 원판 · 링 · 칼날 → stones: 스톤이 하나씩 → outer: 눈금 · 사슬 · 꺾쇠 · 가시 · 이름 → 그 뒤로는 전부."""
    from . import infinity
    order = ("eyes", "inner", "stones", "outer")
    step = order.index(name) if name in order else len(order)
    k = _clamp(k)

    def at(when: int, a: float, b: float) -> float:
        return 1.0 if step > when else (fade_in(k, a, b) if step == when else 0.0)

    cv = {"eyes": 1.0 if step > 0 else eye_light(k),
          "disc": at(1, 0.0, 0.5), "ring": at(1, 0.15, 0.75), "band": at(1, 0.4, 1.0),
          "ticks": at(3, 0.0, 0.45), "chain": at(3, 0.15, 0.6), "hex": at(3, 0.32, 0.72), "spikes": at(3, 0.5, 0.9),
          "word": at(3, 0.65, 1.0), "gems": 1.0 if step > 2 else 0.0,
          "stones": [1.0] * 6 if step > 2 else (infinity.stones_in(k) if step == 2 else [0.0] * 6)}
    # 후광은 단계마다 조금씩 짙어진다 (한꺼번에 밝아지지 않게)
    cv["glow"] = (0.0, 0.35, 0.7, 1.0, 1.0)[step] if step == 0 else _lerp((0.0, 0.0, 0.35, 0.7, 1.0)[step],
                                                                       (0.0, 0.35, 0.7, 1.0, 1.0)[step], smooth(k))
    return cv


def looks(scene: R.Scene, t: float) -> dict:
    """t 초 때 무엇이 얼마나 보이는가.
    hack(해킹 단계인가) · k(해킹 세기) · tune(지직으로 넘어가는 정도) · static(지직 불투명도) · black(검은 바탕) ·
    eyes · open · core(부분별) · done(완성 코어 한 장: (가운데 x, 가운데 y, 지름, 진하기)) — 크기는 화면 비율이 아니라 픽셀."""
    name, k = R.phase(scene, t)
    out = {"phase": name, "hack": False, "k": 0.0, "tune": 0.0, "static": 0.0, "black": 0.0, "eyes": 0.0, "open": 0.55,
           "core": {key: 0.0 for key in reveal(0)}, "done": None}
    w, h = scene.size
    big = CORE_SIZE * min(w, h)
    tx, ty, ts = scene.target
    if scene.infinity and name not in ("hack", "static", "settle", "end"):
        # 인피니티 울트론: inf = {cv, open, at: (가운데 x, 가운데 y, 440 단위 하나의 픽셀 크기, 진하기)} — 늘 살아 움직이는 채로 그린다
        from . import infinity
        unit, small = big / 440, ts / infinity.BOX           # HUD 에서는 가시까지 든 상자(BOX)가 엠블럼 자리에 맞는다
        inf = {"cv": infinity_parts(name, k), "open": eye_open(k) if name == "eyes" else 1.0, "at": (w / 2, h / 2, unit, 1.0)}
        out["black"] = 1.0
        if name == "shrink":
            q = smooth(k)
            out["black"] = 1.0 - q
            inf["at"] = (_lerp(w / 2, tx, q), _lerp(h / 2, ty, q), _lerp(unit, small, q), 1.0)
        elif name == "handoff":
            out["black"] = 0.0
            inf["at"] = (tx, ty, small, 1.0 - smooth(k))
        out["inf"] = inf
        out["eyes"], out["open"] = inf["cv"]["eyes"], inf["open"]
        # 과격한 부분: 스톤이 박힐 때 · 다 나타날 때의 번쩍임, 코어의 흔들림, 번개
        out["flash"] = R.burst(scene, t)
        jx, jy = R.jolt(scene, t)
        out["jolt"] = (jx * min(w, h), jy * min(w, h))
        out["strikes"] = R.strikes(scene, t)
        return out
    if name == "hack":
        out["hack"], out["k"], out["tune"] = True, R.intensity(R.stutter(t)), R.tune(t)
        out["static"] = smooth(out["tune"])
    elif name == "static":
        out["static"] = 1.0
    elif name == "settle":
        out["black"] = 1.0
        out["static"] = 1.0 - smooth(k)
    elif name == "eyes":
        out["black"], out["eyes"], out["open"] = 1.0, eye_light(k), eye_open(k)
    elif name == "form":
        out["black"], out["eyes"], out["open"], out["core"] = 1.0, 1.0, 1.0, reveal(k)
    elif name == "hold":
        out["black"], out["done"] = 1.0, (w / 2, h / 2, big, 1.0)
    elif name == "shrink":                                          # 검은 바탕이 걷히며 그 자리에서 HUD 크기로
        q = smooth(k)
        out["black"] = 1.0 - q
        out["done"] = (_lerp(w / 2, tx, q), _lerp(h / 2, ty, q), _lerp(big, ts, q), 1.0)
    elif name == "handoff":                                         # 실제 HUD 와 겹친 채 옅어진다
        out["done"] = (tx, ty, ts, 1.0 - smooth(k))
    return out


# ---------------------------------------------------------------- 그림 재료
def _rgb_image(rgb: np.ndarray) -> QImage:
    h, w, _ = rgb.shape
    return QImage(rgb.data, w, h, w * 3, QImage.Format_RGB888).convertToFormat(QImage.Format_RGB32)


class Assets:
    """장면마다 한 번 만들어 두는 Qt 그림들. w · h: 그릴 화면 크기 (논리 픽셀)."""

    def __init__(self, scene: R.Scene, w: int, h: int) -> None:
        self.w, self.h = w, h
        shot = np.ascontiguousarray(scene.shot[..., :3])
        self.plain = _rgb_image(shot)                              # 찍은 실제 화면
        cyan, red = shot.copy(), shot.copy()
        cyan[..., 0] = 0                                           # 초록 · 파랑만
        red[..., 1:] = 0                                           # 빨강만 — 두 층을 반대로 밀어 더하면 색이 번진다
        self.cyan, self.red = _rgb_image(cyan), _rgb_image(red)
        self.code = QFont("Consolas")
        self.code.setStyleHint(QFont.Monospace)
        self.code.setBold(True)
        self.code.setPixelSize(max(11, h // 46))
        self.static = []
        for g in scene.static:
            g = np.ascontiguousarray(g)
            self.static.append(QImage(g.data, g.shape[1], g.shape[0], g.shape[1], QImage.Format_Grayscale8).copy())
        # 주사선 + 가장자리 어둡게 (옛날 브라운관) — 화면 크기로 한 번만 그려 둔다
        self.crt = QImage(max(1, w), max(1, h), QImage.Format_ARGB32_Premultiplied)
        self.crt.fill(Qt.transparent)
        q = QPainter(self.crt)
        line = _c(QColor(0, 0, 0), 0.26)
        for y in range(0, h, 3):
            q.fillRect(0, y, w, 1, line)
        g = QRadialGradient(QPointF(w / 2, h / 2), math.hypot(w, h) / 2)
        g.setColorAt(0.55, _c(QColor(0, 0, 0), 0.0))
        g.setColorAt(1.0, _c(QColor(0, 0, 0), 0.6))
        q.fillRect(0, 0, w, h, g)
        q.end()
        self.size = CORE_SIZE * min(w, h)                          # 코어 지름 (픽셀)
        self.eye_glow = self._eye_glow(int(self.size))
        # 돌아도 모양이 같은 것(둥근 빛 번짐 · 원판)은 한 번만 그려 두고 매번 찍기만 한다 (선마다 덧그리면 몇 배 느리다)
        self.px = max(40, int(round(self.size)))
        self.disc = self._disc(self.px)
        self.halo = self._halo(self.px)
        self.glow = {name: self._ring_glow(self.px, rings) for name, rings in (
            ("inner", [(107, 6)]), ("ticks", [(167, 10)]), ("saw", [(190, 13), (180, 2)]), ("hex", [(211, 7)]))}
        self.done: QImage | None = None                             # 다 나타난 코어 (머무는 · 옅어지는 동안 이것만 찍는다)
        self.font = QFont("Bahnschrift")
        self.font.setBold(True)
        self.font.setPixelSize(30)
        self.font.setLetterSpacing(QFont.AbsoluteSpacing, 30 * 0.32)
        if not scene.infinity:                                      # (인피니티 울트론은 끝까지 살아 움직이는 채로 그린다)
            self.finished_core(spin(scene, scene.marks()["form"]))   # 다 나타난 코어를 미리 그려 둔다 (그 순간 멈칫하지 않게)

    def finished_core(self, t: float) -> QImage:
        """다 나타나 멈춘 코어 그림 — 한 번만 그린다."""
        if self.done is None:
            img = QImage(self.px, self.px, QImage.Format_ARGB32_Premultiplied)
            img.fill(Qt.transparent)
            q = QPainter(img)
            full = {"eyes": 1.0, "open": 1.0, "core": reveal(1.0)}
            draw_core(q, self, self.px / 2, self.px / 2, full, t)
            q.end()
            self.done = img
        return self.done

    @staticmethod
    def _halo(px: int) -> QImage:
        img = QImage(px, px, QImage.Format_ARGB32_Premultiplied)
        img.fill(Qt.transparent)
        q = QPainter(img)
        q.setRenderHint(QPainter.Antialiasing)
        g = QRadialGradient(QPointF(px / 2, px / 2), px / 2)
        g.setColorAt(0.0, _c(ACC, 0.0))
        g.setColorAt(0.62, _c(ACC, 0.10))
        g.setColorAt(0.89, _c(ACC, 0.24))
        g.setColorAt(1.0, _c(ACC, 0.0))
        q.setPen(Qt.NoPen)
        q.setBrush(g)
        q.drawEllipse(QPointF(px / 2, px / 2), px / 2, px / 2)
        q.end()
        return img

    @staticmethod
    def _ring_glow(px: int, rings: list[tuple[float, float]]) -> QImage:
        """둥글게 번지는 붉은 빛 (반지름 · 굵기는 440 단위) — 링 밑에 깔아 Emblem.qml 의 발광 효과를 낸다."""
        from PIL import Image, ImageDraw, ImageFilter
        img = Image.new("RGBA", (px, px), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        u, c = px / 440, px / 2
        for r, width in rings:
            d.ellipse([c - r * u, c - r * u, c + r * u, c + r * u], outline=(255, 45, 63, 150), width=max(1, int(width * u)))
        return to_qimage(np.asarray(img.filter(ImageFilter.GaussianBlur(max(1.5, 7 * u)))))

    @staticmethod
    def _disc(px: int) -> QImage:
        """안쪽 어두운 원판과 희미한 무늬."""
        img = QImage(px, px, QImage.Format_ARGB32_Premultiplied)
        img.fill(Qt.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        p.translate(px / 2, px / 2)
        p.scale(px / 440, px / 440)
        g = QRadialGradient(QPointF(0, 0), 105, QPointF(0, -30))
        g.setColorAt(0.0, QColor.fromRgbF(0.18, 0.03, 0.05, 0.96))
        g.setColorAt(0.85, QColor.fromRgbF(0.07, 0.01, 0.02, 0.96))
        g.setColorAt(1.0, _c(RING, 0.35))
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawEllipse(QPointF(0, 0), 105, 105)
        dash = QPen(_c(RING, 0.22), 1.2)
        dash.setDashPattern([3, 2.5])
        p.setPen(dash)
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(0, 0), 94, 94)
        p.setPen(QPen(_c(RING, 0.15), 1.2))
        p.drawPolygon(QPolygonF([pt(90, 88), pt(210, 88), pt(330, 88)]))
        p.setPen(QPen(_c(RING, 0.11), 1))
        p.drawPolygon(QPolygonF([pt(270, 66), pt(30, 66), pt(150, 66)]))
        p.setPen(QPen(_c(RING, 0.09), 1))
        p.drawLine(QPointF(-100, 8), QPointF(100, 8))
        p.drawLine(QPointF(-84, 56), QPointF(84, 56))
        p.end()
        return img

    @staticmethod
    def _eye_glow(px: int) -> QImage:
        """두 눈에서 번지는 빛 (흐리게 번진 눈 모양) — 매번 흐리게 만들지 않고 이 그림을 찍는다."""
        from PIL import Image, ImageDraw, ImageFilter
        px = max(40, px)
        img = Image.new("RGBA", (px, px), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        u, c = px / 440, px / 2
        for sx in (-1, 1):
            d.polygon([(c + sx * x * u, c + y * u) for x, y in EYE_OUTLINE], fill=(255, 60, 70, 255))
        out = to_qimage(np.asarray(img.filter(ImageFilter.GaussianBlur(px / 34)))).convertToFormat(
            QImage.Format_ARGB32_Premultiplied)
        q = QPainter(out)                                           # 눈 둘레에 번지는 붉은 빛 무리
        q.setRenderHint(QPainter.Antialiasing)
        q.setPen(Qt.NoPen)
        for sx in (-1, 1):
            at, r = QPointF(c + sx * 46 * u, c - 36 * u), 70 * u
            spot = QRadialGradient(at, r)
            spot.setColorAt(0.0, _c(ACC, 0.32))
            spot.setColorAt(1.0, _c(ACC, 0.0))
            q.setBrush(spot)
            q.drawEllipse(at, r, r)
        q.end()
        return out


# ---------------------------------------------------------------- 그리기
def _pen(c: QColor, width: float, cap=Qt.FlatCap) -> QPen:
    pen = QPen(c, width)
    pen.setCapStyle(cap)
    pen.setJoinStyle(Qt.MiterJoin)
    return pen


def _qt_arc(p: QPainter, r: float, start: float, sweep: float) -> None:
    """호 (440 단위). start · sweep 은 이 파일의 각도(3시 방향 0, 시계 방향 +) — Qt 는 반시계 방향이 + 라 부호를 뒤집는다."""
    p.drawArc(QRectF(-r, -r, 2 * r, 2 * r), int(-start * 16), int(-sweep * 16))


def _k(c: QColor, a: float) -> QColor:
    """검은 바탕 위에 a 만큼 비친 색을 불투명한 색으로. 반투명으로 그리면 몇 배 느린데, 코어는 늘 검은 바탕 위라 보이는 건 같다."""
    a = _clamp(a)
    return QColor(int(c.red() * a), int(c.green() * a), int(c.blue() * a))


def spin(scene: R.Scene, t: float) -> float:
    """링이 도는 데 쓰는 시간 — 코어가 다 나타나는 순간에 맞춰 부드럽게 멈춘다 (그 뒤로는 완성된 그림 한 장만 찍는다)."""
    t2 = scene.marks()["form"]
    t1 = t2 - 0.6
    if t <= t1:
        return t
    x = min(t, t2) - t1
    return t1 + x - x * x / (2 * (t2 - t1))


def draw_core(p: QPainter, a: Assets, cx: float, cy: float, look: dict, t: float) -> None:
    """울트론 코어 (Emblem.qml 과 같은 440 단위 좌표, 가운데 0,0). 검은 바탕 위에 불투명하게 그린다. t = 링이 도는 시간."""
    cv = look["core"]
    u = a.size / 440
    half = a.px / 2
    p.save()
    p.translate(cx, cy)
    p.setRenderHint(QPainter.Antialiasing)

    # 미리 그려 둔 층 (픽셀 단위로 그대로 찍는다 — 늘이거나 줄이지 않아 빠르다)
    for key, layer in (("glow", a.halo), ("disc", a.disc), ("inner", a.glow["inner"]), ("ticks", a.glow["ticks"]),
                       ("saw", a.glow["saw"]), ("hex", a.glow["hex"])):
        if cv[key] > 0:
            p.setOpacity(cv[key])
            p.drawImage(QPointF(-half, -half), layer)
    if look["eyes"] > 0:                                            # 눈에서 번지는 빛 (눈을 뜨는 만큼 세로로)
        e, open_ = look["eyes"], max(0.06, look["open"])
        p.save()
        p.translate(0, -35 * u)
        p.scale(1, open_)
        p.translate(0, 35 * u)
        p.setOpacity(min(1.0, e * 1.1))
        p.drawImage(QPointF(-half, -half), a.eye_glow)
        p.restore()
    p.setOpacity(1.0)
    p.scale(u, u)
    p.setBrush(Qt.NoBrush)

    # 안쪽 밝은 링 (위에서부터 시계 방향으로 그려진다)
    if cv["inner"] > 0:
        p.setPen(_pen(RING_HOT, 5))
        _qt_arc(p, 107, 270, 360 * cv["inner"])

    # 강철 호 (반대로 돈다)
    if cv["steel"] > 0:
        k = cv["steel"]
        p.save()
        p.rotate(-14 * t)
        p.setPen(_pen(_k(STEEL, min(1, k * 1.5)), 2.6))
        for start in (200, 20):
            _qt_arc(p, 116, start, 52 * k)
        dash = _pen(_k(STEEL, 0.5 * min(1, k * 1.5)), 5)
        dash.setDashPattern([0.25, 0.6])
        p.setPen(dash)
        for start in (262, 82):
            _qt_arc(p, 116, start, 40 * k)
        p.restore()

    # 칼날 띠 (비스듬한 칼날 6개 — 바깥 가장자리가 밝다)
    if cv["band"] > 0:
        p.save()
        p.rotate(10 * t)
        for i in range(6):
            q = stage(cv["band"], i * 0.05, 0.7 + i * 0.05) * 0.9
            if q <= 0:
                continue
            a0 = i * 60
            inner = [pt(a0 + 40 * j / 8, 124) for j in range(9)]
            outer = [pt(a0 + 11 + 40 * j / 8, 151) for j in range(8, -1, -1)]
            p.setBrush(_k(BAND, 0.62 * q))
            p.setPen(_pen(_k(BAND.lighter(170), 0.85 * q), 1.2))
            p.drawPolygon(QPolygonF(inner + outer))
            p.setBrush(Qt.NoBrush)
            p.setPen(_pen(_k(BAND.lighter(150), 0.95 * q), 2.4))
            p.drawPolyline(QPolygonF(outer))
        p.restore()

    # 눈금 링 (72개 — 빛이 한 바퀴 훑는다)
    if cv["ticks"] > 0:
        p.save()
        p.rotate(-4 * t)
        scan = (t * 90) % 360
        for i in range(72):
            q = stage(cv["ticks"], i * 0.004, 0.6 + i * 0.004)
            if q <= 0:
                continue
            ang = i * 5 - 90
            big = i % 6 == 0
            wave = (0.5 + 0.5 * math.cos(math.radians((i * 5 - scan) % 360))) ** 10
            p.setPen(_pen(_k(RING_HOT if big else RING, q * min(1, 0.6 + 0.4 * wave)), 3 if big else 1.6))
            p.drawLine(pt(ang, 160), pt(ang, 160 + (14 if big else 9)))
        p.restore()

    # 톱니 링 (한 바퀴 그려지며 나타난다)
    if cv["saw"] > 0:
        k = cv["saw"]
        p.save()
        p.rotate(6 * t)
        pts = []
        for j in range(61):
            pts.append(pt(j * 6, 184))
            if j < 60:
                pts.append(pt(j * 6 + 4.5, 196))
        p.setPen(_pen(_k(RING_HOT, min(1, k * 2)), 2))
        p.drawPolyline(QPolygonF(pts[:max(2, math.ceil(len(pts) * k))]))
        p.setPen(_pen(_k(RING, 0.45 * k), 1.2))
        p.drawEllipse(QPointF(0, 0), 180, 180)
        p.restore()

    # 육각 꺾쇠 (천천히 흔들린다)
    if cv["hex"] > 0:
        p.save()
        p.rotate(2.0 * math.sin(t * 0.23) + math.sin(t * 0.11 + 1.3))
        hexp = [pt(-90 + i * 60, 211) for i in range(6)]
        center = QPointF(0, 0)
        for i in range(6):
            q = stage(cv["hex"], i * 0.04, 0.75 + i * 0.04)
            if q <= 0:
                continue
            v, prev, nxt = hexp[i], hexp[(i + 5) % 6], hexp[(i + 1) % 6]
            p.setBrush(Qt.NoBrush)
            p.setPen(_pen(_k(RING_HOT, min(1, q * 1.5)), 4.5))
            p.drawPolyline(QPolygonF([_mix(v, prev, 0.16 * q), v, _mix(v, nxt, 0.16 * q)]))
            p.setPen(Qt.NoPen)
            p.setBrush(_k(RING, 0.8 * q))
            p.drawPolygon(QPolygonF([_mix(v, center, 0.035), _mix(_mix(v, prev, 0.05), center, 0.075),
                                     _mix(_mix(v, nxt, 0.05), center, 0.075)]))
        p.restore()

    # 두 눈 (가장 먼저 켜진다)
    if look["eyes"] > 0:
        e, open_ = look["eyes"], max(0.06, look["open"])
        p.save()
        p.translate(0, -35)
        p.scale(1, open_)
        p.translate(0, 35)
        fill = QLinearGradient(QPointF(0, -54), QPointF(0, -17))
        fill.setColorAt(0.0, _k(EYE_HOT, e))
        fill.setColorAt(0.55, _k(EYE_MID, e))
        fill.setColorAt(1.0, _k(ACC, e))
        p.setBrush(fill)
        p.setPen(_pen(_k(ACC, 0.95 * e), 2.2))
        for sx in (-1, 1):
            p.drawPolygon(QPolygonF([QPointF(sx * x, y) for x, y in EYE_OUTLINE]))
        p.restore()

    # 이름 ULTRON (마지막에)
    if cv["word"] > 0:
        k = cv["word"]
        fm = QFontMetricsF(a.font)
        tw = max(1.0, fm.horizontalAdvance("ULTRON"))
        p.save()
        p.translate(0, 30)
        p.scale(168 / tw * (0.94 + 0.06 * k), 0.94 + 0.06 * k)
        p.setFont(a.font)
        rect = QRectF(-tw / 2, -fm.height() / 2, tw, fm.height())
        p.setPen(_k(ACC, 0.45 * k))
        for dx, dy in ((-1.4, 0), (1.4, 0), (0, -1.4), (0, 1.4)):
            p.drawText(rect.translated(dx, dy), Qt.AlignCenter, "ULTRON")
        p.setPen(_k(QColor(255, 255, 255), k))
        p.drawText(rect, Qt.AlignCenter, "ULTRON")
        p.restore()
    p.restore()


INK = [QColor(255, 45, 63), QColor(80, 230, 255), QColor(235, 235, 240)]


def draw_hack(p: QPainter, scene: R.Scene, a: Assets, t: float, w: int, h: int, look: dict) -> None:
    """점점 심해지는 해킹: 색 번짐 → 찢김 · 블록 · 얼룩 · 신호선 · 화면 튐 · 해킹 글자 → 어두워지며 흘러가 지직으로."""
    te = R.stutter(t)                                              # 심해질수록 움직임이 버벅거린다
    k, tn = look["k"], look["tune"]
    iw, ih = a.plain.width(), a.plain.height()
    scaled = (iw, ih) != (w, h)
    if scaled:
        p.setRenderHint(QPainter.SmoothPixmapTransform)
    dy = R.jump_at(scene, te) * h                                  # 화면이 위아래로 툭 튄다
    roll = (tn ** 2) * h * 0.4                                     # 지직으로 넘어가며 화면이 위로 흘러간다 (세로 동기가 풀림)
    split = w * (0.003 + 0.02 * k) * (1 + 0.35 * math.sin(te * 9.1))   # 색 번짐 — 갈수록 크게, 흔들리며

    def layers(rect: QRectF | None, dx: float, s: float) -> None:
        """찍은 화면을 빨강 · 청록이 어긋난 채로 (rect 안에만, 옆으로 dx 밀어서)."""
        if rect is not None:
            p.save()
            p.setClipRect(rect)
        for oy in ((dy - roll, dy - roll + h) if roll > 0.5 else (dy,)):
            p.setCompositionMode(QPainter.CompositionMode_Source)
            p.drawImage(QRectF(dx - s, oy, w, h), a.cyan)
            p.setCompositionMode(QPainter.CompositionMode_Plus)
            p.drawImage(QRectF(dx + s, oy, w, h), a.red)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        if rect is not None:
            p.restore()

    layers(None, 0.0, split)
    if k > 0.25:                                                   # 색이 옆으로 더 번진다 (잔상)
        p.setOpacity(0.22 * k)
        p.drawImage(QRectF(split * 2.6, dy, w, h), a.red)
        p.setOpacity(0.14 * k)
        p.drawImage(QRectF(-split * 2.6, dy, w, h), a.cyan)
        p.setOpacity(1.0)

    # 찢어진 띠 (그 띠만 옆으로 밀리고 색이 더 어긋난다) + 띠 끝의 가는 신호선
    for t0, t1, y, bh, dx in R.active(scene.tears, te):
        rect = QRectF(0, y * h + dy, w, max(2.0, bh * h))
        layers(rect, dx * w, split * 1.8)
        if k > 0.3:
            ink = INK[int(t0 * 1000) % 3]
            p.fillRect(QRectF(0, rect.top(), w, max(1.0, h / 540)), _c(ink, 0.8))
    # 한 줄을 옆으로 길게 늘인 얼룩
    for t0, t1, y, bh, x, width, sx in R.active(scene.smears, te):
        p.drawImage(QRectF(x * w, y * h + dy, width * w, max(1.0, bh * h)), a.plain,
                    QRectF(sx * (iw - 2), y * ih, 1.5, max(1.0, bh * ih)))
    # 깨진 블록 (다른 자리 조각 · 원색 · 반전)
    unit = max(4.0, h / 46)
    for t0, t1, x, y, cols, rows, kind, sx, sy in R.active(scene.blocks, te):
        rect = QRectF(x * w, y * h + dy, unit * cols, unit * rows)
        if kind == 0:
            p.drawImage(rect, a.plain, QRectF(sx * iw, sy * ih, rect.width() * iw / w, rect.height() * ih / h))
        elif kind == 1:
            p.fillRect(rect, INK[int(t0 * 997) % 3])
        else:
            p.setCompositionMode(QPainter.CompositionMode_Difference)
            p.fillRect(rect, QColor(255, 255, 255))
            p.setCompositionMode(QPainter.CompositionMode_SourceOver)
    # 해킹 글자 (한 글자씩 쳐진다 · 갈수록 늘어난다)
    p.setFont(a.code)
    shown = [c for c in scene.codes if c[0] <= te][-18:]
    for t0, x, y, text, kind in shown:
        n = min(len(text), int((te - t0) * 42) + 1)
        at = QPointF(x * w, y * h + dy)
        p.setPen(QColor(0, 0, 0, 170))
        p.drawText(at + QPointF(1, 1), text[:n])
        p.setPen(INK[0] if kind == 0 else INK[2])
        p.drawText(at, text[:n])
    if k > 0.3:                                                    # 되살리는 중이라는 진행 표시
        pct = int(min(99, 100 * k))
        bar = "#" * (pct // 10) + "." * (10 - pct // 10)
        p.setPen(INK[0])
        p.drawText(QPointF(w * 0.03, h * 0.95), f"RESTORING U.L.T.R.O.N CORE [{bar}] {pct}%")
    # 브라운관 주사선 — 갈수록 진하게
    p.setOpacity(min(1.0, 0.15 + 0.6 * k))
    p.drawImage(0, 0, a.crt)
    p.setOpacity(1.0)
    # 끝자락: 어두워진다 (모래알은 paint 가 그 위에 차오르게 그린다)
    if tn > 0:
        p.fillRect(QRectF(0, 0, w, h), _c(QColor(0, 0, 0), 0.55 * smooth(tn)))


def draw_static(p: QPainter, a: Assets, t: float, w: int, h: int, opacity: float) -> None:
    """옛날 TV 전파가 안 잡힐 때의 지직거리는 흑백 화면."""
    if opacity <= 0 or not a.static:
        return
    p.save()
    p.setOpacity(opacity)
    p.setRenderHint(QPainter.SmoothPixmapTransform)                # 늘인 알갱이가 부드럽게 번진다 (아날로그 느낌)
    frame = int(t / 0.045)                                         # 1초에 22장쯤 모래알이 바뀐다
    tile = a.static[frame % len(a.static)]
    tw, th = tile.width(), tile.height()
    cw, ch = tw * 3 // 4, th * 3 // 4                               # 매번 다른 자리를 잘라 쓴다 (되풀이가 안 보이게)
    sx, sy = (frame * 7919) % max(1, tw - cw), (frame * 104729) % max(1, th - ch)
    p.drawImage(QRectF(0, 0, w, h), tile, QRectF(sx, sy, cw, ch))
    # 가끔 한 줄이 옆으로 밀려 찢긴다 (수평 동기가 깨질 때)
    slot = int(t / 0.22)
    if (slot * 2654435761) % 3 != 0:
        y = (slot * 40503) % max(1, h)
        bh = max(2, int(h * (0.015 + 0.03 * ((slot * 97) % 10) / 10)))
        shift = int(w * (0.05 + 0.15 * ((slot * 31) % 10) / 10)) * (1 if slot % 2 else -1)
        src = QRectF(sx, sy + (y / h) * ch, cw, bh / h * ch)
        p.drawImage(QRectF(shift, y, w, bh), tile, src)
        p.drawImage(QRectF(shift - w if shift > 0 else shift + w, y, w, bh), tile, src)
    # 화면을 타고 천천히 흐르는 어두운 띠 (전파 동기 어긋남)
    band_h = h * 0.14
    y0 = ((t / 1.3) % 1.0) * (h + band_h) - band_h
    g = QLinearGradient(QPointF(0, y0), QPointF(0, y0 + band_h))
    g.setColorAt(0.0, _c(QColor(0, 0, 0), 0.0))
    g.setColorAt(0.5, _c(QColor(0, 0, 0), 0.32))
    g.setColorAt(1.0, _c(QColor(0, 0, 0), 0.0))
    p.fillRect(QRectF(0, y0, w, band_h), g)
    p.drawImage(0, 0, a.crt)                                        # 주사선 + 가장자리 어둡게
    p.restore()


def bolt(a: tuple[float, float], b: tuple[float, float], seed: int, rough: float = 0.2, depth: int = 5) -> list[QPointF]:
    """a → b 로 치는 번개 한 줄기 — 가운데를 거듭 꺾어 만든다. seed 가 같으면 모양도 같다 (같은 순간은 늘 같은 그림)."""
    rng = np.random.default_rng(seed)
    pts = [a, b]
    for _ in range(depth):
        nxt = [pts[0]]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            length = math.hypot(x1 - x0, y1 - y0) or 1.0
            d = float(rng.normal(0, rough * length))
            nxt.append(((x0 + x1) / 2 - (y1 - y0) / length * d, (y0 + y1) / 2 + (x1 - x0) / length * d))
            nxt.append((x1, y1))
        pts = nxt
    return [QPointF(x, y) for x, y in pts]


def draw_bolt(p: QPainter, pts: list[QPointF], col: QColor, k: float, width: float = 1.0) -> None:
    """번개 한 줄기: 색이 번진 굵은 줄 위에 흰 심지."""
    p.setBrush(Qt.NoBrush)
    p.setPen(_pen(_c(col, 0.38 * k), 9 * width, Qt.RoundCap))
    p.drawPolyline(QPolygonF(pts))
    p.setPen(_pen(_c(col.lighter(140), 0.8 * k), 3.4 * width, Qt.RoundCap))
    p.drawPolyline(QPolygonF(pts))
    p.setPen(_pen(_c(QColor(255, 255, 255), min(1.0, k * 1.3)), 1.4 * width, Qt.RoundCap))
    p.drawPolyline(QPolygonF(pts))


def draw_strikes(p: QPainter, scene: R.Scene, look: dict, t: float, w: int, h: int) -> None:
    """인피니티 장면의 번개 — 스톤이 박히는 순간 그 스톤에서 제 색의 번개가 뻗고, 다 나타나는 순간 코어에서 사방으로 친다.
    1/18 초마다 모양이 바뀐다 (지직거리며 친다)."""
    if not look.get("strikes"):
        return
    from . import infinity
    cx, cy, unit, _ = look["inf"]["at"]
    cx, cy = cx + look["jolt"][0], cy + look["jolt"][1]
    spin_t = t - scene.marks()["settle"]
    tick = int(t * 18)
    reach = min(w, h)
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    p.setCompositionMode(QPainter.CompositionMode_Plus)
    for i, k in look["strikes"]:
        if i >= 0:
            ang = infinity.gem_angle(i, spin_t)
            at = pt(ang, infinity.GEM_R * unit)
            for n in range(3):
                rng = np.random.default_rng(tick * 131 + i * 17 + n)
                far = pt(ang + float(rng.uniform(-55, 55)), reach * float(rng.uniform(0.34, 0.62)))
                draw_bolt(p, bolt((cx + at.x(), cy + at.y()), (cx + far.x(), cy + far.y()), tick * 977 + i * 31 + n),
                          infinity.GEMS[i], k, unit)
        else:
            for n in range(10):
                rng = np.random.default_rng(tick * 151 + n)
                ang = n * 36 + float(rng.uniform(-14, 14))
                a0, far = pt(ang, infinity.REACH * unit * 0.9), pt(ang + float(rng.uniform(-10, 10)), reach * float(rng.uniform(0.6, 1.05)))
                draw_bolt(p, bolt((cx + a0.x(), cy + a0.y()), (cx + far.x(), cy + far.y()), tick * 733 + n, 0.16),
                          infinity.GEMS[n % 6] if n % 2 else QColor(255, 120, 130), k, unit * 1.2)
    p.restore()


def paint(p: QPainter, scene: R.Scene, a: Assets, t: float, w: int, h: int) -> None:
    """t 초 때의 장면 (덮개 창 전체). 투명하게 남긴 곳으로는 아래의 실제 화면이 보인다."""
    look = looks(scene, t)
    if look["hack"]:
        draw_hack(p, scene, a, t, w, h, look)
    if look["black"] > 0:
        p.fillRect(QRectF(0, 0, w, h), _c(QColor(0, 0, 0), look["black"]))
    draw_static(p, a, t, w, h, look["static"])
    if look.get("inf") is not None:                                 # 인피니티 울트론 (infinity.py) — 자리 · 크기 · 진하기만 바꿔 매번 그린다
        from . import infinity
        cx, cy, unit, alpha = look["inf"]["at"]
        flash, tint = look["flash"]
        if flash > 0:                                               # 스톤이 박힐 때 · 다 나타날 때: 화면 전체가 번쩍인다
            p.fillRect(QRectF(0, 0, w, h), _c(QColor(*tint), flash))
        draw_strikes(p, scene, look, t, w, h)
        if alpha > 0:
            p.save()
            p.translate(cx + look["jolt"][0], cy + look["jolt"][1])
            p.scale(unit, unit)
            p.setOpacity(alpha)
            infinity.paint(p, t - scene.marks()["settle"], cv=look["inf"]["cv"], eye_open=look["inf"]["open"])
            p.restore()
    elif look["done"] is not None:                                    # 다 나타나 멈춘 코어 — 한 장을 크기 · 자리 · 진하기만 바꿔 찍는다
        cx, cy, size, alpha = look["done"]
        if alpha > 0:
            p.save()
            p.setOpacity(alpha)
            p.setRenderHint(QPainter.SmoothPixmapTransform)
            p.drawImage(QRectF(cx - size / 2, cy - size / 2, size, size), a.finished_core(spin(scene, t)))
            p.restore()
    elif look["eyes"] > 0 or any(v > 0 for v in look["core"].values()):
        draw_core(p, a, w / 2, h / 2, look, spin(scene, t))


def render(scene: R.Scene, t: float, background: np.ndarray | None = None, assets: Assets | None = None) -> np.ndarray:
    """(시험 · 미리보기) t 초 때의 장면을 background(RGB, 실제 화면 대신) 위에 덮은 모습 → RGB 배열."""
    w, h = scene.size
    img = QImage(w, h, QImage.Format_RGB888)
    img.fill(Qt.black)
    p = QPainter(img)
    if background is not None:
        bg = np.ascontiguousarray(background[..., :3])
        p.drawImage(QRectF(0, 0, w, h), QImage(bg.data, bg.shape[1], bg.shape[0], bg.shape[1] * 3, QImage.Format_RGB888))
    paint(p, scene, assets or Assets(scene, w, h), t, w, h)
    p.end()
    raw = np.frombuffer(img.constBits(), np.uint8, count=img.sizeInBytes())
    return raw.reshape(h, img.bytesPerLine())[:, :w * 3].reshape(h, w, 3).copy()


# ---------------------------------------------------------------- 덮개 창
class ReviveView(QWidget):
    handoff = Signal()         # 울트론이 HUD 크기로 다 줄어들었다 — 지금 실제 HUD 를 그 자리에 띄우면 겹쳐 넘겨받는다
    finished = Signal()

    def __init__(self) -> None:
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                         | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setWindowTitle("U.L.T.R.O.N REVIVE")
        self._scene: R.Scene | None = None
        self._assets: Assets | None = None
        self._handed = False
        self._clock = QElapsedTimer()
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

    def play(self, geometry: QRect, scene: R.Scene) -> None:
        self.setGeometry(geometry)
        self._scene, self._assets = scene, Assets(scene, geometry.width(), geometry.height())
        scene.drop_pixels()                        # 그릴 그림은 Assets 에 있다 — numpy 쪽은 놓아 준다
        self._handed = False
        self.show()
        self.raise_()                              # 울트론 HUD 도 '항상 위' 창이다 — 그 위로 올라간다
        self._clock.start()
        self._timer.start()
        self._guard.start(int(scene.duration * 1000) + 2000)
        self.update()

    def stop(self) -> None:
        self._timer.stop()
        self._guard.stop()
        if self._scene is not None and not self._handed:
            self._handed = True
            self.handoff.emit()                    # 중간에 멈췄어도 HUD 는 띄운다
        if self._scene is not None:
            self._scene.release()                  # 그림을 놓아 준다 (메모리)
            self._scene = self._assets = None
            self.hide()
            self.finished.emit()

    def _tick(self) -> None:
        sc = self._scene
        if sc is None:
            return
        t = self._clock.elapsed() / 1000
        if not self._handed and t >= sc.marks()["shrink"]:
            self._handed = True
            self.handoff.emit()
            self.raise_()                          # 방금 뜬 HUD 보다 위에서 겹친 채 옅어진다
        if t >= sc.duration:
            self.stop()
        else:
            self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setCompositionMode(QPainter.CompositionMode_Source)
        p.fillRect(self.rect(), Qt.transparent)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        if self._scene is not None and self._assets is not None:
            t = min(self._clock.elapsed() / 1000, self._scene.duration)
            paint(p, self._scene, self._assets, t, self.width(), self.height())
        p.end()
