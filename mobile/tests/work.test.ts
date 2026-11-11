import { describe, expect, it } from "vitest";
import JSZip from "jszip";
import { writeFileSync, mkdirSync } from "node:fs";
import { checkSchema, runWork, validateWork, type WorkHost, type NewDoc } from "../src/work";
import { calendarUrl } from "../src/tools";
import { buildPptx } from "../src/office/pptx";
import { cardnewsMarkdown } from "../src/office/outline";

function host() {
  const made: NewDoc[] = [];
  const h: WorkHost = {
    makeDoc: (d) => { made.push(d); return { id: d.docId ?? "doc1", revised: !!d.docId }; },
    docCard: () => {},
    progress: () => {},
    team: {
      sections: async (_t, outline, _f, onDone) => outline.map((o) => { onDone(1); return `${o.heading} 본문`; }),
      slides: async (_t, outline, _f, onDone) => { onDone(outline.length); return outline.map((o) => ({ title: o.heading, bullets: ["가", "나"] })); },
    },
  };
  return { h, made };
}

describe("입력 검사 (스키마)", () => {
  it("타입 · 필수 · 개수 · 열거", () => {
    const s = { type: "object", properties: { a: { type: "string", enum: ["x", "y"] }, b: { type: "array", maxItems: 2, items: { type: "number" } } }, required: ["a"] };
    expect(checkSchema(s, { a: "x", b: [1, 2] })).toBeNull();
    expect(checkSchema(s, { b: [1] })).toMatch(/a 가 필요함/);
    expect(checkSchema(s, { a: "z" })).toMatch(/x · y/);
    expect(checkSchema(s, { a: "x", b: [1, 2, 3] })).toMatch(/2개 이하/);
    expect(checkSchema(s, { a: "x", b: ["1"] })).toMatch(/number/);
  });
  it("차트 값 개수가 항목 수와 다르면 거절", () => {
    const bad = { title: "t", slides: [{ title: "s", bullets: [], chart: { type: "bar", labels: ["a", "b"], series: [{ name: "n", values: [1] }] } }] };
    expect(validateWork("make_presentation", bad)).toMatch(/values 개수/);
  });
  it("모르는 테마는 거절", () => {
    expect(validateWork("make_cardnews", { title: "t", cards: [{ title: "c", bullets: ["a"] }], style: "neon" })).toMatch(/중 하나/);
  });
});

describe("결과물 도구", () => {
  it("카드뉴스 · 포스터를 만들고 doc_id 로 고친다", async () => {
    const { h, made } = host();
    const r1 = await runWork("make_cardnews", { title: "분리배출 꿀팁", subtitle: "환경 상식", cards: [{ title: "페트병", bullets: ["라벨 떼기", "찌그러뜨리기"], highlight: "뚜껑은 따로" }], style: "green" }, h);
    expect(r1.isError).toBeUndefined();
    expect(r1.content).toContain("doc_id: doc1");
    expect(made[0]).toMatchObject({ kind: "cardnews", style: "green", want: "png" });
    const r2 = await runWork("make_poster", { title: "축제", sections: [{ heading: "일시", bullets: ["5월 3일"] }], doc_id: "abc" }, h);
    expect(r2.content).toContain("고쳤다");
    expect(made[1]).toMatchObject({ kind: "poster", docId: "abc" });
  });
  it("팀: 긴 문서 · 발표 자료를 개요대로 조립한다", async () => {
    const { h, made } = host();
    await runWork("write_long_document", { title: "보고서", outline: [{ heading: "서론", brief: "b" }, { heading: "본론", brief: "b" }], file: "hwpx" }, h);
    expect(made[0].content).toBe("## 서론\n\n서론 본문\n\n## 본론\n\n본론 본문");
    expect(made[0].want).toBe("hwpx");
    await runWork("write_long_presentation", { title: "발표", outline: [{ heading: "1장", brief: "b" }, { heading: "2장", brief: "b" }], style: "navy" }, h);
    expect(made[1]).toMatchObject({ kind: "slides", style: "navy" });
    expect(made[1].slides).toHaveLength(2);
  });
});

describe("일정", () => {
  it("구글 캘린더 주소", () => {
    const u = new URL(calendarUrl("치과", "2026-11-20T15:00", undefined, "강남", "스케일링"));
    expect(u.searchParams.get("action")).toBe("TEMPLATE");
    expect(u.searchParams.get("text")).toBe("치과");
    expect(u.searchParams.get("dates")).toMatch(/^\d{8}T\d{6}Z\/\d{8}T\d{6}Z$/);
    expect(new URL(calendarUrl("소풍", "2026-11-20")).searchParams.get("dates")).toBe("20261120/20261121");
  });
});

describe("PPT 차트 · 표 · 테마", () => {
  it("차트와 표가 들어간다", async () => {
    const data = await buildPptx({
      title: "우리 반 설문", subtitle: "3학년 2반", style: "teal",
      slides: [
        { title: "좋아하는 과목", bullets: ["체육이 1위", "수학은 3위"], chart: { type: "bar", title: "학생 수", labels: ["체육", "미술", "수학"], series: [{ name: "명", values: [12, 8, 5] }] } },
        { title: "비율", bullets: [], chart: { type: "pie", labels: ["찬성", "반대"], series: [{ name: "비율", values: [70, 30] }] } },
        { title: "월별 독서량", bullets: ["꾸준히 증가"], chart: { type: "line", labels: ["9월", "10월", "11월"], series: [{ name: "권", values: [3, 5, 8] }, { name: "목표", values: [4, 4, 4] }] } },
        { title: "비교표", bullets: ["A 가 저렴"], table: { columns: ["제품", "가격"], rows: [["A", 1000], ["B", "1,500"]] } },
      ],
    });
    if (process.env.OFFICE_OUT) { mkdirSync(process.env.OFFICE_OUT, { recursive: true }); writeFileSync(`${process.env.OFFICE_OUT}/charts.pptx`, data); }
    const zip = await JSZip.loadAsync(data);
    const charts = Object.keys(zip.files).filter((f) => /^ppt\/charts\/chart\d+\.xml$/.test(f));
    expect(charts).toHaveLength(3);
    const s5 = await zip.file("ppt/slides/slide5.xml")!.async("string");
    expect(s5).toContain("<a:tbl>");
    expect(cardnewsMarkdown("t", "s", [{ title: "c", bullets: ["a"], highlight: "h" }], "끝", ["src"])).toContain("> h");
  });
});
