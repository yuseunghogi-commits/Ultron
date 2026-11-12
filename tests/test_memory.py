"""메모리 — 연출이 끝나면 큰 그림 · 소리를 놓아 준다."""
import os

import pytest


def test_glitch_view_lets_go_of_frames_when_it_stops():
    pytest.importorskip("PySide6.QtWidgets")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QRect
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QApplication
    from jarvis.glitch_view import GlitchView
    app = QApplication.instance() or QApplication([])
    v = GlitchView()
    done = []
    v.finished.connect(lambda: done.append(1))
    img = QImage(64, 36, QImage.Format_RGBA8888)
    v.play(QRect(0, 0, 64, 36), [(img, 30), (None, 30), (img, 30)])
    assert len(v._frames) == 3
    v.stop()
    assert v._frames == [] and v._img is None and done == [1]
    v.stop()                                                     # 두 번 멈춰도 괜찮다
    assert done == [1]
    app.processEvents()
