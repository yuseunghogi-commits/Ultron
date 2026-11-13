"""카드뉴스 · 포스터 (design.py · tools.py 의 make_cardnews / make_poster) — 화면 클릭 없이 그림으로 바로 만든다."""
import re
import tempfile
import time
from pathlib import Path

import pytest

from jarvis import design, office
from jarvis import tools as T

pytest.importorskip("PIL")
from PIL import Image, ImageDraw  # noqa: E402

try:
    design.font_file()
except ValueError:
    pytest.skip("한글 글꼴이 없다", allow_module_level=True)

CARDS = [
    {"title": "분리배출이 왜 중요할까", "bullets": ["재활용률을 높인다", "- 플라스틱은 깨끗이 씻어서", "매립 쓰레기를 줄인다"],
     "highlight": "제대로 버리면 70%가 다시 쓰인다"},
    {"title": "헷갈리는 것들", "bullets": "영수증은 일반 쓰레기\n깨진 유리는 신문지에 싸서"},
    "글자만 준 카드",
]


def pages(pdf) -> int:
    return len(re.findall(rb"/Type\s*/Page\b", pdf.read_bytes()))


def colours(path) -> int:
    with Image.open(path) as im:
        return len(im.convert("RGB").getcolors(1 << 22) or [])


def draw():
    return ImageDraw.Draw(Image.new("RGB", (10, 10)))


# ---------------------------------------------------------------- 글 배치
def test_korean_wraps_at_spaces_and_breaks_long_words_by_letter():
    d, f = draw(), design._font("regular", 40)
    text = "기후 변화는 우리 모두의 문제입니다 지금 행동해야 합니다"
    lines = design.wrap(d, text, f, 300)
    assert len(lines) > 1 and " ".join(lines) == text                        # 낱말 중간에서 끊지 않는다
    assert all(d.textlength(x, font=f) <= 300 for x in lines)
    long = design.wrap(d, "가" * 40, f, 300)
    assert len(long) > 1 and "".join(long) == "가" * 40 and all(d.textlength(x, font=f) <= 300 for x in long)


def test_text_shrinks_to_fit_and_is_cut_with_an_ellipsis_only_when_it_must():
    d = draw()
    f, lines, size = design.fit(d, "짧은 제목", "bold", 800, 200, 100, 40)
    assert size == 100 and lines == ["짧은 제목"]
    f, lines, size = design.fit(d, "조금 긴 제목이라서 한 줄에는 다 들어가지 않는다", "bold", 600, 400, 100, 40)
    assert 40 <= size < 100 and "".join(lines).replace(" ", "") == "조금긴제목이라서한줄에는다들어가지않는다"
    f, lines, size = design.fit(d, "아주 긴 문장 " * 60, "regular", 600, 200, 60, 30, max_lines=3)
    assert size == 30 and len(lines) == 3 and lines[-1].endswith("…")
    assert all(d.textlength(x, font=f) <= 600 for x in lines)


# ---------------------------------------------------------------- 카드뉴스
def test_cardnews_has_cover_cards_closing_and_one_pdf(tmp_path):
    started = time.perf_counter()
    info = design.build_cardnews(tmp_path / "분리배출", "분리배출 제대로 하기", CARDS, subtitle="우리 반 환경 캠페인",
                                 closing="함께 실천해요\n월요일마다 점검합니다",
                                 sources=["환경부 — https://www.me.go.kr/%EC%9E%90%EB%A3%8C"])
    took = time.perf_counter() - started
    files = sorted((tmp_path / "분리배출").glob("*.png"))
    assert info["cards"] == len(CARDS) + 2 == len(files) and info["files"] == files
    assert [f.name for f in files] == ["01.png", "02.png", "03.png", "04.png", "05.png"]
    for f in files:
        with Image.open(f) as im:
            assert im.size == (design.CARD, design.CARD)
        assert colours(f) > 50                                               # 글자 · 도형이 실제로 그려졌다
    assert info["pdf"] == tmp_path / "분리배출" / "분리배출.pdf" and pages(info["pdf"]) == len(files)
    assert took < 15                                                         # 화면을 조작하는 것보다 훨씬 빠르다


