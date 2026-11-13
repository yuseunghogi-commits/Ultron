"""한글(HWPX) 문서 만들기 — 보고서를 한컴오피스 한글에서 바로 열리는 .hwpx 로 저장한다.

HWPX 는 한컴오피스의 열린 문서 형식(OWPML, KS X 6101)으로, XML 파일 몇 개를 ZIP 으로 묶은 것이다.
바탕 틀(hwpx_template/)은 python-hwpx(Apache-2.0)의 빈 문서 Skeleton.hwpx 에서 가져왔다 — hwpx_template/LICENSE-python-hwpx 참고.
그 틀의 글자 모양(charPr) · 문단 모양(paraPr) · 테두리(borderFill) 목록에 보고서용 모양을 덧붙이고, 본문(section0)에 문단을 채운다.
워드 보고서(office.build_document)와 같은 sections 를 받는다: heading · level · paragraphs · bullets · points · table · callout.
워드 보고서와 같은 모양: 표지(쪽 번호 감춤) → 목차(큰 장 제목이 셋 이상일 때) → 핵심 요약 상자 → 본문 (번호가 강조색인 장 제목 ·
왼쪽 띠가 있는 작은 제목 · 진한 머리줄의 표 · 핵심 상자). 바탕 틀에 이미 있는 요소(문단 테두리 · 채우기 · 쪽 나눔)만 쓴다.
표준 라이브러리만 쓴다 (한컴오피스가 없어도 만들 수 있다).
"""
from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .office import _HEAD_NUM, DOC, _lines, _strings, _text, numeric_text, parse_bullets, pretty_ref, rich_parts

TEMPLATE = Path(__file__).with_name("hwpx_template")
BODY_WIDTH = 42520          # A4 본문 폭 (바탕 틀의 쪽 여백 기준, HWPUNIT = 1/7200 인치)
ACCENT = "#" + DOC["accent"]  # 워드 보고서와 같은 색들
BRIGHT, INK, MUTED, LINE, SOFT = ("#" + DOC[k] for k in ("bright", "ink", "muted", "line", "soft"))


def _esc(s: str) -> str:
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", s)      # XML 에 넣을 수 없는 제어 문자


