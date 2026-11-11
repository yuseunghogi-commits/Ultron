"""작업 결과물 만들기 — 발표 자료(PowerPoint) · 보고서(Word) · 표(Excel).

울트론이 "OO 자료조사해서 PPT 만들어 줘" 같은 일을 끝까지 해내도록, Claude 가 조사해서 짠 내용을 실제 파일로 만든다.
  · build_presentation: 16:9 PowerPoint — 표지 · 목차 · 본문(목록 · 장 구분 · 비교 · 숫자 · 인용 · 마무리) · 참고 자료.
    장마다 발표 대본(슬라이드 노트)을 넣는다. 글이 많으면 글자를 줄이고, 그래도 넘치면 다음 장으로 나눈다.
  · build_document: Word 보고서 — 제목 · 장(제목 · 문단 · 목록 · 표) · 참고 자료 · 쪽 번호.
  · build_spreadsheet: Excel — 시트마다 제목 · 머리글 · 행. 칸 너비 자동, 머리글 고정 · 거르기. '=' 로 시작하면 수식.
글꼴은 Windows 기본 한글 글꼴(맑은 고딕). 이 파일은 파일만 만든다 (저장 폴더 고르기 · 열기는 tools.py).
라이브러리(python-pptx · python-docx · XlsxWriter)는 쓸 때 불러온다 — 없어도 울트론의 다른 기능은 그대로 켜진다.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

FONT = "맑은 고딕"
MAX_SLIDES = 40


# ---------------------------------------------------------------- 저장 위치 · 파일 이름
_BAD = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_name(name: str, fallback: str = "ULTRON 작업") -> str:
    """파일 이름으로 쓸 수 없는 글자를 지우고 너무 길면 자른다."""
    s = re.sub(r"\s+", " ", _BAD.sub(" ", name or "")).strip(" .")
    return (s or fallback)[:80].rstrip(" .")


def target(folder: Path, name: str, ext: str, overwrite: bool = False) -> Path:
    """저장할 경로. 같은 이름이 있으면 '이름 (2)' 처럼 새 이름을 쓴다 (overwrite 면 그대로 덮어쓴다)."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    base = safe_name(name)
    first = folder / f"{base}{ext}"
    if overwrite or not first.exists():
        return first
    for i in range(2, 1000):
        p = folder / f"{base} ({i}){ext}"
        if not p.exists():
            return p
    raise ValueError("같은 이름의 파일이 너무 많습니다. 다른 이름을 주세요.")


def pretty_ref(ref: str) -> str:
    """출처 한 줄을 읽기 좋게: 주소 속 '%EA%B8…' 같은 부호를 한글로 푼다."""
    import urllib.parse
    return re.sub(r"https?://\S+", lambda m: urllib.parse.unquote(m.group(0)), ref)


def _text(v) -> str:
    return re.sub(r"\s+", " ", str(v if v is not None else "")).strip()


def _listish(v) -> list:
    """목록으로 읽는다: ['1월', '2월'] 그대로 · '1월, 2월, 3월' 처럼 글자로 와도 나눈다 (쉼표 · 줄바꿈 · |)."""
    if v is None:
        return []
    if isinstance(v, str):
        return [x.strip() for x in re.split(r"[,\n|]", v) if x.strip()]
    if isinstance(v, (list, tuple)):
        return list(v)
    return [v]


def _strings(v) -> list[str]:
    if v is None:
        return []
    if isinstance(v, str):
        v = [line for line in v.splitlines()]
    return [s for s in (str(x).rstrip() for x in v) if s.strip()]


# ---------------------------------------------------------------- 글자 폭 어림 (글이 칸에 들어가는지)
def _em(text: str) -> float:
    """글자 폭의 합 (글자 크기를 1 로 볼 때). 한글 · 한자는 1, 영문 · 숫자는 0.56, 띄어쓰기는 0.3."""
    w = 0.0
    for ch in text:
        o = ord(ch)
        if ch == " ":
            w += 0.3
        elif 0x1100 <= o <= 0x11FF or 0x2E80 <= o <= 0xA4CF or 0xAC00 <= o <= 0xD7A3 or 0xF900 <= o <= 0xFAFF \
                or 0xFE30 <= o <= 0xFE4F or 0xFF00 <= o <= 0xFF60:
            w += 1.0
        else:
            w += 0.56
    return w


def _lines(text: str, size: float, width_in: float) -> int:
    per_line = max(1.0, width_in * 72 / size)
    return max(1, math.ceil(_em(text) / per_line))


# ---------------------------------------------------------------- 발표 자료 (PowerPoint)
@dataclass(frozen=True)
class Theme:
    bg: str
    surface: str
    title: str
    text: str
    muted: str
    accent: str
    soft: str          # 장식 · 카드 테두리용 연한 강조색
    on_accent: str     # 강조색 위의 글자


THEMES = {
    "light": Theme("FFFFFF", "F3F5F9", "16213A", "2A3346", "6B7487", "2F5BEA", "C9D6FF", "FFFFFF"),
    "dark": Theme("15171D", "20242D", "F4F5F7", "D9DDE5", "9199A8", "FF4D5E", "5A2A30", "FFFFFF"),
    "navy": Theme("0E2240", "173156", "FFFFFF", "DCE5F2", "A6B6CE", "4FC3F7", "1E4372", "0E2240"),
    "warm": Theme("FFF8F1", "FCEBDA", "3A2417", "4B3425", "8B705E", "E5702F", "F7CFAE", "FFFFFF"),
    "green": Theme("F4FAF6", "E1F0E6", "16392A", "23402F", "5C786A", "2E9D63", "BFE3CD", "FFFFFF"),
}
LAYOUTS = ("bullets", "section", "two_column", "stats", "chart", "quote", "closing")
CHARTS = ("column", "bar", "line", "pie")
W, H, M = 13.333, 7.5, 0.8            # 슬라이드 크기 · 좌우 여백 (인치)
BODY_SIZES = (26, 24, 22, 20, 18, 16)


