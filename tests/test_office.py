"""작업 결과물 — 자료조사 PPT · 보고서 · 엑셀 (office.py · tools.py 의 make_* · brain.py 의 작업 요청 처리)."""
import threading
import types
import zipfile

import pytest

import jarvis.brain as bm
from jarvis import office
from jarvis import tools as T
from jarvis.config import DEFAULTS

pptx = pytest.importorskip("pptx")
docx = pytest.importorskip("docx")
pytest.importorskip("xlsxwriter")

SLIDES = [
    {"layout": "section", "title": "왜 지금인가", "bullets": ["우리 생활에 들어온 변화"], "notes": "첫 장 대본."},
    {"title": "개념", "bullets": ["• 첫째 내용", "- 하위 내용", "둘째 내용", "셋째 내용"], "notes": "개념 설명 대본."},
    {"layout": "stats", "title": "숫자로 보기", "stats": [{"value": "1.1℃", "label": "기온 상승"}, {"value": "2배", "label": "폭염"}]},
    {"layout": "two_column", "title": "원인과 영향", "left": {"heading": "원인", "bullets": ["화석 연료"]},
     "right": {"heading": "영향", "bullets": ["폭염", "가뭄"]}, "notes": "비교 대본."},
    {"layout": "quote", "title": "인용", "quote": "행동할 마지막 세대다.", "by": "누군가"},
    {"layout": "이상한레이아웃", "title": "알 수 없는 레이아웃은 목록으로", "bullets": ["내용"]},
    "글자만 준 장",
    {"layout": "closing", "title": "감사합니다", "bullets": ["질문 있으신가요?"]},
]


def texts(slide) -> str:
    return "\n".join(sh.text_frame.text for sh in slide.shapes if sh.has_text_frame)


# ---------------------------------------------------------------- 발표 자료
def test_presentation_has_cover_agenda_every_layout_notes_and_sources(tmp_path):
    path = tmp_path / "deck.pptx"
    info = office.build_presentation(path, "기후 변화와 우리", SLIDES, subtitle="3학년 2반",
                                     sources=["자료 하나 — https://a.example.kr", "자료 둘"])
    prs = pptx.Presentation(str(path))
    slides = list(prs.slides)
    assert info == {"slides": len(slides), "notes": 3, "split": 0}
    assert len(slides) == 1 + 1 + len(SLIDES) + 1                              # 표지 + 목차 + 본문 + 참고 자료
    assert prs.slide_width / prs.slide_height == pytest.approx(16 / 9, rel=0.01)
    assert "기후 변화와 우리" in texts(slides[0]) and "3학년 2반" in texts(slides[0])
    agenda = texts(slides[1])
    assert agenda.startswith("목차") and "왜 지금인가" in agenda                   # 장 구분이 있으면 장 제목으로 목차
    assert "01" in texts(slides[2]) and "왜 지금인가" in texts(slides[2])
    assert "첫째 내용" in texts(slides[3]) and "• 첫째" not in texts(slides[3])   # 글머리 기호는 지우고 모양으로 그린다
    assert "1.1℃" in texts(slides[4]) and "기온 상승" in texts(slides[4])
    assert "원인" in texts(slides[5]) and "가뭄" in texts(slides[5])
    assert "행동할 마지막 세대다." in texts(slides[6]) and "— 누군가" in texts(slides[6])
    assert "알 수 없는 레이아웃은 목록으로" in texts(slides[7]) and "글자만 준 장" in texts(slides[8])
    assert "감사합니다" in texts(slides[9])
    assert "참고 자료" in texts(slides[-1]) and "1. 자료 하나 — https://a.example.kr" in texts(slides[-1])
    talk = [s.notes_slide.notes_text_frame.text for s in slides if s.has_notes_slide]
    assert talk == ["첫 장 대본.", "개념 설명 대본.", "비교 대본."]
    assert prs.core_properties.title == "기후 변화와 우리"


def _order(parent, schema):
    """자식 요소들이 스키마 순서를 지키는가 (파워포인트는 순서가 틀리면 '복구' 를 묻는다)."""
    seen = [c.tag.split("}")[1] for c in parent if c.tag.split("}")[1] in schema]
    return [schema.index(t) for t in seen] == sorted(schema.index(t) for t in seen)


