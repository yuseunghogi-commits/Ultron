"""해킹 연출 덮개 창 — glitch.py 가 만든 장면들을 화면 위에 차례로 그린다.

마우스 · 키보드는 아래 창으로 그대로 통과하고(연출 중에도 PC 를 쓸 수 있다), 포커스를 빼앗지 않는다.
비어 있는 장면(gap)이나 투명한 부분에서는 실제 화면이 그대로 보인다.
"""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import QRect, Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QWidget

from .glitch import MAX_EDGE


def from_qimage(img: QImage) -> np.ndarray:
    """Qt 로 찍은 화면 → RGB uint8 배열 (너무 크면 가로 MAX_EDGE 로 줄인다)."""
    if img.width() > MAX_EDGE:
        img = img.scaledToWidth(MAX_EDGE, Qt.SmoothTransformation)
    img = img.convertToFormat(QImage.Format_RGB888)
    w, h, bpl = img.width(), img.height(), img.bytesPerLine()
    raw = np.frombuffer(img.constBits(), np.uint8, count=img.sizeInBytes())
    return raw.reshape(h, bpl)[:, :w * 3].reshape(h, w, 3).copy()


def to_qimage(rgba: np.ndarray) -> QImage:
    """RGBA uint8 배열 → QImage (배열과 메모리를 나누지 않도록 복사)."""
    h, w, _ = rgba.shape
    data = np.ascontiguousarray(rgba)
    return QImage(data.data, w, h, w * 4, QImage.Format_RGBA8888).copy()


class GlitchView(QWidget):
    finished = Signal()

    def __init__(self) -> None:
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                         | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setWindowTitle("U.L.T.R.O.N GLITCH")
        self._frames: list[tuple[QImage | None, int]] = []
        self._i = -1
        self._img: QImage | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._next)
        self._guard = QTimer(self)                 # 무슨 일이 있어도 덮개는 사라진다
        self._guard.setSingleShot(True)
        self._guard.timeout.connect(self.stop)

    @property
    def playing(self) -> bool:
        return self.isVisible()

    def play(self, geometry: QRect, frames: list[tuple[QImage | None, int]]) -> None:
        self._frames, self._i = list(frames), -1
        self.setGeometry(geometry)
        self.show()
        self._guard.start(sum(ms for _, ms in self._frames) + 1500)
        self._next()

    def stop(self) -> None:
        self._timer.stop()
        self._guard.stop()
        if self.isVisible():
            self._img = None
            self.hide()
            self.finished.emit()

    def _next(self) -> None:
        self._i += 1
        if self._i >= len(self._frames):
            self.stop()
            return
        self._img, ms = self._frames[self._i]
        self.repaint()                             # 장면이 짧아서 바로 그린다
        self._timer.start(max(16, int(ms)))

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setCompositionMode(QPainter.CompositionMode_Source)
        p.fillRect(self.rect(), Qt.transparent)
        if self._img is not None:
            p.setCompositionMode(QPainter.CompositionMode_SourceOver)
            p.setRenderHint(QPainter.SmoothPixmapTransform)
            p.drawImage(self.rect(), self._img)
        p.end()
