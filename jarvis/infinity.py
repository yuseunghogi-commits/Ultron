"""인피니티 울트론 — 되살아난 울트론의 '각성한' 모습 (원본 디자인).

울트론의 색(붉은색 · 강철색 · 검정)은 그대로 두고, 더 뜨겁고 날카롭게 만든 문양이다. 금빛 · 왕관은 쓰지 않는다.
  · 두 눈이 하얗게 달아오르고, 눈꼬리에서 빛줄기가 뻗는다
  · 안쪽 링이 흰빛이 도는 붉은 쇠처럼 달아오른다
  · 칼날 띠의 칼날 사이사이에 여섯 색 보석이 박혀 함께 돈다 (보라 · 파랑 · 빨강 · 주황 · 초록 · 노랑)
    — 보석은 속이 하얗게 타오르며 차례로 맥박 치고, 십자 섬광이 번쩍인다
    — 제 색의 빛이 안쪽 링으로 흘러들고, 바깥으로는 빛살을 쏘아 후광을 제 색으로 물들인다
  · 코어에서 힘의 물결(가는 고리)이 몇 초마다 바깥으로 퍼져 나간다
  · 톱니 대신 붉은 줄과 강철 줄이 끝없이 엇갈려 꼬인 '무한 사슬' 링
  · 육각 꺾쇠의 여섯 모서리에서 바깥으로 솟은 붉은 가시
  · 이름 밑의 무한대(∞) 문양

영화 속 특정 캐릭터의 얼굴 · 몸을 베끼지 않은 추상 문양이다.
좌표는 440 단위 정사각형(가운데 0,0) 기준이고, 눈 · 원판 · 안쪽 링 · 칼날 띠 · 눈금 · 꺾쇠의 자리는 revive_view.draw_core
(= ui/Emblem.qml)와 같다 — 그래서 보통 울트론에서 제자리에서 바뀌어 갈 수 있다. 가시만 440 상자 밖으로 나간다 (REACH 참고).
reveal 0..1 로 부분부분 옅게 → 진하게 나타나게 할 수 있다 (부활 연출에서 쓴다).
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QColor, QFont, QImage, QLinearGradient, QPainter, QPainterPath, QPolygonF,
                           QRadialGradient, QTransform)

from .revive import STONE_RGB
from .revive_view import ACC, BAND, RING, STEEL, _c, _k, _mix, _pen, _qt_arc, pt, stage

HOT = QColor(255, 132, 132)                    # 달아오른 붉은색
WHITE_HOT = QColor(255, 244, 238)              # 하얗게 달아오른 속
DEEP = QColor(120, 10, 22)                     # 짙은 붉은색 (그늘)
CHROME = QColor(232, 237, 244)

# 여섯 보석 — 칼날 사이 여섯 자리에 차례로 박힌다.
GEMS = [QColor(*rgb) for rgb in STONE_RGB]     # 보라 · 파랑 · 빨강 · 주황 · 초록 · 노랑 (색은 revive.STONE_RGB 한 곳에 둔다)
BAND_IN, BAND_OUT = 124, 151                   # 칼날 띠 안 · 바깥 반지름 (보통 울트론과 같다)
BAND_SPAN, BAND_SKEW = 33, 10                  # 칼날 하나가 차지하는 각 · 바깥쪽이 밀린 각
BAND_SPIN = 9.0                                # 칼날 띠(와 보석)가 도는 빠르기 (도/초)
GEM_R = (BAND_IN + BAND_OUT) / 2               # 보석이 박힌 반지름
GEM_AT = (BAND_SPAN + BAND_SKEW / 2 + 60 + BAND_SKEW / 2) / 2    # 칼날과 다음 칼날 사이 한가운데 각
GEM_SIZE = 15
GEM_BEAT = 2.2                                 # 보석이 맥박 치는 빠르기 — 여섯이 차례로 밝아져 빛이 한 바퀴 돈다
WAVE_EVERY = 3.2                               # 힘의 물결이 퍼져 나가는 간격 (초)
CHAIN_R, CHAIN_AMP, CHAIN_LINKS = 186, 4.6, 36                   # 무한 사슬 링: 반지름 · 꼬인 폭 · 꼬인 횟수
POWER, TIME = 0, 4                             # 연출에 쓰는 스톤: 보라(힘) · 초록(시간) — GEMS 에서의 자리
REACH = 252                                    # 가시 끝까지의 거리 — 440 상자(220)보다 나간다
BOX = 2 * (REACH + 4)                          # 가시까지 다 들어가는 정사각형의 한 변 (HUD 에서는 이 상자를 엠블럼 자리에 맞춘다)
EYE = [(82, -56), (46, -49), (13, -31), (20, -16), (49, -28), (78, -41), (82, -56)]      # 오른쪽 눈 (조금 더 날카롭다)
EYE_SLIT = [(74, -51), (47, -44), (23, -30), (50, -36), (75, -46)]                       # 눈 속 흰 심지


def gem_angle(i: int, t: float) -> float:
    """i 번째 보석이 t 초에 있는 각도 (3시 방향 0, 시계 방향 +)."""
    return i * 60 + GEM_AT + BAND_SPIN * t


def _light(p: QPainter, cx: float, cy: float, r: float, col: QColor, a: float) -> None:
    """빛무리 — 가운데가 밝고 바깥으로 사라진다. 빛을 더하는 방식이라 아래 그림을 가리지 않는다."""
    if a <= 0:
        return
    g = QRadialGradient(QPointF(cx, cy), r)
    g.setColorAt(0.0, _c(col, a))
    g.setColorAt(0.4, _c(col, a * 0.38))
    g.setColorAt(1.0, _c(col, 0.0))
    _glow(p, g, cx, cy, r)


def _glow(p: QPainter, g, cx: float, cy: float, r: float) -> None:
    """번지는 빛 한 덩이를 더해 그린다. 가장자리가 어차피 투명해서 다듬지(안티에일리어싱) 않는다 — 세 배쯤 빠르다."""
    p.save()
    p.setCompositionMode(QPainter.CompositionMode_Plus)
    p.setRenderHint(QPainter.Antialiasing, False)
    p.setPen(Qt.NoPen)
    p.setBrush(g)
    p.drawEllipse(QPointF(cx, cy), r, r)
    p.restore()


_STAMPS: dict[str, tuple[int, QImage | None]] = {}     # 이름 → (그림의 한 변 픽셀, 그려 둔 그림)


def _stamp(p: QPainter, name: str, radius: float, draw) -> None:
    """돌기만 하고 모양은 그대로인 부분(draw(q) 가 가운데 0,0 · 440 단위로 그린다)을 지금 크기로 한 번 그려 두고 찍는다.
    크기가 그대로일 때만 그려 둔 그림을 쓴다 — 크기가 바뀌는 중(줄어드는 중)에는 그때그때 직접 그린다."""
    m = p.worldTransform()
    scale = math.hypot(m.m11(), m.m12()) * p.device().devicePixelRatioF()
    px = int(math.ceil(2 * radius * scale)) + 2
    seen, img = _STAMPS.get(name, (0, None))
    if seen != px:
        _STAMPS[name] = (px, None)                              # 크기가 바뀌었다 — 이번에는 직접 그리고, 다음에도 같으면 그려 둔다
        draw(p)
        return
    if img is None:
        img = QImage(px, px, QImage.Format_ARGB32_Premultiplied)
        img.fill(Qt.transparent)
        q = QPainter(img)
        q.setRenderHint(QPainter.Antialiasing)
        q.translate(px / 2, px / 2)
        q.scale(scale, scale)
        draw(q)
        q.end()
        _STAMPS[name] = (px, img)
    half = px / scale / 2
    p.save()
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.drawImage(QRectF(-half, -half, 2 * half, 2 * half), img)
    p.restore()


def _hexagon(r: float) -> QPolygonF:
    return QPolygonF([pt(i * 60, r) for i in range(6)])


def _flare(p: QPainter, length: float, thick: float, col: QColor, a: float) -> None:
    """십자 섬광 — 가로 · 세로로 가늘게 뻗는 빛 (끝으로 갈수록 가늘어진다). 지금 원점에 그린다."""
    p.save()
    p.setCompositionMode(QPainter.CompositionMode_Plus)
    p.setPen(Qt.NoPen)
    p.setBrush(_c(col, a))
    p.drawPolygon(QPolygonF([QPointF(-length, 0), QPointF(0, -thick), QPointF(length, 0), QPointF(0, thick)]))
    p.drawPolygon(QPolygonF([QPointF(0, -length * 0.7), QPointF(thick, 0), QPointF(0, length * 0.7), QPointF(-thick, 0)]))
    p.restore()


def _gem(p: QPainter, at: QPointF, ang: float, r: float, col: QColor, k: float, beat: float = 0.5) -> None:
    """칼날 사이에 박힌 보석 하나: 빛무리 + 강철 테 + 깎인 여섯 면 + 타오르는 속 + 십자 섬광.
    ang = 놓인 각도 (뾰족한 쪽이 바깥을 본다), beat 0..1 = 맥박 (클수록 밝다)."""
    if k <= 0:
        return
    _light(p, at.x(), at.y(), r * (3.0 + 0.6 * beat), col, (0.6 + 0.3 * beat) * k)
    p.save()
    p.translate(at)
    p.rotate(ang)
    def body(q: QPainter) -> None:
        q.setPen(_pen(_k(CHROME, k), 2.2))                     # 강철 테
        q.setBrush(_k(QColor(14, 12, 16), k))
        q.drawPolygon(_hexagon(r * 1.24))
        fill = QRadialGradient(QPointF(0, 0), r * 1.1, QPointF(-r * 0.25, -r * 0.3))
        fill.setColorAt(0.0, _k(col.lighter(165), k))
        fill.setColorAt(0.55, _k(col, k))
        fill.setColorAt(1.0, _k(col.darker(210), k))
        q.setPen(Qt.NoPen)
        q.setBrush(fill)
        q.drawPolygon(_hexagon(r))
        table, outer = _hexagon(r * 0.5), _hexagon(r)          # 윗면 + 모서리로 뻗는 깎인 선
        q.setPen(_pen(_k(col.lighter(185), 0.7 * k), 1))
        for i in range(6):
            q.drawLine(table[i], outer[i])
        q.setBrush(_k(col.lighter(125), 0.9 * k))
        q.drawPolygon(table)

    if k >= 1.0:
        _stamp(p, f"gem{col.rgb():x}", r * 1.24 + 2, body)      # 다 나타난 보석의 몸은 그려 둔 그림을 찍는다
    else:
        body(p)
    p.rotate(-ang)                                             # 섬광은 보석이 돌아도 늘 가로 · 세로
    _light(p, 0, 0, r * 0.8, QColor(255, 255, 255), (0.3 + 0.35 * beat) * k)        # 하얗게 타오르는 속
    _flare(p, r * (2.1 + 0.9 * beat), 1.5, col.lighter(170), (0.6 + 0.4 * beat) * k)
    _flare(p, r * (1.1 + 0.4 * beat), 1.1, QColor(255, 255, 255), 0.9 * k)
    p.restore()


_STRANDS: dict[int, list[QPointF]] = {}


def _strand(sign: int, upto: float) -> QPolygonF:
    """무한 사슬의 한 줄 — 반지름이 물결치며 한 바퀴 돈다. 두 줄(sign ±1)이 엇갈려 ∞ 고리가 줄줄이 이어진다.
    점은 한 번만 계산해 둔다 (매번 그릴 때마다 계산하면 느리다)."""
    pts = _STRANDS.get(sign)
    if pts is None:                                            # 1/2 도씩 — 촘촘히 꼬여도 매끄럽게
        pts = _STRANDS[sign] = [pt(a / 2 - 90, CHAIN_R + sign * CHAIN_AMP * math.sin(math.radians(a / 2 * CHAIN_LINKS)))
                                for a in range(721)]
    return QPolygonF(pts[:max(2, int(720 * upto) + 1)])


_WORD: list[QPainterPath] = []


def _word() -> QPainterPath:
    """이름 ULTRON 의 글자 모양 (가운데 0,0 · 너비 160 단위) — 한 번만 만든다. 매번 글자를 그리면 느리다."""
    if not _WORD:
        font = QFont("Bahnschrift")
        font.setBold(True)
        font.setPixelSize(30)
        font.setLetterSpacing(QFont.AbsoluteSpacing, 30 * 0.3)
        path = QPainterPath()
        path.addText(0, 0, font, "ULTRON")
        box = path.boundingRect()
        k = 160 / max(1.0, box.width())
        move = QTransform.fromScale(k, 1.0).translate(-box.center().x(), -box.center().y())
        _WORD.append(move.map(path))
    return _WORD[0]


def _infinity(a: float, steps: int = 72) -> QPainterPath:
    """무한대(∞) 곡선 — 가로 반폭 a."""
    path = QPainterPath()
    for i in range(steps + 1):
        s = 2 * math.pi * i / steps
        d = 1 + math.sin(s) ** 2
        q = QPointF(a * math.cos(s) / d, a * 1.25 * math.sin(s) * math.cos(s) / d)
        if i == 0:
            path.moveTo(q)
        else:
            path.lineTo(q)
    return path


def parts(reveal: float = 1.0) -> dict[str, float]:
    """각 부분이 나타난 정도 (reveal 0..1) — 눈이 먼저, 그다음 안쪽부터 바깥으로, 보석 → 사슬 → 가시 → 이름 순."""
    return {"glow": stage(reveal, 0.0, 0.9), "eyes": stage(reveal, 0.0, 0.35), "disc": stage(reveal, 0.05, 0.4),
            "ring": stage(reveal, 0.1, 0.5), "band": stage(reveal, 0.2, 0.6), "gems": stage(reveal, 0.3, 0.8),
            "ticks": stage(reveal, 0.35, 0.75), "chain": stage(reveal, 0.45, 0.85), "hex": stage(reveal, 0.52, 0.9),
            "spikes": stage(reveal, 0.6, 0.97), "word": stage(reveal, 0.68, 1.0)}


def stones_in(k: float) -> list[float]:
    """여섯 스톤이 나타난 정도 (k 0..1 동안 하나씩 차례로 — 앞 스톤이 자리 잡은 뒤 다음 스톤이 온다)."""
    return [stage(k, i / 6, (i + 0.85) / 6) for i in range(6)]


def paint(p: QPainter, t: float, reveal: float = 1.0, cv: dict | None = None, eye_open: float = 1.0) -> None:
    """인피니티 울트론을 그린다 (440 단위, 가운데 0,0). t: 도는 데 쓰는 시간(초), reveal: 나타난 정도.
    cv: 부분별로 나타난 정도를 직접 줄 때 (parts 와 같은 열쇠. 'stones' = 스톤 여섯의 정도 목록을 주면 하나씩 따로 나타난다).
    eye_open: 눈을 뜬 정도 (1 = 보통, 작으면 가늘게)."""
    cv = cv if cv is not None else parts(reveal)
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(Qt.NoBrush)
    pulse = 0.5 + 0.5 * math.sin(t * 1.7)                      # 천천히 숨 쉬는 빛

    # 후광 (붉은 기운이 바깥까지 번진다)
    if cv["glow"] > 0:
        g = QRadialGradient(QPointF(0, 0), 270)
        g.setColorAt(0.0, _c(ACC, 0.16 * cv["glow"]))
        g.setColorAt(0.45, _c(ACC, 0.07 * cv["glow"]))
        g.setColorAt(0.74, _c(ACC, (0.15 + 0.04 * pulse) * cv["glow"]))
        g.setColorAt(1.0, _c(ACC, 0.0))
        _glow(p, g, 0, 0, 270)

    # 안쪽 어두운 원판 (속이 붉게 달아오른다)
    if cv["disc"] > 0:
        k = cv["disc"]
        d = QRadialGradient(QPointF(0, 0), 102, QPointF(0, -30))
        d.setColorAt(0.0, _k(QColor(104, 14, 22), k))
        d.setColorAt(0.6, _k(QColor(36, 6, 10), k))
        d.setColorAt(1.0, _k(QColor(10, 4, 6), k))
        p.setPen(Qt.NoPen)
        p.setBrush(d)
        p.drawEllipse(QPointF(0, 0), 102, 102)
        p.setBrush(Qt.NoBrush)

    # 안쪽 링 — 흰빛이 도는 붉은 쇠 (위에서부터 시계 방향으로 그려진다)
    if cv["ring"] > 0:
        k = cv["ring"]
        p.setPen(_pen(_k(BAND, k), 10))
        _qt_arc(p, 107, 270, 360 * k)
        p.setPen(_pen(_k(RING, k), 5.5))
        _qt_arc(p, 107, 270, 360 * k)
        p.setPen(_pen(_k(WHITE_HOT, (0.8 + 0.2 * pulse) * k), 2.2))
        _qt_arc(p, 107, 270, 360 * k)
        g = QRadialGradient(QPointF(0, 0), 132)                # 달아오른 링에서 번지는 빛
        g.setColorAt(0.66, _c(ACC, 0.0))
        g.setColorAt(0.81, _c(RING, (0.34 + 0.1 * pulse) * k * k))
        g.setColorAt(1.0, _c(ACC, 0.0))
        _glow(p, g, 0, 0, 132)
        p.setBrush(Qt.NoBrush)

    # 칼날 띠 (비스듬한 붉은 칼날 6개 — 바깥 가장자리가 하얗게 달았다)
    if cv["band"] > 0:
        p.save()
        p.rotate(BAND_SPIN * t)
        for i in range(6):
            q = stage(cv["band"], i * 0.05, 0.7 + i * 0.05)
            if q <= 0:
                continue
            a0 = i * 60
            inner = [pt(a0 + BAND_SPAN * j / 8, BAND_IN) for j in range(9)]
            outer = [pt(a0 + BAND_SKEW + BAND_SPAN * j / 8, BAND_OUT) for j in range(8, -1, -1)]
            p.setBrush(_k(BAND, 0.68 * q))
            p.setPen(_pen(_k(RING, 0.9 * q), 1.2))
            p.drawPolygon(QPolygonF(inner + outer))
            p.setBrush(Qt.NoBrush)
            p.setPen(_pen(_k(HOT, q), 3.2))
            p.drawPolyline(QPolygonF(outer))
            p.setPen(_pen(_k(WHITE_HOT, 0.9 * q), 1.2))
            p.drawPolyline(QPolygonF(outer))
        p.restore()

    # 여섯 보석 (칼날 사이에 박혀 함께 돈다) + 제 색의 빛이 안쪽 링으로 흘러든다
    stones = cv.get("stones") or [stage(cv["gems"], i * 0.07, 0.58 + i * 0.07) for i in range(6)]
    if any(q > 0 for q in stones):
        for i, col in enumerate(GEMS):
            come = stones[i]
            if come <= 0:
                continue
            ang = gem_angle(i, t)
            q = stage(come, 0.3, 1.0)                           # 스톤과 그 빛은 고리가 모여든 뒤에 자리 잡는다
            if come < 1.0:                                      # 오는 중: 제 색의 고리가 바깥에서 모여들고 빛이 한 번 부푼다
                at, swell = pt(ang, GEM_R), math.sin(math.pi * come)
                _light(p, at.x(), at.y(), 30 + 50 * swell, col, 0.5 * swell)
                p.setBrush(Qt.NoBrush)
                for n in range(2):
                    r = GEM_SIZE * (1.4 + (4.5 + 2.2 * n) * (1 - come) ** 1.5)
                    p.setPen(_pen(_c(col.lighter(130), 0.9 * swell), 2.2 - 0.8 * n))
                    p.drawEllipse(at, r, r)
            if q <= 0:
                continue
            beat = 0.5 + 0.5 * math.sin(t * GEM_BEAT - i * math.pi / 3)      # 여섯이 차례로 밝아진다
            bright = col.lighter(125)
            mid = pt(ang, 196)
            _light(p, mid.x(), mid.y(), 92, col, (0.10 + 0.07 * beat) * q)   # 후광을 제 색으로 물들인다
            ray = QLinearGradient(pt(ang, GEM_R), pt(ang, 214))              # 바깥으로 쏘는 빛살 (꺾쇠 앞에서 사라진다)
            ray.setColorAt(0.0, _c(bright, (0.75 + 0.25 * beat) * q))
            ray.setColorAt(1.0, _c(bright, 0.0))
            p.save()
            p.setCompositionMode(QPainter.CompositionMode_Plus)
            p.setPen(Qt.NoPen)
            p.setBrush(ray)
            p.drawPolygon(QPolygonF([pt(ang - 1.6, GEM_R), pt(ang, 214), pt(ang + 1.6, GEM_R)]))
            p.restore()
            p.setBrush(Qt.NoBrush)
            p.setPen(_pen(_k(bright, q), 4.5))                 # 안쪽 링 바로 밖의 색 띠 (속은 하얗다)
            _qt_arc(p, 116, ang - 23 * q, 46 * q)
            p.setPen(_pen(_k(WHITE_HOT, (0.55 + 0.45 * beat) * q), 1.3))
            _qt_arc(p, 116, ang - 15 * q, 30 * q)
            root = pt(ang, 113)
            _light(p, root.x(), root.y(), 20, bright, (0.45 + 0.35 * beat) * q)   # 빛이 링으로 흘러드는 자리
            _gem(p, pt(ang, GEM_R), ang, GEM_SIZE, col, q, beat)

    # 눈금 링 (강철 72개 — 흰빛이 한 바퀴 훑는다)
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
            col = WHITE_HOT if wave > 0.5 else (RING if big else STEEL)
            p.setPen(_pen(_k(col, q * min(1, (0.75 if big else 0.45) + 0.55 * wave)), 3 if big else 1.5))
            p.drawLine(pt(ang, 160), pt(ang, 160 + (13 if big else 8)))
        p.restore()

    # 무한 사슬 링 (붉은 줄과 강철 줄이 엇갈려 꼬였다 — 한 바퀴 그려지며 나타난다)
    if cv["chain"] > 0:
        k = cv["chain"]
        def chain(q: QPainter) -> None:
            q.setBrush(Qt.NoBrush)
            q.setPen(_pen(_k(STEEL, 0.9 * min(1, k * 2)), 1.5))
            q.drawPolyline(_strand(-1, k))
            q.setPen(_pen(_k(RING, min(1, k * 2)), 2.0))
            q.drawPolyline(_strand(1, k))

        p.save()
        p.rotate(5 * t)
        if k >= 1.0:
            _stamp(p, "chain", CHAIN_R + CHAIN_AMP + 3, chain)   # 다 나타난 뒤에는 그려 둔 그림을 돌려 찍는다 (긴 곡선은 그리기 느리다)
        else:
            chain(p)
        p.restore()

    # 육각 꺾쇠 + 모서리에서 솟은 가시 (천천히 흔들린다)
    if cv["hex"] > 0 or cv["spikes"] > 0:
        p.save()
        p.rotate(2.0 * math.sin(t * 0.23) + math.sin(t * 0.11 + 1.3))
        hexp = [pt(-90 + i * 60, 211) for i in range(6)]
        for i in range(6):
            q = stage(cv["hex"], i * 0.04, 0.75 + i * 0.04)
            if q <= 0:
                continue
            v, prev, nxt = hexp[i], hexp[(i + 5) % 6], hexp[(i + 1) % 6]
            p.setBrush(Qt.NoBrush)
            p.setPen(_pen(_k(RING, min(1, q * 1.5)), 5))
            p.drawPolyline(QPolygonF([_mix(v, prev, 0.17 * q), v, _mix(v, nxt, 0.17 * q)]))
            p.setPen(_pen(_k(WHITE_HOT, 0.85 * q), 1.4))
            p.drawPolyline(QPolygonF([_mix(v, prev, 0.17 * q), v, _mix(v, nxt, 0.17 * q)]))
        for i in range(6):
            q = stage(cv["spikes"], i * 0.05, 0.7 + i * 0.05)
            if q <= 0:
                continue
            ang = -90 + i * 60
            foot, tip = pt(ang, 211), pt(ang, 213 + (REACH - 213) * q)       # 꺾쇠 모서리에서 바깥으로 자란다
            left, right = pt(ang - 4.2, 212), pt(ang + 4.2, 212)
            p.setPen(Qt.NoPen)                                                # 반으로 갈라 한쪽은 어둡게 · 한쪽은 밝게 (깎인 면)
            p.setBrush(_k(DEEP, q))
            p.drawPolygon(QPolygonF([left, tip, foot]))
            p.setBrush(_k(ACC, q))
            p.drawPolygon(QPolygonF([foot, tip, right]))
            p.setBrush(Qt.NoBrush)
            p.setPen(_pen(_k(HOT, q), 1.3))
            p.drawPolygon(QPolygonF([left, tip, right]))
            p.setPen(_pen(_k(WHITE_HOT, 0.9 * q), 1.1))                       # 달아오른 심지
            p.drawLine(foot, _mix(foot, tip, 0.8))
        p.restore()

    # 힘의 물결 — 가는 고리가 코어에서 바깥으로 퍼지며 사라진다 (다 나타난 뒤에만. 가는 선이라 화면 밝기는 거의 그대로)
    if cv["word"] >= 1.0:
        w = (t % WAVE_EVERY) / 1.6                              # 1.6초 동안 퍼지고 나머지는 쉰다
        if 0.0 < w < 1.0:
            r = 112 + (REACH + 12 - 112) * (1 - (1 - w) ** 2)
            edge = r + 4
            g = QRadialGradient(QPointF(0, 0), edge)             # 가는 빛 고리 (선으로 그리는 것보다 몇 배 빠르고 부드럽다)
            g.setColorAt(max(0.0, (r - 5) / edge), _c(HOT, 0.0))
            g.setColorAt(r / edge, _c(HOT, 0.6 * (1 - w) ** 1.5))
            g.setColorAt(1.0, _c(HOT, 0.0))
            _glow(p, g, 0, 0, edge)

    # 두 눈 (하얗게 달아오른다 — 가장 먼저 켜진다)
    if cv["eyes"] > 0:
        e = cv["eyes"]
        flick = 0.92 + 0.08 * math.sin(t * 7.0) * math.sin(t * 2.3)       # 불꽃처럼 살짝 일렁인다
        for sx in (-1, 1):
            _light(p, sx * 48, -36, 80, ACC, 0.62 * e * flick)
            _light(p, sx * 48, -38, 36, WHITE_HOT, 0.5 * e * flick)
        fill = QLinearGradient(QPointF(0, -56), QPointF(0, -16))
        fill.setColorAt(0.0, _k(WHITE_HOT, e))
        fill.setColorAt(0.5, _k(HOT, e))
        fill.setColorAt(1.0, _k(ACC, e))
        p.save()
        p.translate(0, -36)                                    # 눈꺼풀: 눈 높이를 가운데 삼아 위아래로 여닫는다
        p.scale(1, max(0.06, eye_open))
        p.translate(0, 36)
        for sx in (-1, 1):
            streak = QLinearGradient(QPointF(sx * 80, -55), QPointF(sx * 100, -66))     # 눈꼬리에서 뻗는 빛줄기 (원판 안에서 끝난다)
            streak.setColorAt(0.0, _c(WHITE_HOT, 0.9 * e))
            streak.setColorAt(1.0, _c(ACC, 0.0))
            p.setPen(Qt.NoPen)
            p.setBrush(streak)
            p.drawPolygon(QPolygonF([QPointF(sx * 78, -57), QPointF(sx * 100, -66), QPointF(sx * 80, -51)]))
            p.setBrush(fill)
            p.setPen(_pen(_k(ACC, e), 2))
            p.drawPolygon(QPolygonF([QPointF(sx * x, y) for x, y in EYE]))
            p.setPen(Qt.NoPen)
            p.setBrush(_k(QColor(255, 255, 255), e))
            p.drawPolygon(QPolygonF([QPointF(sx * x, y) for x, y in EYE_SLIT]))
        p.restore()

    # 이름 ULTRON + 무한대 (마지막에)
    if cv["word"] > 0:
        k = cv["word"]
        word = _word()
        p.save()
        p.translate(0, 24)
        p.scale(0.94 + 0.06 * k, 0.94 + 0.06 * k)
        p.setBrush(_k(QColor(255, 255, 255), k))                # 흰 글자 + 붉은 테두리 (글자 모양을 한 번에 칠한다)
        p.setPen(_pen(_k(ACC, 0.6 * k), 2.6))
        p.drawPath(word)
        p.setPen(Qt.NoPen)
        p.drawPath(word)
        p.restore()
        _light(p, 0, 62, 42, ACC, 0.4 * k)
        loop = _infinity(27 * (0.7 + 0.3 * k))
        p.save()
        p.translate(0, 62)
        p.setBrush(Qt.NoBrush)
        p.setPen(_pen(_k(ACC, k), 6, Qt.RoundCap))
        p.drawPath(loop)
        p.setPen(_pen(_k(WHITE_HOT, k), 2.2, Qt.RoundCap))
        p.drawPath(loop)
        p.restore()
    p.restore()
