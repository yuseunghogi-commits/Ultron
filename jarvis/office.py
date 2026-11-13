"""작업 결과물 만들기 — 발표 자료(PowerPoint) · 보고서(Word) · 표(Excel).

울트론이 "OO 자료조사해서 PPT 만들어 줘" 같은 일을 끝까지 해내도록, Claude 가 조사해서 짠 내용을 실제 파일로 만든다.
  · build_presentation: 16:9 PowerPoint — 표지 · 목차 · 본문(목록 · 장 구분 · 비교 · 숫자 · 인용 · 마무리) · 참고 자료.
    장마다 발표 대본(슬라이드 노트)을 넣는다. 글이 많으면 글자를 줄이고, 그래도 넘치면 다음 장으로 나눈다.
  · build_document: Word 보고서 — 표지(아이콘 · 큰 제목) · 목차 · 장(제목 · 문단 · 목록 · 표 · 강조 상자) · 참고 자료 ·
    머리글 · 쪽 번호 (본문부터 1쪽).
  · build_spreadsheet: Excel — 시트마다 제목 · 머리글 · 행. 칸 너비 자동, 머리글 고정 · 거르기. '=' 로 시작하면 수식.
글꼴은 Windows 기본 한글 글꼴(맑은 고딕). 이 파일은 파일만 만든다 (저장 폴더 고르기 · 열기는 tools.py).
라이브러리(python-pptx · python-docx · XlsxWriter)는 쓸 때 불러온다 — 없어도 울트론의 다른 기능은 그대로 켜진다.
"""
from __future__ import annotations

import datetime
import io
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
    """이 너비에서 몇 줄이 되는가. 파워포인트는 한글도 띄어쓰기 단위로 줄을 바꾸므로 낱말 단위로 채워 본다
    (글자 수만 세면 좁은 칸에서 줄 수를 적게 어림해 글이 겹친다). 한 줄보다 긴 낱말은 글자 단위로 끊는다."""
    per_line = max(1.0, width_in * 72 / size)
    lines, used = 1, 0.0
    for word in str(text).split(" "):
        w = _em(word)
        if not w:
            continue
        if used and used + 0.3 + w > per_line:           # 이 낱말은 다음 줄로
            lines, used = lines + 1, 0.0
        if w > per_line:                                  # 한 줄보다 긴 낱말
            extra = math.ceil(w / per_line) - 1
            lines, used = lines + extra, w - extra * per_line
        else:
            used += (0.3 if used else 0.0) + w
    return lines


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
THEMES.update({
    "purple": Theme("FFFFFF", "F5F1FF", "24173F", "32284A", "756C8F", "7C4DFF", "DCCFFF", "FFFFFF"),
    "teal": Theme("F7FCFC", "E3F4F4", "0E3B43", "1F4A52", "5F8087", "0E9AA7", "B9E6EA", "FFFFFF"),
    "rose": Theme("FFF9FA", "FDEBEF", "43202B", "55323D", "8E6B75", "E0527A", "F9CBD8", "FFFFFF"),
    "mono": Theme("FFFFFF", "F3F3F3", "111111", "2B2B2B", "767676", "FFC400", "FFE89A", "111111"),
    "midnight": Theme("12122B", "1D1D42", "FFFFFF", "DAD9F0", "9C9BC2", "9D7BFF", "3A3470", "12122B"),
    "forest": Theme("10231B", "1A3327", "F3FAF5", "D5E7DC", "93AD9F", "6FCF97", "254D3A", "10231B"),
})
LAYOUTS = ("bullets", "section", "two_column", "stats", "chart", "timeline", "process", "cards", "table", "highlight",
           "quote", "closing")
CHARTS = ("column", "bar", "line", "pie")
# 디자인 스타일 (deck.py 가 그린다) — 표지 · 제목 자리 · 카드 · 장식이 서로 완전히 다르다
STYLES = ("clean", "bold", "side", "tech", "editorial", "pastel", "corporate")
STYLE_NAMES = {"clean": "깔끔", "bold": "강렬", "side": "사이드바", "tech": "테크", "editorial": "매거진", "pastel": "파스텔",
               "corporate": "비즈니스"}
_STYLE_WORDS = {"깔끔": "clean", "미니멀": "clean", "심플": "clean", "단순": "clean", "강렬": "bold", "볼드": "bold",
                "임팩트": "bold", "화려": "bold", "눈에 띄": "bold", "사이드바": "side", "모던": "side", "세련": "side",
                "테크": "tech", "기술": "tech", "미래": "tech", "사이버": "tech", "매거진": "editorial", "잡지": "editorial",
                "고급": "editorial", "클래식": "editorial", "차분": "editorial", "파스텔": "pastel", "귀여": "pastel",
                "귀엽": "pastel", "아기자기": "pastel", "발랄": "pastel", "비즈니스": "corporate", "회사": "corporate",
                "보고": "corporate", "공식": "corporate", "격식": "corporate"}
# 스타일마다 잘 어울리는 색 (색을 말하지 않았을 때 이 가운데서 고른다)
STYLE_THEMES = {"clean": ("light", "green", "purple", "teal", "rose", "warm"),
                "bold": ("light", "purple", "rose", "teal", "warm", "mono", "dark"),
                "side": ("light", "teal", "purple", "green", "mono", "navy"),
                "tech": ("navy", "midnight", "dark", "forest"),
                "editorial": ("warm", "mono", "light", "forest", "teal"),
                "pastel": ("rose", "warm", "green", "purple", "light", "teal"),
                "corporate": ("light", "teal", "mono", "green", "navy")}
W, H, M = 13.333, 7.5, 0.8            # 슬라이드 크기 · 좌우 여백 (인치)
BODY_SIZES = (26, 24, 22, 20, 18, 16)