def test_korean_font_and_bullet_xml_follow_the_powerpoint_schema(tmp_path):
    path = tmp_path / "deck.pptx"
    office.build_presentation(path, "제목", SLIDES[:2])
    prs = pptx.Presentation(str(path))
    rpr_schema = ["ln", "noFill", "solidFill", "gradFill", "blipFill", "pattFill", "grpFill", "effectLst", "effectDag",
                  "highlight", "uLnTx", "uLn", "uFillTx", "uFill", "latin", "ea", "cs", "sym", "hlinkClick",
                  "hlinkMouseOver", "rtl", "extLst"]
    ppr_schema = ["lnSpc", "spcBef", "spcAft", "buClrTx", "buClr", "buSzTx", "buSzPct", "buSzPts", "buFontTx", "buFont",
                  "buNone", "buAutoNum", "buChar", "buBlip", "tabLst", "defRPr", "extLst"]
    runs = bullets = 0
    for slide in prs.slides:
        for el in slide._element.iter():
            tag = el.tag.split("}")[1]
            if tag == "rPr":
                runs += 1
                assert _order(el, rpr_schema)
                ea = [c for c in el if c.tag.endswith("}ea")]
                assert ea and ea[0].get("typeface") == office.FONT               # 한글은 동아시아 글꼴 칸에
            if tag == "pPr" and any(c.tag.endswith("}buChar") for c in el):
                bullets += 1
                assert _order(el, ppr_schema)
    assert runs > 10 and bullets >= 4


def test_long_lists_shrink_then_split_evenly_and_every_part_fits(tmp_path):
    many = [f"{i}번째 항목: 내용이 아주 많아서 한 장에 다 들어가지 않으면 자동으로 다음 장으로 넘어가야 합니다" for i in range(1, 15)]
    path = tmp_path / "long.pptx"
    info = office.build_presentation(path, "긴 목록", [{"title": "많은 내용", "bullets": many, "notes": "대본"}], agenda=False)
    prs = pptx.Presentation(str(path))
    titles = [texts(s).splitlines()[0] for s in list(prs.slides)[1:]]
    assert info["split"] >= 1 and titles[0] == "많은 내용" and titles[1] == "많은 내용 (계속)"
    parts = office.split_items([(t, 0) for t in many], office.W - 2 * office.M, office.H - 2.75, 18)
    assert sum(len(p) for p in parts) == len(many) and max(map(len, parts)) - min(map(len, parts)) <= 1   # 고르게
    assert all(office.fit_size(p, office.W - 2 * office.M, office.H - 2.75) for p in parts)
    few = [("짧은 항목", 0)] * 3
    assert office.fit_size(few, 11.7, 4.75) == office.BODY_SIZES[0]                                      # 적으면 크게
    assert office.roomy_gap(few, 26, 11.7, 4.75) > office.roomy_gap([("항목", 0)] * 7, 26, 11.7, 4.75)  # 남는 공간에 맞춰 띄운다


def test_sub_points_stay_with_their_parent_when_splitting():
    items = [(f"윗 항목 {i}", 0) if i % 3 == 0 else (f"하위 {i}", 1) for i in range(30)]
    for part in office.split_items(items, 11.7, 4.75, 18):
        assert part[0][1] == 0                                                   # 어느 장도 하위 항목으로 시작하지 않는다


def test_bullet_parsing():
    assert office.parse_bullets(["• 첫째", "- 하위", "  들여쓴 하위", "1. 번호", "", "* 별표"]) == [
        ("첫째", 0), ("하위", 1), ("들여쓴 하위", 1), ("번호", 0), ("별표", 0)]
    assert office.parse_bullets(["- 처음부터 하위"]) == [("처음부터 하위", 0)]   # 첫 줄은 하위가 될 수 없다
    assert office.parse_bullets("첫 줄\n- 둘째 줄") == [("첫 줄", 0), ("둘째 줄", 1)]


def test_presentation_input_errors_are_clear(tmp_path):
    with pytest.raises(ValueError, match="제목"):
        office.build_presentation(tmp_path / "a.pptx", " ", SLIDES)
    with pytest.raises(ValueError, match="슬라이드"):
        office.build_presentation(tmp_path / "a.pptx", "제목", [])
    with pytest.raises(ValueError, match="너무 많"):
        office.build_presentation(tmp_path / "a.pptx", "제목", [{"title": "x"}] * (office.MAX_SLIDES + 1))
    office.build_presentation(tmp_path / "b.pptx", "제목", [{"title": "x"}], theme="없는테마")       # 모르는 테마는 기본으로
    for name in office.THEMES:
        office.build_presentation(tmp_path / f"{name}.pptx", "제목", SLIDES, theme=name)


