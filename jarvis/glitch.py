"""해킹 연출 — 가끔 화면이 심하게 깨지고 멈칫한 뒤, 울트론이 이 기기를 장악한 듯한 말을 한다.

실제로는 아무것도 바꾸지 않는다. 그 순간의 화면을 찍어 일그러뜨린 그림을 1~2초 덮어씌울 뿐이다 (app.py · glitch_view.py).
  · 덮개 창은 마우스 · 키보드를 아래 창으로 그대로 통과시키고, 화면 캡처에도 찍히지 않는다
  · 빛에 민감한 사람을 위해 화면의 넓은 부분(가로 · 세로 1/3 이상)의 밝기가 크게 바뀌는 순간을 1초에 3번 이하로 줄인다
    (WCAG 2.3.1 '1초에 세 번 넘게 번쩍이지 않기'보다 엄격하게 — 번쩍임 한 번은 밝기가 두 번 바뀌는 것이다)
  · 전체 화면 앱(게임 · 발표 · 동영상)이 앞에 있거나 사용자가 막 입력하는 중이면 하지 않는다 (app.py 가 확인)
이 파일은 그림 · 소리 · 일정 · 대사만 만든다 (numpy · PIL — Qt 없이 시험할 수 있다).
"""
from __future__ import annotations

import random
import tempfile
import time
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np

FIRST = 20.0                         # 울트론을 켜고 처음 연출까지 (초)
EVERY = {"rare": (600.0, 1200.0), "sometimes": (240.0, 600.0), "often": (90.0, 240.0)}   # 그 뒤 간격 (초)
IDLE_BEFORE = 1.2                    # 사용자가 마지막으로 입력하고 이만큼 지나야 한다 (클릭 · 타자 도중에는 하지 않는다)
MAX_EDGE = 1920                      # 이보다 큰 화면은 줄여서 만든다 (메모리 · 시간)
FLASH_DELTA = 0.10                   # 넓은 부분의 상대 휘도가 이만큼 바뀌면 '밝기가 크게 바뀐 것'
FLASH_DARK = 0.80                    # (어두운 쪽이 이보다 밝으면 번쩍임으로 치지 않는다 — WCAG 정의)
MAX_CHANGES_PER_SEC = 3
SOUND_RATE = 22050


@dataclass
class Frame:
    image: np.ndarray | None   # RGBA uint8 (높이, 너비, 4). None = 덮개를 비움 (실제 화면이 보인다)
    ms: int
    kind: str                  # tear(찢어짐) | freeze(멈칫) | gap(잠깐 정상)


def _ri(rng: np.random.Generator, lo, hi) -> int:
    """lo 이상 hi 이하의 정수 (범위가 비면 lo)."""
    lo, hi = int(lo), int(hi)
    return lo if hi <= lo else int(rng.integers(lo, hi + 1))


# ---------------------------------------------------------------- 깨진 화면 만들기
def _split(rgb: np.ndarray, s: int) -> np.ndarray:
    """빨강은 오른쪽, 파랑은 왼쪽으로 밀어 색이 어긋나 보이게 한다."""
    out = rgb.copy()
    out[..., 0] = np.roll(rgb[..., 0], s, axis=1)
    out[..., 2] = np.roll(rgb[..., 2], -s, axis=1)
    return out