_NUMBERED = re.compile(r"^\s*(?:제?\s*\d{1,2}\s*[부장]\s*[·:.\-–—]?|part\s*\d{1,2}\s*[:.\-–—]?|chapter\s*\d{1,2}\s*[:.\-–—]?|\d{1,2}\s*[.)])\s*", re.I)


def unnumbered(title: str) -> str:
    """'1. 원인' · '2부 · 영향' · 'Part 3: 대책' → '원인' · '영향' · '대책' (제목만 남으면 그대로 둔다)."""
    t = _NUMBERED.sub("", title or "", count=1).strip()
    return t or (title or "").strip()


def _seed(text: str) -> int:
    import hashlib
    return int(hashlib.md5((text or "").encode("utf-8")).hexdigest()[:8], 16)


# 주제 · 듣는 사람에 어울리는 스타일 (앞에서부터 먼저 맞는 것). 어느 것에도 안 맞으면 무난한 다섯 가지 가운데서 고른다
_STYLE_POOLS = (
    (re.compile(r"초등|유치|어린이|저학년|아이들"), ("pastel", "bold", "clean")),
    (re.compile(r"회사|임원|팀장|부장|대표|보고|비즈니스|사업|실적|매출|전략|기획안|제안서|투자", re.I), ("corporate", "side", "clean", "bold")),
    (re.compile(r"인공\s*지능|\bAI\b|로봇|우주|반도체|컴퓨터|코딩|프로그래밍|데이터|블록체인|메타버스|디지털|양자|드론|자율\s*주행|소프트웨어|"
                r"사이버|해킹|보안|게임|\bIT\b", re.I), ("tech", "side", "bold", "clean")),
    (re.compile(r"전쟁|역사|문학|철학|조선|고려|삼국|독립|민주|인권|헌법|근대|세계사|한국사|소설|작가|예술|미술|고전|사상|종교|인물"),
     ("editorial", "clean", "side", "corporate")),
    (re.compile(r"여행|음식|요리|동물|반려|취미|우리\s*반|학급|친구|가족|놀이|축제|동아리|소개|꿈|장래"), ("pastel", "bold", "clean", "side")),
)
_STYLE_DEFAULT = ("clean", "bold", "side", "editorial", "corporate")


def pick_style(style: str, title: str, audience: str = "", avoid: str = "") -> str:
    """디자인 스타일을 정한다. 이름(영어 · 한국어)을 주면 그것으로. 없으면 주제 · 듣는 사람에 어울리는 것들 가운데
    제목에 따라 고르되, 바로 앞에 쓴 스타일(avoid)은 피한다 — 만들 때마다 같은 모양이 나오지 않게."""
    s = (style or "").strip().lower()
    if s in STYLES:
        return s
    for word, name in _STYLE_WORDS.items():
        if word in s:
            return name
    about = f"{title} {audience}"
    pool = next((names for pattern, names in _STYLE_POOLS if pattern.search(about)), _STYLE_DEFAULT)
    k = _seed(title) % len(pool)
    for name in pool[k:] + pool[:k]:
        if name != avoid:
            return name
    return pool[k]


