import { describe, expect, it } from "vitest";
import JSZip from "jszip";
import { writeFileSync, mkdirSync } from "node:fs";
import { buildHwpx } from "../src/office/hwpx";
import { buildDocx } from "../src/office/docx";
import { buildPptx, type Deck } from "../src/office/pptx";
import { deckMarkdown, sheetsMarkdown } from "../src/office/outline";
import { buildCsv, buildXlsx, colName, sheetNames, type Sheet } from "../src/office/xlsx";
import { fileName, parseBlocks, parseRuns } from "../src/office/blocks";

const OUT = process.env.OFFICE_OUT;   // 지정하면 만든 파일을 저장한다 (한컴 · 리브레오피스로 열어 보기용)
const save = (name: string, data: Uint8Array) => {
  if (!OUT) return;
  mkdirSync(OUT, { recursive: true });
  writeFileSync(`${OUT}/${name}`, data);
};

const MD = `# 화성 탐사 보고서

## 1. 개요
화성은 태양계의 **네 번째** 행성이며, *붉은 행성*이라 불린다. <특수문자> & "따옴표" 도 깨지지 않아야 한다.

## 2. 주요 임무
- 퍼서비어런스: 2021년 착륙, 생명 흔적 탐사
- 인저뉴어티: 최초의 다른 행성 동력 비행
1. 시료 채취
2. 지구 귀환

| 임무 | 연도 | 국가 |
|---|---|---|
| 퍼서비어런스 | 2021 | 미국 |
| 톈원 1호 | 2021 | 중국 |

> 화성의 하루는 24시간 37분이다.

### 출처
- [NASA](https://mars.nasa.gov)
`;

const DECK: Deck = {
  title: "화성 탐사의 오늘",
  subtitle: "3학년 2반 과학 발표",
  slides: [
    { title: "화성은 어떤 행성인가", bullets: ["태양계 네 번째 행성", "지구의 절반 크기", "하루는 24시간 37분"], notes: "먼저 화성이 어떤 곳인지 간단히 소개합니다." },
    { title: "지금 활동 중인 탐사선", bullets: ["퍼서비어런스 (미국, 2021)", "톈원 1호 (중국, 2021)", "인저뉴어티 헬리콥터 — 72번 비행 후 임무 종료"] },
  ],
};

const SHEETS: Sheet[] = [
  { name: "탐사선", columns: ["이름", "국가", "착륙 연도", "무게(kg)"], rows: [["퍼서비어런스", "미국", 2021, "1,025"], ["톈원 1호", "중국", "2021", 240], ["우편번호", "01234", "", ""]] },
  { name: "일정/계획?", columns: ["단계", "내용"], rows: [["1", "시료 채취"], ["2", "지구 귀환"]] },
];

describe("마크다운 → 블록", () => {
  it("굵게 · 기울임 · 링크", () => {
    expect(parseRuns("가 **나** *다* [라](https://a.b)")).toEqual([
      { text: "가 " }, { text: "나", bold: true }, { text: " " }, { text: "다", italic: true }, { text: " " }, { text: "라 (https://a.b)" },
    ]);
  });
  it("제목 · 목록 · 표 · 인용", () => {
    const types = parseBlocks(MD).map((b) => b.type);
    expect(types).toEqual(["heading", "heading", "para", "heading", "bullet", "bullet", "number", "number", "table", "quote", "heading", "bullet"]);
  });
  it("파일 이름", () => {
    expect(fileName('보고서: "화성"/최종', "hwpx")).toBe("보고서 화성 최종.hwpx");
  });
});

describe("한글(HWPX)", () => {
  it("mimetype 이 맨 앞에 압축 없이 들어가고 본문 · 모양이 채워진다", async () => {
    const data = await buildHwpx("화성 탐사 보고서", MD);
    save("report.hwpx", data);
    // 첫 로컬 파일 헤더: 이름이 mimetype, 압축 방식 0(STORE)
    const view = new DataView(data.buffer, data.byteOffset);
    expect(view.getUint32(0, true)).toBe(0x04034b50);
    expect(view.getUint16(8, true)).toBe(0);
    expect(new TextDecoder().decode(data.slice(30, 38))).toBe("mimetype");
    const zip = await JSZip.loadAsync(data);
    const header = await zip.file("Contents/header.xml")!.async("string");
    const section = await zip.file("Contents/section0.xml")!.async("string");
    expect(header).toMatch(/<hh:charProperties itemCnt="20">/);
    expect(header).toMatch(/<hh:paraProperties itemCnt="29">/);
    expect(header).toMatch(/<hh:borderFills itemCnt="4">/);
    expect((header.match(/<hh:charPr /g) ?? []).length).toBe(20);
    expect((header.match(/<hh:paraPr /g) ?? []).length).toBe(29);
    expect(section).toContain("&lt;특수문자&gt; &amp; &quot;따옴표&quot;");
    expect(section).toContain('rowCnt="3" colCnt="3"');
    expect(section).toContain("<hp:t>화성 탐사 보고서</hp:t>");
    expect((section.match(/<hp:t>화성 탐사 보고서<\/hp:t>/g) ?? []).length).toBe(1);   // 제목이 두 번 들어가지 않는다
  });
});

describe("워드 · 발표 · 표", () => {
  it("DOCX", async () => {
    const data = await buildDocx("화성 탐사 보고서", MD);
    save("report.docx", data);
    const zip = await JSZip.loadAsync(data);
    const doc = await zip.file("word/document.xml")!.async("string");
    expect(doc).toContain("퍼서비어런스");
    expect(doc).toContain("<w:tbl>");
  });
  it("PPTX", async () => {
    const data = await buildPptx(DECK);
    save("deck.pptx", data);
    save("deck-dark.pptx", await buildPptx({ ...DECK, style: "dark" }));
    const zip = await JSZip.loadAsync(data);
    expect(Object.keys(zip.files).filter((f) => /^ppt\/slides\/slide\d+\.xml$/.test(f))).toHaveLength(3);
    expect(deckMarkdown(DECK)).toContain("## 2. 지금 활동 중인 탐사선");
  });
  it("XLSX · CSV", async () => {
    const data = await buildXlsx(SHEETS);
    save("table.xlsx", data);
    save("table.csv", buildCsv(SHEETS[0]));
    const zip = await JSZip.loadAsync(data);
    const s1 = await zip.file("xl/worksheets/sheet1.xml")!.async("string");
    expect(s1).toContain('<c r="D2" s="0"><v>1025</v></c>');      // "1,025" → 숫자
    expect(s1).toContain('<c r="B4" s="0" t="inlineStr"><is><t xml:space="preserve">01234</t>');   // 0 으로 시작하면 글자
    expect(colName(0)).toBe("A");
    expect(colName(27)).toBe("AB");
    expect(sheetNames(SHEETS)).toEqual(["탐사선", "일정 계획"]);
    expect(sheetsMarkdown("탐사", SHEETS)).toContain("| 퍼서비어런스 | 미국 | 2021 | 1,025 |");
  });
});
