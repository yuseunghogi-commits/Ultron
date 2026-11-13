"""디자인 결과물 — 카드뉴스 · 포스터를 화면 클릭 없이 바로 이미지로 만든다.

미리캔버스 같은 사이트를 화면을 보며 조작하면 느리고 실패할 수 있다. 자주 만드는 카드뉴스 · 포스터는 여기서 직접 그린다:
  · build_cardnews: 1080×1080 정사각형 카드 여러 장 (표지 · 내용 · 마무리) → 폴더에 01.png… + 한 묶음 PDF
  · build_poster: A4(또는 A3) 세로 포스터 → PNG + PDF (인쇄용)

카드뉴스가 '발표 슬라이드'처럼 보이지 않게 — 카드마다 내용에 맞는 모양을 쓴다 (layout):
  point   핵심 한 가지: 큰 아이콘 + 굵은 제목 + 짧은 설명            (글이 1~2줄일 때 기본)
  list    목록: 번호 붙은 줄 상자가 카드를 채운다                       (글이 3줄 이상일 때 기본)
  stat    큰 숫자: '6시간' · '70%' 를 카드 가득 크게                     (stat 을 주면)
  steps   단계: 번호 동그라미를 잇는 세로선                              (순서 · 방법)
  compare 비교: 왼쪽(✕) · 오른쪽(○) 두 칸                               (left · right 를 주면)
  quote   한 문장: 큰 따옴표 + 굵은 문장                                 (quote 를 주면)
디자인 스타일(style) 4가지 — 같은 색 테마라도 모양이 완전히 다르다: clean(깔끔) · bold(강렬) · gradient(그라데이션) ·
pastel(파스텔). 색은 발표 자료(office.py)와 같은 색 테마 11가지.
카드마다 아이콘(icons.py — Material Icons Round)을 넣고, 글꼴은 저장소에 넣어 둔 Pretendard (없으면 맑은 고딕).
글은 상자에 맞게 크기를 줄이고 줄을 바꾼다 (한국어는 띄어쓰기 단위로). 두 배 크기로 그린 뒤 줄여 가장자리를 매끄럽게 한다.
이 파일은 그림만 만든다 (저장 폴더 · 열기는 tools.py).
"""
from __future__ import annotations

import os
import re
import shutil
import urllib.parse
from pathlib import Path

from . import icons
from .office import THEMES, Theme, _strings, _text

SS = 2                                  # 두 배로 그려서 줄인다 (도형 가장자리를 매끄럽게)
CARD = 1080
A4 = (1240, 1754)                       # 150dpi A4 세로
MAX_CARDS = 12
M = 88                                  # 카드 바깥 여백

STYLES = ("clean", "bold", "gradient", "pastel")
STYLE_NAMES = {"clean": "깔끔", "bold": "강렬", "gradient": "그라데이션", "pastel": "파스텔"}
LAYOUTS = ("point", "list", "stat", "steps", "compare", "quote")

_ROOT = Path(__file__).resolve().parent.parent
_OWN = _ROOT / "assets" / "fonts"
_WIN = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
_NANUM = Path("/usr/share/fonts/truetype/nanum")
_FONTS = {
    "black": [_OWN / "Pretendard-Black.otf", _WIN / "malgunbd.ttf", _NANUM / "NanumGothicExtraBold.ttf",
              _NANUM / "NanumSquareEB.ttf"],
    "extrabold": [_OWN / "Pretendard-ExtraBold.otf", _WIN / "malgunbd.ttf", _NANUM / "NanumGothicExtraBold.ttf",
                  _NANUM / "NanumSquareEB.ttf"],
    "bold": [_OWN / "Pretendard-ExtraBold.otf", _WIN / "malgunbd.ttf", _NANUM / "NanumGothicBold.ttf",
             _NANUM / "NanumSquareB.ttf", _NANUM / "NanumBarunGothicBold.ttf"],
    "semibold": [_OWN / "Pretendard-SemiBold.otf", _WIN / "malgunbd.ttf", _NANUM / "NanumGothicBold.ttf",
                 _NANUM / "NanumBarunGothicBold.ttf"],
    "regular": [_OWN / "Pretendard-Regular.otf", _WIN / "malgun.ttf", _NANUM / "NanumGothic.ttf",
                _NANUM / "NanumSquareR.ttf", _NANUM / "NanumBarunGothic.ttf"],
}
_FALLBACK = {"black": ("black", "extrabold", "bold"), "extrabold": ("extrabold", "bold"), "bold": ("bold",),
             "semibold": ("semibold", "bold"), "regular": ("regular",)}
_CACHE: dict = {}


def font_file(weight: str = "regular") -> Path:
    """한글 글꼴 파일 (저장소의 Pretendard, 없으면 Windows 의 맑은 고딕). 없으면 ValueError."""
    for key in _FALLBACK.get(weight, (weight,)):
        for p in _FONTS.get(key, []):
            if p.exists():
                return p
    raise ValueError("한글 글꼴(맑은 고딕)을 찾지 못했습니다.")


def _font(weight: str, size: float):
    from PIL import ImageFont
    key = (weight, int(size))
    if key not in _CACHE:
        _CACHE[key] = ImageFont.truetype(str(font_file(weight)), max(1, int(size)))
    return _CACHE[key]


def _rgb(hex_: str) -> tuple[int, int, int]:
    return tuple(int(hex_[i:i + 2], 16) for i in (0, 2, 4))


def _mix(a, b, t: float) -> tuple[int, int, int]:
    ca = _rgb(a) if isinstance(a, str) else a
    cb = _rgb(b) if isinstance(b, str) else b
    return tuple(round(x + (y - x) * t) for x, y in zip(ca, cb))


def _alpha(c, a: float) -> tuple[int, int, int, int]:
    c = _rgb(c) if isinstance(c, str) else c
    return (*c[:3], max(0, min(255, round(a * 255))))


def _lum(c) -> float:
    c = _rgb(c) if isinstance(c, str) else c
    return (0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]) / 255


def _rel_lum(c) -> float:
    """눈으로 보는 밝기 (WCAG 상대 휘도)."""
    c = _rgb(c) if isinstance(c, str) else c
    lin = [(v / 255 / 12.92) if v / 255 <= 0.04045 else ((v / 255 + 0.055) / 1.055) ** 2.4 for v in c[:3]]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a, b) -> float:
    """두 색의 대비 (1 ~ 21). 큰 굵은 글씨는 3 이상, 보통 글씨는 4.5 이상이면 잘 읽힌다."""
    la, lb = _rel_lum(a), _rel_lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


# ---------------------------------------------------------------- 글 배치
def wrap(draw, text: str, font, width: float) -> list[str]:
    """띄어쓰기 단위로 줄을 바꾼다. 한 낱말이 너무 길면 글자 단위로 끊는다."""
    lines: list[str] = []
    for para in str(text).splitlines() or [""]:
        cur = ""
        for word in para.split(" "):
            trial = f"{cur} {word}".strip() if cur else word
            if draw.textlength(trial, font=font) <= width:
                cur = trial
                continue
            if cur:
                lines.append(cur)
            if draw.textlength(word, font=font) <= width:
                cur = word
                continue
            cur = ""
            for ch in word:
                if draw.textlength(cur + ch, font=font) <= width:
                    cur += ch
                else:
                    lines.append(cur)
                    cur = ch
        lines.append(cur)
    return [line for line in lines if line.strip()] or [""]


def balance(draw, text: str, font, width: float, lines: list[str]) -> list[str]:
    """줄 수는 그대로 두고 줄 길이를 고르게 — '2026 가을 과학 / 축제' 처럼 마지막 줄에 한 낱말만 남지 않게.
    같은 줄 수가 유지되는 가장 좁은 폭으로 다시 줄을 바꾼다."""
    n = len(lines)
    if n < 2:
        return lines
    lo, hi = width * 0.45, width
    for _ in range(14):
        mid = (lo + hi) / 2
        if len(wrap(draw, text, font, mid)) <= n:
            hi = mid
        else:
            lo = mid
    out = wrap(draw, text, font, hi)
    return out if len(out) == n else lines


