"""결과물 품질 — 엑셀 수식 결과 · 숫자 칸, 워드 A4 · 굵게 · 표, 차트 색, 원 차트 이름표, 큰 제목 줄 나누기."""
import zipfile

import pytest

from jarvis import office


# ---------------------------------------------------------------- 엑셀
def test_formula_results_are_precomputed_for_viewers_that_do_not_recalculate():
    v = {(3, 1): 92, (3, 2): 88, (3, 3): 95, (4, 1): 78}
    assert office.eval_formula("=AVERAGE(B4:D4)", v) == pytest.approx(91.6667, abs=1e-3)
    assert office.eval_formula("=ROUND(AVERAGE(B4:D4),1)", v) == 91.7
    assert office.eval_formula("=B4*2+C4", v) == 272
    assert office.eval_formula("=MAX(B4:D5)-MIN(B4:D5)", v) == 17
    for bad in ("=B9", "=VLOOKUP(A1,B1:C3,2)", "=__import__('os')", "=B4/0", "=" + "1+" * 200 + "1"):
        assert office.eval_formula(bad, v) is None          # 모르는 것은 계산하지 않고 엑셀에 맡긴다


def test_number_like_text_becomes_a_real_number():
    assert office.cell_number("1,025") == (1025, "int")
    assert office.cell_number("86.9") == (86.9, "num")
    assert office.cell_number("12.5%") == (0.125, "0.0%")
    for keep in ("010-1234-5678", "01234", "3학년", "1,2,3", "A1"):
        assert office.cell_number(keep) is None


def test_spreadsheet_row_placeholders_and_widths(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    p = tmp_path / "성적.xlsx"
    office.build_spreadsheet(p, [{"name": "성적", "title": "1학기 성적", "columns": ["이름", "국어", "수학", "평균"],
                                  "rows": [["가", 90, "80", "=AVERAGE(B{r}:C{r})"], ["나", 70, 60, "=AVERAGE(B{r}:C{r})"],
                                           ["합계", "=SUM(B{first}:B{last})", "=SUM(C{first}:C{last})", ""]]}])
    ws = openpyxl.load_workbook(p).active
    assert ws["D4"].value == "=AVERAGE(B4:C4)" and ws["D5"].value == "=AVERAGE(B5:C5)"     # 제목이 있으면 데이터는 4행부터
    assert ws["B6"].value == "=SUM(B4:B6)"
    assert ws["C4"].value == 80                                                              # "80" → 숫자
    cached = openpyxl.load_workbook(p, data_only=True).active
    assert cached["D4"].value == 85 and cached["D5"].value == 65
    assert ws.column_dimensions["D"].width < 15                                             # 수식 글자 길이로 넓히지 않는다


# ---------------------------------------------------------------- 워드
def test_word_report_is_a4_with_real_bold_and_tidy_tables(tmp_path):
    docx = pytest.importorskip("docx")
    p = tmp_path / "r.docx"
    office.build_document(p, "보고서", [
        {"heading": "원인", "paragraphs": ["가장 큰 원인은 **화석 연료**다."], "bullets": ["온실가스: 열을 붙잡는 기체", "그냥 한 줄"]},
        {"heading": "표", "table": {"columns": ["부문", "비중(%)"], "rows": [["에너지", "86.9"], ["산업", "7.8"]]}}])
    d = docx.Document(str(p))
    sec = d.sections[0]
    assert (round(sec.page_width.mm), round(sec.page_height.mm)) == (210, 297)
    text = "".join(par.text for par in d.paragraphs)
    assert "**" not in text
    bold = [r.text for par in d.paragraphs for r in par.runs if r.bold]
    assert "화석 연료" in bold and "온실가스: " in bold and "그냥 한 줄" not in bold
    xml = zipfile.ZipFile(p).read("word/document.xml").decode()
    assert "w:tblHeader" in xml and 'w:color="B8C2D6"' in xml
    styles = zipfile.ZipFile(p).read("word/styles.xml").decode()
    heading = styles[styles.find('w:styleId="Heading1"'):][:900]
    assert "asciiTheme" not in heading and "eastAsiaTheme" not in heading                  # 테마 글꼴이 맑은 고딕을 덮지 않게
    t = d.tables[0]
    assert t.rows[1].cells[1].paragraphs[0].alignment == 2                                   # 숫자 칸 오른쪽 맞춤 (RIGHT)
    assert office.numeric_text("1,200명") and not office.numeric_text("3학년 2반")


# ---------------------------------------------------------------- 발표 자료
def test_chart_colors_are_distinct_hues_starting_with_the_accent():
    for name, t in office.THEMES.items():
        cols = office.palette(t)
        assert cols[0] == t.accent and len(set(cols)) == len(cols) >= 5, name
        hues = [office._hue(c)[0] for c in cols[:4]]
        gaps = [min(abs(a - b), 1 - abs(a - b)) for i, a in enumerate(hues) for b in hues[i + 1:]]
        assert min(gaps) > 0.03, name                                                         # 같은 색의 밝기만 다른 색이 아니다


def test_pie_slices_are_labelled_with_names_instead_of_a_legend(tmp_path):
    pptx = pytest.importorskip("pptx")
    p = tmp_path / "pie.pptx"
    office.build_presentation(p, "원 차트", [{"layout": "chart", "title": "비중", "chart": {
        "type": "pie", "categories": ["에너지", "산업", "농업"], "series": [{"name": "비중", "values": [87, 8, 5]}], "unit": "%"}}])
    chart = next(sh.chart for sl in pptx.Presentation(str(p)).slides for sh in sl.shapes if sh.has_chart)
    assert not chart.has_legend
    dl = chart.plots[0].data_labels
    assert dl.show_category_name and dl.show_value


# ---------------------------------------------------------------- 카드뉴스 · 포스터 제목
def test_big_titles_are_balanced(monkeypatch):
    from jarvis import design

    class Measure:                     # 글자 하나 = 1 (글꼴 파일 없이 줄 나누기만 본다)
        def textlength(self, s, font=None):
            return len(s)
    d = Measure()
    lines = design.wrap(d, "2026 가을 과학 축제", None, 11)
    assert lines == ["2026 가을 과학", "축제"]
    assert design.balance(d, "2026 가을 과학 축제", None, 11, lines) == ["2026 가을", "과학 축제"]
    assert design.balance(d, "짧은 제목", None, 20, ["짧은 제목"]) == ["짧은 제목"]