def _read(name: str) -> str:
    return (TEMPLATE / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------- 글자 · 문단 모양
@dataclass(frozen=True)
class CharSpec:
    size: float
    bold: bool = False
    italic: bool = False
    gothic: bool = False          # True = 함초롬돋움, False = 함초롬바탕
    color: str = "#000000"
    spacing: int = 0              # 자간 (%) — 'REPORT' 같은 작은 영문 글자를 띄울 때


@dataclass(frozen=True)
class ParaSpec:
    align: str                    # JUSTIFY · LEFT · CENTER · RIGHT
    left: int = 0
    right: int = 0
    intent: int = 0               # 음수면 내어쓰기
    prev: int = 0
    next: int = 0
    line: int = 160               # 줄 간격 %
    keep_next: bool = False
    border: int = 2               # 문단 테두리/배경 (borderFill 번호, 2 = 없음)
    pad: tuple = (0, 0, 0, 0)     # 테두리 안쪽 여백 (왼쪽 · 오른쪽 · 위 · 아래)
    connect: int = 0              # 1 = 같은 테두리의 이어진 문단을 한 상자로


# 바탕 틀에 글자 모양 0~6 번, 문단 모양 0~19 번, 테두리 1~2 번이 있으므로 그 뒤에 붙인다
# 테두리 · 채우기 (바탕 틀에 1~2 번이 있으므로 3 번부터)
BORDER_TABLE, BORDER_HEAD, BORDER_STRIPE, BORDER_H1, BORDER_H2, BORDER_BOX, BORDER_RULE, BORDER_TOC = 3, 4, 5, 6, 7, 8, 9, 10

CHARS: dict[str, CharSpec] = {
    "body": CharSpec(11),
    "bodyB": CharSpec(11, bold=True),
    "title": CharSpec(28, bold=True, gothic=True, color=INK),
    "subtitle": CharSpec(11, color=MUTED),
    "h1": CharSpec(16, bold=True, gothic=True, color=INK),
    "h1num": CharSpec(16, bold=True, gothic=True, color=BRIGHT),
    "h2": CharSpec(13, bold=True, gothic=True, color=ACCENT),
    "th": CharSpec(10, bold=True, gothic=True, color="#FFFFFF"),
    "td": CharSpec(10),
    "tdB": CharSpec(10, bold=True),
    "caption": CharSpec(9, color=MUTED),
    "ref": CharSpec(10, color=MUTED),
    "label": CharSpec(10, bold=True, gothic=True, color=BRIGHT, spacing=40),
    "info": CharSpec(13, bold=True, gothic=True, color=INK),
    "info2": CharSpec(12, gothic=True, color=MUTED),
    "toc": CharSpec(13, bold=True, gothic=True, color=INK),
    "tocnum": CharSpec(14, bold=True, gothic=True, color=BRIGHT),
    "toc2": CharSpec(11, gothic=True, color=MUTED),
    "tocTitle": CharSpec(24, bold=True, gothic=True, color=INK),
    "box": CharSpec(11, color=INK),
    "boxB": CharSpec(11, bold=True, color=ACCENT),
    "boxLabel": CharSpec(11, bold=True, gothic=True, color=BRIGHT),
    "keyB": CharSpec(11, bold=True, color=ACCENT),
}
PARAS: dict[str, ParaSpec] = {
    "body": ParaSpec("JUSTIFY", next=600, line=165),
    "title": ParaSpec("LEFT", next=1000, line=130),
    "subtitle": ParaSpec("CENTER", next=1400, line=130),
    "h1": ParaSpec("LEFT", prev=2200, next=900, line=130, keep_next=True, border=BORDER_H1, pad=(0, 0, 0, 500)),
    "h2": ParaSpec("LEFT", left=700, prev=1400, next=500, line=130, keep_next=True, border=BORDER_H2, pad=(600, 0, 0, 0)),
    "list": ParaSpec("LEFT", left=1800, intent=-1100, next=200, line=150),
    "list2": ParaSpec("LEFT", left=3400, intent=-1100, next=200, line=150),
    "cell": ParaSpec("LEFT", line=130),
    "cellR": ParaSpec("RIGHT", line=130),
    "cellC": ParaSpec("CENTER", line=130),
    "caption": ParaSpec("CENTER", prev=200, next=600, line=130),
    "label": ParaSpec("LEFT", line=130, border=BORDER_RULE, pad=(0, 0, 0, 600)),
    "gap": ParaSpec("LEFT", prev=15000, next=300, line=130),
    "infoTop": ParaSpec("RIGHT", prev=19000, line=140),
    "infoTopLong": ParaSpec("RIGHT", prev=11000, line=140),
    "info": ParaSpec("RIGHT", line=140),
    "tocTitle": ParaSpec("LEFT", prev=200, next=1800, line=130),
    "toc": ParaSpec("LEFT", prev=600, next=600, line=130, border=BORDER_TOC, pad=(0, 0, 0, 500)),
    "toc2": ParaSpec("LEFT", left=4500, next=200, line=130),
    "box": ParaSpec("LEFT", left=700, right=700, prev=0, next=200, line=150, border=BORDER_BOX, pad=(1400, 850, 700, 700),
                    connect=1),
    "boxItem": ParaSpec("LEFT", left=2100, right=700, intent=-1100, next=200, line=150, border=BORDER_BOX,
                        pad=(1400, 850, 700, 700), connect=1),
}
CHAR_ID = {k: 7 + i for i, k in enumerate(CHARS)}
PARA_ID = {k: 20 + i for i, k in enumerate(PARAS)}


def _char_pr(template: str, cid: int, s: CharSpec) -> str:
    font = "0" if s.gothic else "1"
    x = re.sub(r' id="\d+"', f' id="{cid}"', template, count=1)
    x = re.sub(r'height="\d+"', f'height="{round(s.size * 100)}"', x, count=1)
    x = re.sub(r'textColor="#[0-9A-Fa-f]{6}"', f'textColor="{s.color}"', x, count=1)
    x = re.sub(r"<hh:fontRef [^>]*/>", "<hh:fontRef " + " ".join(
        f'{k}="{font}"' for k in ("hangul", "latin", "hanja", "japanese", "other", "symbol", "user")) + "/>", x, count=1)
    if s.spacing:
        x = re.sub(r"<hh:spacing [^>]*/>", "<hh:spacing " + " ".join(
            f'{k}="{s.spacing}"' for k in ("hangul", "latin", "hanja", "japanese", "other", "symbol", "user")) + "/>", x, count=1)
    marks = ("<hh:italic/>" if s.italic else "") + ("<hh:bold/>" if s.bold else "")   # 스키마 순서: offset 다음 italic, bold
    if marks:
        x = re.sub(r"(<hh:offset [^>]*/>)", lambda m: m.group(1) + marks, x, count=1)
    return x


def _para_pr(template: str, pid: int, s: ParaSpec) -> str:
    x = re.sub(r' id="\d+"', f' id="{pid}"', template, count=1)
    x = re.sub(r'<hh:align horizontal="\w+"', f'<hh:align horizontal="{s.align}"', x, count=1)
    x = re.sub(r'keepWithNext="\d"', f'keepWithNext="{1 if s.keep_next else 0}"', x, count=1)
    for name, val in (("intent", s.intent), ("left", s.left), ("right", s.right), ("prev", s.prev), ("next", s.next)):
        x = re.sub(rf'<hc:{name} value="-?\d+" unit="HWPUNIT"/>', f'<hc:{name} value="{val}" unit="HWPUNIT"/>', x)
    x = re.sub(r'<hh:lineSpacing type="PERCENT" value="\d+"', f'<hh:lineSpacing type="PERCENT" value="{s.line}"', x)
    left, right, top, bottom = s.pad
    return re.sub(r'<hh:border borderFillIDRef="\d+" offsetLeft="\d+" offsetRight="\d+" offsetTop="\d+" offsetBottom="\d+" '
                  r'connect="\d"',
                  f'<hh:border borderFillIDRef="{s.border}" offsetLeft="{left}" offsetRight="{right}" offsetTop="{top}" '
                  f'offsetBottom="{bottom}" connect="{s.connect}"', x, count=1)


BORDERS = {   # 번호: ({쪽: (선 종류, 굵기, 색)}, 채우기 색) — 적지 않은 쪽은 선 없음
    BORDER_TABLE: ({s: ("SOLID", "0.12 mm", LINE) for s in ("left", "right", "top", "bottom")}, None),
    BORDER_HEAD: ({s: ("SOLID", "0.12 mm", LINE) for s in ("left", "right", "top", "bottom")}, ACCENT),
    BORDER_STRIPE: ({s: ("SOLID", "0.12 mm", LINE) for s in ("left", "right", "top", "bottom")}, "#" + DOC["zebra"]),
    BORDER_H1: ({"bottom": ("SOLID", "0.4 mm", LINE)}, None),                 # 큰 장 제목 밑줄
    BORDER_H2: ({"left": ("SOLID", "0.7 mm", BRIGHT)}, None),                # 작은 제목 왼쪽 띠
    BORDER_BOX: ({"left": ("SOLID", "0.7 mm", BRIGHT)}, SOFT),               # 핵심 상자: 연한 바탕 + 왼쪽 띠
    BORDER_RULE: ({"bottom": ("SOLID", "0.4 mm", INK)}, None),               # 표지 맨 위 'REPORT' 밑줄
    BORDER_TOC: ({"bottom": ("SOLID", "0.12 mm", LINE)}, None),              # 목차 줄
}


def _border_fills() -> str:
    def one(bid: int, sides: dict, fill: str | None) -> str:
        lines = "".join(f'<hh:{s}Border type="{sides[s][0]}" width="{sides[s][1]}" color="{sides[s][2]}"/>' if s in sides else
                        f'<hh:{s}Border type="NONE" width="0.1 mm" color="#000000"/>' for s in ("left", "right", "top", "bottom"))
        brush = (f'<hc:fillBrush><hc:winBrush faceColor="{fill}" hatchColor="#999999" alpha="0"/></hc:fillBrush>'
                 if fill else "")
        return (f'<hh:borderFill id="{bid}" threeD="0" shadow="0" centerLine="NONE" breakCellSeparateLine="0">'
                '<hh:slash type="NONE" Crooked="0" isCounter="0"/><hh:backSlash type="NONE" Crooked="0" isCounter="0"/>'
                f'{lines}<hh:diagonal type="SOLID" width="0.1 mm" color="#000000"/>{brush}</hh:borderFill>')
    return "".join(one(bid, sides, fill) for bid, (sides, fill) in BORDERS.items())


def build_header() -> str:
    """바탕 틀의 header.xml 에 보고서용 모양을 덧붙인다."""
    h = _read("header.xml")
    char0 = re.search(r'<hh:charPr id="0".*?</hh:charPr>', h, re.S).group(0)
    para0 = re.search(r'<hh:paraPr id="0".*?</hh:paraPr>', h, re.S).group(0)

    def count(tag: str) -> int:
        return int(re.search(rf'<hh:{tag} itemCnt="(\d+)"', h).group(1))
    n_char, n_para, n_border = count("charProperties"), count("paraProperties"), count("borderFills")
    if (n_char, n_para, n_border) != (7, 20, 2):
        raise ValueError("HWPX 바탕 틀이 예상과 다릅니다.")
    chars = "".join(_char_pr(char0, CHAR_ID[k], s) for k, s in CHARS.items())
    paras = "".join(_para_pr(para0, PARA_ID[k], s) for k, s in PARAS.items())
    h = h.replace(f'<hh:charProperties itemCnt="{n_char}">', f'<hh:charProperties itemCnt="{n_char + len(CHARS)}">', 1)
    h = h.replace("</hh:charProperties>", chars + "</hh:charProperties>", 1)
    h = h.replace(f'<hh:paraProperties itemCnt="{n_para}">', f'<hh:paraProperties itemCnt="{n_para + len(PARAS)}">', 1)
    h = h.replace("</hh:paraProperties>", paras + "</hh:paraProperties>", 1)
    h = h.replace(f'<hh:borderFills itemCnt="{n_border}">', f'<hh:borderFills itemCnt="{n_border + len(BORDERS)}">', 1)
    return h.replace("</hh:borderFills>", _border_fills() + "</hh:borderFills>", 1)


# ---------------------------------------------------------------- 본문
class _Body:
    def __init__(self) -> None:
        self.parts: list[str] = []
        self._id = 0

    def pid(self) -> int:
        self._id += 1
        return self._id

    def para(self, para_key: str, inner: str, page: bool = False) -> str:
        return (f'<hp:p id="{self.pid()}" paraPrIDRef="{PARA_ID[para_key]}" styleIDRef="0" pageBreak="{int(page)}" '
                f'columnBreak="0" merged="0">{inner}</hp:p>')

    def add(self, para_key: str, inner: str, page: bool = False) -> None:
        self.parts.append(self.para(para_key, inner, page))


def _run(char_key: str, text: str) -> str:
    t = f"<hp:t>{_esc(text)}</hp:t>" if text else "<hp:t/>"
    return f'<hp:run charPrIDRef="{CHAR_ID[char_key]}">{t}</hp:run>'


def _rich(text: str, base: str = "body", bold: str = "bodyB", keyword: bool = False) -> str:
    """**굵게** 표시를 굵은 글자로 (keyword=True 면 '핵심어: 설명' 의 핵심어를 제목 색으로 — 워드 · 발표 자료와 같게)."""
    return "".join(_run(("keyB" if keyword else bold) if b else base, t) for t, b in rich_parts(text, keyword))


def _table(body: _Body, columns: list[str], rows: list[list[str]]) -> str:
    cols = max(1, len(columns))
    cw = BODY_WIDTH // cols
    grid = [columns] + rows
    numeric = [all(numeric_text(r[c]) or not r[c] for r in rows if c < len(r)) and any(c < len(r) and r[c] for r in rows)
               for c in range(cols)]

    def cell(text: str, r: int, c: int) -> str:
        head = r == 0
        fill = BORDER_HEAD if head else BORDER_STRIPE if r % 2 == 0 else BORDER_TABLE
        align = "cellC" if head else "cellR" if numeric[c] else "cell"      # 숫자 칸은 오른쪽 맞춤
        style = "th" if head else "tdB" if c == 0 else "td"                   # 머리줄은 진한 바탕에 흰 글자, 첫 칸은 굵게
        return (f'<hp:tc name="" header="{1 if head else 0}" hasMargin="0" protect="0" editable="0" dirty="0" '
                f'borderFillIDRef="{fill}">'
                '<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="CENTER" linkListIDRef="0" '
                'linkListNextIDRef="0" textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">'
                + body.para(align, _run(style, text)) +
                f'</hp:subList><hp:cellAddr colAddr="{c}" rowAddr="{r}"/><hp:cellSpan colSpan="1" rowSpan="1"/>'
                f'<hp:cellSz width="{cw}" height="1000"/><hp:cellMargin left="510" right="510" top="141" bottom="141"/></hp:tc>')
    trs = "".join("<hp:tr>" + "".join(cell(row[c] if c < len(row) else "", r, c) for c in range(cols)) + "</hp:tr>"
                  for r, row in enumerate(grid))
    tbl = (f'<hp:tbl id="{body.pid()}" zOrder="0" numberingType="TABLE" textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" '
           'lock="0" dropcapstyle="None" pageBreak="CELL" repeatHeader="1" '
           f'rowCnt="{len(grid)}" colCnt="{cols}" cellSpacing="0" borderFillIDRef="{BORDER_TABLE}" noAdjust="0">'
           f'<hp:sz width="{cw * cols}" widthRelTo="ABSOLUTE" height="{1000 * len(grid)}" heightRelTo="ABSOLUTE" protect="0"/>'
           '<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" '
           'horzRelTo="COLUMN" vertAlign="TOP" horzAlign="LEFT" vertOffset="0" horzOffset="0"/>'
           '<hp:outMargin left="0" right="0" top="0" bottom="0"/><hp:inMargin left="510" right="510" top="141" bottom="141"/>'
           f"{trs}</hp:tbl>")
    return body.para("body", f'<hp:run charPrIDRef="{CHAR_ID["body"]}">{tbl}</hp:run>')


def _cover(b: _Body, title: str, subtitle: str) -> None:
    """표지: 맨 위 'REPORT' 와 밑줄, 가운데 큰 제목, 아래 오른쪽에 과목 · 이름 · 날짜 (워드 보고서와 같은 배치)."""
    b.add("label", _run("label", "REPORT"))
    b.add("gap", _run("body", ""))                                          # 제목 위를 띄우는 빈 줄
    b.add("title", _run("title", title))
    info = [x for x in re.split(r"\s*[·|/]\s*|\n", _text(subtitle)) if x.strip()][:5]
    if not re.search(r"(?:19|20)\d\d", _text(subtitle)):
        info.append(datetime.now().strftime("%Y. %m. %d."))              # 제출일 (부제에 날짜가 없으면 오늘)
    top = "infoTop" if _lines(title, 28, 6.3) <= 2 else "infoTopLong"       # 제목이 길면 덜 띄운다 (쪽을 넘지 않게)
    for i, line in enumerate(info):
        b.add(top if i == 0 else "info", _run("info" if i == 0 else "info2", line))


def _contents(b: _Body, entries: list[tuple[int, str]]) -> None:
    """목차 쪽 (새 쪽에서): 큰 장 제목은 번호(강조색) + 아래 점선 대신 연한 선, 작은 제목은 들여 쓴다."""
    b.add("label", _run("label", "CONTENTS"), page=True)
    b.add("tocTitle", _run("tocTitle", "목차"))
    n = 0
    for level, text in entries:
        m = _HEAD_NUM.match(text)
        if level == 1:
            n += 1
            num, rest = (m.group(0).strip().rstrip(".)"), text[m.end():].strip()) if m else (f"{n:02d}", text)
            num = f"{int(num):02d}" if num.isdigit() else num
            b.add("toc", _run("tocnum", num) + _run("toc", "    " + rest))
        else:
            b.add("toc2", _run("toc2", text))


def _box(b: _Body, lines: list[str], label: str) -> None:
    """핵심 상자 (연한 바탕 + 왼쪽 강조 띠). 같은 테두리로 이어진 문단은 한 상자로 붙는다."""
    if len(lines) == 1:
        b.add("box", _run("boxLabel", label + "   ") + _rich(lines[0], "box", "boxB"))
        return
    b.add("box", _run("boxLabel", label))
    for line in lines:
        b.add("boxItem", _run("boxLabel", "•  ") + _rich(line, "box", "boxB", keyword=True))


def build_section(title: str, sections: list, subtitle: str = "", sources=None, summary=None) -> tuple[str, dict]:
    """본문 section0.xml → (XML, {'sections': 장 수, 'tables': 표 수})."""
    b = _Body()
    _cover(b, title, subtitle)
    clean = [s if isinstance(s, dict) else {"paragraphs": [str(s)]} for s in sections]
    heads = [(2 if str(s.get("level", 1)).strip() == "2" else 1, _text(s.get("heading"))) for s in clean]
    heads = [(lvl, h) for lvl, h in heads if h]
    refs = [pretty_ref(_text(r)) for r in _strings(sources)]
    if sum(1 for lvl, _ in heads if lvl == 1) >= 3:
        _contents(b, heads + ([(1, "참고 자료")] if refs else []))
    first = len(b.parts)                                                    # 본문의 첫 문단은 새 쪽에서
    points = [_text(x) for x in _strings(summary) if _text(x)]
    if points:
        _box(b, points[:6], "핵심 요약")
    tables = 0
    for sec in clean:
        heading = _text(sec.get("heading"))
        level = 2 if str(sec.get("level", 1)).strip() == "2" else 1
        if heading:
            m = _HEAD_NUM.match(heading) if level == 1 else None
            b.add(f"h{level}", (_run("h1num", m.group(0)) + _run("h1", heading[m.end():])) if m else
                  _run(f"h{level}", heading))
        for para in _strings(sec.get("paragraphs")):
            b.add("body", _rich(para.strip()))
        outline = sec.get("points") if not (sec.get("paragraphs") or sec.get("bullets")) else None   # 개요만 받은 장
        for line, lvl in parse_bullets(sec.get("bullets") or outline):
            b.add("list2" if lvl else "list", _run("body", "–  " if lvl else "•  ") + _rich(line, keyword=not lvl))
        table = sec.get("table")
        if isinstance(table, dict) and table.get("columns"):
            cols = [_text(c) for c in table["columns"]]
            rows = [[_text(v) for v in r] for r in (table.get("rows") or []) if isinstance(r, (list, tuple))]
            b.parts.append(_table(b, cols, rows))
            if _text(table.get("caption")):
                b.add("caption", _run("caption", _text(table["caption"])))
            tables += 1
        note = [_text(x) for x in _strings(sec.get("callout")) if _text(x)]
        if note:
            _box(b, note[:3], "핵심")
    if refs:
        b.add("h1", _run("h1", "참고 자료"))
        for i, r in enumerate(refs, 1):
            b.add("list", _run("ref", f"{i}.  {r}"))
    if first < len(b.parts):
        b.parts[first] = b.parts[first].replace('pageBreak="0"', 'pageBreak="1"', 1)
    section = _read("section0.xml")
    # 첫 문단(쪽 설정이 든 바탕 틀 문단)에 아래 가운데 쪽 번호를 넣고, 첫 쪽(표지)에서는 쪽 번호를 감춘다
    section = section.replace(
        '<hp:ctrl><hp:colPr id="" type="NEWSPAPER" layout="LEFT" colCount="1" sameSz="1" sameGap="0"/></hp:ctrl>',
        '<hp:ctrl><hp:colPr id="" type="NEWSPAPER" layout="LEFT" colCount="1" sameSz="1" sameGap="0"/></hp:ctrl>'
        '<hp:ctrl><hp:pageNum pos="BOTTOM_CENTER" formatType="DIGIT" sideChar="-"/></hp:ctrl>', 1)
    section = section.replace('hideFirstPageNum="0"', 'hideFirstPageNum="1"', 1)
    return section.replace("</hs:sec>", "".join(b.parts) + "</hs:sec>"), {"sections": len(sections), "tables": tables}


def _content_hpf(title: str) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    x = _read("content.hpf").replace("<opf:title/>", f"<opf:title>{_esc(title)}</opf:title>", 1)
    x = x.replace("synthetic-fixture-author", "U.L.T.R.O.N")
    x = re.sub(r'(<opf:meta name="CreatedDate" content="text">)[^<]*', lambda m: m.group(1) + now, x)
    x = re.sub(r'(<opf:meta name="ModifiedDate" content="text">)[^<]*', lambda m: m.group(1) + now, x)
    return re.sub(r'(<opf:meta name="date" content="text">)[^<]*',
                  lambda m: m.group(1) + _esc(datetime.now().strftime("%Y년 %m월 %d일")), x)


def build_hwpx(path: Path, title: str, sections: list, subtitle: str = "", sources=None, summary=None,
               icon: str = "") -> dict:
    """보고서를 한글(.hwpx) 파일로 만든다 → {'sections': 장 수, 'tables': 표 수}."""
    title = _text(title)
    if not title:
        raise ValueError("문서 제목(title)이 필요합니다.")
    if not isinstance(sections, list) or not sections:
        raise ValueError("내용(sections)이 하나 이상 필요합니다.")
    section, info = build_section(title, sections, subtitle, sources, summary)   # (icon: 워드와 같은 인자 — 한글에는 그림 없이)
    preview = "\r\n".join([title] + [_text(s.get("heading")) for s in sections if isinstance(s, dict) and s.get("heading")])
    with zipfile.ZipFile(str(path), "w") as z:
        # mimetype 은 맨 앞에, 압축하지 않고 (OCF 규칙 — 한글이 이것으로 형식을 알아본다)
        z.writestr(zipfile.ZipInfo("mimetype"), "application/hwp+zip", compress_type=zipfile.ZIP_STORED)
        for name, data in (
            ("version.xml", _read("version.xml")),
            ("Contents/header.xml", build_header()),
            ("Contents/section0.xml", section),
            ("Preview/PrvText.txt", preview[:1024]),
            ("settings.xml", _read("settings.xml")),
            ("META-INF/container.rdf", _read("container.rdf")),
            ("Contents/content.hpf", _content_hpf(title)),
            ("META-INF/container.xml", _read("container.xml")),
            ("META-INF/manifest.xml", _read("manifest.xml")),
        ):
            z.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)
    return info
