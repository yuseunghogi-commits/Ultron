"""부활 연출 — 가디언이 되살린 울트론이 처음 뜰 때, 화면 전체에 한 번 흐르는 장면 (약 8초).

  1) 해킹: 지금 화면이 살짝 찢어지다가 점점 심하게 깨지고 멈칫거린다 (해킹 연출 glitch.py 의 도구를 쓴다) — 약 1.6초
  2) TV 지직: 옛날 TV 전파가 안 잡힐 때처럼 흑백 모래알이 지직거린다 — 2초 유지
  3) 지직이 가라앉아 캄캄해지고, 울트론의 두 눈이 먼저 켜진다 (네온이 들어오듯 깜빡이다 또렷해지며 뜬다)
  4) 눈 둘레로 코어(원판 · 링 · 칼날 · 톱니 · 꺾쇠 · 이름)가 안쪽부터 차례로 나타난다
  5) 잠깐 머문 뒤 장면 전체가 옅어지며 원래 화면과 울트론 HUD 가 드러난다

실제로는 아무것도 바꾸지 않는다. 그 순간의 화면을 찍어 일그러뜨린 그림과 모래알을 덮개 창에 그릴 뿐이다.
이 파일은 그림 재료 · 시간표 · 소리만 만든다 (numpy — Qt 없이 시험할 수 있다). 그리는 것은 revive_view.py.

메모리: 해킹 장면 열두어 장만 미리 만들고(작게 줄여서), 지직 · 눈 · 코어는 매 순간 그린다 (모두 미리 만들면 수백 MB).
빛에 민감한 사람을 위해: 해킹 장면은 glitch.limit_flashes 로 넓은 면의 밝기 급변을 1초에 3번 이하로 줄이고,
단계가 바뀌는 곳(해킹 → 지직 → 검정 → 눈 → 원래 화면)은 모두 서서히 넘어간다. 지직은 중간 회색이라 번쩍이지 않는다.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import glitch

MAX_EDGE = 1280            # 해킹 장면은 이 긴 변 크기로 만들어 화면에 늘여 띄운다 (깨진 화면은 늘여도 티가 안 난다)
STATIC_EDGE = 960          # 지직 모래알 그림의 긴 변 (늘여 그리면 알갱이가 아날로그처럼 부드러워진다)
STATIC_TILES = 6           # 모래알 그림 몇 장을 돌려 가며 (매번 다른 자리를 잘라 써서 되풀이가 안 보인다)
SAFE_DELTA = 0.07          # 번쩍임을 잴 때 기준(0.10)보다 여유 있게 — 줄여서 재는 오차로 경계의 변화를 놓치지 않게

# 시간표 (초)
CROSS = 0.50               # 해킹 끝자락에 지직이 겹쳐 들어오는 시간 (밝은 화면에서도 확 바뀌지 않게)
STATIC = 2.0               # 지직 유지 (요청: 2초)
SETTLE = 0.6               # 지직이 가라앉아 캄캄해지는 시간
EYES = 1.1                 # 두 눈이 켜지는 시간
FORM = 1.4                 # 눈 둘레로 코어가 나타나는 시간
HOLD = 0.5                 # 완성된 채 머무는 시간
FADE = 0.7                 # 장면 전체가 옅어지며 원래 화면이 드러나는 시간


@dataclass
class Scene:
    hack: list[glitch.Frame]     # 1) 점점 심해지는 해킹 (RGBA — 투명한 곳은 실제 화면이 보인다)
    static: list[np.ndarray]     # 2) TV 지직 모래알 (흑백 uint8)
    size: tuple[int, int]        # 덮을 화면의 크기 (w, h)

    @property
    def t_hack(self) -> float:
        return sum(f.ms for f in self.hack) / 1000

    def marks(self) -> dict[str, float]:
        """각 단계가 끝나는 때 (초)."""
        m = {"hack": self.t_hack}
        m["static"] = m["hack"] + STATIC
        m["settle"] = m["static"] + SETTLE
        m["eyes"] = m["settle"] + EYES
        m["form"] = m["eyes"] + FORM
        m["hold"] = m["form"] + HOLD
        m["end"] = m["hold"] + FADE
        return m

    @property
    def duration(self) -> float:
        return self.marks()["end"]

    def drop_pixels(self) -> None:
        """화면에 그릴 그림(Qt)을 만든 뒤에는 numpy 그림을 놓아 준다 — 시간표(장면 길이)는 남긴다 (메모리를 두 벌 쓰지 않게)."""
        self.hack = [glitch.Frame(None, f.ms, f.kind) for f in self.hack]
        self.static = []

    def release(self) -> None:
        """다 보여 줬으면 그림을 놓아 준다 (메모리)."""
        self.hack, self.static = [], []


def phase(scene: Scene, t: float) -> tuple[str, float]:
    """t 초 때의 단계와 그 단계 안에서의 진행 0..1: hack · static · settle · eyes · form · hold · fade · end."""
    m = scene.marks()
    start = 0.0
    for name, key in (("hack", "hack"), ("static", "static"), ("settle", "settle"), ("eyes", "eyes"),
                      ("form", "form"), ("hold", "hold"), ("fade", "end")):
        end = m[key]
        if t < end:
            return name, (t - start) / max(1e-6, end - start)
        start = end
    return "end", 1.0


def hack_index(scene: Scene, t: float) -> int:
    """해킹 단계에서 t 초 때 보이는 장면의 번호 (그 장면의 그림이 None 이면 잠깐 정상 — 실제 화면)."""
    ms = t * 1000
    for i, f in enumerate(scene.hack):
        if ms < f.ms:
            return i
        ms -= f.ms
    return max(0, len(scene.hack) - 1)


# ---------------------------------------------------------------- 1) 점점 심해지는 해킹
def _shrink(shot: np.ndarray) -> np.ndarray:
    h, w, _ = shot.shape
    if max(w, h) <= MAX_EDGE:
        return shot
    from PIL import Image
    s = MAX_EDGE / max(w, h)
    return np.asarray(Image.fromarray(shot).resize((max(2, int(w * s)), max(2, int(h * s))), Image.BILINEAR))


def escalate(shot: np.ndarray, rng: np.random.Generator | None = None) -> list[glitch.Frame]:
    """찍은 화면(RGB)이 살짝 찢어지다가 → 글자가 뜨며 크게 찢어지고 → 더는 돌아오지 않고 조각 · 색 번짐 · 해킹 글자로
    뒤덮이며 무너진다 (약 1.6초).
    심해지는 느낌은 화면 전체를 흔들거나 물들이지 않고(밝은 화면에서 넓은 면의 밝기가 확 바뀐다), 갈수록 늘어나는
    조각 · 색 번짐 · 신호선 · 해킹 글자로 낸다 — 그래야 번쩍임 제한에 걸려 마지막 장면들이 잘려 나가지 않는다."""
    rng = rng or np.random.default_rng()
    h, w, _ = shot.shape
    R = glitch._ri

    def tear(level: float, text: bool = False) -> np.ndarray:
        img = glitch._tear(shot, rng, n=R(rng, 2 + int(level * 6), 3 + int(level * 9)),
                           max_shift=max(2, int(w * (0.04 + 0.22 * level))),
                           split=max(2, int(w * (0.004 + 0.012 * level))), cover=0.06 + 0.2 * level)
        if level >= 0.3:
            glitch._blocks(img, shot, rng, R(rng, 1, 1 + int(level * 3)))
            glitch._lines(img, rng, R(rng, 2, 2 + int(level * 6)))
        for _ in range(_lines_of_code(level, text)):
            glitch._text(img, rng)
        return img

    def freeze(level: float, text: bool = False) -> np.ndarray:
        img = glitch._freeze(shot, rng, (max(1, w // 160), max(1, h // 220)), max(3, int(w * (0.006 + 0.016 * level))))
        glitch._mosh(img, shot, rng, R(rng, 2 + int(level * 4), 3 + int(level * 8)))
        glitch._blocks(img, shot, rng, R(rng, 1 + int(level * 2), 2 + int(level * 4)))
        glitch._lines(img, rng, R(rng, 3 + int(level * 4), 4 + int(level * 10)))
        if level >= 0.75:                                          # 세로로 밀린 좁은 조각 몇 개
            for _ in range(R(rng, 1, 2 + int(level * 2))):
                cw = R(rng, max(2, w // 60), max(3, w // 22))
                x = R(rng, 0, w - cw)
                img[:, x:x + cw, :3] = np.roll(shot[:, x:x + cw], R(rng, -h // 8, h // 8), axis=0)
        for _ in range(_lines_of_code(level, text)):
            glitch._text(img, rng)
        return img

    F = glitch.Frame
    plan = [F(tear(0.15), 110, "tear"), F(None, 170, "gap"),            # 처음엔 살짝 — 화면이 금방 돌아온다
            F(tear(0.3), 120, "tear"), F(None, 110, "gap"),
            F(tear(0.45, text=True), 130, "tear"), F(None, 60, "gap"),  # 돌아오는 틈이 점점 짧아진다
            F(tear(0.6), 120, "tear"),
            F(freeze(0.65, text=True), 150, "freeze"),                   # 이제 돌아오지 않는다 — 멈칫거리며 무너진다
            F(freeze(0.75), 120, "freeze"),
            F(freeze(0.85, text=True), 140, "freeze"),
            F(freeze(0.95, text=True), 150, "freeze"),
            F(freeze(1.0, text=True), 180, "freeze")]
    return glitch.limit_flashes(shot, plan, delta=SAFE_DELTA)


def _lines_of_code(level: float, text: bool) -> int:
    """해킹 글자 덩어리 수 — 심해질수록 화면 여기저기에 늘어난다."""
    if not text:
        return 0
    return 1 if level < 0.8 else 2 if level < 0.95 else 3


# ---------------------------------------------------------------- 2) TV 지직
def static_tiles(w: int, h: int, rng: np.random.Generator | None = None, n: int = STATIC_TILES) -> list[np.ndarray]:
    """흑백 모래알 그림들 (화면의 절반쯤 크기). 가로로 살짝 번진 알갱이 + 줄마다 미세한 밝기 차 = 아날로그 TV 느낌.
    밝기는 중간 회색 둘레 — 장마다 바뀌어도 넓은 면의 평균 밝기는 거의 그대로라 번쩍이지 않는다."""
    rng = rng or np.random.default_rng()
    tw, th = max(2, w // 2), max(2, h // 2)
    if max(tw, th) > STATIC_EDGE:
        s = STATIC_EDGE / max(tw, th)
        tw, th = max(2, int(tw * s)), max(2, int(th * s))
    out = []
    for _ in range(n):
        g = rng.integers(0, 256, (th, tw), dtype=np.int32)
        g = (g + np.roll(g, 1, axis=1)) // 2                       # 가로로 번진 알갱이
        row = rng.normal(0, 9, (th, 1))                             # 줄마다 미세한 밝기 차
        out.append(np.clip(40 + g * 175 // 255 + row, 0, 255).astype(np.uint8))
    return out


# ---------------------------------------------------------------- 엮기
def build(shot: np.ndarray, size: tuple[int, int], rng: np.random.Generator | None = None) -> Scene:
    """찍은 화면(RGB)과 덮을 화면 크기(w, h)로 장면 재료를 만든다 (0.3초쯤 — 다른 스레드에서 부른다)."""
    rng = rng or np.random.default_rng()
    return Scene(escalate(_shrink(shot), rng), static_tiles(size[0], size[1], rng), (int(size[0]), int(size[1])))


# ---------------------------------------------------------------- 소리
def sound(scene: Scene, rng: np.random.Generator | None = None, sr: int = glitch.SOUND_RATE) -> np.ndarray:
    """장면에 맞춘 소리 (int16 모노): 점점 거칠어지는 디지털 잡음 → 쉭 하는 TV 지직 → 눈이 켜질 때 웅 하는 네온 울림 →
    코어가 다 나타날 때 낮게 쿵 → 옅어지며 끝."""
    rng = rng or np.random.default_rng()
    m = scene.marks()
    out = np.zeros(int(m["end"] * sr) + 1, np.float32)

    # 1) 해킹 — 해킹 연출의 소리를 쓰되 갈수록 크게
    hack = glitch.sound(scene.hack, rng, sr).astype(np.float32) / 32767
    if len(hack):
        hack *= np.linspace(0.5, 1.15, len(hack))
        out[:len(hack)] += hack[:len(out)]

    # 2) TV 지직 — 해킹 끝자락에서 들어와 2초 유지, 가라앉으며 사라진다
    s0, s1, s2 = int(max(0.0, m["hack"] - CROSS) * sr), int(m["static"] * sr), int(m["settle"] * sr)
    n = max(1, s2 - s0)
    hiss = rng.uniform(-1, 1, n).astype(np.float32)
    hiss = (hiss + np.roll(hiss, 1)) / 2                           # 너무 날카롭지 않게
    pops = rng.random(n) < 0.0009                                   # 가끔 탁 튀는 소리
    hiss[pops] *= 3.0
    env = np.ones(n, np.float32)
    ramp = max(1, min(n, s1 - s0, int(CROSS * sr)))
    env[:ramp] = np.linspace(0, 1, ramp)
    tail = max(1, s2 - s1)
    env[-tail:] = np.linspace(1, 0, tail)
    out[s0:s0 + n] += 0.34 * hiss * env

    # 3) 눈 · 코어 — 네온이 들어오는 웅 소리가 차올라 이어지다 옅어진다
    e0, e1 = int(m["settle"] * sr), len(out)
    t = np.arange(e1 - e0, dtype=np.float32) / sr
    hum = (0.26 * np.sin(2 * np.pi * 55 * t) + 0.12 * np.sin(2 * np.pi * 110 * t)
           + 0.05 * np.sign(np.sin(2 * np.pi * 100 * t)))          # 낮은 울림 + 네온 특유의 지잉
    env = np.clip(t / EYES, 0, 1) ** 1.5
    fade_at = m["hold"] - m["settle"]
    env *= np.clip(1 - (t - fade_at) / FADE, 0, 1)
    out[e0:e1] += hum * env

    # 4) 코어가 다 나타날 때 낮게 쿵
    k0 = int(m["form"] * sr)
    k = np.arange(min(int(0.9 * sr), len(out) - k0), dtype=np.float32) / sr
    out[k0:k0 + len(k)] += 0.5 * np.sin(2 * np.pi * 42 * k) * np.exp(-k * 4.5)

    edge = min(len(out), int(0.01 * sr))                            # 시작 · 끝이 '틱' 하지 않게
    if edge:
        out[:edge] *= np.linspace(0, 1, edge)
        out[-edge:] *= np.linspace(1, 0, edge)
    return (np.clip(out * 0.8, -1, 1) * 32767).astype(np.int16)