# ---------------------------------------------------------------- 보고서 · 엑셀
def test_document_has_title_headings_bullets_table_sources_and_page_numbers(tmp_path):
    path = tmp_path / "report.docx"
    info = office.build_document(path, "환경오염 보고서", [
        {"heading": "1. 서론", "paragraphs": ["환경오염은 중요한 문제다.", "둘째 문단."]},
        {"heading": "1-1. 배경", "level": 2, "bullets": ["대기", "- 미세먼지", "수질"]},
        {"heading": "2. 비교", "table": {"columns": ["구분", "내용"], "rows": [["대기", "미세먼지"], ["수질"]], "caption": "표 1"}},
    ], subtitle="과학 · 홍길동", sources=["자료 — https://b.example.kr"])
    assert info == {"sections": 3, "tables": 1}
    d = docx.Document(str(path))
    paras = [(p.style.name, p.text) for p in d.paragraphs]
    assert ("Title", "환경오염 보고서") in paras and ("Heading 1", "1. 서론") in paras and ("Heading 2", "1-1. 배경") in paras
    assert ("List Bullet", "미세먼지") in paras and ("Heading 1", "참고 자료") in paras
    assert ("List Number", "자료 — https://b.example.kr") in paras
    cells = [[c.text for c in r.cells] for r in d.tables[0].rows]
    assert cells == [["구분", "내용"], ["대기", "미세먼지"], ["수질", ""]]
    with zipfile.ZipFile(path) as z:
        assert "PAGE" in z.read("word/footer1.xml").decode() and 'w:eastAsia="맑은 고딕"' in z.read("word/styles.xml").decode()
    with pytest.raises(ValueError):
        office.build_document(tmp_path / "x.docx", "제목", [])


def test_spreadsheet_keeps_numbers_formulas_and_clean_sheet_names(tmp_path):
    path = tmp_path / "t.xlsx"
    info = office.build_spreadsheet(path, [
        {"name": "1학기/성적:정리", "title": "성적표", "columns": ["과목", "점수"], "rows": [["국어", 90], ["수학", 85.5], ["합계", "=SUM(B4:B5)"]]},
        {"name": "1학기/성적:정리", "columns": ["요일"], "rows": [["월"], [None], [True]]},
    ])
    assert info == {"sheets": 2, "rows": 6}
    with zipfile.ZipFile(path) as z:
        book = z.read("xl/workbook.xml").decode()
        s1 = z.read("xl/worksheets/sheet1.xml").decode()
        strings = z.read("xl/sharedStrings.xml").decode()
    assert 'name="1학기 성적 정리"' in book and 'name="1학기 성적 정리 (2)"' in book   # 쓸 수 없는 글자 · 같은 이름
    assert "<f>SUM(B4:B5)</f>" in s1 and "<v>90</v>" in s1 and "<v>85.5</v>" in s1
    assert 'state="frozen"' in s1 and "<autoFilter" in s1 and "성적표" in strings and "예" in strings
    with pytest.raises(ValueError, match="열 이름"):
        office.build_spreadsheet(tmp_path / "x.xlsx", [{"name": "빈 시트", "rows": []}])


def test_file_names_are_safe_and_never_overwrite_unless_asked(tmp_path):
    assert office.safe_name('보고서: "최종"/v2?.') == "보고서 최종 v2"
    assert office.safe_name("   ") == "ULTRON 작업"
    first = office.target(tmp_path / "새폴더", "발표", ".pptx")
    first.write_bytes(b"x")
    assert office.target(tmp_path / "새폴더", "발표", ".pptx").name == "발표 (2).pptx"
    assert office.target(tmp_path / "새폴더", "발표", ".pptx", overwrite=True) == first


# ---------------------------------------------------------------- 도구 (tools.py)
@pytest.fixture
def pc(tmp_path, monkeypatch):
    me = T.PCTools.__new__(T.PCTools)
    folders = {"문서": tmp_path / "docs", "바탕화면": tmp_path / "desk"}
    monkeypatch.setattr(T.winutil, "known_folder", lambda name: folders.get(name.replace(" ", "")))
    me.opened = []
    monkeypatch.setattr(T.os, "startfile", lambda p: me.opened.append(p), raising=False)
    return me