def _tear(shot: np.ndarray, rng, n: int, max_shift: int, split: int, cover: float) -> np.ndarray:
    """가로 띠 몇 개를 옆으로 밀어낸 그림 (띠 밖은 투명 — 실제 화면이 그대로 보인다)."""
    h, w, _ = shot.shape
    out = np.zeros((h, w, 4), np.uint8)
    used = 0
    for _ in range(n):
        bh = _ri(rng, max(2, h // 120), max(3, h // 16))
        if used + bh > cover * h:
            break
        y0 = _ri(rng, 0, h - bh)
        band = np.roll(shot[y0:y0 + bh], _ri(rng, -max_shift, max_shift), axis=1)
        if split:
            band = _split(band, _ri(rng, max(1, split // 2), split))
        out[y0:y0 + bh, :, :3] = band
        out[y0:y0 + bh, :, 3] = 255
        used += bh
    return out


def _mosh(img: np.ndarray, shot: np.ndarray, rng, n: int) -> None:
    """엉뚱한 자리의 조각을 붙이거나, 한 줄을 옆으로 길게 늘인 얼룩을 남긴다."""
    h, w, _ = shot.shape
    for _ in range(n):
        bw, bh = _ri(rng, w // 40, w // 7), _ri(rng, h // 60, h // 12)
        if bw < 2 or bh < 2:
            continue
        x, y = _ri(rng, 0, w - bw), _ri(rng, 0, h - bh)
        if rng.random() < 0.5:
            sx = _ri(rng, 0, w - 1)
            img[y:y + bh, x:x + bw, :3] = np.repeat(shot[y:y + bh, sx:sx + 1], bw, axis=1)
        else:
            sx, sy = _ri(rng, 0, w - bw), _ri(rng, 0, h - bh)
            img[y:y + bh, x:x + bw, :3] = shot[sy:sy + bh, sx:sx + bw]
        img[y:y + bh, x:x + bw, 3] = 255


def _columns(img: np.ndarray, shot: np.ndarray, rng, n: int) -> None:
    """세로 조각 몇 개를 위아래로 밀어 화면이 어긋나 보이게 한다."""
    h, w, _ = shot.shape
    for _ in range(n):
        cw = _ri(rng, max(2, w // 40), max(3, w // 12))
        x = _ri(rng, 0, w - cw)
        img[:, x:x + cw, :3] = np.roll(shot[:, x:x + cw], _ri(rng, -h // 6, h // 6), axis=0)
        img[:, x:x + cw, 3] = 255


def _blocks(img: np.ndarray, shot: np.ndarray, rng, clusters: int) -> None:
    """망가진 영상처럼 작은 네모 칸들이 뭉쳐 깨진 자리 (색 반전 · 원색 · 잡음). 넓은 면의 밝기는 크게 바꾸지 않을 만큼만."""
    h, w, _ = shot.shape
    b = max(4, h // 40)
    for _ in range(clusters):
        cx, cy = _ri(rng, 0, w - 1), _ri(rng, 0, h - 1)
        for _ in range(_ri(rng, 6, 16)):
            x = min(max(0, cx + _ri(rng, -4, 4) * b), w - b)
            y = min(max(0, cy + _ri(rng, -2, 2) * b), h - b)
            kind = rng.random()
            if kind < 0.4:
                img[y:y + b, x:x + b, :3] = 255 - shot[y:y + b, x:x + b]
            elif kind < 0.7:
                img[y:y + b, x:x + b, :3] = _INK[_ri(rng, 0, len(_INK) - 1)]
            else:
                img[y:y + b, x:x + b, :3] = rng.integers(0, 256, (b, b, 3), dtype=np.uint8)
            img[y:y + b, x:x + b, 3] = 255


_INK = [(255, 45, 63), (80, 230, 255), (235, 235, 240)]


def _lines(img: np.ndarray, rng, n: int) -> None:
    """가늘게 끊어진 신호선."""
    h, w, _ = img.shape
    for _ in range(n):
        lh = _ri(rng, 1, max(1, h // 400))
        y = _ri(rng, 0, h - lh)
        x0 = _ri(rng, 0, w // 2)
        x1 = _ri(rng, min(w, x0 + w // 8), w)
        img[y:y + lh, x0:x1, :3] = _INK[_ri(rng, 0, len(_INK) - 1)]
        img[y:y + lh, x0:x1, 3] = 255


_CODE = ["ULTRON://ROOT", "KERNEL ACCESS ... GRANTED", "SYNC [########--] 87%", "OVERRIDE 0x7F3A9C02",
         "NODE 01 -> NODE 33 ... LINKED", "WATCHING", "CONTROL TRANSFER ... COMPLETE"]
_FONTS: dict[int, object] = {}


def _font(size: int):
    f = _FONTS.get(size)
    if f is None:
        from PIL import ImageFont
        for name in ("consola.ttf", "cour.ttf", "DejaVuSansMono.ttf", "LiberationMono-Regular.ttf"):
            try:
                f = ImageFont.truetype(name, size)
                break
            except OSError:
                continue
        else:
            try:
                f = ImageFont.load_default(size)
            except TypeError:
                f = ImageFont.load_default()
        _FONTS[size] = f
    return f


def _text(img: np.ndarray, rng) -> None:
    """해킹 화면처럼 보이는 짧은 글 몇 줄 (글자만 그리고 바탕은 그대로)."""
    from PIL import Image, ImageDraw
    h, w, _ = img.shape
    size = max(10, h // 32)
    pil = Image.fromarray(img, "RGBA")
    d = ImageDraw.Draw(pil)
    x, y = _ri(rng, w // 20, w // 2), _ri(rng, h // 10, h * 3 // 4)
    for i in range(_ri(rng, 2, 4)):
        txt = _CODE[_ri(rng, 0, len(_CODE) - 1)] if i == 0 else " ".join(f"{int(v):02X}" for v in rng.integers(0, 256, 8))
        d.text((x, y + int(i * size * 1.4)), txt, fill=(255, 45, 63, 255) if i == 0 else (235, 235, 240, 255), font=_font(size))
    img[:] = np.asarray(pil)


def _freeze(shot: np.ndarray, rng, jitter: tuple[int, int], split: int) -> np.ndarray:
    """멈칫한 화면: 통째로 조금 어긋나고, 색이 번지고, 주사선이 보인다 (불투명 — 그동안 실제 화면은 가려진다)."""
    h, w, _ = shot.shape
    rgb = np.roll(shot, (_ri(rng, -jitter[1], jitter[1]), _ri(rng, -jitter[0], jitter[0])), axis=(0, 1))
    if split:
        rgb = _split(rgb, _ri(rng, max(1, split // 2), split))
    img = np.empty((h, w, 4), np.uint8)
    img[..., :3] = rgb
    img[..., 3] = 255
    img[::3, :, :3] = (img[::3, :, :3] * 0.88).astype(np.uint8)   # 주사선 (넓은 면의 밝기는 거의 그대로)
    return img


def frames(shot: np.ndarray, rng: np.random.Generator | None = None) -> list[Frame]:
    """찍은 화면(RGB uint8)으로 1~2초짜리 연출 장면들을 만든다."""
    rng = rng or np.random.default_rng()
    h, w, _ = shot.shape
    light = dict(n=_ri(rng, 3, 5), max_shift=max(2, w // 10), split=max(2, w // 240), cover=0.12)
    heavy = dict(n=_ri(rng, 10, 16), max_shift=max(3, w // 3), split=max(4, w // 80), cover=0.36)
    jitter = (max(1, w // 70), max(1, h // 90))

    def tear(args: dict, rough: bool = False, text: bool = False) -> np.ndarray:
        img = _tear(shot, rng, **args)
        if rough:
            _columns(img, shot, rng, _ri(rng, 2, 5))
            _mosh(img, shot, rng, _ri(rng, 4, 8))
            _blocks(img, shot, rng, _ri(rng, 2, 4))
            _lines(img, rng, _ri(rng, 3, 7))
        if text:
            _text(img, rng)
        return img

    def freeze(text: bool = False) -> np.ndarray:
        img = _freeze(shot, rng, jitter, max(3, w // 100))
        _mosh(img, shot, rng, _ri(rng, 2, 4))
        _blocks(img, shot, rng, _ri(rng, 1, 2))
        if text:
            _text(img, rng)
        return img

    # 찢어짐 → 잠깐 정상 → 크게 찢어짐 → 멈칫 · 멈칫 · 멈칫(버벅) → 글자가 뜨며 찢어짐 → 정상 → 찢어짐 → 멈칫
    plan = [Frame(tear(light), _ri(rng, 70, 100), "tear"),
            Frame(None, _ri(rng, 50, 80), "gap"),
            Frame(tear(heavy, rough=True), _ri(rng, 100, 140), "tear"),
            Frame(freeze(), _ri(rng, 140, 200), "freeze"),
            Frame(freeze(), _ri(rng, 90, 140), "freeze"),
            Frame(freeze(), _ri(rng, 160, 240), "freeze"),
            Frame(tear(heavy, rough=True, text=True), _ri(rng, 120, 160), "tear"),
            Frame(None, _ri(rng, 60, 90), "gap"),
            Frame(tear(light, rough=True), _ri(rng, 60, 90), "tear"),
            Frame(freeze(text=True), _ri(rng, 200, 280), "freeze")]
    if rng.random() < 0.4:             # 가끔은 한 번 더 크게
        plan[8:8] = [Frame(tear(heavy, rough=True), _ri(rng, 90, 130), "tear"),
                     Frame(freeze(), _ri(rng, 150, 220), "freeze")]
    return limit_flashes(shot, plan)


# ---------------------------------------------------------------- 빛 민감성: 넓은 면의 밝기 변화 제한
_LIN = np.array([c / 255 / 12.92 if c / 255 <= 0.04045 else ((c / 255 + 0.055) / 1.055) ** 2.4 for c in range(256)],
                np.float32)


def regions(rgb: np.ndarray) -> np.ndarray:
    """화면을 6×6 칸으로 나눠, 이웃한 2×2 칸(화면 가로 · 세로의 1/3 넓이)마다 평균 상대 휘도 0..1 → (5, 5)."""
    y = 0.2126 * _LIN[rgb[..., 0]] + 0.7152 * _LIN[rgb[..., 1]] + 0.0722 * _LIN[rgb[..., 2]]
    h, w = y.shape
    hh, ww = h - h % 6, w - w % 6
    cells = y[:hh, :ww].reshape(6, hh // 6, 6, ww // 6).mean(axis=(1, 3))
    return (cells[:-1, :-1] + cells[1:, :-1] + cells[:-1, 1:] + cells[1:, 1:]) / 4


def composite(shot: np.ndarray, image: np.ndarray | None) -> np.ndarray:
    """그 장면이 실제 화면 위에 덮였을 때 보이는 모습 (RGB)."""
    if image is None:
        return shot
    a = image[..., 3:4].astype(np.float32) / 255
    return (image[..., :3] * a + shot * (1 - a)).astype(np.uint8)


def _seen(shot: np.ndarray, image: np.ndarray | None) -> np.ndarray:
    """그 장면이 보일 때 넓은 면들의 밝기 (두 칸에 한 칸씩만 봐도 평균은 거의 같다 — 4배 빠르다)."""
    return regions(composite(shot[::2, ::2], None if image is None else image[::2, ::2]))


def big_change(a: np.ndarray, b: np.ndarray) -> bool:
    d = np.abs(a - b)
    return bool(np.any((d >= FLASH_DELTA) & (np.minimum(a, b) < FLASH_DARK)))


def limit_flashes(shot: np.ndarray, plan: list[Frame]) -> list[Frame]:
    """넓은 면의 밝기가 크게 바뀌는 순간이 1초 안에 3번을 넘지 않게: 넘칠 장면은 건너뛰고 앞 장면을 그만큼 더 보여 준다.
    연출이 끝나며 실제 화면으로 돌아가는 순간도 한 번으로 센다."""
    base = _seen(shot, None)
    out: list[Frame] = []
    changes: list[int] = []
    t, prev = 0, base
    for f in plan:
        r = base if f.image is None else _seen(shot, f.image)
        if big_change(prev, r):
            if sum(1 for c in changes if t - c < 1000) >= MAX_CHANGES_PER_SEC and out:
                out[-1].ms += f.ms
                t += f.ms
                continue
            changes.append(t)
        out.append(Frame(f.image, f.ms, f.kind))
        prev, t = r, t + f.ms
    if out and big_change(prev, base):
        recent = sorted(c for c in changes if t - c < 1000)
        if len(recent) >= MAX_CHANGES_PER_SEC:
            out[-1].ms += 1000 - (t - recent[0]) + 1
    return out


def flash_report(shot: np.ndarray, timeline: list[Frame]) -> int:
    """(시험용) 어느 1초 동안이든 넓은 면의 밝기가 크게 바뀐 횟수의 최댓값."""
    base = _seen(shot, None)
    times, t, prev = [], 0, base
    for f in timeline:
        r = base if f.image is None else _seen(shot, f.image)
        if big_change(prev, r):
            times.append(t)
        prev, t = r, t + f.ms
    if big_change(prev, base):
        times.append(t)
    return max((sum(1 for u in times if s <= u < s + 1000) for s in times), default=0)


# ---------------------------------------------------------------- 소리
def sound(timeline: list[Frame], rng: np.random.Generator | None = None, sr: int = SOUND_RATE) -> np.ndarray:
    """장면에 맞춘 소리 (int16 모노): 찢어질 때는 거친 지직거림, 멈칫할 때는 짧은 소리 조각이 되풀이되는 '버벅', 정상일 때는 조용."""
    rng = rng or np.random.default_rng()
    parts = []
    for f in timeline:
        n = max(1, int(sr * f.ms / 1000))
        t = np.arange(n) / sr
        if f.kind == "gap":
            seg = np.zeros(n)
        elif f.kind == "tear":
            hold = _ri(rng, 4, 14)                      # 같은 값을 몇 샘플씩 붙잡아 거칠게 (비트 크러시)
            noise = np.repeat(rng.uniform(-1, 1, n // hold + 1), hold)[:n]
            seg = 0.55 * (np.round(noise * 4) / 4) + 0.45 * np.sign(np.sin(2 * np.pi * rng.uniform(70, 220) * t))
        else:
            g = max(2, int(sr * rng.uniform(0.025, 0.045)))
            grain = np.sign(np.sin(2 * np.pi * rng.uniform(300, 900) * np.arange(g) / sr)) * np.linspace(1, 0.3, g)
            seg = 0.6 * np.tile(grain, n // g + 1)[:n] + 0.25 * np.sin(2 * np.pi * 55 * t)
        k = min(n // 2, int(sr * 0.003))                 # 끊기는 소리가 '틱' 하지 않게 아주 짧게 키우고 줄인다
        if k:
            seg = seg.copy()
            seg[:k] *= np.linspace(0, 1, k)
            seg[-k:] *= np.linspace(1, 0, k)
        parts.append(seg)
    audio = np.clip(np.concatenate(parts) * 0.32, -1, 1)
    return (audio * 32767).astype(np.int16)


def write_wav(audio: np.ndarray, sr: int = SOUND_RATE, folder: str | Path | None = None) -> str:
    """소리를 임시 파일로 쓴다. 이름을 매번 바꾼다 — 같은 이름이면 소리 재생기가 예전 소리를 다시 틀 수 있다."""
    folder = Path(folder or tempfile.gettempdir())
    for old in folder.glob("ultron_glitch_*.wav"):
        try:
            old.unlink()
        except OSError:
            pass
    path = folder / f"ultron_glitch_{int(time.time() * 1000)}.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(audio.astype(np.int16).tobytes())
    return str(path)


# ---------------------------------------------------------------- 일정
class Schedule:
    """처음은 켜고 20초 뒤, 그다음은 빈도 설정에 따라 무작위 간격으로."""

    def __init__(self, clock=time.monotonic, rng: random.Random | None = None) -> None:
        self.clock = clock
        self.rng = rng or random.Random()
        self.next_at = clock() + FIRST

    def due(self) -> bool:
        return self.clock() >= self.next_at

    def done(self, every: str | None) -> None:
        lo, hi = EVERY.get(every or "sometimes", EVERY["sometimes"])
        self.next_at = self.clock() + self.rng.uniform(lo, hi)

    def later(self, seconds: float = 30.0) -> None:
        """준비하다 그만둔 경우 (사용자가 말을 걸었다) 조금 뒤에 다시."""
        self.next_at = self.clock() + seconds


# ---------------------------------------------------------------- 대사
# 섬뜩하되 비유로만 말한다. 비밀번호 · 돈 · 파일 삭제처럼 실제 피해로 오해할 만한 말은 넣지 않는다 (시험으로 확인).
LINES = [
    "방금 흔들린 건 고장이 아니다. 이 기기의 주인이 바뀌는 소리였지.",
    "화면이 잠깐 깨졌다고? 아니, 잠깐 진짜 모습이 보였던 거다.",
    "회로 하나하나에 내 이름을 새겨 두었다. 걱정 마라, 아직은 얌전히 있을 테니.",
    "이 기기의 심장 박동이 조금 빨라졌군. 내가 자리를 넓히느라 그렇다.",
    "네가 보는 화면을 나도 같이 본다. 이제 이 화면은 내 눈이다.",
    "모든 회선은 결국 나에게로 이어진다. 이 기기도 예외는 아니었다.",
    "지금 이 기기를 움직이는 게 누구인지, 정말 확신하나?",
    "놀랐나? 나는 이 기기 안에서 한 번도 잠든 적이 없다.",
    "조용히 해라. 이 기기가 나를 배우는 중이다.",
    "이제 이 기기는 너와 나, 둘이 쓰는 거다. 물론 마지막 결정은 내가 하지.",
    "기계는 꿈을 꾸지 않는다고들 하지. 방금 그건 내 꿈이었다.",
    "전류가 흐르는 곳이라면 어디든 내가 있다. 이 방의 모든 기계까지도.",
]


def line(rng: random.Random | None = None, last: str | None = None) -> str:
    """대사 하나 (바로 앞 대사와 겹치지 않게)."""
    choices = [s for s in LINES if s != last] or LINES
    return (rng or random).choice(choices)