def test_rebuilding_the_same_cardnews_leaves_no_stale_cards(tmp_path):
    folder = tmp_path / "카드"
    design.build_cardnews(folder, "처음", CARDS * 3)
    design.build_cardnews(folder, "다시", CARDS[:1])
    assert sorted(p.name for p in folder.iterdir()) == ["01.png", "02.png", "03.png", "카드.pdf"]


@pytest.mark.parametrize("theme", sorted(office.THEMES))
def test_every_theme_paints_cover_cards_and_closing_in_its_own_colours(tmp_path, theme):
    th = office.THEMES[theme]
    files = design.build_cardnews(tmp_path / theme, "테마", CARDS[:1], theme=theme)["files"]
    for f, colour in zip(files, (th.accent, th.bg, th.surface)):
        with Image.open(f) as im:
            assert im.convert("RGB").getpixel((5, 5)) == design._rgb(colour)


def test_unknown_theme_falls_back_and_long_text_never_breaks_the_card(tmp_path):
    long = "아주 길게 늘어지는 설명 문장이 계속 이어진다 " * 12
    info = design.build_cardnews(tmp_path / "긴 글", "제목도 " * 30, [{"title": "카드 제목 " * 15, "bullets": [long] * 8,
                                                                     "highlight": long}], theme="없는테마")
    assert info["cards"] == 3
    with Image.open(info["files"][0]) as im:
        assert im.convert("RGB").getpixel((5, 5)) == design._rgb(office.THEMES["light"].accent)


@pytest.mark.parametrize("title, cards, msg", [("", CARDS, "제목"), ("제목", [], "하나 이상"), ("제목", "카드", "하나 이상"),
                                               ("제목", ["x"] * 13, "12장 이하")])
def test_cardnews_input_errors_are_clear(tmp_path, title, cards, msg):
    with pytest.raises(ValueError, match=msg):
        design.build_cardnews(tmp_path / "x", title, cards)


# ---------------------------------------------------------------- 포스터
def test_poster_is_an_a4_png_and_a_printable_pdf(tmp_path):
    info = design.build_poster(tmp_path / "축제.png", "2026 가을 축제", [
        {"heading": "일시", "bullets": ["11월 20일 (금)", "오후 1시 ~ 5시"]},
        {"heading": "장소", "bullets": ["학교 운동장"]},
        {"heading": "프로그램", "bullets": ["공연", "먹거리 장터", "체험 부스"]},
        "글자만 준 구역"], subtitle="모두 함께 즐겨요", highlight="입장 무료 · 누구나 환영", footer="학생회",
        sources=["https://example.kr/a"], theme="warm")
    assert info["sections"] == 4 and info["size"] == design.A4 and info["pdf"] == tmp_path / "축제.pdf"
    with Image.open(tmp_path / "축제.png") as im:
        assert im.size == design.A4
        assert im.convert("RGB").getpixel((5, 5)) == design._rgb(office.THEMES["warm"].accent)
    assert colours(tmp_path / "축제.png") > 50 and pages(info["pdf"]) == 1


def test_a3_poster_is_bigger_and_bad_input_is_explained(tmp_path):
    info = design.build_poster(tmp_path / "큰.png", "큰 포스터", [], highlight="강조 문구만 있어도 된다", size="A3")
    assert info["size"] == (round(1240 * 1.4142), round(1754 * 1.4142)) and info["sections"] == 0
    with Image.open(tmp_path / "큰.png") as im:
        assert im.size == info["size"]
    with pytest.raises(ValueError, match="내용"):
        design.build_poster(tmp_path / "x.png", "제목", [])
    with pytest.raises(ValueError, match="6개 이하"):
        design.build_poster(tmp_path / "x.png", "제목", ["a"] * 7)
    with pytest.raises(ValueError, match="제목"):
        design.build_poster(tmp_path / "x.png", " ", ["a"])


# ---------------------------------------------------------------- 도구 (tools.py)
@pytest.fixture
def pc(tmp_path, monkeypatch):
    me = T.PCTools.__new__(T.PCTools)
    folders = {"문서": tmp_path / "docs", "바탕화면": tmp_path / "desk"}
    monkeypatch.setattr(T.winutil, "known_folder", lambda name: folders.get(name.replace(" ", "")))
    me.opened = []
    monkeypatch.setattr(T.os, "startfile", lambda p: me.opened.append(p), raising=False)
    return me