def test_make_presentation_saves_in_documents_ultron_and_opens_it(pc, tmp_path):
    msg = pc.t_make_presentation(title="기후 변화", slides=SLIDES[:3], sources=["자료"])
    path = tmp_path / "docs" / "ULTRON" / "기후 변화.pptx"
    assert path.exists() and pc.opened == [str(path)]
    assert str(path) in msg and "표지 포함" in msg and "발표 대본 2장" in msg
    again = pc.t_make_presentation(title="기후 변화", slides=SLIDES[:1], open=False)
    assert "기후 변화 (2).pptx" in again and len(pc.opened) == 1                  # 덮어쓰지 않고, 열지 말라면 열지 않는다
    pc.t_make_presentation(title="기후 변화", slides=SLIDES[:1], overwrite=True, filename="기후 변화")
    assert not (tmp_path / "docs" / "ULTRON" / "기후 변화 (3).pptx").exists()
    desk = pc.t_make_presentation(title="바탕화면에", slides=SLIDES[:1], folder="바탕화면")
    assert str(tmp_path / "desk" / "바탕화면에.pptx") in desk
    full = pc.t_make_presentation(title="경로", slides=SLIDES[:1], folder=str(tmp_path / "어디든"))
    assert (tmp_path / "어디든" / "경로.pptx").exists() and "경로.pptx" in full
    with pytest.raises(T.ToolError, match="알 수 없습니다"):
        pc.t_make_presentation(title="x", slides=SLIDES[:1], folder="모르는폴더")


def test_locked_file_is_saved_under_a_new_name_and_errors_are_explained(pc, tmp_path, monkeypatch):
    calls = []
    real = office.build_presentation

    def locked_once(path, *a, **k):
        calls.append(path.name)
        if len(calls) == 1:
            raise PermissionError("파일이 열려 있음")
        return real(path, *a, **k)

    (tmp_path / "docs" / "ULTRON").mkdir(parents=True)
    (tmp_path / "docs" / "ULTRON" / "열린 파일.pptx").write_bytes(b"x")
    monkeypatch.setattr(office, "build_presentation", locked_once)
    msg = pc.t_make_presentation(title="열린 파일", slides=SLIDES[:1], overwrite=True)
    assert calls == ["열린 파일.pptx", "열린 파일 (2).pptx"] and "새 이름으로 저장" in msg

    def missing(*a, **k):
        raise ModuleNotFoundError("No module named 'pptx'", name="pptx")

    monkeypatch.setattr(office, "build_presentation", missing)
    with pytest.raises(T.ToolError, match="python-pptx.*setup.bat"):
        pc.t_make_presentation(title="x", slides=SLIDES[:1])
    monkeypatch.setattr(office, "build_presentation", real)
    with pytest.raises(T.ToolError, match="슬라이드"):
        pc.t_make_presentation(title="x", slides=[])


def test_no_program_to_open_the_file_is_reported_not_raised(pc, monkeypatch):
    def nothing(p):
        raise OSError("연결된 프로그램 없음")

    monkeypatch.setattr(T.os, "startfile", nothing, raising=False)
    assert "열지는 못했다" in pc.t_make_document(title="보고서", sections=[{"heading": "서론", "paragraphs": ["내용"]}])


def test_make_document_and_spreadsheet(pc, tmp_path):
    msg = pc.t_make_document(title="조사 보고서", sections=[{"heading": "서론", "paragraphs": ["내용"],
                                                           "table": {"columns": ["a"], "rows": [["1"]]}}])
    assert (tmp_path / "docs" / "ULTRON" / "조사 보고서.docx").exists() and "표 1개" in msg
    msg = pc.t_make_spreadsheet(sheets=[{"name": "시간표", "columns": ["요일", "1교시"], "rows": [["월", "국어"]]}])
    assert (tmp_path / "docs" / "ULTRON" / "시간표.xlsx").exists() and "시트 1개, 1행" in msg