def number(v) -> float | None:
    """숫자로 읽는다: 73 · '73%' · '1,200명' · '3.7mm' · '-2.5' → 73 · 73 · 1200 · 3.7 · -2.5. 숫자가 아니면 None."""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    m = re.search(r"-?\d[\d,]*(?:\.\d+)?", str(v or ""))
    return float(m.group(0).replace(",", "")) if m else None


def _hexmix(a: str, b: str, t: float) -> str:
    ca = [int(a[i:i + 2], 16) for i in (0, 2, 4)]
    cb = [int(b[i:i + 2], 16) for i in (0, 2, 4)]
    return "".join(f"{round(x + (y - x) * t):02X}" for x, y in zip(ca, cb))


def palette(t: "Theme") -> list[str]:
    """차트 색 (테마에서): 강조색부터, 서로 잘 구분되게."""
    return [t.accent, _hexmix(t.accent, t.title, 0.55), t.muted, _hexmix(t.accent, t.bg, 0.45), t.title,
            _hexmix(t.muted, t.bg, 0.45)]


def parse_bullets(lines) -> list[tuple[str, int]]:
    """'- ' 로 시작하는 줄은 바로 앞 줄의 하위 항목. 앞에 붙은 글머리 기호(•·▪*)는 지운다."""
    out = []
    for raw in _strings(lines):
        s = raw.strip()
        level = 1 if re.match(r"^[-–—]\s+", s) or raw.startswith(("  ", "\t")) else 0
        s = re.sub(r"^(?:[-–—•●▪◦·*]|\d+[.)])\s+", "", s).strip()
        if s:
            out.append((s, level if out else 0))
    return out


def _height(items: list[tuple[str, int]], size: float, width_in: float) -> float:
    pts = 0.0
    for text, level in items:
        sz = size * (0.86 if level else 1.0)
        pts += _lines(text, sz, width_in - 0.42 - 0.4 * level) * sz * 1.22 + sz * 0.55
    return pts / 72


def roomy_gap(items: list[tuple[str, int]], size: float, width_in: float, height_in: float) -> float:
    """항목이 적어 공간이 남으면 문단 사이를 넓힌다 (위에 몰려 있지 않게). 기본 0.55 (글자 크기의 배수)."""
    if not items:
        return 0.55
    spare = height_in * 0.9 - _height(items, size, width_in)
    return 0.55 + max(0.0, min(0.75, spare * 72 / len(items) / size))


def fit_size(items: list[tuple[str, int]], width_in: float, height_in: float, sizes=BODY_SIZES) -> int | None:
    """칸에 다 들어가는 가장 큰 글자 크기. 가장 작은 크기로도 안 들어가면 None."""
    for size in sizes:
        if _height(items, size, width_in) <= height_in:
            return size
    return None


def _greedy(items: list[tuple[str, int]], width_in: float, height_in: float, size: int) -> list[list]:
    groups, cur = [], []
    for item in items:
        trial = cur + [item]
        if cur and _height(trial, size, width_in) > height_in:
            if item[1] and cur and cur[-1][1] == 0 and len(cur) > 1:   # 윗 항목을 다음 장으로 데리고 간다
                head = cur.pop()
                groups.append(cur)
                cur = [head, item]
            else:
                groups.append(cur)
                cur = [(item[0], 0)]
        else:
            cur = trial
    if cur:
        groups.append(cur)
    return groups


def split_items(items: list[tuple[str, int]], width_in: float, height_in: float, size: int = 18) -> list[list]:
    """한 장에 다 안 들어가는 목록을 여러 장으로 고르게 나눈다 (하위 항목은 윗 항목과 떨어뜨리지 않는다)."""
    greedy = _greedy(items, width_in, height_in, size)
    if len(greedy) <= 1:
        return greedy
    blocks: list[list] = []                       # 윗 항목 + 그 하위 항목 = 한 덩어리 (나누지 않는다)
    for item in items:
        if item[1] and blocks:
            blocks[-1].append(item)
        else:
            blocks.append([(item[0], 0)])
    n = len(greedy)
    while True:
        target = math.ceil(sum(len(b) for b in blocks) / n)
        groups, cur = [], []
        for b in blocks:
            if cur and len(cur) + len(b) > target and len(groups) < n - 1:
                groups.append(cur)
                cur = []
            cur = cur + b
        groups.append(cur)
        if all(_height(g, size, width_in) <= height_in for g in groups) or n > len(blocks):
            return groups if all(_height(g, size, width_in) <= height_in for g in groups) else greedy
        n += 1


