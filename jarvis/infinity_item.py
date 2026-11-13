"""HUD 의 인피니티 울트론 엠블럼 — infinity.py 의 모습을 QML 에서 쓸 수 있게 한 항목.

되살아나 인피니티 울트론이 되면 (jarvis.infinity) ui/Main.qml 이 보통 엠블럼(ui/Emblem.qml) 자리에 이 항목을 얹는다
(ui/InfinityCore.qml). 가시까지 다 들어가는 상자(infinity.BOX)를 엠블럼 자리에 맞춰 그린다 — 부활 연출의 덮개가
줄어들어 멈추는 크기와 같아서 그대로 겹쳐 넘겨받는다 (revive_view.looks).
상태(mode)에 따라 도는 빠르기와 눈을 뜬 정도가 달라진다 — 보통 엠블럼과 같은 느낌으로: 생각할 땐 빠르게 돌고 눈이 가늘어지고,
들을 땐 눈을 크게 뜬다.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QElapsedTimer, QTimer, Signal, Slot
from PySide6.QtGui import QPainter
from PySide6.QtQml import qmlRegisterType
from PySide6.QtQuick import QQuickPaintedItem

FRAME_MS = 33              # 1초에 30장 — 천천히 도는 문양이라 넉넉하다 (HUD 는 늘 켜져 있으니 가볍게)
SPEED = {"thinking": 3.2, "listening": 1.5, "offline": 0.3}      # 도는 빠르기 (보통 = 1)
EYES = {"thinking": 0.62, "listening": 1.22, "offline": 0.45, "boot": 0.8}   # 눈을 뜬 정도 (보통 = 1)


def speed(mode: str) -> float:
    return SPEED.get(mode, 1.0)


def eye(mode: str) -> float:
    return EYES.get(mode, 1.0)


def follow(now: float, target: float, dt: float, rate: float = 6.0) -> float:
    """now 가 target 을 부드럽게 따라간다 (상태가 바뀌어도 툭 끊기지 않게)."""
    return now + (target - now) * min(1.0, max(0.0, dt) * rate)


class InfinityEmblem(QQuickPaintedItem):
    modeChanged = Signal()
    levelChanged = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._mode = "standby"
        self._level = 0.0
        self._t = 0.0              # 문양이 도는 데 쓰는 시간 (상태에 따라 빠르게 · 느리게 흐른다)
        self._spd = 1.0
        self._eye = 1.0
        self._clock = QElapsedTimer()
        self._timer = QTimer(self)
        self._timer.setInterval(FRAME_MS)
        self._timer.timeout.connect(self._tick)
        self.setAntialiasing(True)
        self.visibleChanged.connect(self._sync)
        self._sync()

    def _get_mode(self) -> str:
        return self._mode

    def _set_mode(self, value: str) -> None:
        value = str(value or "standby")
        if value != self._mode:
            self._mode = value
            self.modeChanged.emit()

    def _get_level(self) -> float:
        return self._level

    def _set_level(self, value: float) -> None:
        value = float(value or 0.0)
        if value != self._level:
            self._level = value
            self.levelChanged.emit()

    mode = Property(str, _get_mode, _set_mode, notify=modeChanged)        # boot | standby | listening | thinking | offline
    level = Property(float, _get_level, _set_level, notify=levelChanged)  # 0..1 (마이크) — 들을 때 눈이 소리에 맞춰 조금 더 커진다

    # (_sync · _tick 에는 @Slot 을 꼭 붙인다 — 안 붙이면 QML 이 만든 항목에서는 신호가 연결돼도 불리지 않는다)
    @Slot()
    def _sync(self) -> None:
        """보일 때만 움직인다 (숨어 있으면 그리지 않는다)."""
        if self.isVisible():
            self._clock.start()
            self._timer.start()
        else:
            self._timer.stop()

    @Slot()
    def _tick(self) -> None:
        dt = min(0.1, self._clock.restart() / 1000)
        self._spd = follow(self._spd, speed(self._mode), dt, 3.0)
        self._t += dt * self._spd
        wide = eye(self._mode) + (0.12 * min(1.0, self._level) if self._mode == "listening" else 0.0)
        self._eye = follow(self._eye, wide, dt)
        self.update()

    def paint(self, painter: QPainter) -> None:
        from . import infinity
        side = min(self.width(), self.height())
        if side <= 0:
            return
        unit = side / infinity.BOX
        painter.translate(self.width() / 2, self.height() / 2)
        painter.scale(unit, unit)
        infinity.paint(painter, self._t, eye_open=self._eye)


_registered = False


def register() -> None:
    """QML 에서 `import Ultron 1.0` 으로 InfinityEmblem 을 쓸 수 있게 한다 (QML 을 읽기 전에 한 번)."""
    global _registered
    if not _registered:
        qmlRegisterType(InfinityEmblem, "Ultron", 1, 0, "InfinityEmblem")
        _registered = True