def test_tools_are_described_for_claude_with_labels():
    schemas = {d["name"]: d for d in T.PCTools.schemas(T.PCTools.__new__(T.PCTools))}
    for name, required in (("make_presentation", ["title", "slides"]), ("make_document", ["title", "sections"]),
                           ("make_spreadsheet", ["sheets"])):
        assert schemas[name]["input_schema"]["required"] == required and len(schemas[name]["description"]) > 80
    layouts = schemas["make_presentation"]["input_schema"]["properties"]["slides"]["items"]["properties"]["layout"]["enum"]
    assert set(layouts) == set(office.LAYOUTS)
    assert set(schemas["make_presentation"]["input_schema"]["properties"]["theme"]["enum"]) == set(office.THEMES)
    assert T.PCTools.label("make_presentation", {"title": "기후"}) == "PPT 만들기 · 기후"
    assert T.PCTools.label("web_fetch", {"url": "https://a.kr"}) == "웹 페이지 읽기 · https://a.kr"


# ---------------------------------------------------------------- 작업 요청 처리 (brain.py)
class Cfg(dict):
    def __getitem__(self, k):
        return self.get(k, DEFAULTS.get(k))

    def api_key(self):
        return ""


class Tools:
    def __init__(self):
        self.ran = []

    def schemas(self):
        return T.PCTools.schemas(T.PCTools.__new__(T.PCTools))

    def set_vision_model(self, model):
        pass

    def label(self, name, args):
        return T.PCTools.label(name, args)

    def run(self, name, args):
        self.ran.append((name, args))
        return "ok"

    def _find_app(self, name, min_score=38):
        return None

    def _match_windows(self, name):
        return []


def brain(**cfg):
    return bm.Brain(Cfg(cfg), Tools(), on_action=lambda *a: None, context_fn=lambda: "")


WORK = ["인공지능에 대해 자료조사해서 PPT 만들어 줘", "파워포인트로 기후 변화 발표 자료 만들어 줘", "환경오염 보고서 써 줘",
        "엑셀로 이번 주 시간표 만들어 줘", "미리캔버스에서 포스터 만들어 줘", "미리캠퍼스로 카드뉴스 만들어 줘",
        "한국 전쟁 조사해서 워드로 정리해 줘", "피피티 10장 만들어줘 주제는 우주", "캔바로 발표 슬라이드 꾸며 줘"]
EVERYDAY = ["오늘 날씨 어때", "크롬 열어 줘", "볼륨 올려 줘", "농담 하나 해 줘", "이 화면 요약해 줘"]


@pytest.mark.parametrize("text", WORK)
def test_work_requests_get_the_stronger_model_deeper_thought_and_more_time(text):
    b = brain()
    assert bm.WORK_TASK.search(text) and b._pro_model(text) == "sonnet" and b._effort_for(text) == "medium"


@pytest.mark.parametrize("text", EVERYDAY)
def test_everyday_requests_are_unchanged(text):
    b = brain()
    assert not bm.WORK_TASK.search(text) and b._effort_for(text) == "low"


def test_effort_never_goes_down_from_the_users_setting():
    assert brain(effort="high")._effort_for(WORK[0]) == "high" and brain(effort="medium")._effort_for(WORK[0]) == "medium"


def test_local_ai_never_turns_a_work_request_into_opening_an_app():
    b = brain(local_ai=True)
    asked = []
    b.local_ai.interpret = lambda text: asked.append(text) or "파워포인트 열어"
    assert b._try_local_ai("파워포인트로 발표 자료 만들어 줘", fallback=True) is None and asked == []
    assert b.tools.ran == []
    b._try_local_ai("크롬 좀 켜 봐", fallback=True)
    assert len(asked) == 1 and asked[0].startswith("크롬")                         # 다른 짧은 명령은 그대로 로컬 AI 로


def test_design_and_research_sites_open_as_websites():
    b = brain(brain="local", local_ai=False)
    for said, url in (("미리캔버스 열어 줘", "miricanvas.com"), ("미리캠퍼스 들어가 줘", "miricanvas.com"),
                      ("캔바 열어 줘", "canva.com"), ("riss 들어가 줘", "riss.kr")):
        b.tools.ran = []
        assert b.local.try_handle(said, fallback=True) is not None
        assert any(url in str(args) for _, args in b.tools.ran), (said, b.tools.ran)


def test_api_mode_can_read_web_pages_and_search_more_but_haiku_only_searches():
    b = brain()
    opus = {d.get("type", d["name"]): d for d in b._tool_defs("claude-opus-5-5")}
    haiku = {d.get("type", d["name"]): d for d in b._tool_defs("claude-haiku-4-5")}
    assert opus["web_fetch_20260209"] == {"type": "web_fetch_20260209", "name": "web_fetch"}
    assert opus["web_search_20260209"]["max_uses"] == 8 and "web_fetch_20260209" not in haiku
    assert all(not t.get("type", "").startswith("web_") for t in b.mcp_tools())  # 서버 도구는 Pro 모드 도구 목록에 넣지 않는다
    assert {"make_presentation", "make_document", "make_spreadsheet"} <= {t["name"] for t in b.mcp_tools()}


