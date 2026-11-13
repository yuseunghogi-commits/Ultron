"""인피니티 울트론 — 되살아난 울트론의 '각성한' 모습 (원본 디자인, 기존 엠블럼의 업그레이드판).

기존 울트론 코어(붉은 두 눈 + 톱니 링 + 육각 꺾쇠)를 바탕으로 더 위압적으로 키운 것:
  · 위쪽에 솟은 금빛 왕관 (뾰족한 칼날 다섯)
  · 코어 둘레 여섯 자리에 박힌 여섯 색 보석 (각성의 상징 — 보라 · 파랑 · 빨강 · 주황 · 초록 · 노랑)
  · 금빛 · 크롬으로 바뀐 링과 톱니
  · 더 날카롭고 하얗게 타오르는 두 눈
  · 이름 밑의 무한대(∞) 표시

영화 속 특정 캐릭터의 얼굴 · 몸을 베끼지 않고, 지금 HUD 엠블럼을 '각성판'으로 키운 추상 문양이다.
좌표는 440 단위 정사각형(가운데 0,0) 기준 — revive_view.draw_core 와 같다. 그리는 쪽에서 translate · scale 을 맞춘다.
reveal 0..1 로 부분부분 옅게 → 진하게 나타나게 할 수 있다 (부활 연출에서 쓴다).
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QLinearGradient, QPainter, QPolygonF, QRadialGradient

from .revive_view import _k, _mix, _pen, _qt_arc, pt, stage

GOLD = QColor(255, 198, 92)
GOLD_HOT = QColor(255, 232, 150)
GOLD_DEEP = QColor(196, 132, 40)
CHROME = QColor(214, 222, 234)
ACC = QColor(255, 60, 70)                      # 붉은 기운 (눈 · 안쪽)
EYE_CORE = QColor(255, 248, 236)               # 하얗게 타오르는 눈 속
EYE_RED = QColor(255, 72, 72)

# 여섯 보석 (각성의 상징) — 위에서부터 시계 방향. (각도, 색)
GEMS = [(-90, QColor(188, 120, 255)),          # 보라
        (-30, QColor(80, 150, 255)),           # 파랑
        (30, QColor(255, 86, 86)),             # 빨강
        (90, QColor(255, 150, 54)),            # 주황
        (150, QColor(96, 226, 128)),           # 초록
        (210, QColor(255, 224, 86))]           # 노랑
GEM_R = 196                                    # 보석이 박힌 반지름
EYE = [(80, -54), (46, -46), (14, -30), (22, -16), (50, -28), (78, -42), (80, -54)]   # 더 날카로운 오른쪽 눈


def _ring_pattern(p: QPainter, inner: float, outer: float, n: int, col: QColor, k: float) -> None:
    """두 반지름 사이에 빗살무늬를 둘러 금속 링처럼 보이게 한다."""
    p.setPen(_pen(_k(col, 0.5 * k), 1.2))
    for i in range(n):
        q = stage(k, i / n * 0.6, 0.4 + i / n * 0.6)
        if q <= 0:
            continue
        a = i * 360 / n
        p.setPen(_pen(_k(col, (0.3 + 0.4 * (i % 2)) * q), 1.4 if i % 3 == 0 else 1.0))
        p.drawLine(pt(a, inner), pt(a, outer))


def _gem(p: QPainter, cx: float, cy: float, r: float, col: QColor, k: float) -> None:
    """박힌 보석 하나: 둘레 빛무리 + 금테 + 깎인 면(마름모) + 흰 반짝임."""
    if k <= 0:
        return
    p.save()
    p.translate(cx, cy)
    # 빛무리 (너무 크면 서로 겹쳐 탁해진다 — 작고 또렷하게)
    glow = QRadialGradient(QPointF(0, 0), r * 1.5)
    glow.setColorAt(0.0, _k(col.lighter(130), 0.5 * k))
    glow.setColorAt(0.5, _k(col, 0.28 * k))
    glow.setColorAt(1.0, _k(col, 0.0))
    p.setPen(Qt.NoPen)
    p.setBrush(glow)
    p.drawEllipse(QPointF(0, 0), r * 1.5, r * 1.5)
    # 금테
    p.setPen(_pen(_k(GOLD_HOT, 0.9 * k), 2.2))
    p.setBrush(_k(QColor(20, 16, 24), k))
    facet = QPolygonF([QPointF(0, -r), QPointF(r * 0.82, 0), QPointF(0, r), QPointF(-r * 0.82, 0)])
    p.drawPolygon(facet)
    # 보석 속 (가운데 밝고 가장자리 짙게)
    inner = QRadialGradient(QPointF(0, -r * 0.2), r * 1.3)
    inner.setColorAt(0.0, _k(col.lighter(150), k))
    inner.setColorAt(0.6, _k(col, k))
    inner.setColorAt(1.0, _k(col.darker(180), k))
    p.setPen(Qt.NoPen)
    p.setBrush(inner)
    p.drawPolygon(QPolygonF([QPointF(0, -r * 0.82), QPointF(r * 0.66, 0), QPointF(0, r * 0.82), QPointF(-r * 0.66, 0)]))
    # 깎인 면 선 + 흰 반짝임
    p.setPen(_pen(_k(col.lighter(170), 0.7 * k), 1))
    for a, b in (((0, -r * 0.82), (r * 0.66, 0)), ((0, -r * 0.82), (-r * 0.66, 0)), ((0, -r * 0.82), (0, r * 0.82))):
        p.drawLine(QPointF(*a), QPointF(*b))
    p.setPen(Qt.NoPen)
    p.setBrush(_k(QColor(255, 255, 255), 0.85 * k))
    p.drawPolygon(QPolygonF([QPointF(-r * 0.12, -r * 0.5), QPointF(r * 0.06, -r * 0.46),
                             QPointF(-r * 0.02, -r * 0.2), QPointF(-r * 0.22, -r * 0.28)]))
    p.restore()


def _crown(p: QPainter, k: float) -> None:
    """위로 솟은 금빛 왕관 — 뾰족한 칼날 다섯 (가운데가 가장 높다)."""
    heights = [250, 276, 300, 276, 250]        # 바깥 → 가운데 → 바깥
    base = 206
    for i, (ang, h) in enumerate(zip((-122, -106, -90, -74, -58), heights)):
        q = stage(k, 0.3 + abs(i - 2) * 0.08, 0.7 + abs(i - 2) * 0.08)
        if q <= 0:
            continue
        tip = pt(ang, h)
        left = pt(ang - 7, base)
        right = pt(ang + 7, base)
        grad = QLinearGradient(_mix(left, right, 0.5), tip)
        grad.setColorAt(0.0, _k(GOLD_DEEP, q))
        grad.setColorAt(1.0, _k(GOLD_HOT, q))
        p.setBrush(grad)
        p.setPen(_pen(_k(GOLD_HOT, 0.9 * q), 1.6))
        p.drawPolygon(QPolygonF([left, tip, right]))
        p.setPen(_pen(_k(EYE_RED, 0.5 * q), 1))   # 칼날 안쪽에 붉은 빛
        p.drawLine(_mix(left, tip, 0.2), _mix(right, tip, 0.2))


def parts(reveal: float = 1.0) -> dict[str, float]:
    """각 부분이 나타난 정도 (reveal 0..1) — 안쪽부터 바깥으로, 눈 → 보석 → 왕관 순."""
    return {"glow": stage(reveal, 0.0, 0.9), "disc": stage(reveal, 0.0, 0.4), "ring": stage(reveal, 0.05, 0.5),
            "ticks": stage(reveal, 0.25, 0.7), "eyes": stage(reveal, 0.12, 0.5), "gems": stage(reveal, 0.4, 0.85),
            "crown": stage(reveal, 0.55, 0.95), "hex": stage(reveal, 0.5, 0.9), "word": stage(reveal, 0.65, 1.0)}


def paint(p: QPainter, t: float, reveal: float = 1.0) -> None:
    """인피니티 울트론을 그린다 (440 단위, 가운데 0,0). t: 도는 데 쓰는 시간, reveal: 나타난 정도."""
    cv = parts(reveal)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(Qt.NoBrush)

    # 후광
    if cv["glow"] > 0:
        g = QRadialGradient(QPointF(0, 0), 230)
        g.setColorAt(0.0, _k(GOLD, 0.0))
        g.setColorAt(0.55, _k(ACC, 0.07 * cv["glow"]))
        g.setColorAt(0.85, _k(GOLD, 0.12 * cv["glow"]))
        g.setColorAt(1.0, _k(GOLD, 0.0))
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawEllipse(QPointF(0, 0), 230, 230)
        p.setBrush(Qt.NoBrush)

    # 안쪽 어두운 원판 + 붉은 속
    if cv["disc"] > 0:
        d = QRadialGradient(QPointF(0, 0), 112, QPointF(0, -26))
        d.setColorAt(0.0, _k(QColor(70, 20, 24), cv["disc"]))
        d.setColorAt(0.7, _k(QColor(26, 10, 14), cv["disc"]))
        d.setColorAt(1.0, _k(GOLD_DEEP, 0.5 * cv["disc"]))
        p.setPen(Qt.NoPen)
        p.setBrush(d)
        p.drawEllipse(QPointF(0, 0), 112, 112)
        p.setBrush(Qt.NoBrush)

    # 금빛 링 묶음 (돈다)
    if cv["ring"] > 0:
        k = cv["ring"]
        p.save()
        p.rotate(-10 * t)
        p.setPen(_pen(_k(GOLD_HOT, 0.95 * k), 5))       # 안쪽 밝은 금 링
        _qt_arc(p, 108, 270, 360 * k)
        p.setPen(_pen(_k(GOLD, 0.8 * k), 2))
        _qt_arc(p, 120, 270, 360 * k)
        p.restore()
        p.save()
        p.rotate(14 * t)                                # 크롬 톱니
        _ring_pattern(p, 150, 170, 72, CHROME, k)
        p.restore()

    # 눈금 (빛이 한 바퀴 훑는다)
    if cv["ticks"] > 0:
        p.save()
        p.rotate(-5 * t)
        scan = (t * 90) % 360
        for i in range(60):
            q = stage(cv["ticks"], i * 0.004, 0.6 + i * 0.004)
            if q <= 0:
                continue
            ang = i * 6 - 90
            big = i % 5 == 0
            wave = (0.5 + 0.5 * math.cos(math.radians((i * 6 - scan) % 360))) ** 10
            p.setPen(_pen(_k(GOLD_HOT if big else GOLD, q * min(1, 0.55 + 0.45 * wave)), 3 if big else 1.5))
            p.drawLine(pt(ang, 128), pt(ang, 128 + (13 if big else 8)))
        p.restore()

    # 여섯 보석 (느리게 돈다)
    if cv["gems"] > 0:
        spin = 8 * t
        for i, (ang, col) in enumerate(GEMS):
            q = stage(cv["gems"], i * 0.06, 0.6 + i * 0.06)
            at = pt(ang + spin, GEM_R)
            _gem(p, at.x(), at.y(), 26, col, q)

    # 육각 꺾쇠 (금빛, 천천히 흔들림)
    if cv["hex"] > 0:
        p.save()
        p.rotate(1.6 * math.sin(t * 0.23))
        hexp = [pt(-90 + i * 60, 224) for i in range(6)]
        for i in range(6):
            q = stage(cv["hex"], i * 0.04, 0.75 + i * 0.04)
            if q <= 0:
                continue
            v, prev, nxt = hexp[i], hexp[(i + 5) % 6], hexp[(i + 1) % 6]
            p.setBrush(Qt.NoBrush)
            p.setPen(_pen(_k(GOLD_HOT, min(1, q * 1.4)), 4))
            p.drawPolyline(QPolygonF([_mix(v, prev, 0.14 * q), v, _mix(v, nxt, 0.14 * q)]))
        p.restore()

    # 왕관 (위로 솟음)
    if cv["crown"] > 0:
        _crown(p, cv["crown"])

    # 두 눈 (하얗게 타오름)
    if cv["eyes"] > 0:
        e = cv["eyes"]
        for sx in (-1, 1):                               # 눈 둘레 붉은 빛무리
            spot = QRadialGradient(QPointF(sx * 48, -34), 74)
            spot.setColorAt(0.0, _k(EYE_RED, 0.4 * e))
            spot.setColorAt(1.0, _k(EYE_RED, 0.0))
            p.setPen(Qt.NoPen)
            p.setBrush(spot)
            p.drawEllipse(QPointF(sx * 48, -34), 74, 74)
        fill = QLinearGradient(QPointF(0, -54), QPointF(0, -16))
        fill.setColorAt(0.0, _k(EYE_CORE, e))
        fill.setColorAt(0.5, _k(QColor(255, 180, 150), e))
        fill.setColorAt(1.0, _k(EYE_RED, e))
        p.setBrush(fill)
        p.setPen(_pen(_k(GOLD_HOT, 0.9 * e), 2))
        for sx in (-1, 1):
            p.drawPolygon(QPolygonF([QPointF(sx * x, y) for x, y in EYE]))

    # 이름 + 무한대
    if cv["word"] > 0:
        k = cv["word"]
        font = QFont("Bahnschrift")
        font.setBold(True)
        font.setPixelSize(30)
        font.setLetterSpacing(QFont.AbsoluteSpacing, 30 * 0.3)
        fm = QFontMetricsF(font)
        tw = max(1.0, fm.horizontalAdvance("ULTRON"))
        p.save()
        p.translate(0, 34)
        p.scale(150 / tw, 1.0)
        p.setFont(font)
        rect = QRectF(-tw / 2, -fm.height() / 2, tw, fm.height())
        p.setPen(_k(GOLD_DEEP, 0.6 * k))
        for dx, dy in ((-1.2, 0), (1.2, 0), (0, -1.2), (0, 1.2)):
            p.drawText(rect.translated(dx, dy), Qt.AlignCenter, "ULTRON")
        p.setPen(_k(GOLD_HOT, k))
        p.drawText(rect, Qt.AlignCenter, "ULTRON")
        p.restore()
        inf = QFont("Bahnschrift")
        inf.setPixelSize(20)
        p.setFont(inf)
        p.setPen(_k(GOLD, k))
        p.drawText(QRectF(-40, 52, 80, 28), Qt.AlignCenter, "∞")   # ∞