def pick_theme(theme: str, style: str, title: str) -> str:
    """색 테마를 정한다. 이름을 주면 그것으로, 없으면 그 스타일에 어울리는 색 가운데 제목에 따라 고른다."""
    t = (theme or "").strip().lower()
    if t in THEMES:
        return t
    choices = STYLE_THEMES.get(style, ("light",))
    return choices[(_seed(title) // 7) % len(choices)]


def _items(v) -> list:
    if v is None:
        return []
    if isinstance(v, str):
        return [line for line in v.splitlines() if line.strip()]
    if isinstance(v, (list, tuple)):
        return list(v)
    return [v]


_SPLIT = r"\s*[:：]\s+|\s+[—–-]\s+|\s*\|\s*"
_LEAD = r"^(?:[-–—•●▪◦·*]|\d+[.)])\s+"


def pairs(v) -> list[dict]:
    """[{title, text}] 로 읽는다 (단계 · 카드): dict 그대로 · '제목: 설명' · '제목 — 설명' · 글자만."""
    out = []
    for x in _items(v):
        if isinstance(x, dict):
            title = _text(x.get("title") or x.get("heading") or x.get("name") or x.get("label"))
            text = _text(x.get("text") or x.get("desc") or x.get("description") or x.get("detail"))
            if not text and x.get("bullets"):
                text = " · ".join(_text(b) for b in _strings(x.get("bullets")))
        else:
            parts = re.split(_SPLIT, re.sub(_LEAD, "", str(x).strip()), maxsplit=1)
            title, text = (_text(parts[0]), _text(parts[1]) if len(parts) > 1 else "")
        if title or text:
            out.append({"title": title or text, "text": text if title else ""})
            if isinstance(x, dict) and _text(x.get("icon")):
                out[-1]["icon"] = _text(x.get("icon"))           # 작가가 고른 아이콘 (Material Icons 이름)
    return out


def events(v) -> list[dict]:
    """[{when, title, text}] 로 읽는다 (연표): dict 그대로 · '1950: 전쟁 발발 — 설명' · '1950 | 전쟁 발발'."""
    out = []
    for x in _items(v):
        if isinstance(x, dict):
            when = _text(x.get("when") or x.get("date") or x.get("year") or x.get("time"))
            title = _text(x.get("title") or x.get("event") or x.get("name"))
            text = _text(x.get("text") or x.get("desc") or x.get("description") or x.get("detail"))
        else:
            parts = [_text(p) for p in re.split(_SPLIT, re.sub(_LEAD, "", str(x).strip()), maxsplit=2)]
            when, title, text = (parts + ["", ""])[:3]
            if not title:
                when, title = "", when
        if when or title:
            out.append({"when": when, "title": title, "text": text})
    return out


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


_DISTINCT = ("2F5BEA", "E5702F", "2E9D63", "E0527A", "7C4DFF", "0E9AA7", "F2B705", "8B705E")


def _hue(hex_: str) -> tuple[float, float, float]:
    import colorsys
    r, g, b = (int(hex_[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return colorsys.rgb_to_hls(r, g, b)


def palette(t: "Theme") -> list[str]:
    """차트 색: 테마의 강조색부터, 그다음은 색상(hue)이 뚜렷이 다른 색들 — 같은 색의 밝기만 다르면 원 차트 · 여러 막대를 구분하기 어렵다.
    어두운 바탕에서는 조금 밝게, 밝은 바탕에서는 그대로."""
    ah, al, as_ = _hue(t.accent)
    out = [t.accent]
    for c in _DISTINCT:
        h, l, s_ = _hue(c)
        gap = min(abs(h - ah), 1 - abs(h - ah))
        if as_ > 0.15 and gap < 0.07:              # 강조색과 거의 같은 색은 건너뛴다
            continue
        bg_dark = _hue(t.bg)[1] < 0.4
        out.append(_hexmix(c, "FFFFFF", 0.18) if bg_dark else c)
    return out[:7]


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


def build_presentation(path: Path, title: str, slides: list, subtitle: str = "", sources=None,
                       theme: str = "light", agenda: bool | None = None, style: str = "clean") -> dict:
    """발표 자료를 만든다 → {'slides': 장 수, 'notes': 대본을 넣은 장 수, 'split': 넘쳐서 나눈 장 수, 'style', 'theme'}."""
    from .deck import Deck
    title = _text(title)
    if not title:
        raise ValueError("발표 제목(title)이 필요합니다.")
    if not isinstance(slides, list) or not slides:
        raise ValueError("슬라이드(slides)가 하나 이상 필요합니다.")
    if len(slides) > MAX_SLIDES:
        raise ValueError(f"슬라이드가 너무 많습니다 ({len(slides)}장). {MAX_SLIDES}장 이하로 나눠 만드세요.")
    theme = (theme or "light").strip().lower()
    theme = theme if theme in THEMES else "light"
    style = (style or "clean").strip().lower()
    style = style if style in STYLES else "clean"
    deck = Deck(THEMES[theme], title, style)
    deck.cover(title, _text(subtitle))
    clean = []
    for i, raw in enumerate(slides, 1):
        if not isinstance(raw, dict):
            raw = {"title": str(raw)}
        layout = str(raw.get("layout") or "bullets").strip().lower().replace("-", "_")
        if layout not in LAYOUTS:
            layout = "bullets"
        name = _text(raw.get("title")) or f"{i}"
        clean.append((layout, unnumbered(name) if layout == "section" else name, raw))
    if agenda is None:
        agenda = sum(1 for lay, _, _ in clean if lay not in ("closing", "quote")) >= 4
    if agenda:
        sections = [name for lay, name, _ in clean if lay == "section"]            # 장 구분이 둘 이상이면 그 제목들로
        deck.agenda(sections if len(sections) >= 2 else [name for lay, name, _ in clean if lay not in ("closing", "quote")])
    split = 0
    part = 0
    width, height = deck.body

    def listed(name, items, notes):
        """목록 장 (넘치면 여러 장으로 나눈다) → 더 만든 장 수."""
        if items and fit_size(items, width, height) is None:
            parts = split_items(items, width, height, 18)
            for k, chunk in enumerate(parts):
                deck.bullet_slide(name if k == 0 else f"{name} (계속)", chunk, notes if k == 0 else "")
            return len(parts) - 1
        deck.bullet_slide(name, items, notes)
        return 0

    for layout, name, raw in clean:
        notes = str(raw.get("notes") or "")
        outline = raw.get("bullets") or raw.get("points")          # points: 개요만 받은 경우 (작가가 쓰지 못했을 때도 그린다)
        items = parse_bullets(outline)
        if layout == "section":
            part += 1
            deck.section(part, name, items, notes, raw.get("icon"))
        elif layout == "two_column":
            side = [x if isinstance(x, dict) else {"heading": "", "bullets": _strings(x)} for x in (raw.get("left"), raw.get("right"))]
            if not any(side[k].get("bullets") or side[k].get("points") for k in (0, 1)) and items:
                half = (len(items) + 1) // 2                     # 개요만 있으면 반씩 나눠 두 칸에
                side = [{"heading": "", "bullets": [t for t, _ in items[:half]]}, {"heading": "", "bullets": [t for t, _ in items[half:]]}]
            deck.two_column(name, side[0] or {}, side[1] or {}, notes)
        elif layout == "stats":
            stats = [x if isinstance(x, dict) else dict(zip(("value", "label"), (re.split(r"\s*\|\s*|\s+[—–-]\s+|\s*:\s+", str(x), maxsplit=1) + [""])[:2]))
                     for x in (raw.get("stats") or _strings(outline))]
            deck.stats(name, stats, notes)
        elif layout == "chart":
            spec = raw.get("chart") if isinstance(raw.get("chart"), dict) else raw
            if not deck.chart(name, spec, items, notes):          # 차트로 그릴 수 없는 데이터 → 목록 장 (실패시키지 않는다)
                rows = [(f"{_text(c)}: {', '.join(_text(v) for v in vals)}", 0)
                        for c, *vals in zip(_listish(spec.get("categories")), *[_listish(x.get("values")) for x in
                                                                               _listish(spec.get("series")) if isinstance(x, dict)])]
                split += listed(name, items + rows or [("(차트 데이터 없음)", 0)], notes)
        elif layout == "timeline":
            ev = events(raw.get("events") or outline)
            if len(ev) >= 2:
                deck.timeline(name, ev, notes)
            else:
                split += listed(name, items, notes)
        elif layout in ("process", "cards"):
            got = pairs(raw.get("steps" if layout == "process" else "cards") or outline)
            if len(got) >= 2:
                (deck.process if layout == "process" else deck.cards)(name, got, notes)
            else:
                split += listed(name, items, notes)
        elif layout == "table":
            spec = raw.get("table") if isinstance(raw.get("table"), dict) else raw
            if not deck.table(name, spec, notes):
                split += listed(name, items, notes)
        elif layout == "highlight":
            statement = _text(raw.get("statement")) or (items[0][0] if items else name)
            detail = _text(raw.get("detail")) or (items[1][0] if len(items) > 1 and not _text(raw.get("statement")) else "")
            deck.highlight(name, statement, detail, notes, raw.get("icon"))
        elif layout == "quote":
            deck.quote(name, _text(raw.get("quote")) or (items[0][0] if items else name), _text(raw.get("by")), notes)
        elif layout == "closing":
            deck.closing(name, items, notes, raw.get("icon"))
        else:
            split += listed(name, items, notes)
    refs = [pretty_ref(_text(r)) for r in _strings(sources)]
    if refs:
        deck.sources(refs)
    deck.prs.core_properties.title = title
    deck.prs.core_properties.author = "U.L.T.R.O.N"
    deck.prs.save(str(path))
    return {"slides": deck.count, "notes": deck.notes, "split": split, "style": style, "theme": theme}


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
    # 기본 서식의 '테마 글꼴' 표시가 남아 있으면 워드는 그쪽을 먼저 쓴다 → 맑은 고딕이 적용되지 않으므로 지운다
    for attr in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
        if fonts.get(qn(attr)) is not None:
            del fonts.attrib[qn(attr)]


_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_KEY = re.compile(r"^([^:：]{1,24})[:：]\s+(.+)$")


def rich_parts(text: str, keyword: bool = False) -> list[tuple[str, bool]]:
    """글 → (조각, 굵게?) 목록. **굵게** 표시를 굵은 글자로, keyword=True 면 '핵심어: 설명' 의 핵심어도 굵게 (발표 자료와 같게)."""
    text = text.strip()
    if keyword and "**" not in text:
        m = _KEY.match(text)
        if m and not re.search(r"https?$", m.group(1)):
            return [(m.group(1) + ": ", True), (m.group(2), False)]
    out, last = [], 0
    for m in _BOLD.finditer(text):
        if m.start() > last:
            out.append((text[last:m.start()], False))
        out.append((m.group(1), True))
        last = m.end()
    if last < len(text):
        out.append((text[last:], False))
    return [(t, b) for t, b in out if t] or [("", False)]


_NUM_UNIT = re.compile(r"^[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\s*(?:%|％|℃|°C|명|원|만 ?원|억 ?원|개|건|회|배|위|점|년|월|일|시간|분|초|"
                       r"t|kg|g|km|m|cm|mm|ppm|GW|MW|kWh|L|ml)?$")


def numeric_text(v) -> bool:
    """표 칸이 숫자(+단위)인가 — '86.9' · '1,200명' · '73%' 는 예, '3학년 2반' · '2021년 착륙' 은 아니오."""
    return isinstance(v, (int, float)) and not isinstance(v, bool) or bool(_NUM_UNIT.match(_text(v)))


def _table_borders(table, color: str = "B8C2D6") -> None:
    """표 테두리를 얇고 연한 색으로 (기본 '표 눈금'은 검고 진하다)."""
    from docx.oxml.ns import qn
    tblpr = table._tbl.tblPr
    old = tblpr.find(qn("w:tblBorders"))
    if old is not None:
        tblpr.remove(old)
    borders = tblpr.makeelement(qn("w:tblBorders"), {})
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        borders.append(borders.makeelement(qn(f"w:{side}"), {qn("w:val"): "single", qn("w:sz"): "6", qn("w:space"): "0",
                                                             qn("w:color"): color}))
    tblpr.append(borders)


def _repeat_header(row) -> None:
    """표가 다음 쪽으로 넘어가면 머리줄을 다시 보여 준다."""
    from docx.oxml.ns import qn
    trpr = row._tr.get_or_add_trPr()
    trpr.append(trpr.makeelement(qn("w:tblHeader"), {qn("w:val"): "true"}))


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


DOC = {"ink": "16213A", "accent": "1F3A8A", "bright": "2F5BEA", "muted": "6B7487", "line": "C9D3E6", "soft": "EEF2FB",
       "zebra": "F5F7FB"}                       # 보고서 색: 글 · 제목 · 강조 · 흐린 글 · 선 · 강조 상자 · 표 줄무늬
_HEAD_NUM = re.compile(r"^(?:제\s*)?(?:\d{1,2}(?:[.\-]\d{1,2})*[.)]?|[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]{1,4}[.)]?)(?=\s)")
_PPR_ORDER = ("pStyle", "keepNext", "keepLines", "pageBreakBefore", "framePr", "widowControl", "numPr", "suppressLineNumbers",
              "pBdr", "shd", "tabs", "suppressAutoHyphens", "kinsoku", "wordWrap", "overflowPunct", "topLinePunct",
              "autoSpaceDE", "autoSpaceDN", "bidi", "adjustRightInd", "snapToGrid", "spacing", "ind", "contextualSpacing",
              "mirrorIndents", "suppressOverlap", "jc", "textDirection", "textAlignment", "textboxTightWrap", "outlineLvl",
              "divId", "cnfStyle", "rPr", "sectPr", "pPrChange")


def _ppr_child(p, tag: str):
    """문단 속성(pPr)의 자식 하나를 스키마 순서에 맞는 자리에 만든다 (있으면 그것)."""
    from docx.oxml.ns import qn
    ppr = p._p.get_or_add_pPr()
    el = ppr.find(qn(f"w:{tag}"))
    if el is None:
        el = ppr.makeelement(qn(f"w:{tag}"), {})
        later = _PPR_ORDER[_PPR_ORDER.index(tag) + 1:]
        ppr.insert_element_before(el, *[f"w:{t}" for t in later])
    return el


def _pborder(p, sides: dict) -> None:
    """문단 테두리: {'left': (굵기 1/8pt, 색, 띄움 pt), …} — 제목 밑줄 · 강조 상자의 띠."""
    from docx.oxml.ns import qn
    bdr = _ppr_child(p, "pBdr")
    for side in ("top", "left", "bottom", "right", "between"):                # (스키마 순서)
        if side in sides:
            size, color, space = sides[side]
            bdr.append(bdr.makeelement(qn(f"w:{side}"), {qn("w:val"): "single", qn("w:sz"): str(size),
                                                         qn("w:space"): str(space), qn("w:color"): color}))


def _pshade(p, fill: str) -> None:
    from docx.oxml.ns import qn
    shd = _ppr_child(p, "shd")
    for k, v in (("w:val", "clear"), ("w:color", "auto"), ("w:fill", fill)):
        shd.set(qn(k), v)


def _track(run, points: float) -> None:
    """글자 사이를 띄운다 (표지의 'REPORT' 같은 작은 글)."""
    from docx.oxml.ns import qn
    rpr = run._r.get_or_add_rPr()
    el = rpr.makeelement(qn("w:spacing"), {qn("w:val"): str(round(points * 20))})
    rpr.insert_element_before(el, "w:w", "w:kern", "w:position", "w:sz", "w:szCs", "w:highlight", "w:u", "w:effect",
                              "w:bdr", "w:shd", "w:fitText", "w:vertAlign", "w:rtl", "w:cs", "w:em", "w:lang",
                              "w:eastAsianLayout", "w:specVanish", "w:oMath")


def _run(p, text: str, size: float | None = None, color: str | None = None, bold: bool | None = None):
    from docx.shared import Pt, RGBColor
    run = p.add_run(text)
    if size:
        run.font.size = Pt(size)
    if color:
        run.font.color.rgb = RGBColor.from_string(color)
    if bold is not None:
        run.bold = bold
    return run


def _rich_paragraph(doc, text: str, style: str | None = None, keyword: bool = False):
    p = doc.add_paragraph(style=style)
    for part, bold in rich_parts(text, keyword):
        run = p.add_run(part)
        if bold:
            run.bold = True
            if keyword:
                from docx.shared import RGBColor
                run.font.color.rgb = RGBColor.from_string(DOC["accent"])     # 목록의 핵심어는 제목 색으로
    return p


def _space(p, before: float = 0, after: float = 0, line: float | None = None):
    from docx.shared import Pt
    f = p.paragraph_format
    f.space_before, f.space_after = Pt(before), Pt(after)
    if line is not None:
        f.line_spacing = line
    return p


def _bar_png(color: str, w: int = 320, h: int = 20) -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (w, h), tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))).save(buf, "PNG")
    return buf.getvalue()


def _cover(doc, title: str, subtitle: str, icon: str = "") -> None:
    """표지: 위에 'REPORT' 띠, 가운데에 아이콘 · 큰 제목 · 짧은 강조 막대, 아래 오른쪽에 과목 · 이름 · 날짜."""
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Cm
    from . import icons
    c = DOC
    p = _space(doc.add_paragraph(), 0, 0)
    _track(_run(p, "REPORT", 10, c["bright"], True), 3)
    _pborder(p, {"bottom": (8, c["ink"], 6)})
    lines = _lines(title, 32, 6.3)
    mark = icons.pick(icon, title, subtitle, kind="cover")
    art = icons.png(mark, c["bright"], 400) if mark else None
    gap = max(50, 165 - 45 * max(0, lines - 2))
    p = _space(doc.add_paragraph(), gap, 12)
    if art:
        p.add_run().add_picture(io.BytesIO(art), width=Cm(2.7))
    t = doc.add_paragraph(style="Title")
    _run(t, title)
    _space(t, 0, 10, 1.15)
    p = _space(doc.add_paragraph(), 0, 0)
    p.add_run().add_picture(io.BytesIO(_bar_png(c["bright"])), width=Cm(2.6), height=Cm(0.16))
    info = [x for x in re.split(r"\s*[·|/]\s*|\n", _text(subtitle)) if x.strip()][:5]
    if not re.search(r"(?:19|20)\d\d", _text(subtitle)):
        info.append(datetime.date.today().strftime("%Y. %m. %d."))         # 제출일 (부제에 날짜가 없으면 오늘)
    used = 32 + gap + 90 + lines * 32 * 1.5 + 12 + 14 + len(info) * 21      # 맑은 고딕의 줄 높이로 어림 (pt)
    for i, line in enumerate(info):                                    # 아래쪽으로 밀어 둔다 (쪽을 넘지 않게 넉넉히)
        p = _space(doc.add_paragraph(), max(24, 640 - used) if i == 0 else 0, 0, 1.3)
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        _run(p, line, 13 if i == 0 else 12, c["ink"] if i == 0 else c["muted"], i == 0)


def _contents(doc, entries: list[tuple[int, str]]) -> None:
    """목차 쪽: 큰 장 제목에는 번호(강조색)와 점선, 작은 제목은 들여 쓴다. (쪽 번호는 워드가 고칠 수 있게 두지 않는다)"""
    from docx.shared import Cm
    c = DOC
    p = _space(doc.add_paragraph(), 0, 2)
    _track(_run(p, "CONTENTS", 10, c["bright"], True), 3)
    p = _space(doc.add_paragraph(), 0, 18)
    _run(p, "목차", 24, c["ink"], True)
    n = 0
    for level, text in entries:
        m = _HEAD_NUM.match(text)
        if level == 1:
            n += 1
            num, rest = (m.group(0).strip().rstrip(".)"), text[m.end():].strip()) if m else (f"{n:02d}", text)
            num = f"{int(num):02d}" if num.isdigit() else num
            p = _space(doc.add_paragraph(), 6, 6, 1.2)
            p.paragraph_format.tab_stops.add_tab_stop(Cm(1.6))
            _run(p, num, 14, c["bright"], True)
            _run(p, "\t" + rest, 13, c["ink"], True)
            _pborder(p, {"bottom": (4, c["line"], 6), "between": (4, c["line"], 6)})   # 이어진 줄마다 선 (한 덩어리로 묶이지 않게)
        else:
            p = _space(doc.add_paragraph(), 0, 2, 1.2)
            p.paragraph_format.left_indent = Cm(1.6)
            _run(p, text, 11, c["muted"])


def _heading(doc, text: str, level: int):
    """장 제목: 큰 제목은 번호를 강조색으로 + 연한 밑줄, 작은 제목은 왼쪽 띠."""
    from docx.shared import Cm
    c = DOC
    p = doc.add_paragraph(style=f"Heading {level}")
    m = _HEAD_NUM.match(text)
    if level == 1:
        if m:
            _run(p, m.group(0), color=c["bright"])
            _run(p, text[m.end():], color=c["ink"])
        else:
            _run(p, text, color=c["ink"])
        _pborder(p, {"bottom": (8, c["line"], 5)})
    else:
        _run(p, text, color=c["accent"])
        p.paragraph_format.left_indent = Cm(0.25)
        _pborder(p, {"left": (24, c["bright"], 6)})
    return p


def _box(doc, lines: list[str], label: str) -> None:
    """강조 상자 (연한 바탕 + 왼쪽 강조 띠): 첫 줄에 이름표, 그 아래 줄들. 같은 테두리의 문단들은 한 상자로 붙는다."""
    from docx.shared import Cm
    c = DOC
    sides = {"top": (4, c["soft"], 8), "left": (36, c["bright"], 10), "bottom": (4, c["soft"], 8), "right": (4, c["soft"], 10)}
    paras = []
    if len(lines) == 1:
        p = doc.add_paragraph()
        _run(p, label + "   ", 10.5, c["bright"], True)
        for part, bold in rich_parts(lines[0]):
            _run(p, part, 11, c["ink"], True if bold else None)
        paras.append(p)
    else:
        p = doc.add_paragraph()
        _run(p, label, 11, c["bright"], True)
        paras.append(p)
        for line in lines:
            p = doc.add_paragraph()
            p.paragraph_format.first_line_indent = Cm(-0.5)
            p.paragraph_format.left_indent = Cm(0.75)
            _run(p, "•  ", 11, c["bright"], True)
            for part, bold in rich_parts(line, keyword=True):
                _run(p, part, 11, c["accent"] if bold else c["ink"], True if bold else None)
            paras.append(p)
    for i, p in enumerate(paras):
        f = p.paragraph_format
        f.left_indent = f.left_indent or Cm(0.25)
        f.right_indent = Cm(0.25)
        _space(p, 10 if i == 0 else 0, 10 if i == len(paras) - 1 else 3, 1.35)
        _pborder(p, sides)
        _pshade(p, c["soft"])


def build_document(path: Path, title: str, sections: list, subtitle: str = "", sources=None, summary=None,
                   icon: str = "") -> dict:
    """보고서를 만든다 → {'sections': 장 수, 'tables': 표 수}.
    표지(아이콘 · 큰 제목 · 과목 · 이름 · 날짜) → 목차(큰 장 제목이 셋 이상일 때) → 본문(머리글 · 쪽 번호는 본문부터 1).
    summary: 본문 맨 앞의 '핵심 요약' 상자, 장마다 callout: 그 장의 핵심 한 문장 상자."""
    from docx import Document
    from docx.enum.section import WD_SECTION
    from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_ROW_HEIGHT_RULE, WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.shared import Cm, Mm, Pt, RGBColor
    title = _text(title)
    if not title:
        raise ValueError("문서 제목(title)이 필요합니다.")
    if not isinstance(sections, list) or not sections:
        raise ValueError("내용(sections)이 하나 이상 필요합니다.")
    c = DOC
    doc = Document()
    for sec in doc.sections:
        sec.page_width, sec.page_height = Mm(210), Mm(297)          # A4 (기본 서식은 미국 레터 크기)
        sec.top_margin = sec.bottom_margin = Cm(2.5)
        sec.left_margin = sec.right_margin = Cm(2.4)
        sec.header_distance = sec.footer_distance = Cm(1.2)
    normal = doc.styles["Normal"]
    _docx_font(normal.font, normal.element)
    normal.font.size = Pt(11)
    normal.font.color.rgb = RGBColor.from_string("2A3346")
    normal.paragraph_format.line_spacing = 1.6
    normal.paragraph_format.space_after = Pt(6)
    for name, size in (("Title", 32), ("Heading 1", 16), ("Heading 2", 13), ("List Bullet", 11), ("List Number", 10)):
        st = doc.styles[name]
        _docx_font(st.font, st.element)
        st.font.size = Pt(size)
        if name.startswith(("Title", "Heading")):
            st.font.bold = True
            st.font.color.rgb = RGBColor.from_string(c["ink"] if name == "Title" else c["accent"])
            ppr = st.element.pPr
            old = ppr.find(qn("w:pBdr")) if ppr is not None else None
            if old is not None:
                ppr.remove(old)                                     # 기본 서식의 파란 밑줄은 떼고 직접 그린다
        if name == "Heading 1":
            st.paragraph_format.space_before, st.paragraph_format.space_after = Pt(22), Pt(10)
        elif name == "Heading 2":
            st.paragraph_format.space_before, st.paragraph_format.space_after = Pt(14), Pt(6)
    clean = [s if isinstance(s, dict) else {"paragraphs": [str(s)]} for s in sections]
    heads = [(2 if str(s.get("level", 1)).strip() == "2" else 1, _text(s.get("heading"))) for s in clean]
    heads = [(lvl, h) for lvl, h in heads if h]
    _cover(doc, title, _text(subtitle), icon)
    if sum(1 for lvl, _ in heads if lvl == 1) >= 3:                 # 목차 (표지와 같이 쪽 번호 없는 앞부분)
        doc.add_page_break()
        _contents(doc, heads + ([(1, "참고 자료")] if _strings(sources) else []))
    body = doc.add_section(WD_SECTION.NEW_PAGE)                    # 본문: 머리글 · 쪽 번호
    brk = doc.paragraphs[-1]._p                                     # 앞부분(표지 · 목차)의 끝 표시가 든 빈 문단
    prev = brk.getprevious()
    if prev is not None and prev.tag == qn("w:p"):                  # 그 표시를 앞 문단으로 옮긴다 (빈 줄이 넘쳐 빈 쪽이 생기지 않게)
        sect = brk.find(qn("w:pPr")).find(qn("w:sectPr"))
        prev.get_or_add_pPr().insert_element_before(sect, "w:pPrChange")
        brk.getparent().remove(brk)
    pg = body._sectPr.makeelement(qn("w:pgNumType"), {qn("w:start"): "1"})
    body._sectPr.insert_element_before(pg, "w:cols", "w:formProt", "w:vAlign", "w:noEndnote", "w:titlePg",
                                       "w:textDirection", "w:bidi", "w:rtlGutter", "w:docGrid", "w:printerSettings",
                                       "w:sectPrChange")
    body.footer.is_linked_to_previous = False
    foot = body.footer.paragraphs[0]
    foot.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _page_number(foot)
    for r in foot.runs:
        r.font.size, r.font.bold = Pt(9), True
        r.font.color.rgb = RGBColor.from_string(c["bright"])
    body.header.is_linked_to_previous = False
    head = body.header.paragraphs[0]
    head.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    _run(head, title, 8.5, c["muted"])
    _pborder(head, {"bottom": (4, c["line"], 4)})
    points = [_text(x) for x in _strings(summary) if _text(x)]
    if points:
        _box(doc, points[:6], "핵심 요약")
    tables = 0
    for sec in clean:
        heading = _text(sec.get("heading"))
        level = 2 if str(sec.get("level", 1)).strip() == "2" else 1
        if heading:
            _heading(doc, heading, level)
        for para in _strings(sec.get("paragraphs")):
            p = _rich_paragraph(doc, para)
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        outline = sec.get("points") if not (sec.get("paragraphs") or sec.get("bullets")) else None   # 개요만 받은 장
        for line, lvl in parse_bullets(sec.get("bullets") or outline):
            p = _rich_paragraph(doc, line, "List Bullet", keyword=not lvl)
            if lvl:
                p.paragraph_format.left_indent = Cm(1.6)
        table = sec.get("table")
        if isinstance(table, dict) and table.get("columns"):
            cols = [_text(x) for x in table["columns"]]
            rows = [r for r in (table.get("rows") or []) if isinstance(r, (list, tuple))]
            t = doc.add_table(rows=1 + len(rows), cols=len(cols))
            t.style = "Table Grid"
            t.alignment = WD_TABLE_ALIGNMENT.CENTER
            _table_borders(t, c["line"])
            _repeat_header(t.rows[0])
            numeric = [all(numeric_text(r[j]) or not _text(r[j]) for r in rows if j < len(r))
                       and any(j < len(r) and _text(r[j]) for r in rows) for j in range(len(cols))]
            for row in t.rows:
                row.height, row.height_rule = Cm(0.85), WD_ROW_HEIGHT_RULE.AT_LEAST
            for j, name in enumerate(cols):
                cell = t.rows[0].cells[j]
                cell.text = name
                run = cell.paragraphs[0].runs[0]
                run.font.bold, run.font.size = True, Pt(10.5)
                run.font.color.rgb = RGBColor.from_string("FFFFFF")
                cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
                _shade(cell, c["accent"])                             # 머리줄은 진한 제목 색 + 흰 글자
            for r, row in enumerate(rows, 1):
                for j in range(len(cols)):
                    cell = t.rows[r].cells[j]
                    cell.text = _text(row[j]) if j < len(row) else ""
                    para = cell.paragraphs[0]
                    for run in para.runs:
                        run.font.size = Pt(10.5)
                        if j == 0:
                            run.font.bold = True                     # 첫 칸(항목 이름)은 굵게
                    if numeric[j]:                               # 숫자 칸은 오른쪽 맞춤 (자릿수가 맞게)
                        para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                    if r % 2 == 0:
                        _shade(cell, c["zebra"])                 # 줄무늬로 읽기 쉽게
            for row in t.rows:
                for cell in row.cells:
                    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
                    _space(cell.paragraphs[0], 2, 2, 1.2)
            if _text(table.get("caption")):
                cap = _space(doc.add_paragraph(), 4, 10)
                cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
                _run(cap, _text(table["caption"]), 9, c["muted"])
            tables += 1
        note = [_text(x) for x in _strings(sec.get("callout")) if _text(x)]
        if note:
            _box(doc, note[:3], "핵심")
    refs = [pretty_ref(_text(r)) for r in _strings(sources)]
    if refs:
        _heading(doc, "참고 자료", 1)
        for r in refs:
            p = doc.add_paragraph(r, style="List Number")
            p.runs[0].font.color.rgb = RGBColor.from_string(c["muted"])
    doc.core_properties.title = title
    doc.core_properties.author = "U.L.T.R.O.N"
    doc.save(str(path))
    return {"sections": len(sections), "tables": tables}


# ---------------------------------------------------------------- 표 (Excel)
def _width(v) -> float:
    s = str(v if v is not None else "")
    if s.startswith("="):                       # 수식은 글이 아니라 결과(숫자)가 보인다
        return 10
    return max((_em(line) * 1.9 for line in s.splitlines()), default=0.0) + 2


# ---- 칸 값 다듬기 · 수식 결과 미리 계산
_NUMLIKE = re.compile(r"^-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?$")


def cell_number(v) -> tuple[float | int, str] | None:
    """'1,025' · '86.9' · '12.5%' 처럼 숫자로 보이는 글 → (숫자, 표시 형식). 전화번호 · 우편번호처럼 0 으로 시작하면 글자로 둔다."""
    if not isinstance(v, str):
        return None
    t = v.strip()
    pct = t.endswith("%")
    core = t[:-1].strip() if pct else t
    if not _NUMLIKE.match(core) or re.match(r"^-?0\d", core):
        return None
    n = float(core.replace(",", ""))
    if pct:
        return n / 100, "0%" if n == int(n) else "0.0%"
    return (int(n), "int") if n == int(n) and "." not in core else (n, "num")


def _col_index(letters: str) -> int:
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n - 1


def eval_formula(formula: str, values: dict) -> float | None:
    """간단한 수식의 결과를 미리 계산한다 (=SUM(B3:D3), =AVERAGE(...), =B3*2+C3 …).
    엑셀은 열 때 다시 계산하지만, 미리 보기 · 휴대폰 뷰어 · 일부 프로그램은 저장된 결과만 보여 주기 때문.
    values: {(행, 열): 숫자} (0 부터). 모르는 함수 · 아직 없는 칸 · 오류면 None."""
    import ast
    import operator as op
    src = formula.lstrip("=").strip().upper()
    if not src or len(src) > 300:
        return None

    def rng(m: re.Match) -> str:
        c1, r1, c2, r2 = _col_index(m.group(1)), int(m.group(2)) - 1, _col_index(m.group(3)), int(m.group(4)) - 1
        return f"__R({min(r1, r2)},{min(c1, c2)},{max(r1, r2)},{max(c1, c2)})"
    src = re.sub(r"\$?([A-Z]{1,3})\$?(\d+):\$?([A-Z]{1,3})\$?(\d+)", rng, src)
    src = re.sub(r"(?<![A-Z_])\$?([A-Z]{1,3})\$?(\d+)(?![\d(])", lambda m: f"__C({int(m.group(2)) - 1},{_col_index(m.group(1))})", src)

    class Missing(Exception):
        pass

    def cell(r, c):
        if (r, c) not in values:
            raise Missing
        return values[(r, c)]

    def area(r1, c1, r2, c2):
        return [values[(r, c)] for r in range(r1, r2 + 1) for c in range(c1, c2 + 1) if (r, c) in values]

    def flat(args):
        out = []
        for a in args:
            out.extend(a if isinstance(a, list) else [a])
        return out

    funcs = {
        "SUM": lambda *a: sum(flat(a)),
        "AVERAGE": lambda *a: (lambda xs: sum(xs) / len(xs) if xs else None)(flat(a)),
        "MIN": lambda *a: min(flat(a)) if flat(a) else 0,
        "MAX": lambda *a: max(flat(a)) if flat(a) else 0,
        "COUNT": lambda *a: len(flat(a)),
        "ROUND": lambda x, n=0: round(x, int(n)),
        "ABS": lambda x: abs(x),
        "__R": area, "__C": cell,
    }
    ops = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv, ast.Pow: op.pow}

    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in ops:
            return ops[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            v = ev(node.operand)
            return -v if isinstance(node.op, ast.USub) else v
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in funcs and not node.keywords:
            return funcs[node.func.id](*[ev(a) for a in node.args])
        raise ValueError("지원하지 않는 수식")
    try:
        v = ev(ast.parse(src, mode="eval"))
    except (Missing, ValueError, SyntaxError, TypeError, ZeroDivisionError, OverflowError, RecursionError):
        return None
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


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
    f_pct = {k: wb.add_format({**base, "border": 1, "border_color": "#D5DBE6", "num_format": k}) for k in ("0%", "0.0%")}
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
        known: dict = {}                          # 숫자가 든 칸 (수식 결과 미리 계산용)
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
                    known[(r, j)] = v
                elif isinstance(v, float):
                    ws.write_number(r, j, v, f_num if v != int(v) else f_int)
                    known[(r, j)] = v
                else:
                    s = str(v)
                    if s.startswith("="):                 # {r} = 이 행, {first} · {last} = 첫 · 마지막 데이터 행 (행 번호를 셀 필요 없게)
                        s = s.replace("{r}", str(r + 1)).replace("{first}", str(r0 + 2)).replace("{last}", str(r0 + 1 + len(rows)))
                    num = cell_number(s)
                    if s.startswith("=") and len(s) > 1:
                        result = eval_formula(s, known)
                        if result is None:
                            ws.write_formula(r, j, s, f_num)
                        else:
                            ws.write_formula(r, j, s, f_num if result != int(result) else f_int,
                                             int(result) if result == int(result) else round(result, 10))
                            known[(r, j)] = result
                    elif num is not None:                 # '1,025' · '86.9' · '12.5%' → 계산되는 숫자로
                        n, kind = num
                        ws.write_number(r, j, n, f_int if kind == "int" else f_num if kind == "num" else f_pct[kind])
                        known[(r, j)] = n
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