def test_system_prompt_explains_how_to_finish_work_tasks():
    text = brain()._build_system()
    assert "# 작업" in text and "make_presentation" in text and "web_fetch" in text and "미리캔버스" in text
    assert "overwrite=true" in text and "결제는 사용자가 시키지 않았으면" in text


class Block(types.SimpleNamespace):
    pass


class FakeClient:
    """Anthropic 클라이언트 흉내: 보낸 인자를 기록하고 정해 둔 답을 돌려준다."""

    def __init__(self, content):
        self.sent, self.content = [], content
        self.beta = types.SimpleNamespace(messages=types.SimpleNamespace(create=self.create))

    def create(self, **kw):
        self.sent.append(kw)
        return types.SimpleNamespace(content=self.content, stop_reason="end_turn")


def test_api_mode_thinks_deeper_for_work_and_shows_page_reading(monkeypatch):
    b = brain(brain="api")
    shown = []
    b.on_action = lambda aid, label, status, detail: shown.append(label)
    client = FakeClient([Block(type="server_tool_use", name="web_fetch", id="f1", input={"url": "https://a.kr"}),
                         Block(type="text", text="발표 자료를 만들었다.")])
    b._client_for = lambda key: client
    assert b._claude(WORK[0], "key", threading.Event()) == "발표 자료를 만들었다."
    b._claude("오늘 날씨 어때", "key", threading.Event())
    assert [kw["output_config"]["effort"] for kw in client.sent] == ["medium", "low"]
    assert client.sent[0]["max_tokens"] == 16000 and "웹 페이지 읽기 · https://a.kr" in shown


# ---- Pro 모드: 켜 둔 Claude Code (pro_keep_alive)
class FakeSession:
    made: list = []

    def __init__(self, args_fn, env_fn, cwd):
        self.args_fn, self.alive, self.session_id = args_fn, False, None
        self.asked, self.models, self.closed = [], [], []
        FakeSession.made.append(self)

    def set_model(self, model):
        self.models.append(model)
        return True

    def ask(self, prompt, cancel, on_text=None, on_event=None, timeout=240):
        self.alive = True
        args = self.args_fn(self.session_id)
        self.asked.append((args[args.index("--model") + 1], args[args.index("--effort") + 1], timeout))
        self.session_id = self.session_id or "s1"
        return "답", False, ""

    def close(self, forget=False):
        self.alive = False
        self.closed.append(forget)
        if forget:
            self.session_id = None

    def close_if_idle(self, seconds):
        return False


def test_keep_alive_session_restarts_once_with_deeper_thought_for_work_then_stays(monkeypatch):
    FakeSession.made = []
    monkeypatch.setattr(bm, "ClaudeSession", FakeSession)
    monkeypatch.setattr(bm.Brain, "_mcp_config", lambda self: "mcp.json")
    monkeypatch.setattr(bm.Brain, "_reap", lambda self: None)
    b = brain()
    b.claude_exe = lambda: "claude"
    b._build_system = lambda chat=False: "system"
    b.tool_server = object()
    b._claude_code("오늘 일정 알려 줘", threading.Event())
    b._claude_code(WORK[0], threading.Event())
    b._claude_code("고마워", threading.Event())
    s = FakeSession.made[0]
    assert len(FakeSession.made) == 1                                             # 같은 대화를 이어 간다
    assert s.asked == [("haiku", "low", bm.CMD_TIMEOUT), ("sonnet", "medium", bm.WORK_TIMEOUT), ("haiku", "medium", bm.CMD_TIMEOUT)]
    assert s.closed == [False]                    # 작업 요청 때 한 번만 껐다 켰다 (대화 번호는 남김 → --resume)
    assert s.models == ["haiku"]                  # 작업이 끝난 뒤 평소 모델로는 켠 채로 바꾼다