class _Deck:
    def __init__(self, theme: Theme, title: str) -> None:
        from pptx import Presentation
        from pptx.util import Inches
        self.t, self.title = theme, title
        self.prs = Presentation()
        self.prs.slide_width, self.prs.slide_height = Inches(W), Inches(H)
        self.blank = self.prs.slide_layouts[6]
        self.count = 0
        self.notes = 0

    # ---- 기본 도구
    def rgb(self, hex_: str):
        from pptx.dml.color import RGBColor
        return RGBColor.from_string(hex_)

    def slide(self, notes: str = ""):
        s = self.prs.slides.add_slide(self.blank)
        bg = s.background.fill
        bg.solid()
        bg.fore_color.rgb = self.rgb(self.t.bg)
        self.count += 1
        if _text(notes):
            s.notes_slide.notes_text_frame.text = str(notes).strip()
            self.notes += 1
        return s

    def box(self, s, x, y, w, h, color: str, shape: str = "rect", radius: float = 0.08):
        from pptx.enum.shapes import MSO_SHAPE
        from pptx.util import Inches
        kind = {"rect": MSO_SHAPE.RECTANGLE, "round": MSO_SHAPE.ROUNDED_RECTANGLE, "oval": MSO_SHAPE.OVAL}[shape]
        sh = s.shapes.add_shape(kind, Inches(x), Inches(y), Inches(w), Inches(h))
        sh.fill.solid()
        sh.fill.fore_color.rgb = self.rgb(color)
        sh.line.fill.background()
        sh.shadow.inherit = False
        if shape == "round":
            sh.adjustments[0] = radius
        return sh

    def _font(self, run, size: float, color: str, bold: bool = False) -> None:
        from pptx.oxml.ns import qn
        from pptx.util import Pt
        f = run.font
        f.size, f.bold, f.name = Pt(size), bold, FONT
        f.color.rgb = self.rgb(color)
        rpr = run._r.get_or_add_rPr()
        latin = rpr.find(qn("a:latin"))
        prev = latin
        for tag in ("a:ea", "a:cs"):          # 한글 글꼴은 '동아시아 글꼴' 칸에 넣어야 적용된다 (순서: latin → ea → cs)
            el = rpr.find(qn(tag))
            if el is None:
                el = rpr.makeelement(qn(tag), {})
                prev.addnext(el)
            el.set("typeface", FONT)
            prev = el

    def text(self, s, x, y, w, h, lines, size: float, color: str, bold: bool = False, align: str = "left",
             anchor: str = "top", spacing: float = 1.15):
        """글 상자 (lines: 문단들). 줄 바꿈 · 여백 · 정렬을 맞춘다."""
        from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
        from pptx.util import Inches, Pt
        tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.auto_size = MSO_AUTO_SIZE.NONE
        tf.margin_left = tf.margin_right = Inches(0.04)
        tf.margin_top = tf.margin_bottom = Inches(0.02)
        tf.vertical_anchor = {"top": MSO_ANCHOR.TOP, "middle": MSO_ANCHOR.MIDDLE, "bottom": MSO_ANCHOR.BOTTOM}[anchor]
        for i, line in enumerate([lines] if isinstance(lines, str) else lines):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = {"left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER, "right": PP_ALIGN.RIGHT}[align]
            p.line_spacing = spacing
            if i:
                p.space_before = Pt(size * 0.3)
            self._font(p.add_run(), size, color, bold)
            p.runs[0].text = str(line)
        return tb

    def bullets(self, s, x, y, w, h, items: list[tuple[str, int]], size: float, color: str | None = None,
                gap: float = 0.55):
        """글머리 기호 목록 (강조색 동그라미 · 하위 항목은 짧은 줄)."""
        from pptx.enum.text import MSO_AUTO_SIZE
        from pptx.oxml.ns import qn
        from pptx.util import Inches, Pt
        tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.auto_size = MSO_AUTO_SIZE.NONE                    # 크기는 fit_size 로 미리 맞춘다 (프로그램마다 줄이는 방식이 달라서)
        tf.margin_left = tf.margin_right = Inches(0.04)
        for i, (line, level) in enumerate(items):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            sz = size * (0.86 if level else 1.0)
            p.line_spacing = 1.12
            p.space_before = Pt(0 if i == 0 else sz * gap)
            ppr = p._p.get_or_add_pPr()
            ppr.set("marL", str(int(Inches(0.42 + 0.4 * level))))
            ppr.set("indent", str(int(-Inches(0.32))))
            for tag, attrs in (("a:buClr", None), ("a:buSzPct", {"val": "100000"}), ("a:buFont", {"typeface": "Arial"}),
                               ("a:buChar", {"char": "–" if level else "●"})):
                el = ppr.makeelement(qn(tag), attrs or {})
                if tag == "a:buClr":
                    clr = el.makeelement(qn("a:srgbClr"), {"val": self.t.muted if level else self.t.accent})
                    el.append(clr)
                ppr.append(el)
            self._font(p.add_run(), sz, color or (self.t.muted if level else self.t.text))
            p.runs[0].text = line
        return tb

    def header(self, s, title: str) -> None:
        size = 30 if _em(title) <= 26 else 26 if _em(title) <= 36 else 22
        self.text(s, M, 0.48, W - 2 * M, 0.95, title, size, self.t.title, bold=True, anchor="bottom")
        self.box(s, M, 1.5, 0.9, 0.07, self.t.accent)

    def footer(self, s) -> None:
        self.text(s, M, H - 0.5, 8, 0.3, self.title, 10, self.t.muted)
        self.text(s, W - M - 1.5, H - 0.5, 1.5, 0.3, str(self.count), 10, self.t.muted, align="right")

    # ---- 장 종류
    def cover(self, title: str, subtitle: str) -> None:
        s = self.slide()
        t = self.t
        self.box(s, W - 4.6, -1.6, 6.2, 6.2, t.surface, "oval")       # 장식 원
        self.box(s, W - 2.3, 3.9, 3.4, 3.4, t.soft, "oval")
        self.box(s, M, 2.35, 0.14, 2.2, t.accent)
        size = 54 if _em(title) <= 12 else 46 if _em(title) <= 18 else 38 if _em(title) <= 26 else 32 if _em(title) <= 36 else 28
        self.text(s, M + 0.45, 2.1, W - 2 * M - 3.2, 1.9, title, size, t.title, bold=True, anchor="bottom", spacing=1.05)
        if subtitle:
            self.text(s, M + 0.45, 4.1, W - 2 * M - 3.2, 0.9, subtitle, 18, t.muted)

    def agenda(self, titles: list[str]) -> None:
        s = self.slide()
        self.header(s, "목차")
        titles = titles[:12]
        cols = 1 if len(titles) <= 6 else 2
        per = math.ceil(len(titles) / cols)
        col_w = (W - 2 * M) / cols
        big = len(titles) <= 4
        step, num, size = (1.05, 34, 28) if big else (0.78, 26, 22 if cols == 1 else 18)
        top = 2.05 + (max(0, 4 - len(titles)) * 0.35 if big else 0)
        for c in range(cols):
            for r, name in enumerate(titles[c * per:(c + 1) * per]):
                n = c * per + r + 1
                y = top + r * step
                self.text(s, M + c * col_w, y, 1.3, step - 0.1, f"{n:02d}", num, self.t.accent, bold=True)
                self.text(s, M + c * col_w + (1.35 if big else 1.0), y + (0.08 if big else 0.04),
                          col_w - 1.5, step - 0.1, name, size, self.t.text)
        self.footer(s)

    def bullet_slide(self, title: str, items: list[tuple[str, int]], notes: str) -> None:
        width, height = W - 2 * M, H - 2.0 - 0.75
        size = fit_size(items, width, height) or BODY_SIZES[-1]
        s = self.slide(notes)
        self.header(s, title)
        if items:
            self.bullets(s, M, 1.95, width, height, items, size, gap=roomy_gap(items, size, width, height))
        self.footer(s)

    def section(self, number: int, title: str, items: list[tuple[str, int]], notes: str) -> None:
        s = self.slide(notes)
        t = self.t
        self.box(s, 0, 0, 4.4, H, t.accent)
        self.text(s, 0.6, 2.3, 3.4, 1.6, f"{number:02d}", 88, t.on_accent, bold=True, anchor="middle")
        size = 40 if _em(title) <= 14 else 34 if _em(title) <= 22 else 28
        self.text(s, 5.0, 2.4, W - 5.0 - M, 1.5, title, size, t.title, bold=True, anchor="bottom")
        if items:
            self.text(s, 5.0, 4.05, W - 5.0 - M, 2.0, [line for line, _ in items[:3]], 18, t.muted)

    def two_column(self, title: str, left: dict, right: dict, notes: str) -> None:
        s = self.slide(notes)
        self.header(s, title)
        gap = 0.4
        cw = (W - 2 * M - gap) / 2
        top, ch = 1.95, H - 1.95 - 0.8
        cards = [(left or {}), (right or {})]
        parsed = [parse_bullets(c.get("bullets")) for c in cards]
        size = min(fit_size(p, cw - 0.6, ch - 1.2, (24, 22, 20, 18, 16, 14)) or 14 for p in parsed) if any(parsed) else 18
        for i, (card, items) in enumerate(zip(cards, parsed)):
            x = M + i * (cw + gap)
            self.box(s, x, top, cw, ch, self.t.surface, "round", 0.05)
            self.box(s, x, top, cw, 0.09, self.t.accent if i == 0 else self.t.muted)
            self.text(s, x + 0.3, top + 0.25, cw - 0.6, 0.7, _text(card.get("heading")) or ("A" if i == 0 else "B"),
                      22, self.t.accent if i == 0 else self.t.title, bold=True)
            if items:
                spread = min(roomy_gap(p, size, cw - 0.6, ch - 1.2) for p in parsed if p)   # (gap 은 카드 사이 간격)
                self.bullets(s, x + 0.3, top + 1.0, cw - 0.6, ch - 1.2, items, size, gap=spread)
        self.footer(s)

    def stats(self, title: str, stats: list[dict], notes: str) -> None:
        s = self.slide(notes)
        self.header(s, title)
        stats = [st for st in stats if _text(st.get("value")) or _text(st.get("label"))][:4] or [{"value": "-", "label": ""}]
        n, gap = len(stats), 0.35
        cw = (W - 2 * M - gap * (n - 1)) / n
        top, ch = 2.2, 3.9
        for i, st in enumerate(stats):
            x = M + i * (cw + gap)
            self.box(s, x, top, cw, ch, self.t.surface, "round", 0.06)
            value = _text(st.get("value"))
            vsize = 54 if _em(value) <= 4 else 44 if _em(value) <= 6 else 34 if _em(value) <= 9 else 26
            self.text(s, x + 0.2, top + 0.45, cw - 0.4, 1.5, value, vsize, self.t.accent, bold=True, align="center",
                      anchor="middle")
            self.box(s, x + cw / 2 - 0.35, top + 2.05, 0.7, 0.05, self.t.soft)
            label = _text(st.get("label"))
            lsize = 20 if _lines(label, 20, cw - 0.5) <= 2 else 17 if _lines(label, 17, cw - 0.5) <= 3 else 14
            self.text(s, x + 0.25, top + 2.25, cw - 0.5, 1.5, label, lsize, self.t.text, align="center")
        self.footer(s)

    def chart(self, title: str, spec: dict, items: list[tuple[str, int]], notes: str) -> bool:
        """진짜 차트 (파워포인트에서 바로 고칠 수 있음). 데이터가 차트로 그릴 수 없으면 False (→ 목록 장으로)."""
        from pptx.chart.data import CategoryChartData
        from pptx.enum.chart import (XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION, XL_MARKER_STYLE,
                                     XL_TICK_LABEL_POSITION)
        from pptx.oxml.ns import qn
        from pptx.util import Inches, Pt
        kind = str(spec.get("type") or "column").strip().lower()
        kind = {"막대": "column", "가로막대": "bar", "꺾은선": "line", "선": "line", "원": "pie", "파이": "pie"}.get(kind, kind)
        if kind not in CHARTS:
            kind = "column"
        cats = [_text(c) for c in _listish(spec.get("categories"))][:24]
        series = []
        for i, ser in enumerate([x for x in _listish(spec.get("series")) if isinstance(x, dict)][:6]):
            vals = [number(v) for v in _listish(ser.get("values"))][:len(cats)]
            if any(v is not None for v in vals):
                series.append((_text(ser.get("name")) or f"값 {i + 1}", vals + [None] * (len(cats) - len(vals))))
        if not cats or not series:
            return False
        if kind == "pie":
            series = series[:1]
        data = CategoryChartData()
        data.categories = cats
        for name, vals in series:
            data.add_series(name, vals)
        s = self.slide(notes)
        self.header(s, title)
        width = (W - 2 * M) * (0.64 if items else 1.0)
        top, height = 1.85, H - 1.85 - 0.75
        xl = {"column": XL_CHART_TYPE.COLUMN_CLUSTERED, "bar": XL_CHART_TYPE.BAR_CLUSTERED,
              "line": XL_CHART_TYPE.LINE_MARKERS, "pie": XL_CHART_TYPE.PIE}[kind]
        ch = s.shapes.add_chart(xl, Inches(M), Inches(top), Inches(width), Inches(height), data).chart
        t, colors = self.t, palette(self.t)
        ch.has_title = False                    # 장 제목이 위에 있다
        ch.font.size, ch.font.name = Pt(14), FONT
        ch.font.color.rgb = self.rgb(t.text)
        unit = _text(spec.get("unit")).replace('"', "")
        plot = ch.plots[0]
        plot.has_data_labels = True
        dl = plot.data_labels
        fmt = f'General"{unit}"' if unit else "General"
        dl.number_format, dl.number_format_is_linked = fmt, False
        dl.font.size = Pt(13)
        dl.font.color.rgb = self.rgb(t.text)
        if kind == "pie":
            dl.position = XL_LABEL_POSITION.OUTSIDE_END
            for i, pt in enumerate(plot.series[0].points):
                pt.format.fill.solid()
                pt.format.fill.fore_color.rgb = self.rgb(colors[i % len(colors)] if i < len(colors) else
                                                         _hexmix(colors[i % len(colors)], t.bg, 0.3))
        else:
            dl.position = XL_LABEL_POSITION.ABOVE if kind == "line" else XL_LABEL_POSITION.OUTSIDE_END
            if kind != "line":
                plot.gap_width = 70
            mean = [sum(v for v in vals if v is not None) / max(1, sum(v is not None for v in vals)) for _, vals in series]
            high, low = mean.index(max(mean)), mean.index(min(mean))
            for i, ser in enumerate(plot.series):
                c = self.rgb(colors[i % len(colors)])
                if kind == "line":
                    ser.smooth = False
                    ser.format.line.color.rgb = c
                    ser.format.line.width = Pt(3)
                    ser.marker.style, ser.marker.size = XL_MARKER_STYLE.CIRCLE, 8
                    ser.marker.format.fill.solid()
                    ser.marker.format.fill.fore_color.rgb = c
                    ser.marker.format.line.color.rgb = c
                    if len(series) > 1:                 # 선이 여러 개: 위쪽 선은 숫자를 위에, 아래쪽 선은 아래에 (겹치지 않게)
                        sl = ser.data_labels
                        sl.show_value = i in (high, low)       # 가운데 선들의 숫자는 감춘다 (눈금으로 읽는다)
                        sl.number_format, sl.number_format_is_linked = fmt, False
                        sl.font.size = Pt(13)
                        sl.font.color.rgb = self.rgb(t.text)
                        sl.position = XL_LABEL_POSITION.ABOVE if i == high else XL_LABEL_POSITION.BELOW
                else:
                    ser.format.fill.solid()
                    ser.format.fill.fore_color.rgb = c
            for axis in (ch.category_axis, ch.value_axis):
                axis.tick_labels.font.size = Pt(13)
                axis.tick_labels.font.color.rgb = self.rgb(t.muted)
                axis.format.line.color.rgb = self.rgb(t.soft)
            ch.category_axis.tick_label_position = XL_TICK_LABEL_POSITION.LOW   # 음수가 있어도 이름은 맨 아래에
            if kind == "bar":                               # 가로 막대: 첫 항목이 맨 위에 (위에서 아래로 읽게), 눈금은 아래 그대로
                ch.category_axis.reverse_order = True
                crosses = ch.value_axis._element.find(qn("c:crosses"))
                if crosses is not None:
                    crosses.set("val", "max")              # 숫자 축이 마지막 항목(맨 아래) 쪽에서 만나게
            ch.value_axis.has_major_gridlines = True
            ch.value_axis.major_gridlines.format.line.color.rgb = self.rgb(t.soft)
            ch.value_axis.format.line.fill.background()
        ch.has_legend = kind == "pie" or len(series) > 1
        if ch.has_legend:
            ch.legend.position = XL_LEGEND_POSITION.RIGHT if kind == "pie" else XL_LEGEND_POSITION.BOTTOM
            ch.legend.include_in_layout = False
            ch.legend.font.size = Pt(13)
            ch.legend.font.color.rgb = self.rgb(t.text)
        self._chart_fonts(ch)
        if items:
            bx = M + width + 0.35
            bw = W - M - bx
            size = fit_size(items, bw, height - 0.3, (22, 20, 18, 16, 14)) or 14
            self.bullets(s, bx, top + 0.3, bw, height - 0.3, items, size)
        self.footer(s)
        return True

    def _chart_fonts(self, ch) -> None:
        """차트 안의 모든 글자에 한글 글꼴(동아시아 글꼴 칸)을 넣는다 — 순서: latin → ea → cs."""
        from pptx.oxml.ns import qn
        after = {qn(t) for t in ("a:cs", "a:sym", "a:hlinkClick", "a:hlinkMouseOver", "a:rtl", "a:extLst")}
        for rpr in list(ch._chartSpace.iter(qn("a:defRPr"))) + list(ch._chartSpace.iter(qn("a:rPr"))):
            latin = rpr.find(qn("a:latin"))
            if latin is None:
                latin = rpr.makeelement(qn("a:latin"), {})
                nxt = next((c for c in rpr if c.tag in after or c.tag == qn("a:ea")), None)
                nxt.addprevious(latin) if nxt is not None else rpr.append(latin)
            latin.set("typeface", FONT)
            ea = rpr.find(qn("a:ea"))
            if ea is None:
                ea = rpr.makeelement(qn("a:ea"), {})
                latin.addnext(ea)
            ea.set("typeface", FONT)

    def quote(self, title: str, quote: str, by: str, notes: str) -> None:
        s = self.slide(notes)
        t = self.t
        self.box(s, M, 1.2, 0.12, 4.6, t.accent)
        self.text(s, M + 0.5, 0.75, 2, 1.4, "“", 110, t.soft, bold=True)
        size = 32 if _em(quote) <= 60 else 26 if _em(quote) <= 100 else 22 if _em(quote) <= 150 else 18
        self.text(s, M + 0.6, 1.9, W - 2 * M - 1.0, 3.3, quote, size, t.title, anchor="middle", spacing=1.25)
        if _text(by):
            self.text(s, M + 0.6, 5.35, W - 2 * M - 1.0, 0.6, f"— {_text(by)}", 18, t.muted, align="right")
        self.footer(s)

    def closing(self, title: str, items: list[tuple[str, int]], notes: str) -> None:
        s = self.slide(notes)
        t = self.t
        self.box(s, -1.8, H - 3.2, 5.2, 5.2, t.surface, "oval")
        self.box(s, W - 3.0, -1.4, 4.2, 4.2, t.soft, "oval")
        size = 54 if _em(title) <= 10 else 42 if _em(title) <= 18 else 34
        self.text(s, M, 2.5, W - 2 * M, 1.5, title or "감사합니다", size, t.title, bold=True, align="center", anchor="middle")
        if items:
            self.text(s, M, 4.15, W - 2 * M, 1.6, [line for line, _ in items[:3]], 20, t.muted, align="center")

    def sources(self, refs: list[str]) -> None:
        width, height = W - 2 * M, H - 2.0 - 0.75
        items = [(r, 0) for r in refs]
        parts = split_items(items, width, height, 14)
        start = 0
        for k, part in enumerate(parts):
            s = self.slide()
            self.header(s, "참고 자료" if k == 0 else "참고 자료 (계속)")
            size = fit_size(part, width, height, (18, 16, 15, 14, 13, 12)) or 12
            lines = [f"{start + i + 1}. {line}" for i, (line, _) in enumerate(part)]
            start += len(part)
            self.text(s, M, 1.95, width, height, lines, size, self.t.text, spacing=1.1)
            self.footer(s)


def build_presentation(path: Path, title: str, slides: list, subtitle: str = "", sources=None,
                       theme: str = "light", agenda: bool | None = None) -> dict:
    """발표 자료를 만든다 → {'slides': 장 수, 'notes': 대본을 넣은 장 수, 'split': 넘쳐서 나눈 장 수}."""
    title = _text(title)
    if not title:
        raise ValueError("발표 제목(title)이 필요합니다.")
    if not isinstance(slides, list) or not slides:
        raise ValueError("슬라이드(slides)가 하나 이상 필요합니다.")
    if len(slides) > MAX_SLIDES:
        raise ValueError(f"슬라이드가 너무 많습니다 ({len(slides)}장). {MAX_SLIDES}장 이하로 나눠 만드세요.")
    th = THEMES.get((theme or "light").strip().lower(), THEMES["light"])
    deck = _Deck(th, title)
    deck.cover(title, _text(subtitle))
    clean = []
    for i, raw in enumerate(slides, 1):
        if not isinstance(raw, dict):
            raw = {"title": str(raw)}
        layout = (raw.get("layout") or "bullets").strip().lower().replace("-", "_")
        if layout not in LAYOUTS:
            layout = "bullets"
        clean.append((layout, _text(raw.get("title")) or f"{i}", raw))
    if agenda is None:
        agenda = sum(1 for lay, _, _ in clean if lay not in ("closing", "quote")) >= 4
    if agenda:
        sections = [name for lay, name, _ in clean if lay == "section"]
        deck.agenda(sections or [name for lay, name, _ in clean if lay not in ("closing", "quote")])
    split = 0
    part = 0
    width, height = W - 2 * M, H - 2.0 - 0.75
    for layout, name, raw in clean:
        notes = str(raw.get("notes") or "")
        items = parse_bullets(raw.get("bullets"))
        if layout == "section":
            part += 1
            deck.section(part, name, items, notes)
        elif layout == "two_column":
            side = [x if isinstance(x, dict) else {"heading": "", "bullets": _strings(x)} for x in (raw.get("left"), raw.get("right"))]
            deck.two_column(name, side[0] or {}, side[1] or {}, notes)
        elif layout == "stats":
            stats = [x if isinstance(x, dict) else dict(zip(("value", "label"), (re.split(r"\s*\|\s*|\s+[—–-]\s+|\s*:\s+", str(x), maxsplit=1) + [""])[:2]))
                     for x in (raw.get("stats") or [])]
            deck.stats(name, stats, notes)
        elif layout == "chart":
            spec = raw.get("chart") if isinstance(raw.get("chart"), dict) else raw
            if not deck.chart(name, spec, items, notes):          # 차트로 그릴 수 없는 데이터 → 목록 장 (실패시키지 않는다)
                rows = [(f"{_text(c)}: {', '.join(_text(v) for v in vals)}", 0)
                        for c, *vals in zip(_listish(spec.get("categories")), *[_listish(x.get("values")) for x in
                                                                               _listish(spec.get("series")) if isinstance(x, dict)])]
                deck.bullet_slide(name, items + rows or [("(차트 데이터 없음)", 0)], notes)
        elif layout == "quote":
            deck.quote(name, _text(raw.get("quote")) or name, _text(raw.get("by")), notes)
        elif layout == "closing":
            deck.closing(name, items, notes)
        elif items and fit_size(items, width, height) is None:          # 넘친다 → 여러 장으로
            parts = split_items(items, width, height, 18)
            split += len(parts) - 1
            for k, part in enumerate(parts):
                deck.bullet_slide(name if k == 0 else f"{name} (계속)", part, notes if k == 0 else "")
        else:
            deck.bullet_slide(name, items, notes)
    refs = [pretty_ref(_text(r)) for r in _strings(sources)]
    if refs:
        deck.sources(refs)
    deck.prs.core_properties.title = title
    deck.prs.core_properties.author = "U.L.T.R.O.N"
    deck.prs.save(str(path))
    return {"slides": deck.count, "notes": deck.notes, "split": split}


# ---------------------------------------------------------------- 보고서 (Word)
def _docx_font(style_font, element, name: str = FONT) -> None:
    from docx.oxml.ns import qn
    style_font.name = name
    rpr = element.get_or_add_rPr()
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = rpr.makeelement(qn("w:rFonts"), {})
        rpr.insert(0, fonts)
    for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        fonts.set(qn(attr), name)


def _shade(cell, hex_: str) -> None:
    from docx.oxml.ns import qn
    tcpr = cell._tc.get_or_add_tcPr()
    shd = tcpr.makeelement(qn("w:shd"), {qn("w:val"): "clear", qn("w:color"): "auto", qn("w:fill"): hex_})
    tcpr.append(shd)


def _page_number(paragraph) -> None:
    from docx.oxml.ns import qn
    run = paragraph.add_run()
    for kind, text in (("begin", None), ("instr", "PAGE"), ("end", None)):
        if kind == "instr":
            el = run._r.makeelement(qn("w:instrText"), {qn("xml:space"): "preserve"})
            el.text = text
        else:
            el = run._r.makeelement(qn("w:fldChar"), {qn("w:fldCharType"): kind})
        run._r.append(el)


def build_document(path: Path, title: str, sections: list, subtitle: str = "", sources=None) -> dict:
    """보고서를 만든다 → {'sections': 장 수, 'tables': 표 수}."""
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Cm, Pt, RGBColor
    title = _text(title)
    if not title:
        raise ValueError("문서 제목(title)이 필요합니다.")
    if not isinstance(sections, list) or not sections:
        raise ValueError("내용(sections)이 하나 이상 필요합니다.")
    doc = Document()
    for sec in doc.sections:
        sec.top_margin = sec.bottom_margin = Cm(2.5)
        sec.left_margin = sec.right_margin = Cm(2.4)
    normal = doc.styles["Normal"]
    _docx_font(normal.font, normal.element)
    normal.font.size = Pt(11)
    normal.paragraph_format.line_spacing = 1.45
    normal.paragraph_format.space_after = Pt(6)
    accent = RGBColor(0x1F, 0x3A, 0x8A)
    for name, size in (("Title", 24), ("Heading 1", 16), ("Heading 2", 13), ("List Bullet", 11), ("List Number", 10)):
        st = doc.styles[name]
        _docx_font(st.font, st.element)
        st.font.size = Pt(size)
        if name.startswith(("Title", "Heading")):
            st.font.bold = True
            st.font.color.rgb = accent if name != "Title" else RGBColor(0x16, 0x21, 0x3A)
    doc.add_paragraph(title, style="Title")
    if _text(subtitle):
        p = doc.add_paragraph(_text(subtitle))
        p.runs[0].font.color.rgb = RGBColor(0x6B, 0x74, 0x87)
    tables = 0
    for i, sec in enumerate(sections, 1):
        if not isinstance(sec, dict):
            sec = {"paragraphs": [str(sec)]}
        heading = _text(sec.get("heading"))
        level = 2 if str(sec.get("level", 1)).strip() == "2" else 1
        if heading:
            doc.add_heading(heading, level=level)
        for para in _strings(sec.get("paragraphs")):
            p = doc.add_paragraph(para.strip())
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        for line, lvl in parse_bullets(sec.get("bullets")):
            p = doc.add_paragraph(line, style="List Bullet")
            if lvl:
                p.paragraph_format.left_indent = Cm(1.6)
        table = sec.get("table")
        if isinstance(table, dict) and table.get("columns"):
            cols = [_text(c) for c in table["columns"]]
            rows = [r for r in (table.get("rows") or []) if isinstance(r, (list, tuple))]
            t = doc.add_table(rows=1 + len(rows), cols=len(cols))
            t.style = "Table Grid"
            for j, c in enumerate(cols):
                cell = t.rows[0].cells[j]
                cell.text = c
                cell.paragraphs[0].runs[0].font.bold = True
                _shade(cell, "DCE4F7")
            for r, row in enumerate(rows, 1):
                for j in range(len(cols)):
                    t.rows[r].cells[j].text = _text(row[j]) if j < len(row) else ""
            if _text(table.get("caption")):
                cap = doc.add_paragraph(_text(table["caption"]))
                cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
                cap.runs[0].font.size = Pt(9)
            tables += 1
    refs = [pretty_ref(_text(r)) for r in _strings(sources)]
    if refs:
        doc.add_heading("참고 자료", level=1)
        for r in refs:
            doc.add_paragraph(r, style="List Number")
    for sec in doc.sections:
        foot = sec.footer.paragraphs[0]
        foot.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _page_number(foot)
    doc.core_properties.title = title
    doc.core_properties.author = "U.L.T.R.O.N"
    doc.save(str(path))
    return {"sections": len(sections), "tables": tables}


# ---------------------------------------------------------------- 표 (Excel)
def _width(v) -> float:
    s = str(v if v is not None else "")
    return max((_em(line) * 1.9 for line in s.splitlines()), default=0.0) + 2


def _sheet_name(name: str, i: int, used: set) -> str:
    base = re.sub(r"[\[\]:*?/\\]", " ", _text(name))[:31].strip("' ") or f"시트{i}"
    s, k = base, 2
    while s.lower() in used:
        s = f"{base[:27]} ({k})"
        k += 1
    used.add(s.lower())
    return s


_EXCEL_COLORS = ["#2F5BEA", "#E5702F", "#2E9D63", "#9B59B6", "#FF4D5E", "#6B7487"]


def _excel_chart(wb, ws, spec: dict, cols: list[str], rows: list, r0: int, title: str) -> None:
    """시트의 표로 엑셀 차트를 만들어 표 오른쪽에 붙인다. category_column: 이름 칸 (기본 0),
    value_columns: 값 칸들 (기본: 숫자가 든 나머지 칸 전부)."""
    kind = str(spec.get("type") or "column").lower()
    kind = kind if kind in CHARTS else "column"
    cat = int(spec.get("category_column") or 0) if str(spec.get("category_column") or 0).isdigit() else 0
    cat = min(max(cat, 0), len(cols) - 1)
    vals = [int(c) for c in (spec.get("value_columns") or []) if str(c).isdigit() and int(c) < len(cols) and int(c) != cat]
    if not vals:
        vals = [j for j in range(len(cols)) if j != cat and any(number(r[j]) is not None for r in rows if j < len(r)
                                                                   and not (isinstance(r[j], str) and r[j].startswith("=")))]
    if not vals:
        return
    ch = wb.add_chart({"type": kind})
    last = r0 + len(rows)
    for i, j in enumerate(vals[:1] if kind == "pie" else vals[:6]):
        ser = {"name": [ws.name, r0, j], "categories": [ws.name, r0 + 1, cat, last, cat],
               "values": [ws.name, r0 + 1, j, last, j], "data_labels": {"value": True}}
        if kind == "pie":
            ser["points"] = [{"fill": {"color": _EXCEL_COLORS[k % len(_EXCEL_COLORS)]}} for k in range(len(rows))]
        elif kind == "line":
            ser["line"] = {"color": _EXCEL_COLORS[i % 6], "width": 2.5}
            ser["marker"] = {"type": "circle", "size": 7, "fill": {"color": _EXCEL_COLORS[i % 6]}, "border": {"none": True}}
        else:
            ser["fill"] = {"color": _EXCEL_COLORS[i % 6]}
        ch.add_series(ser)
    font = {"name": FONT}
    ch.set_title({"name": _text(spec.get("title")) or title or cols[vals[0]], "name_font": {**font, "size": 13}})
    ch.set_legend({"position": "bottom", "font": font} if kind != "pie" and len(vals) > 1 or kind == "pie" else {"none": True})
    if kind != "pie":
        ch.set_x_axis({"num_font": font})
        ch.set_y_axis({"num_font": font, "major_gridlines": {"visible": True, "line": {"color": "#E3E7EF"}}})
    ws.insert_chart(r0, len(cols) + 1, ch, {"x_scale": 1.35, "y_scale": 1.25})


def build_spreadsheet(path: Path, sheets: list) -> dict:
    """엑셀 파일을 만든다 → {'sheets': 시트 수, 'rows': 전체 데이터 행 수}."""
    import xlsxwriter
    import xlsxwriter.exceptions
    if not isinstance(sheets, list) or not sheets:
        raise ValueError("시트(sheets)가 하나 이상 필요합니다.")
    wb = xlsxwriter.Workbook(str(path))
    base = {"font_name": FONT, "font_size": 11, "valign": "vcenter"}
    f_title = wb.add_format({**base, "bold": True, "font_size": 15})
    f_head = wb.add_format({**base, "bold": True, "font_color": "#FFFFFF", "bg_color": "#2F5BEA", "border": 1,
                            "border_color": "#B8C2D6", "align": "center", "text_wrap": True})
    f_cell = wb.add_format({**base, "border": 1, "border_color": "#D5DBE6"})
    f_wrap = wb.add_format({**base, "border": 1, "border_color": "#D5DBE6", "text_wrap": True, "valign": "top"})
    f_int = wb.add_format({**base, "border": 1, "border_color": "#D5DBE6", "num_format": "#,##0"})
    f_num = wb.add_format({**base, "border": 1, "border_color": "#D5DBE6", "num_format": "#,##0.##"})
    used: set[str] = set()
    total = 0
    for i, sh in enumerate(sheets, 1):
        if not isinstance(sh, dict):
            raise ValueError("sheets 의 각 항목은 {name, columns, rows} 형태여야 합니다.")
        cols = [_text(c) for c in (sh.get("columns") or [])]
        rows = [list(r) for r in (sh.get("rows") or []) if isinstance(r, (list, tuple))]
        if not cols and rows:
            cols = [f"열{j + 1}" for j in range(max(len(r) for r in rows))]
        if not cols:
            raise ValueError(f"{i}번째 시트에 열 이름(columns)이 없습니다.")
        ws = wb.add_worksheet(_sheet_name(sh.get("name") or sh.get("title") or "", i, used))
        r0 = 0
        if _text(sh.get("title")):
            ws.write_string(0, 0, _text(sh["title"]), f_title)
            ws.set_row(0, 24)
            r0 = 2
        widths = [_width(c) for c in cols]
        ws.set_row(r0, 22)
        for j, c in enumerate(cols):
            ws.write_string(r0, j, c, f_head)
        for r, row in enumerate(rows, r0 + 1):
            for j in range(len(cols)):
                v = row[j] if j < len(row) else None
                if isinstance(v, bool) or v is None:
                    ws.write_string(r, j, "" if v is None else ("예" if v else "아니오"), f_cell)
                elif isinstance(v, int):
                    ws.write_number(r, j, v, f_int)
                elif isinstance(v, float):
                    ws.write_number(r, j, v, f_num if v != int(v) else f_int)
                else:
                    s = str(v)
                    if s.startswith("=") and len(s) > 1:
                        ws.write_formula(r, j, s, f_cell)
                    else:
                        ws.write_string(r, j, s, f_wrap if len(s) > 60 or "\n" in s else f_cell)
                widths[j] = max(widths[j], min(_width(v), 60))
        for j, w in enumerate(widths):
            ws.set_column(j, j, min(max(w, 6), 60))
        ws.freeze_panes(r0 + 1, 0)
        if rows:
            ws.autofilter(r0, 0, r0 + len(rows), len(cols) - 1)
        spec = sh.get("chart")
        if isinstance(spec, dict) and rows:
            _excel_chart(wb, ws, spec, cols, rows, r0, _text(sh.get("title")))
        total += len(rows)
    try:
        wb.close()
    except xlsxwriter.exceptions.FileCreateError as e:     # 같은 파일이 엑셀에 열려 있다 → 다른 파일 형식과 같게 알린다
        raise PermissionError(str(e)) from e
    return {"sheets": len(sheets), "rows": total}
