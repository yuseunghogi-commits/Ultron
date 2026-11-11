"""말소리 캐시 — 한 번 합성한 짧은 대답을 저장해 두고, 같은 말은 인터넷을 거치지 않고 바로 재생한다.

Edge 음성은 문장마다 인터넷으로 받아 와서 0.5~1초가 걸린다. "볼륨을 낮췄다", "알았다. 바로 만들지." 처럼 자주 하는 짧은 말은
늘 똑같으므로 다듬기 · 기계음 효과까지 끝낸 소리(PCM)를 저장해 두면 다음부터는 곧바로 말한다.
  · 메모리: 최근 것 64개
  · 디스크: data/tts_cache/ 에 .npy (오래 안 쓴 것부터 지워 300개 · 40MB 이하로)
열쇠에는 글 · 목소리 · 빠르기 · 음높이 · 기계음 세기가 모두 들어가므로 설정을 바꾸면 새로 합성한다.
SAPI(인터넷이 끊겼을 때의 대체 음성)로 만든 소리는 저장하지 않는다 — 인터넷이 돌아오면 원래 목소리로 말하도록.
"""
from __future__ import annotations

import collections
import hashlib
import logging
import os
import threading
from pathlib import Path

import numpy as np

log = logging.getLogger("jarvis.tts_cache")

MAX_CHARS = 80            # 이보다 긴 말은 대개 한 번뿐이라 저장하지 않는다
MAX_FILES = 300
MAX_BYTES = 40 * 1024 * 1024
VERSION = "1"             # 다듬기 · 효과 처리 방식이 바뀌면 올린다 (예전 소리를 쓰지 않게)


class TTSCache:
    def __init__(self, folder: Path, memory: int = 64) -> None:
        self.folder = Path(folder)
        self._mem: collections.OrderedDict[str, np.ndarray] = collections.OrderedDict()
        self._memory = memory
        self._lock = threading.Lock()
        self._writes = 0

    @staticmethod
    def key(text: str, voice: str, rate: str, pitch: str, fx: float) -> str:
        raw = "\x1f".join((VERSION, text.strip(), voice, rate, pitch or "+0Hz", f"{float(fx):.3f}"))
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def wanted(text: str) -> bool:
        return 0 < len(text.strip()) <= MAX_CHARS

    def get(self, key: str) -> np.ndarray | None:
        with self._lock:
            pcm = self._mem.get(key)
            if pcm is not None:
                self._mem.move_to_end(key)
                return pcm
        path = self.folder / f"{key}.npy"
        try:
            pcm = np.load(path, allow_pickle=False)
        except (OSError, ValueError):
            return None
        if pcm.dtype != np.float32 or pcm.ndim != 1:
            return None
        try:
            os.utime(path)                     # 최근에 쓴 것으로 표시 (오래된 것부터 지우므로)
        except OSError:
            pass
        self._remember(key, pcm)
        return pcm

    def put(self, key: str, pcm: np.ndarray) -> None:
        if pcm is None or pcm.size == 0:
            return
        pcm = np.ascontiguousarray(pcm, dtype=np.float32)
        self._remember(key, pcm)
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            tmp = self.folder / f"{key}.{threading.get_ident()}.tmp.npy"
            np.save(tmp, pcm, allow_pickle=False)
            os.replace(tmp, self.folder / f"{key}.npy")
        except OSError as e:
            log.debug("말소리 저장 실패: %s", e)
            return
        self._writes += 1
        if self._writes % 20 == 1:
            self.trim()

    def _remember(self, key: str, pcm: np.ndarray) -> None:
        with self._lock:
            self._mem[key] = pcm
            self._mem.move_to_end(key)
            while len(self._mem) > self._memory:
                self._mem.popitem(last=False)

    def trim(self) -> None:
        """오래 안 쓴 것부터 지워 개수 · 크기 한도를 지킨다."""
        try:
            files = sorted(self.folder.glob("*.npy"), key=lambda p: p.stat().st_mtime, reverse=True)
        except OSError:
            return
        total = 0
        for i, p in enumerate(files):
            try:
                size = p.stat().st_size
            except OSError:
                continue
            total += size
            if i >= MAX_FILES or total > MAX_BYTES:
                try:
                    p.unlink()
                except OSError:
                    pass