def fit(draw, text: str, weight: str, width: float, height: float, big: float, small: float,
        gap: float = 1.25, max_lines: int | None = None, even: bool = False) -> tuple[object, list[str], float]:
    """상자에 들어가는 가장 큰 글자 → (글꼴, 줄들, 크기). 가장 작게 해도 넘치면 남는 줄을 '…' 로 줄인다.
    even=True 면 줄 길이를 고르게 나눈다 (큰 제목용)."""
    size = big
    while True:
        f = _font(weight, size)
        lines = wrap(draw, text, f, width)
        if (len(lines) * size * gap <= height and (max_lines is None or len(lines) <= max_lines)) or size <= small:
            break
        size = max(small, size * 0.92)
    keep = max(1, min(len(lines), int(height // (size * gap)), max_lines or 999))
    if keep < len(lines):
        lines = lines[:keep]
        while lines[-1] and draw.textlength(lines[-1] + "…", font=f) > width:
            lines[-1] = lines[-1][:-1]
        lines[-1] += "…"
    elif even:
        lines = balance(draw, text, f, width, lines)
    return f, lines, size


def text_block(draw, xy, lines, font, size, color, gap: float = 1.25, align: str = "left", width: float = 0) -> float:
    """줄들을 그린다 → 그린 높이."""
    x, y = xy
    for i, line in enumerate(lines):
        lx = x
        if align == "center":
            lx = x + (width - draw.textlength(line, font=font)) / 2
        elif align == "right":
            lx = x + width - draw.textlength(line, font=font)
        draw.text((lx, y + i * size * gap), line, font=font, fill=color)
    return len(lines) * size * gap


def _domain(ref: str) -> str:
    """출처 한 줄을 짧게: URL 이면 사이트 주소만, 아니면 앞부분만."""
    m = re.search(r"https?://\S+", ref)
    if m:
        host = urllib.parse.urlparse(m.group(0)).netloc.removeprefix("www.")
        head = ref[:m.start()].strip(" —-:|")
        return f"{head} ({host})" if head else host
    return ref[:60]


def _clean_item(s: str) -> str:
    """글머리 기호 · 번호는 지운다 (모양으로 그린다)."""
    return re.sub(r"^\s*(?:[•·▪*✓✔]\s*|[-–]\s+|\d{1,2}[.)]\s+)", "", str(s)).strip()


# ---------------------------------------------------------------- 그리기 도구 (1080 기준 좌표 → SS 배로 그린다)
class Pen:
    """좌표 · 크기는 결과물 기준(1080 카드 · A4 포스터)으로 받고, 실제로는 s 배로 그린다."""

    def __init__(self, w: int, h: int, color, s: float = SS) -> None:
        from PIL import Image, ImageDraw
        self.w, self.h, self.s = w, h, s
        self.img = Image.new("RGB", (round(w * s), round(h * s)), _rgb(color) if isinstance(color, str) else color)
        self.d = ImageDraw.Draw(self.img, "RGBA")          # 반투명 색을 겹쳐 칠할 수 있게

    def _b(self, box) -> tuple:
        return tuple(v * self.s for v in box)

    def rect(self, box, fill=None, r: float = 0, outline=None, width: float = 0) -> None:
        b = self._b(box)
        if r:
            self.d.rounded_rectangle(b, radius=r * self.s, fill=fill, outline=outline, width=round(width * self.s))
        else:
            self.d.rectangle(b, fill=fill, outline=outline, width=round(width * self.s))

    def circle(self, cx: float, cy: float, r: float, fill=None, outline=None, width: float = 0) -> None:
        self.d.ellipse(self._b((cx - r, cy - r, cx + r, cy + r)), fill=fill, outline=outline, width=round(width * self.s))

    def line(self, pts, fill, width: float) -> None:
        self.d.line([(x * self.s, y * self.s) for x, y in pts], fill=fill, width=round(width * self.s))

    def gradient(self, box, c1, c2, angle: str = "diag") -> None:
        """box 를 c1 → c2 로 물들인다 (diag: 왼쪽 위 → 오른쪽 아래, down: 위 → 아래). 처음 조금은 c1 그대로."""
        import numpy as np
        from PIL import Image
        x0, y0, x1, y1 = (round(v) for v in self._b(box))
        w, h = max(1, x1 - x0), max(1, y1 - y0)
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        t = (yy / h) if angle == "down" else (xx / w + yy / h) / 2
        t = np.clip(t * 1.08 - 0.04, 0, 1)[..., None]
        a, b = np.array(_rgb(c1) if isinstance(c1, str) else c1, np.float32), np.array(_rgb(c2) if isinstance(c2, str) else c2, np.float32)
        arr = (a + (b - a) * t).round().astype(np.uint8)
        self.img.paste(Image.fromarray(arr, "RGB"), (x0, y0))

    def shadow(self, box, r: float, blur: float = 22, alpha: float = 0.10, color=(0, 0, 0), dy: float = 10) -> None:
        """상자 아래 부드러운 그림자 (그 둘레만 흐리게 — 빠르다)."""
        from PIL import Image, ImageDraw, ImageFilter
        pad = blur * 2.2
        x0, y0, x1, y1 = box
        ox, oy = x0 - pad, y0 - pad + dy
        w, h = round((x1 - x0 + 2 * pad) * self.s), round((y1 - y0 + 2 * pad) * self.s)
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle((pad * self.s, pad * self.s, w - pad * self.s, h - pad * self.s),
                                               radius=r * self.s, fill=round(255 * alpha))
        mask = mask.filter(ImageFilter.GaussianBlur(blur * self.s / 2))
        self.img.paste(Image.new("RGB", (w, h), color), (round(ox * self.s), round(oy * self.s)), mask)

    def font(self, weight: str, size: float):
        return _font(weight, size * self.s)

    def fit(self, text: str, weight: str, width: float, height: float, big: float, small: float, gap: float = 1.25,
            max_lines: int | None = None, even: bool = False) -> tuple[object, list[str], float]:
        """fit 의 결과물 기준 판 → (글꼴, 줄들, 크기 — 결과물 기준)."""
        f, lines, size = fit(self.d, text, weight, width * self.s, height * self.s, big * self.s, small * self.s,
                             gap, max_lines, even)
        return f, lines, size / self.s

    def lines(self, x: float, y: float, lines, font, size: float, fill, gap: float = 1.25, align: str = "left",
              width: float = 0) -> float:
        """줄들을 그린다 → 그린 높이 (결과물 기준)."""
        if isinstance(fill, tuple) and len(fill) == 4 and fill[3] < 255:
            for i, line in enumerate(lines):
                lx = x * self.s
                lw = self.d.textlength(line, font=font)
                if align == "center":
                    lx += (width * self.s - lw) / 2
                elif align == "right":
                    lx += width * self.s - lw
                self._glyphs((lx, (y + i * size * gap) * self.s), line, font, fill, "la")
            return len(lines) * size * gap
        return text_block(self.d, (x * self.s, y * self.s), lines, font, size * self.s, fill, gap, align,
                          width * self.s) / self.s

    def _glyphs(self, xy, s: str, font, fill, anchor: str) -> None:
        """글자(또는 아이콘)를 그린다. 반투명 색이면 글자 모양을 가림판으로 만들어 그 비율만큼 칠한다."""
        if not (isinstance(fill, tuple) and len(fill) == 4 and fill[3] < 255):
            self.d.text(xy, s, font=font, fill=fill, anchor=anchor)
            return
        from PIL import Image, ImageDraw
        left, top, right, bottom = self.d.textbbox(xy, s, font=font, anchor=anchor)
        left, top, right, bottom = int(left) - 2, int(top) - 2, int(right) + 3, int(bottom) + 3
        if right <= left or bottom <= top:
            return
        mask = Image.new("L", (right - left, bottom - top), 0)
        ImageDraw.Draw(mask).text((xy[0] - left, xy[1] - top), s, font=font, fill=fill[3], anchor=anchor)
        self.img.paste(Image.new("RGB", mask.size, fill[:3]), (left, top), mask)

    def text(self, x: float, y: float, s: str, weight: str, size: float, fill, anchor: str = "la") -> None:
        self._glyphs((x * self.s, y * self.s), s, self.font(weight, size), fill, anchor)

    def length(self, s: str, weight: str, size: float) -> float:
        return self.d.textlength(s, font=self.font(weight, size)) / self.s

    def icon(self, name: str | None, cx: float, cy: float, size: float, fill) -> bool:
        cp = icons.codes().get(icons.normalize(name)) if name else None
        if cp is None or not icons.FONT.exists():
            return False
        self._glyphs((cx * self.s, cy * self.s), chr(cp), icons.font(round(size * self.s)), fill, "mm")
        return True

    def save(self, path: Path):
        return _save(self.img, self.w, self.h, path)


def _save(img, w: int, h: int, path: Path) -> object:
    """두 배로 그린 그림을 결과 크기로 줄여 PNG 로 저장한다 → 줄인 그림."""
    from PIL import Image
    if img.size == (w * SS, h * SS):
        out = img.reduce(SS)            # 정확히 절반: 상자 평균으로 줄인다 (LANCZOS 와 거의 같은 결과, 몇 배 빠름)
    else:
        out = img.resize((w, h), Image.LANCZOS)
    out.save(path, compress_level=3)    # 압축은 가볍게 (기본 6 보다 훨씬 빠르고 파일은 조금 큼 · optimize 는 쓰지 않음)
    return out


# ---------------------------------------------------------------- 색 묶음 (테마 × 스타일)
class Look:
    """한 카드뉴스의 색 · 모양. 테마(색)와 스타일(모양)에서 정한다."""

    def __init__(self, th: Theme, style: str) -> None:
        self.th, self.style = th, style
        self.accent = _rgb(th.accent)
        self.on_accent = _rgb(th.on_accent)
        self.dark_theme = _lum(th.bg) < 0.4
        self.deep = _mix(th.accent, "0B0B1A" if _lum(th.accent) > 0.35 else "000000", 0.38)   # 그라데이션 끝 · 짙은 강조
        # 그라데이션 두 끝: 밝은 강조색은 조금 눌러 흰 글씨가 읽히게. 그래도 밝으면(노랑 등) 어두운 글씨를 쓴다
        self.g1 = _mix(th.accent, "000000", 0.22 if _lum(th.accent) > 0.45 else 0.06)
        self.g2 = self.deep
        dark = _rgb(th.title) if _lum(th.title) < 0.3 else (17, 17, 17)
        white = (255, 255, 255)
        # 흰 글씨 · 어두운 글씨 중 그라데이션 양끝 어디서든 더 잘 읽히는 쪽 (노랑 같은 밝은 색은 어두운 글씨)
        worst = lambda ink: min(contrast(ink, self.g1), contrast(ink, self.g2))      # noqa: E731
        self.grad_light = worst(dark) > worst(white)
        if style == "gradient":
            self.bg = self.g1
            self.ink = dark if self.grad_light else white
            self.body = _mix(self.ink, self.g1, 0.12)
            self.muted = _mix(self.ink, self.g1, 0.28)
            self.panel = (*(white if not self.grad_light else dark), 34)
            self.chip = (*(white if not self.grad_light else dark), 40)
            self.mark, self.on_mark = self.ink, self.g1
            self.hi, self.on_hi = self.ink, self.g1
        elif style == "pastel":
            self.bg = _mix(th.soft, "FFFFFF", 0.45) if not self.dark_theme else _rgb(th.bg)
            self.ink, self.body, self.muted = _rgb(th.title), _rgb(th.text), _rgb(th.muted)
            self.panel = (255, 255, 255, 255) if not self.dark_theme else (*_rgb(th.surface), 255)
            self.chip = (*_rgb("FFFFFF" if not self.dark_theme else th.surface), 255)
            self.mark, self.on_mark = self.accent, self.on_accent
            self.hi, self.on_hi = self.accent, self.on_accent
        else:                                   # clean · bold
            self.bg, self.ink, self.body, self.muted = _rgb(th.bg), _rgb(th.title), _rgb(th.text), _rgb(th.muted)
            self.panel = (*_rgb(th.surface), 255)
            self.chip = (*_rgb(th.surface), 255)
            self.mark, self.on_mark = self.accent, self.on_accent
            self.hi, self.on_hi = self.accent, self.on_accent


# ---------------------------------------------------------------- 카드 틀 (머리 · 꼬리 · 배경)
def _frame(look: Look, n: int, total: int, brand: str) -> tuple[Pen, tuple[float, float, float, float]]:
    """내용 카드의 바탕 → (펜, 내용을 놓을 상자)."""
    th, st = look.th, look.style
    p = Pen(CARD, CARD, look.bg)
    if st == "gradient":
        p.gradient((0, 0, CARD, CARD), look.g1, look.g2)
        p.circle(CARD + 40, -30, 330, outline=(*look.ink, 30), width=2)
        p.circle(CARD + 40, -30, 250, outline=(*look.ink, 22), width=2)
        p.circle(-60, CARD + 60, 260, fill=(*look.ink, 14))
    elif st == "pastel":
        p.circle(CARD - 70, 90, 180, fill=_alpha(th.accent, 0.10))
        p.circle(60, CARD - 40, 150, fill=_alpha(th.soft, 0.9 if not look.dark_theme else 0.35))
        for i in range(5):
            for j in range(4):
                p.circle(820 + i * 26, 900 + j * 26, 3.4, fill=_alpha(th.accent, 0.22))
    elif st == "bold":
        p.rect((0, 0, CARD, 136), fill=look.accent)
        p.text(CARD - 34, CARD - 26, f"{n:02d}", "black", 300, _alpha(th.accent, 0.07), anchor="rd")
    else:                                       # clean
        p.circle(CARD - 50, 30, 230, fill=(*_rgb(th.surface), 255))
    # 머리: 이름표 · 쪽 번호
    tag = (brand or "")[:24]
    head_ink = look.on_accent if st == "bold" else (look.ink if st == "gradient" else look.muted)
    if tag:
        tw = p.length(tag, "semibold", 26)
        chip = _alpha(look.on_accent, 0.18) if st == "bold" else look.chip
        p.rect((M, 43, M + tw + 48, 93), fill=chip, r=25) if st == "bold" else p.rect((M, 60, M + tw + 48, 110), fill=chip, r=25)
        p.text(M + 24, 68 if st == "bold" else 85, tag, "semibold", 26, head_ink, anchor="lm")
    page = f"{n + 1:02d} / {total:02d}"
    p.text(CARD - M, 68 if st == "bold" else 85, page, "semibold", 26, head_ink, anchor="rm")
    # 꼬리: 진행 막대
    track = (*look.ink, 60) if st == "gradient" else _alpha(th.soft, 0.9 if not look.dark_theme else 0.6)
    p.rect((M, 1010, CARD - M, 1016), fill=track, r=3)
    done = M + (CARD - 2 * M) * (n + 1) / max(1, total)
    p.rect((M, 1010, done, 1016), fill=look.hi, r=3)
    return p, (M, 150, CARD - M, 975)


def _badge(p: Pen, look: Look, name: str | None, cx: float, cy: float, r: float) -> None:
    """아이콘 동그라미."""
    if look.style == "gradient":
        p.circle(cx, cy, r, fill=(*look.ink, 38))
        p.icon(name, cx, cy, r * 1.12, look.ink)
    elif look.style == "pastel":
        p.shadow((cx - r, cy - r, cx + r, cy + r), r, blur=16, alpha=0.10, dy=8)
        p.circle(cx, cy, r, fill=(255, 255, 255) if not look.dark_theme else _rgb(look.th.surface))
        p.icon(name, cx, cy, r * 1.08, look.accent)
    else:
        p.circle(cx, cy, r, fill=look.mark)
        p.icon(name, cx, cy, r * 1.12, look.on_mark)


def _highlight(p: Pen, look: Look, text: str, top: float, bottom: float, x0: float = M, x1: float = CARD - M) -> float:
    """강조 한 줄 (아래쪽 상자) → 쓴 높이. top 에서 시작하고 bottom 을 넘지 않는다."""
    f, lines, size = p.fit(text, "semibold", x1 - x0 - 128, max(40, min(150, bottom - top) - 40), 40, 26, gap=1.3,
                           max_lines=2)
    h = max(96, len(lines) * size * 1.3 + 46)
    box = (x0, top, x1, top + h)
    if look.style == "gradient":
        p.rect(box, fill=(*look.ink, 235), r=26)
        ink, mark = look.on_hi, look.on_hi
    elif look.style == "pastel":
        p.shadow(box, 26, blur=16, alpha=0.08, dy=6)
        p.rect(box, fill=look.accent, r=26)
        ink, mark = look.on_accent, look.on_accent
    else:
        p.rect(box, fill=look.accent, r=26)
        ink, mark = look.on_accent, look.on_accent
    p.icon("check_circle", x0 + 52, top + h / 2, 44, mark)
    p.lines(x0 + 92, top + (h - len(lines) * size * 1.3) / 2 + size * 0.08, lines, f, size, ink, gap=1.3)
    return h


# ---------------------------------------------------------------- 내용 카드 모양
def _point(p: Pen, look: Look, box, c: dict, icon: str | None, variant: int) -> None:
    """핵심 한 가지: 큰 아이콘 + 굵은 제목 + 짧은 설명 (+ 강조)."""
    x0, y0, x1, y1 = box
    w = x1 - x0
    centered = variant % 2 == 1
    body = [_clean_item(b) for b in c["items"]]
    roomy = not c["highlight"] and len(body) <= 2
    tf, tl, ts = p.fit(c["title"], "bold", w, 320, 92 if roomy else 82, 52, gap=1.2, max_lines=3, even=True)
    bf = bl = None
    bs = 0.0
    if body:
        bf, bl, bs = p.fit("\n".join(body), "regular", w, 280, 46 if roomy else 44, 30, gap=1.5, max_lines=6)
    hl_h = 120 if c["highlight"] else 0
    icon_h = 168
    total = icon_h + 44 + len(tl) * ts * 1.2 + (36 + len(bl) * bs * 1.5 if body else 0) + (52 + hl_h if hl_h else 0)
    y = y0 + max(10, (y1 - y0 - total) / 2)
    cx = CARD / 2 if centered else x0 + 84
    _badge(p, look, icon, cx, y + 84, 84)
    y += icon_h + 44
    align = "center" if centered else "left"
    y += p.lines(x0, y, tl, tf, ts, look.ink, gap=1.2, align=align, width=w)
    if body:
        y += 36
        p.rect((CARD / 2 - 30, y - 18, CARD / 2 + 30, y - 12) if centered else (x0, y - 18, x0 + 60, y - 12),
               fill=look.hi, r=3)
        y += p.lines(x0, y, bl, bf, bs, look.body, gap=1.5, align=align, width=w)
    if c["highlight"]:
        _highlight(p, look, c["highlight"], min(y + 52, y1 - hl_h), y1)


def _list(p: Pen, look: Look, box, c: dict, icon: str | None, numbered: bool = True) -> None:
    """목록: 제목 줄 + 번호 붙은 줄 상자들이 카드를 채운다."""
    x0, y0, x1, y1 = box
    w = x1 - x0
    _badge(p, look, icon, x0 + 46, y0 + 56, 46)
    tf, tl, ts = p.fit(c["title"], "bold", w - 120, 150, 64, 42, gap=1.2, max_lines=2, even=True)
    th_h = len(tl) * ts * 1.2
    p.lines(x0 + 120, y0 + 56 - th_h / 2, tl, tf, ts, look.ink, gap=1.2)
    top = y0 + max(112, th_h) + 40
    bottom = y1 - (150 if c["highlight"] else 0)
    items = [_clean_item(b) for b in c["items"]][:7]
    n = len(items)
    gap = 18
    # 글자 크기: 모든 줄이 상자 안에 들어가는 가장 큰 크기
    size = 40
    while True:
        f = p.font("semibold", size)
        rows = [wrap(p.d, it, f, (w - 128) * p.s) for it in items]
        need = sum(max(1, len(r)) * size * 1.38 + 52 for r in rows) + gap * (n - 1)
        if need <= bottom - top or size <= 26:
            break
        size -= 2
    heights = [max(1, len(r)) * size * 1.38 + 52 for r in rows]
    spare = (bottom - top) - sum(heights) - gap * (n - 1)
    pad = min(30, max(0, spare / max(1, n) / 2))        # 남는 자리는 줄 상자를 조금씩 키워 채운다 (아래가 텅 비지 않게)
    y = top + max(0, spare - pad * 2 * n) / 2
    for i, (lines, h) in enumerate(zip(rows, heights)):
        h += pad * 2
        if y + h > bottom + 1:
            break
        rb = (x0, y, x1, y + h)
        if look.style == "pastel":
            p.shadow(rb, 22, blur=14, alpha=0.07, dy=6)
        p.rect(rb, fill=look.panel, r=22)
        cy = y + h / 2
        if numbered:
            p.circle(x0 + 50, cy, 26, fill=look.hi)
            p.text(x0 + 50, cy, str(i + 1), "bold", 26, look.on_hi,
                   anchor="mm")
        else:
            p.icon("check_circle", x0 + 50, cy, 46, look.hi)
        p.lines(x0 + 96, cy - len(lines) * size * 1.38 / 2 + size * 0.1, lines, f, size, look.ink, gap=1.38)
        y += h + gap
    if c["highlight"]:
        _highlight(p, look, c["highlight"], y1 - 118, y1)


def _split_stat(value: str) -> tuple[str, str]:
    """'6시간' → ('6', '시간') · '70%' → ('70', '%') · '10명 중 7명' → ('10명 중 7명', '')."""
    m = re.fullmatch(r"\s*([~약]?\s*[+-]?[\d][\d,.]*)\s*([^\d\s][^\d]{0,5})?\s*", value)
    if m:
        return m.group(1).strip(), (m.group(2) or "").strip()
    return value.strip(), ""


def _stat(p: Pen, look: Look, box, c: dict, icon: str | None) -> None:
    """큰 숫자: 제목 → 카드 가득 큰 숫자 → 설명."""
    x0, y0, x1, y1 = box
    w = x1 - x0
    stat = c["stat"]
    value, label = (stat.get("value"), stat.get("label")) if isinstance(stat, dict) else (stat, "")
    num, unit = _split_stat(_text(value))
    label = _text(label)
    tf, tl, ts = p.fit(c["title"], "bold", w - 130, 150, 60, 40, gap=1.2, max_lines=2, even=True)
    # 숫자 크기: 폭에 맞는 가장 큰 크기
    size = 300
    while size > 110:
        nw = p.length(num, "black", size) + (p.length(unit, "extrabold", size * 0.4) + 14 if unit else 0)
        if nw <= w:
            break
        size -= 8
    body = [_clean_item(b) for b in c["items"]]
    bf, bl, bs = p.fit("\n".join(body), "regular", w, 170, 38, 28, gap=1.45, max_lines=4) if body else (None, [], 0.0)
    lab_h = 54 if label else 0
    total = len(tl) * ts * 1.2 + 26 + size * 0.98 + lab_h + (30 + len(bl) * bs * 1.45 if bl else 0) + \
        (40 + 110 if c["highlight"] else 0)
    y = y0 + max(0, (y1 - y0 - total) / 2)
    _badge(p, look, icon, x1 - 52, y + len(tl) * ts * 1.2 / 2, 52)
    y += p.lines(x0, y, tl, tf, ts, look.ink, gap=1.2) + 26
    numc = look.hi
    base = y + size * 0.86                       # 숫자의 글자 밑선
    p.text(x0 - size * 0.04, base, num, "black", size, numc, anchor="ls")
    if unit:
        p.text(x0 + p.length(num, "black", size) + 10, base, unit, "extrabold", size * 0.4, numc, anchor="ls")
    y += size * 0.98
    if label:
        p.text(x0, y + 4, label, "semibold", 36, look.muted, anchor="la")
        y += lab_h
    if bl:
        y += 30
        y += p.lines(x0, y, bl, bf, bs, look.body, gap=1.45)
    if c["highlight"]:
        _highlight(p, look, c["highlight"], min(y + 40, y1 - 110), y1)


def _steps(p: Pen, look: Look, box, c: dict, icon: str | None) -> None:
    """단계: 번호 동그라미를 잇는 세로선 + 단계마다 굵은 앞부분 · 설명."""
    x0, y0, x1, y1 = box
    w = x1 - x0
    _badge(p, look, icon, x0 + 46, y0 + 56, 46)
    tf, tl, ts = p.fit(c["title"], "bold", w - 120, 150, 64, 42, gap=1.2, max_lines=2, even=True)
    th_h = len(tl) * ts * 1.2
    p.lines(x0 + 120, y0 + 56 - th_h / 2, tl, tf, ts, look.ink, gap=1.2)
    top = y0 + max(112, th_h) + 50
    bottom = y1 - (140 if c["highlight"] else 0)
    steps = []
    for raw in [_clean_item(b) for b in c["items"]][:6]:
        head, _, rest = raw.partition(":") if ":" in raw[:24] else (raw, "", "")
        steps.append((head.strip(), rest.strip()))
    n = max(1, len(steps))
    slot = (bottom - top) / n
    hs = min(48, max(28, slot * 0.30))
    line_c = _alpha(look.th.soft, 0.9) if look.style != "gradient" else _alpha(look.ink, 0.35)
    cx = x0 + 34
    p.line([(cx, top + 34), (cx, top + slot * (n - 1) + 34)], line_c, 6)
    for i, (head, rest) in enumerate(steps):
        y = top + i * slot
        p.circle(cx, y + 34, 34, fill=look.hi)
        p.text(cx, y + 34, str(i + 1), "bold", 30, look.on_hi, anchor="mm")
        hf, hl, hsz = p.fit(head, "bold", w - 100, slot * 0.5, hs, 26, gap=1.2, max_lines=2)
        used = p.lines(x0 + 100, y + 34 - hsz * 0.66, hl, hf, hsz, look.ink, gap=1.2)
        if rest:
            rf, rl, rsz = p.fit(rest, "regular", w - 100, max(30, slot - used - 20), hs * 0.82, 24, gap=1.4, max_lines=2)
            p.lines(x0 + 100, y + 34 - hsz * 0.66 + used + 6, rl, rf, rsz, look.body, gap=1.4)
    if c["highlight"]:
        _highlight(p, look, c["highlight"], y1 - 112, y1)


def _compare(p: Pen, look: Look, box, c: dict, icon: str | None) -> None:
    """비교: 왼쪽(✕, 흐린 색) · 오른쪽(○, 강조색) 두 칸."""
    x0, y0, x1, y1 = box
    w = x1 - x0
    tf, tl, ts = p.fit(c["title"], "bold", w, 150, 66, 42, gap=1.2, max_lines=2, even=True)
    title_h = len(tl) * ts * 1.2
    gap = 26
    cw = (w - gap) / 2
    hl_room = 140 if c["highlight"] else 0
    room = y1 - y0 - title_h - 50 - hl_room             # 두 칸이 쓸 수 있는 높이
    # 두 칸의 글: 같은 크기로 (칸마다 다르면 어색하다). 들어가는 가장 큰 크기
    sides = []
    for k, side in enumerate((c["left"], c["right"])):
        head = _text(side.get("title")) or ("이렇게" if k else "이건 아니에요")
        sides.append((head, [_clean_item(b) for b in _strings(side.get("bullets") or side.get("text"))]))
    size = 40
    while True:
        bf = p.font("regular", size)
        hf = p.font("bold", size * 1.18)
        need = 0.0
        laid = []
        for head, items in sides:
            hl = wrap(p.d, head, hf, (cw - 60) * p.s)[:2]
            rows = [ln for it in items for ln in wrap(p.d, it, bf, (cw - 64) * p.s)]
            h = 150 + len(hl) * size * 1.18 * 1.2 + 22 + len(rows) * size * 1.5 + 40
            laid.append((hl, rows))
            need = max(need, h)
        if need <= room or size <= 24:
            break
        size -= 2
    col_h = min(room, max(need, room * 0.62))
    y = y0 + max(0, (y1 - y0 - hl_room - (title_h + 50 + col_h)) / 2)
    p.lines(x0, y, tl, tf, ts, look.ink, gap=1.2, align="center", width=w)
    y += title_h + 50
    for k, (hl, rows) in enumerate(laid):
        cx0 = x0 + k * (cw + gap)
        good = k == 1
        cb = (cx0, y, cx0 + cw, y + col_h)
        if look.style == "pastel":
            p.shadow(cb, 26, blur=16, alpha=0.08, dy=8)
        p.rect(cb, fill=(look.accent if look.style != "gradient" else (*look.ink, 235)) if good else look.panel, r=26)
        ink = look.on_hi if good else look.ink
        sub = ink if good else look.body
        content = 150 + len(hl) * size * 1.18 * 1.2 + 22 + len(rows) * size * 1.5
        cy = y + max(0, (col_h - content) / 2)
        p.circle(cx0 + cw / 2, cy + 64, 44, fill=_alpha(ink, 0.18) if good else _alpha(look.muted, 0.20))
        p.icon("check" if good else "close", cx0 + cw / 2, cy + 64, 56, ink)
        hy = cy + 136
        hy += p.lines(cx0 + 30, hy, hl, hf, size * 1.18, ink, gap=1.2, align="center", width=cw - 60) + 22
        p.lines(cx0 + 32, hy, rows, bf, size, sub, gap=1.5, align="center", width=cw - 64)
    if c["highlight"]:
        _highlight(p, look, c["highlight"], y + col_h + 28, y1)


def _quote(p: Pen, look: Look, box, c: dict, icon: str | None) -> None:
    """한 문장: 큰 따옴표 + 굵은 문장 + 말한 사람."""
    x0, y0, x1, y1 = box
    w = x1 - x0
    text = c["quote"] or c["title"]
    who = _text(c["items"][0]) if c["items"] else (c["title"] if c["quote"] else "")
    qf, ql, qs = p.fit(text, "bold", w - 20, 500, 84, 44, gap=1.32, max_lines=6, even=True)
    total = 150 + len(ql) * qs * 1.32 + (90 if who else 0)
    y = y0 + max(0, (y1 - y0 - total) / 2)
    p.icon("format_quote", x0 + 70, y + 60, 170, look.hi)
    y += 150
    y += p.lines(x0, y, ql, qf, qs, look.ink, gap=1.32)
    if who:
        p.rect((x0, y + 40, x0 + 46, y + 45), fill=look.hi, r=2)
        p.text(x0 + 64, y + 42, who[:40], "semibold", 34, look.muted, anchor="lm")


# ---------------------------------------------------------------- 표지 · 마무리
def _cover(look: Look, title: str, tag: str, total: int, icon: str | None) -> Pen:
    th, st = look.th, look.style
    pastel = st == "pastel"
    p = Pen(CARD, CARD, look.bg if pastel else look.accent)
    if st == "gradient":
        p.gradient((0, 0, CARD, CARD), look.g1, look.g2)
    elif st == "bold":
        p.gradient((0, 0, CARD, CARD), look.accent, _mix(th.accent, "000000", 0.18))
    ink = look.ink if st in ("pastel", "gradient") else look.on_accent
    on = _rgb(th.accent) if pastel else ink               # 장식 · 큰 아이콘의 색
    soft = _alpha(on, 0.12 if pastel else 0.10)
    # 큰 아이콘 장식 (오른쪽 아래, 반쯤 걸치게)
    p.circle(820, 840, 330, fill=soft)
    p.circle(820, 840, 230, fill=_alpha(on, 0.16 if pastel else 0.12))
    p.icon(icon, 820, 840, 250, _alpha(on, 0.9 if pastel else 0.95))
    p.circle(990, 170, 26, fill=_alpha(on, 0.5 if pastel else 0.35))
    p.circle(930, 250, 10, fill=_alpha(on, 0.45 if pastel else 0.3))
    if st == "bold":
        p.rect((M, 92, M + 120, 104), fill=ink)
    y = 140 if st == "bold" else 96
    if tag:
        tw = p.length(tag, "semibold", 30)
        if pastel:
            p.rect((M, y, M + tw + 60, y + 62), fill=look.accent, r=31)
            p.text(M + 30, y + 31, tag, "semibold", 30, look.on_accent, anchor="lm")
        else:
            p.rect((M, y, M + tw + 60, y + 62), outline=ink, width=3, r=31)
            p.text(M + 30, y + 31, tag, "semibold", 30, ink, anchor="lm")
    big = 132 if st == "bold" else 118
    f, lines, size = p.fit(title, "black", 860, 520, big, 66, gap=1.16, max_lines=4, even=True)
    h = len(lines) * size * 1.16
    top = 230 + max(0, (480 - h) / 2) * 0.6
    p.lines(M, top, lines, f, size, ink, gap=1.16)
    # 아래: 넘겨 보세요 · 장 표시 점
    p.text(M, 962, "옆으로 넘겨 보세요", "semibold", 28, _alpha(ink, 0.85), anchor="lm")
    p.icon("arrow_forward", M + p.length("옆으로 넘겨 보세요", "semibold", 28) + 30, 963, 34, _alpha(ink, 0.85))
    for i in range(min(total, 10)):
        r = 7 if i == 0 else 5
        p.circle(M + i * 22 + 2, 1010, r, fill=_alpha(ink, 0.95 if i == 0 else 0.38))
    return p


def _closing(look: Look, message: str, lines: list[str], refs: list[str], total: int, brand: str) -> Pen:
    th, st = look.th, look.style
    if st in ("gradient",):
        p = Pen(CARD, CARD, look.g2)
        p.gradient((0, 0, CARD, CARD), look.g2, look.g1)
        ink, body, muted, accent = look.ink, look.body, look.muted, look.ink
    elif st == "pastel":
        p = Pen(CARD, CARD, look.bg)
        ink, body, muted, accent = look.ink, look.body, look.muted, look.accent
    else:
        p = Pen(CARD, CARD, _rgb(th.surface))
        ink, body, muted, accent = _rgb(th.title), _rgb(th.text), _rgb(th.muted), look.accent
    p.circle(-80, CARD + 40, 300, fill=_alpha(th.accent, 0.10) if st != "gradient" else (*look.ink, 16))
    p.circle(CARD + 30, -30, 220, fill=_alpha(th.accent, 0.08) if st != "gradient" else (*look.ink, 14))
    mf, ml, ms = p.fit(message or "감사합니다", "black", 880, 290, 90, 50, gap=1.2, max_lines=3, even=True)
    sub = " ".join(lines)
    sf = sl = None
    ss = 0.0
    if sub:
        sf, sl, ss = p.fit(sub, "regular", 840, 130, 38, 26, gap=1.42, max_lines=3, even=True)
    block = 150 + len(ml) * ms * 1.2 + (28 + len(sl) * ss * 1.42 if sl else 0) + 170
    y = max(150, (CARD - 130 - block) / 2 + 40)
    p.circle(CARD / 2, y + 56, 56, fill=accent if st != "gradient" else (*look.ink, 50))
    p.icon("favorite", CARD / 2, y + 58, 60, look.on_accent if st != "gradient" else look.ink)
    y += 150
    y += p.lines(M, y, ml, mf, ms, ink, gap=1.2, align="center", width=CARD - 2 * M)
    if sl:
        y += 28
        y += p.lines(M + 20, y, sl, sf, ss, body, gap=1.42, align="center", width=CARD - 2 * M - 40)
    # 저장 · 공유 · 좋아요 (SNS 카드뉴스의 마무리)
    y += 60
    acts = (("bookmark", "저장"), ("share", "공유"), ("thumb_up", "좋아요"))
    for i, (ic, word) in enumerate(acts):
        cx = CARD / 2 + (i - 1) * 170
        p.circle(cx, y + 40, 40, outline=_alpha(accent, 0.85), width=3)
        p.icon(ic, cx, y + 40, 40, accent)
        p.text(cx, y + 104, word, "semibold", 24, muted, anchor="mm")
    if refs:
        line = "출처  " + "  ·  ".join(_domain(r) for r in refs[:3])
        rf, rl, rs = p.fit(line, "regular", CARD - 2 * M, 70, 20, 16, gap=1.35, max_lines=2)
        p.lines(M, 1008 - len(rl) * rs * 1.35, rl, rf, rs, muted, gap=1.35)
    elif brand:
        p.text(CARD / 2, 1000, brand[:40], "semibold", 24, muted, anchor="mm")
    return p


# ---------------------------------------------------------------- 카드 한 장의 내용 정리 · 모양 고르기
def _card_data(c, i: int) -> dict:
    c = c if isinstance(c, dict) else {"title": str(c)}
    items = [s for s in _strings(c.get("bullets") or c.get("text") or c.get("items")) if _clean_item(s)]
    left, right = c.get("left"), c.get("right")
    pair = c.get("compare")
    if isinstance(pair, list) and len(pair) >= 2 and not (left or right):
        left, right = pair[0], pair[1]
    return {"title": _text(c.get("title")) or f"{i}", "items": items, "highlight": _text(c.get("highlight")),
            "stat": c.get("stat"), "quote": _text(c.get("quote")), "layout": str(c.get("layout") or "").strip().lower(),
            "icon": c.get("icon"),
            "left": left if isinstance(left, dict) else ({"bullets": left} if left else None),
            "right": right if isinstance(right, dict) else ({"bullets": right} if right else None)}


_UNIT = r"(?:%|퍼센트|배|명|시간|분|초|원|만\s*원|억\s*원|만|억|개|년|살|세|회|번|kg|km|cm|mm|도|℃|위|점|곳|권|잔|kcal|칼로리)"
_STAT_END = re.compile(r"^(?P<head>.*?\S)\s+(?P<num>[약~]?\s*\d[\d,.]*\s*" + _UNIT + r")\s*[!?.]?$")


def auto_stat(c: dict) -> bool:
    """제목이 '…평균 수면 6시간' 처럼 숫자 + 단위로 끝나고 숫자가 그것 하나뿐이며 글이 2줄 이하면 큰 숫자 카드로 바꾼다
    (제목에서 그 숫자는 떼어 크게 보여 준다). 바꿨으면 True."""
    if c["stat"] or c["layout"] not in ("", "stat") or len(c["items"]) > 2:
        return False
    m = _STAT_END.match(c["title"])
    if not m or len(re.findall(r"\d", m.group("head"))) > 0:
        return False
    c["stat"] = m.group("num").replace(" ", "")
    c["title"] = m.group("head")
    return True


def choose_layout(c: dict, prev: str = "") -> str:
    """카드 모양 고르기: 준 layout(쓸 수 있으면) → 준 내용(stat · 비교 · 인용) → 글 줄 수."""
    lay = c["layout"]
    if lay == "stat" and not c["stat"]:
        lay = ""
    if lay == "compare" and not (c["left"] and c["right"]):
        lay = ""
    if lay in LAYOUTS:
        return lay
    if c["stat"]:
        return "stat"
    if c["left"] and c["right"]:
        return "compare"
    if c["quote"]:
        return "quote"
    n = len(c["items"])
    if n >= 3 and re.search(r"단계|순서|방법|하는\s*법|절차|과정", c["title"]):
        return "steps"
    if n >= 3:
        return "list"
    return "point"


def _draw_card(look: Look, n: int, total: int, c: dict, brand: str, layout: str, variant: int,
               used: set | None = None) -> Pen:
    p, box = _frame(look, n, total, brand)
    texts = (c["title"], c["highlight"], " ".join(c["items"]), c["quote"])
    icon = icons.pick(c["icon"], *texts, kind=layout, avoid=used or ())
    if used is not None and icon:
        used.add(icon)
    if layout == "stat":
        _stat(p, look, box, c, icon)
    elif layout == "list":
        _list(p, look, box, c, icon, numbered=not re.search(r"체크|점검|확인|준비물", c["title"]))
    elif layout == "steps":
        _steps(p, look, box, c, icon)
    elif layout == "compare":
        _compare(p, look, box, c, icon)
    elif layout == "quote":
        _quote(p, look, box, c, icon)
    else:
        _point(p, look, box, c, icon, variant)
    return p


def _style_of(style: str | None, theme: str) -> str:
    s = str(style or "").strip().lower()
    for key, name in STYLE_NAMES.items():               # '파스텔' 처럼 한국어로 와도
        if s == name:
            s = key
    return s if s in STYLES else "clean"


def build_cardnews(folder: Path, title: str, cards: list, subtitle: str = "", closing: str = "",
                   sources=None, theme: str = "light", style: str = "", icon: str = "") -> dict:
    """카드뉴스를 만든다 → {'cards': 장 수, 'pdf': PDF 경로, 'files': 그림 경로들, 'layouts': 카드 모양들, 'style': 스타일}."""
    title = _text(title)
    if not title:
        raise ValueError("카드뉴스 제목(title)이 필요합니다.")
    if not isinstance(cards, list) or not cards:
        raise ValueError("내용 카드(cards)가 하나 이상 필요합니다.")
    if len(cards) > MAX_CARDS:
        raise ValueError(f"카드가 너무 많습니다 ({len(cards)}장). 내용 카드는 {MAX_CARDS}장 이하로 만드세요.")
    tkey = (theme or "light").strip().lower()
    th = THEMES.get(tkey, THEMES["light"])
    sty = _style_of(style, tkey)
    look = Look(th, sty)
    folder = Path(folder)
    if folder.exists():
        shutil.rmtree(folder)                    # 고쳐 만들 때 (overwrite) 예전 장이 남지 않게
    folder.mkdir(parents=True)
    refs = [_text(r) for r in _strings(sources)]
    tag = _text(subtitle)
    data = [_card_data(c, i) for i, c in enumerate(cards, 1)]
    total = len(data) + 2
    cover_icon = icons.pick(icon, title, tag, *(d["title"] for d in data), kind="cover")
    pens = [_cover(look, title, tag, total, cover_icon)]
    layouts, prev, streak = [], "", 0
    used = {cover_icon} if cover_icon else set()        # 카드마다 다른 아이콘 (표지와도 되도록 다르게)
    for i, c in enumerate(data, 1):
        auto_stat(c)
        lay = choose_layout(c, prev)
        streak = streak + 1 if lay == prev else 0
        pens.append(_draw_card(look, i, total, c, tag or title, lay, streak, used))
        layouts.append(lay)
        prev = lay
    end = closing if isinstance(closing, str) else ""
    first, *rest = (end.splitlines() or ["감사합니다"]) if end.strip() else ["감사합니다"]
    pens.append(_closing(look, _text(first), [_text(x) for x in rest if x.strip()], refs, total, tag or title))
    files = [folder / f"{i:02d}.png" for i in range(1, len(pens) + 1)]
    from concurrent.futures import ThreadPoolExecutor      # 줄이기 · PNG 저장은 여러 장을 동시에 (Pillow 가 그동안 GIL 을 놓는다)
    with ThreadPoolExecutor(max_workers=min(4, len(pens))) as pool:
        saved = list(pool.map(lambda pair: pair[0].save(pair[1]), zip(pens, files)))
    pdf = folder / f"{folder.name}.pdf"
    saved[0].save(pdf, save_all=True, append_images=saved[1:], resolution=150)
    return {"cards": len(files), "pdf": pdf, "files": files, "layouts": layouts, "style": sty}


# ---------------------------------------------------------------- 포스터
def _info_parts(text: str) -> list[str]:
    """'10월 17일(토) 오전 10시 ~ 오후 4시 · 본관 체육관' → 조각들 (일시 · 장소처럼 나눠 아이콘을 붙인다)."""
    parts = [x.strip() for x in re.split(r"\s+[·|/]\s+|\s*\|\s*", text) if x.strip()]
    return parts[:3] if 1 < len(parts) <= 3 else [text]


def build_poster(path: Path, title: str, sections: list, subtitle: str = "", highlight: str = "", footer: str = "",
                 sources=None, theme: str = "light", size: str = "a4", style: str = "", icon: str = "") -> dict:
    """포스터를 만든다 (PNG + 같은 이름의 PDF) → {'sections': 구역 수, 'pdf': PDF 경로, 'size': (가로, 세로)}."""
    title = _text(title)
    if not title:
        raise ValueError("포스터 제목(title)이 필요합니다.")
    secs = [s if isinstance(s, dict) else {"heading": "", "bullets": [str(s)]} for s in (sections or [])]
    if not secs and not _text(highlight):
        raise ValueError("포스터에 넣을 내용(sections)이 필요합니다.")
    if len(secs) > 6:
        raise ValueError("포스터 구역(sections)은 6개 이하로 만드세요.")
    th = THEMES.get((theme or "light").strip().lower(), THEMES["light"])
    sty = _style_of(style, theme)
    look = Look(th, sty)
    k = 1.4142 if str(size).lower() == "a3" else 1.0
    W, H = round(A4[0] * k), round(A4[1] * k)
    BW, BH = A4                                   # A4 기준 좌표로 그리고, A3 는 크게 (k 배) 그린다
    p = Pen(BW, BH, th.accent, s=SS * k)
    p.w, p.h = W, H                               # 저장 크기
    accent, on, ink, body, muted = look.accent, look.on_accent, _rgb(th.title), _rgb(th.text), _rgb(th.muted)
    # ---- 머리 (제목 · 큰 아이콘)
    head = 760
    p.gradient((0, 0, BW, head), th.accent, look.deep if sty != "pastel" else _mix(th.accent, th.soft, 0.4))
    p.circle(1020, 360, 330, fill=_alpha(th.on_accent, 0.10))
    p.circle(1020, 360, 225, fill=_alpha(th.on_accent, 0.12))
    hero = icons.pick(icon, title, _text(subtitle), _text(highlight), *(_text(s.get("heading")) for s in secs), kind="poster")
    p.icon(hero, 1020, 360, 250, _alpha(th.on_accent, 0.95))
    p.circle(80, head - 60, 120, fill=_alpha(th.on_accent, 0.06))
    p.circle(1160, 90, 18, fill=_alpha(th.on_accent, 0.4))
    f, lines, sz = p.fit(title, "black", 760, 380, 136, 70, gap=1.12, max_lines=3, even=True)
    block = len(lines) * sz * 1.12
    sub = _text(subtitle)
    if sub:
        sf, sl, ss = p.fit(sub, "regular", 740, 120, 40, 28, gap=1.38, max_lines=2, even=True)
        block += 34 + len(sl) * ss * 1.38
    top = 120 + max(0, (head - 220 - block) / 2)
    p.rect((100, top - 46, 190, top - 36), fill=_alpha(th.on_accent, 0.9), r=5)
    used = p.lines(100, top, lines, f, sz, on, gap=1.12)
    if sub:
        p.lines(100, top + used + 34, sl, sf, ss, _alpha(th.on_accent, 0.88), gap=1.38)
    # ---- 아래 바탕 → 핵심 정보 띠 (일시 · 장소처럼 조각마다 아이콘, 머리에 반쯤 걸친다)
    foot_top = BH - 170
    p.rect((0, head, BW, foot_top), fill=_rgb(th.bg))
    y = head + 50
    hl = _text(highlight)
    if hl:
        parts = _info_parts(hl)
        hb = (90, head - 90, BW - 90, head + 90)
        p.shadow(hb, 30, blur=24, alpha=0.14, dy=12)
        p.rect(hb, fill=(255, 255, 255) if not look.dark_theme else _rgb(th.surface), r=30)
        p.rect((90, head - 64, 104, head + 64), fill=accent, r=7)
        # 조각마다 한 줄에 들어갈 폭(글 + 아이콘 · 여백)을 먼저 주고, 남는 폭은 고르게 나눈다. 모자라면 글 길이 비율로
        need = [p.length(part, "bold", 34) + 112 for part in parts]
        full = BW - 240
        if sum(need) <= full:
            widths = [nd + (full - sum(need)) / len(parts) for nd in need]
        else:
            widths = [full * nd / sum(need) for nd in need]
        for i, part in enumerate(parts):
            x0 = 130 + sum(widths[:i])
            pw = widths[i]
            ic = icons.pick(None, part, kind="section") if len(parts) > 1 else "campaign"
            if len(parts) > 1 and i > 0:
                p.line([(x0 - 14, head - 48), (x0 - 14, head + 48)], _alpha(th.muted, 0.35), 2)
            p.circle(x0 + 34, head, 30, fill=_alpha(th.accent, 0.14))
            p.icon(ic, x0 + 34, head, 36, accent)
            pf, pl, ps = p.fit(part, "bold", pw - 100, 130, 42 if len(parts) == 1 else 34, 24, gap=1.25, max_lines=2,
                               even=True)
            p.lines(x0 + 80, head - len(pl) * ps * 1.25 / 2 + ps * 0.06, pl, pf, ps, ink, gap=1.25)
        y = head + 140
    # ---- 구역 (아이콘 동그라미 · 굵은 제목 · 점 목록)
    cols = 1 if len(secs) <= 2 else 2
    rows = max(1, -(-len(secs) // cols))
    gap = 30
    cw = (BW - 200 - gap * (cols - 1)) / cols
    ch = (foot_top - 50 - y - gap * (rows - 1)) / rows if secs else 0
    def _width(i: int) -> float:
        return BW - 200 if cols == 2 and i == len(secs) - 1 and len(secs) % 2 else cw

    def _fits(i: int, size_b: int) -> bool:
        items = [_clean_item(b) for b in _strings(secs[i].get("bullets") or secs[i].get("text"))]
        bf = p.font("regular", size_b)
        blocks = [wrap(p.d, it, bf, (_width(i) - 100) * p.s) for it in items]
        need = sum(len(b) for b in blocks) * size_b * 1.42 + max(0, len(items) - 1) * size_b * 0.5
        return need <= ch - 150
    common = 36                                      # 모든 구역이 같은 글씨 크기 (구역마다 다르면 어색하다)
    while common > 22 and not all(_fits(i, common) for i in range(len(secs))):
        common -= 2
    for i, sec in enumerate(secs):
        r, c = divmod(i, cols)
        x0, y0 = 100 + c * (cw + gap), y + r * (ch + gap)
        sw = _width(i)
        cb = (x0, y0, x0 + sw, y0 + ch)
        p.shadow(cb, 26, blur=18, alpha=0.08, dy=8)
        p.rect(cb, fill=_rgb(th.surface) if sty == "clean" else (255, 255, 255) if not look.dark_theme else _rgb(th.surface),
               r=26)
        heading = _text(sec.get("heading"))
        items = [_clean_item(b) for b in _strings(sec.get("bullets") or sec.get("text"))]
        ic = icons.pick(sec.get("icon"), heading, " ".join(items), kind="section")
        p.circle(x0 + 62, y0 + 64, 34, fill=accent)
        p.icon(ic, x0 + 62, y0 + 64, 40, on)
        top = y0 + 64
        if heading:
            hf, hl2, hs = p.fit(heading, "bold", sw - 140, 100, 44, 30, gap=1.2, max_lines=2)
            p.lines(x0 + 112, top - len(hl2) * hs * 1.2 / 2 + hs * 0.06, hl2, hf, hs, ink, gap=1.2)
        by = y0 + 124
        if items:
            size_b = common
            bf = p.font("regular", size_b)
            blocks = [wrap(p.d, it, bf, (sw - 100) * p.s) for it in items]
            yy = by
            for lines_b in blocks:
                if yy + size_b * 1.42 > y0 + ch - 20:
                    break
                p.circle(x0 + 48, yy + size_b * 0.7, size_b * 0.16, fill=accent)
                for ln in lines_b:
                    if yy + size_b * 1.42 > y0 + ch - 20:
                        break
                    p.d.text(((x0 + 72) * p.s, yy * p.s), ln, font=bf, fill=body)
                    yy += size_b * 1.42
                yy += size_b * 0.5
    # ---- 꼬리 (주최 · 문의 · 출처)
    p.rect((0, foot_top, BW, BH), fill=_rgb(th.title) if not look.dark_theme else _rgb(th.surface))
    fink = (255, 255, 255) if not look.dark_theme else _rgb(th.title)
    fmut = _alpha(fink, 0.7)
    ft = _text(footer)
    if ft:
        p.icon("info", 128, foot_top + 62, 38, accent if not look.dark_theme else accent)
        ff, fl, fs = p.fit(ft, "semibold", BW - 260, 70, 30, 22, gap=1.3, max_lines=2)
        p.lines(162, foot_top + 62 - len(fl) * fs * 1.3 / 2 + fs * 0.06, fl, ff, fs, fink, gap=1.3)
    refs = [_text(r) for r in _strings(sources)]
    if refs:
        line = "출처: " + " · ".join(_domain(r) for r in refs[:3])
        rf, rl, rs = p.fit(line, "regular", BW - 200, 50, 20, 16, gap=1.3, max_lines=2)
        p.lines(100, foot_top + 112, rl, rf, rs, fmut, gap=1.3)
    path = Path(path)
    out = p.save(path)
    pdf = path.with_suffix(".pdf")
    out.save(pdf, resolution=150)
    return {"sections": len(secs), "pdf": pdf, "size": (W, H), "style": sty}