def test_make_cardnews_saves_one_folder_and_opens_it(pc, tmp_path):
    msg = pc.t_make_cardnews(title="분리배출", cards=CARDS, subtitle="캠페인")
    folder = tmp_path / "docs" / "ULTRON" / "분리배출 카드뉴스"
    assert sorted(p.name for p in folder.iterdir()) == [f"0{i}.png" for i in range(1, 6)] + ["분리배출 카드뉴스.pdf"]
    assert pc.opened == [str(folder)]
    assert "카드뉴스를 만들었다 — 5장" in msg and "문서의 ULTRON 폴더 안의 '분리배출 카드뉴스' 폴더" in msg
    again = pc.t_make_cardnews(title="분리배출", cards=CARDS[:1], open=False)
    assert "'분리배출 카드뉴스 (2)' 폴더" in again and len(list(folder.glob("*.png"))) == 5      # 예전 것을 지우지 않는다
    pc.t_make_cardnews(title="분리배출", cards=CARDS[:1], overwrite=True, open=False)
    assert len(list(folder.glob("*.png"))) == 3                                                # 고치라면 같은 폴더를 새로 채운다


def test_make_poster_saves_png_and_pdf_and_opens_the_picture(pc, tmp_path):
    msg = pc.t_make_poster(title="가을 축제", sections=[{"heading": "일시", "bullets": ["11월 20일"]}], size="a3",
                           folder="바탕화면")
    png = tmp_path / "desk" / "가을 축제.png"
    assert png.exists() and png.with_suffix(".pdf").exists() and pc.opened == [str(png)]
    assert "포스터를 만들었다 — A3 세로, 구역 1개" in msg and "저장한 곳: 바탕화면 " in msg


def test_missing_korean_font_or_pillow_is_explained(pc, monkeypatch):
    monkeypatch.setattr(design, "_FONTS", {"regular": [], "bold": []})
    monkeypatch.setattr(design, "_CACHE", {})
    with pytest.raises(T.ToolError, match="맑은 고딕"):
        pc.t_make_poster(title="x", sections=["a"])

    def no_pillow(*a, **k):
        raise ModuleNotFoundError("No module named 'PIL'", name="PIL")

    monkeypatch.setattr(design, "build_cardnews", no_pillow)
    with pytest.raises(T.ToolError, match="Pillow.*setup.bat"):
        pc.t_make_cardnews(title="x", cards=["a"])


def test_design_tools_are_described_for_claude_with_labels():
    schemas = {d["name"]: d for d in T.PCTools.schemas(T.PCTools.__new__(T.PCTools))}
    assert schemas["make_cardnews"]["input_schema"]["required"] == ["title", "cards"]
    assert schemas["make_poster"]["input_schema"]["required"] == ["title", "sections"]
    for name in ("make_cardnews", "make_poster"):
        assert set(schemas[name]["input_schema"]["properties"]["theme"]["enum"]) == set(office.THEMES)
        assert len(schemas[name]["description"]) > 80
    assert T.PCTools.label("make_cardnews", {"title": "분리배출"}) == "카드뉴스 만들기 · 분리배출"
    assert T.PCTools.label("make_poster", {"title": "축제"}) == "포스터 만들기 · 축제"


# ---------------------------------------------------------------- 카드뉴스다운 모양 (카드마다 다른 모양 · 아이콘 · 스타일)
from jarvis import icons  # noqa: E402


def _card(**kw):
    base = {"title": "제목", "bullets": [], "highlight": "", "stat": None, "quote": "", "layout": "", "icon": None,
            "left": None, "right": None}
    base.update(kw)
    return base


def test_bundled_pretendard_is_used_for_every_weight_when_present():
    for w in ("regular", "semibold", "bold", "extrabold", "black"):
        f = design.font_file(w)
        if (design._OWN / "Pretendard-Regular.otf").exists():
            assert f.parent == design._OWN and f.name.startswith("Pretendard")
    assert design.font_file("black") != design.font_file("regular")              # 제목은 굵은 글꼴


