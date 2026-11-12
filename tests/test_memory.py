"""메모리 — 연출이 끝나면 큰 그림 · 소리를 놓아 주고, 말소리 캐시는 16비트로 담는다."""
import os

import numpy as np
import pytest

from jarvis.tts_cache import TTSCache


def test_tts_cache_keeps_sound_as_int16_but_plays_float(tmp_path):
    c = TTSCache(tmp_path)
    k = c.key("알았다.", "v", "r", "p", 0)
    pcm = np.sin(np.linspace(0, 60, 24000)).astype(np.float32) * 0.8
    c.put(k, pcm)
    assert c._mem[k].dtype == np.int16 and c._mem[k].nbytes == pcm.nbytes // 2
    got = c.get(k)
    assert got.dtype == np.float32 and np.allclose(got, pcm, atol=1e-4)
    got[:] = 0                                                   # 재생 쪽이 고쳐 써도 담아 둔 소리는 그대로
    assert np.allclose(c.get(k), pcm, atol=1e-4)
    assert np.load(tmp_path / f"{k}.npy").dtype == np.int16       # 디스크도 절반


def test_tts_cache_still_reads_old_float_files(tmp_path):
    c = TTSCache(tmp_path)
    k = c.key("예전 소리", "v", "r", "p", 0)
    old = np.linspace(-1, 1, 500, dtype=np.float32)
    np.save(tmp_path / f"{k}.npy", old)
    assert np.allclose(c.get(k), old, atol=1e-4) and c._mem[k].dtype == np.int16


def test_tts_cache_clips_loud_sound(tmp_path):
    c = TTSCache(tmp_path)
    k = c.key("크게", "v", "r", "p", 0)
    c.put(k, np.array([1.7, -2.0, 0.5], np.float32))
    assert np.allclose(c.get(k), [1.0, -1.0, 0.5], atol=1e-4)


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