def test_one_shot_runs_pass_deeper_thought_and_longer_time_for_work():
    b = brain(pro_keep_alive=0)
    b.claude_exe = lambda: "claude"
    b._build_system = lambda: "system"
    seen = []

    def run(exe, text, cancel, model, effort=None, timeout=240):
        seen.append((model, effort, timeout))
        return "답", "", False, 0, ""

    b._run_claude_code = run
    b._claude_code(WORK[2], threading.Event())
    b._claude_code("내일 날씨", threading.Event())
    assert seen == [("sonnet", "medium", bm.WORK_TIMEOUT), ("haiku", "low", bm.CMD_TIMEOUT)]


# ---------------------------------------------------------------- 화면 밖으로 나가는 것 · 말로 읽는 답
@pytest.mark.parametrize("theme", sorted(office.THEMES))
def test_every_text_box_and_card_stays_inside_the_slide(tmp_path, theme):
    from pptx.enum.shapes import MSO_SHAPE, MSO_SHAPE_TYPE
    path = tmp_path / "deck.pptx"
    office.build_presentation(path, "아주 긴 제목이 들어가도 슬라이드 안에 있어야 한다", SLIDES * 2, subtitle="부제",
                              sources=[f"자료 {i} — https://example.kr/{'x' * 60}" for i in range(25)], theme=theme)
    prs = pptx.Presentation(str(path))
    W_, H_ = prs.slide_width, prs.slide_height
    checked = 0
    for n, slide in enumerate(prs.slides, 1):
        for sh in slide.shapes:
            if sh.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE and sh.auto_shape_type == MSO_SHAPE.OVAL:
                continue                                                         # 장식 원은 일부러 가장자리에 걸친다
            assert sh.left >= 0 and sh.top >= -1 and sh.left + sh.width <= W_ + 1 and sh.top + sh.height <= H_ + 1, (n, sh.name)
            checked += 1
    assert checked > 100


def test_spoken_reply_drops_the_sources_list_but_keeps_normal_sentences():
    reply = "광합성 발표 자료를 만들었다.\n\n원하면 고칠 수 있다.\n\nSources:\n- [자료](https://a.kr)"
    assert bm.strip_sources(reply) == "광합성 발표 자료를 만들었다.\n\n원하면 고칠 수 있다."
    assert bm.strip_sources("답이다.\n\n**출처:**\n- a") == "답이다."
    assert bm.strip_sources("답이다.\n## References:\n- x") == "답이다."
    for keep in ("출처를 확인했다. 이상 없다.", "Source code 를 고쳤다.", "참고로 말하면 이렇다.", "", None):
        assert bm.strip_sources(keep) == keep


@pytest.mark.parametrize("seed", range(40))
def test_streamed_reply_stops_at_the_sources_list_wherever_it_is_cut(seed):
    import random
    reply = "알았다. 자료를 모아 만들지.\n\n출처를 보니 믿을 만하다.\n참고로 이렇다.\n\nSources:\n- [a](https://a.kr)\n- b"
    rng, got, i = random.Random(seed), [], 0
    f = bm.NoSources(got.append)
    while i < len(reply):
        n = rng.randint(1, 6)
        f(reply[i:i + n])
        i += n
    assert "".join(got).rstrip() == bm.strip_sources(reply)


def test_first_words_are_passed_on_at_once_so_speech_starts_without_delay():
    got = []
    f = bm.NoSources(got.append)
    f("알았다. 자료를 ")
    assert got == ["알았다. 자료를 "]


def test_handle_cleans_both_the_stream_and_the_final_reply():
    b = brain()
    raw = "만들었다.\nSources:\n- [a](https://a.kr)"

    def route(text, cancel, on_text):
        on_text(raw)
        return "claude", raw

    b._route = route
    heard = []
    assert b.handle("자료조사해서 PPT 만들어 줘", threading.Event(), on_text=heard.append) == "만들었다."
    assert "".join(heard).strip() == "만들었다."


def test_tool_result_gives_a_speakable_place_and_keeps_the_full_path_aside(pc, tmp_path):
    msg = pc.t_make_presentation(title="광합성", slides=SLIDES[:1])
    assert "저장한 곳: 문서의 ULTRON 폴더" in msg and "파일을 열었다" in msg
    assert f"[전체 경로: {tmp_path / 'docs' / 'ULTRON' / '광합성.pptx'}]" in msg
    assert "저장한 곳: 바탕화면 " in pc.t_make_presentation(title="x", slides=SLIDES[:1], folder="바탕화면")
    assert "저장한 곳: '어딘가' 폴더" in pc.t_make_presentation(title="x", slides=SLIDES[:1], folder=str(tmp_path / "어딘가"))