def test_layout_is_chosen_from_the_content():
    pick = lambda **kw: design.choose_layout(design._card_data(kw, 1))           # noqa: E731
    assert pick(title="하나", bullets=["짧게"]) == "point"
    assert pick(title="여럿", bullets=["가", "나", "다"]) == "list"
    assert pick(title="만드는 방법", bullets=["가", "나", "다"]) == "steps"
    assert pick(title="숫자", stat={"value": "70%", "label": "재활용"}) == "stat"
    assert pick(title="비교", left={"bullets": ["a"]}, right={"bullets": ["b"]}) == "compare"
    assert pick(title="비교", compare=[{"bullets": ["a"]}, {"bullets": ["b"]}]) == "compare"
    assert pick(title="인용", quote="한 문장") == "quote"
    assert pick(title="고른 모양", layout="list", bullets=["가"]) == "list"
    assert pick(title="stat 없이 stat", layout="stat", bullets=["가"]) == "point"     # 쓸 수 없는 모양은 고르지 않는다
    assert pick(title="한쪽만 비교", layout="compare", left={"bullets": ["a"]}) == "point"


@pytest.mark.parametrize("title, stat, rest", [
    ("한국 청소년 평균 수면 6시간", "6시간", "한국 청소년 평균 수면"),
    ("재활용되는 플라스틱 9%", "9%", "재활용되는 플라스틱"),
    ("하루 3시간 이상 스마트폰", None, None),                                      # 숫자가 끝에 있지 않다 — 그대로
    ("고3 10명 중 7명", None, None),                                               # 숫자가 여럿 — 그대로
])
def test_a_title_ending_with_a_number_becomes_a_big_number_card(title, stat, rest):
    c = design._card_data({"title": title, "bullets": ["설명 한 줄"]}, 1)
    changed = design.auto_stat(c)
    assert changed == (stat is not None)
    if stat:
        assert c["stat"] == stat and c["title"] == rest and design.choose_layout(c) == "stat"
    else:
        assert c["title"] == title and not c["stat"]
    many = design._card_data({"title": "평균 수면 6시간", "bullets": ["가", "나", "다"]}, 1)
    assert not design.auto_stat(many)                                              # 글이 많으면 목록 그대로


def test_stat_value_splits_number_and_unit():
    assert design._split_stat("6시간") == ("6", "시간")
    assert design._split_stat("70%") == ("70", "%")
    assert design._split_stat("4.7시간") == ("4.7", "시간")
    assert design._split_stat("10명 중 7명") == ("10명 중 7명", "")


def test_icons_come_from_korean_words_and_do_not_repeat():
    assert icons.available()
    assert icons.from_text("스마트폰이 잠을 훔친다") == "smartphone"               # 먼저 나온 낱말
    assert icons.from_text("분리배출 제대로 하기") == "recycling"
    assert icons.from_text("특별 강연") == "record_voice_over"
    assert icons.from_text("잠이 줄면 생기는 일") == "bedtime"                      # '일' 은 직업이 아니다
    assert icons.pick("Bed Time") == "bedtime" and icons.pick("없는이름", "커피") == "local_cafe"
    assert icons.pick(None, "아무 관련 없는 글", kind="list") == icons.DEFAULTS["list"]
    assert icons.pick(None, "잠과 스마트폰", avoid={"bedtime"}) == "smartphone"      # 이미 쓴 것은 피한다
    info = design.build_cardnews(Path(tempfile.mkdtemp()) / "아이콘", "잠", [
        {"title": "잠이 부족하면", "bullets": ["가"]}, {"title": "잠과 스마트폰", "bullets": ["나"]},
        {"title": "잠을 늘리려면", "bullets": ["다"]}])
    assert info["cards"] == 5


@pytest.mark.parametrize("style", design.STYLES)
def test_every_style_draws_every_card_shape(tmp_path, style):
    cards = [{"title": "평균 수면", "stat": {"value": "6시간", "label": "청소년"}, "bullets": ["설명"]},
             {"title": "이렇게 바꿔요", "left": {"title": "그만", "bullets": ["새벽 게임"]},
              "right": {"title": "이렇게", "bullets": ["30분 전 화면 끄기"]}},
             {"title": "만드는 방법", "bullets": ["하나: 설명", "둘: 설명", "셋: 설명"]},
             {"title": "", "quote": "잠은 선물이다", "bullets": ["누군가"]},
             {"title": "체크리스트", "bullets": ["가", "나", "다", "라"], "highlight": "꼭 지켜요"},
             {"title": "핵심 하나", "bullets": ["짧은 설명"], "highlight": "강조"}]
    info = design.build_cardnews(tmp_path / style, "스타일 시험", cards, subtitle="캠페인", style=style)
    assert info["style"] == style and info["layouts"] == ["stat", "compare", "steps", "quote", "list", "point"]
    for f in info["files"]:
        assert colours(f) > 50


def test_style_names_in_korean_and_unknown_style_falls_back(tmp_path):
    assert design.build_cardnews(tmp_path / "a", "제목", CARDS[:1], style="파스텔")["style"] == "pastel"
    assert design.build_cardnews(tmp_path / "b", "제목", CARDS[:1], style="없는스타일")["style"] == "clean"


def test_gradient_text_stays_readable_on_light_accents():
    light = design.Look(office.THEMES["mono"], "gradient")                         # 노랑
    dark = design.Look(office.THEMES["navy"], "gradient")
    for look in (light, dark):
        assert min(design.contrast(look.ink, look.g1), design.contrast(look.ink, look.g2)) >= 3.0   # 큰 굵은 글씨 기준
    assert light.ink != (255, 255, 255)                                              # 노랑 바탕엔 어두운 글씨
    assert design.Look(office.THEMES["purple"], "gradient").ink == (255, 255, 255)
    for name in office.THEMES:                                                      # 어떤 색 테마든 읽힌다
        lk = design.Look(office.THEMES[name], "gradient")
        assert min(design.contrast(lk.ink, lk.g1), design.contrast(lk.ink, lk.g2)) >= 3.0, name


def test_translucent_watermark_is_faint_not_solid(tmp_path):
    """강렬 스타일의 큰 쪽 번호는 흐리게 깔린다 (Pillow 는 글자에 반투명을 쓰지 않으므로 따로 칠한다)."""
    th = office.THEMES["warm"]
    f = design.build_cardnews(tmp_path / "w", "제목", [{"title": "짧게", "bullets": ["가"]}], style="bold",
                              theme="warm")["files"][1]
    with Image.open(f) as im:
        crop = im.convert("RGB").crop((780, 820, 1050, 1000))
        accent, bg = design._rgb(th.accent), design._rgb(th.bg)
        solid = sum(1 for px in list(crop.getdata()) if sum(abs(a - b) for a, b in zip(px, accent)) < 30)
        assert solid < crop.width * crop.height * 0.02                              # 강조색 그대로인 곳은 거의 없다


def test_poster_info_bar_splits_date_and_place():
    assert design._info_parts("10월 17일(토) 오전 10시 · 본관 체육관") == ["10월 17일(토) 오전 10시", "본관 체육관"]
    assert design._info_parts("입장 무료") == ["입장 무료"]
    assert design._info_parts("a · b · c · d") == ["a · b · c · d"]                 # 너무 잘게 나누지 않는다


@pytest.mark.parametrize("text, icon", [
    ("집중력 · 기억력 저하", None),                  # '집중력'의 '집'은 집(home)이 아니다
    ("검색 잘하는 법", "lightbulb"),                  # '~하는 법'은 방법 (법원 아님)
    ("법을 지켜요", "gavel"),
    ("아이디어 내기", "lightbulb"),                   # '아이디어'의 '아이'는 어린이가 아니다
    ("준비물 챙기기", None),                          # '준비'의 '비'는 비(rain)가 아니다
    ("회원 가입", "how_to_reg"),                      # '회원'의 '원'은 돈이 아니다
    ("1만 원 아끼기", "payments"),
    ("요약", None),                                   # '요약'의 '약'은 약(medicine)이 아니다
    ("책임감 키우기", None),
    ("잠깐 쉬어요", None),                            # '잠깐'은 잠(sleep)이 아니다
    ("운동장에서 만나요", "place"),
    ("AI와 미래 직업", "smart_toy"),
    ("자연스럽게 말하기", "forum"),
])
def test_icon_words_are_not_mistaken(text, icon):
    assert icons.from_text(text) == icon
