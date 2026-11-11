// 결과물을 만드는 도구들: 문서 · 발표 자료 · 표 · 카드뉴스 · 포스터, 그리고 긴 결과물을 여럿이 나눠 쓰는 "팀" 도구
//
// 도구 입력은 여기 적은 input_schema 그대로 checkSchema 로 검사한다 (설명과 검사가 어긋나지 않게).

import type Anthropic from "@anthropic-ai/sdk";
import type { CardData, Chart, DeckSlide, DocKind, ExportFormat, PosterSection, SheetData } from "./store";
import { THEME_NAMES } from "./store";

export interface NewDoc {
  kind: DocKind;
  title: string;
  content?: string;
  subtitle?: string;
  style?: string;
  slides?: DeckSlide[];
  sheets?: SheetData[];
  cards?: CardData[];
  closing?: string;
  sections?: PosterSection[];
  highlight?: string;
  footer?: string;
  sources?: string[];
  want?: ExportFormat;
  docId?: string;          // 있으면 그 결과물을 고친 판으로 바꾼다
}

export interface Outline { heading: string; brief: string }

/** 여럿이 동시에 쓰기 (brain.ts 가 구현) */
export interface Team {
  sections(title: string, outline: Outline[], facts: string, onDone: (n: number) => void): Promise<string[]>;
  slides(title: string, outline: Outline[], facts: string, onDone: (n: number) => void): Promise<DeckSlide[]>;
}

export interface WorkHost {
  makeDoc(d: NewDoc): { id: string; revised: boolean };
  docCard(id: string, title: string, detail: string, want?: ExportFormat): void;
  progress(text: string): void;
  team: Team;
}

export interface Outcome { content: string; isError?: boolean }

// ---------------------------------------------------------------- 입력 검사 (JSON 스키마의 쓰는 부분만)
type Schema = {
  type?: string | string[]; enum?: unknown[]; properties?: Record<string, Schema>; required?: string[];
  items?: Schema; minItems?: number; maxItems?: number; maxLength?: number; minimum?: number; maximum?: number; description?: string;
};

export function checkSchema(s: Schema, v: unknown, path = "입력"): string | null {
  const types = s.type === undefined ? [] : Array.isArray(s.type) ? s.type : [s.type];
  const is = (t: string) =>
    t === "string" ? typeof v === "string"
    : t === "number" ? typeof v === "number" && Number.isFinite(v)
    : t === "integer" ? Number.isInteger(v)
    : t === "boolean" ? typeof v === "boolean"
    : t === "array" ? Array.isArray(v)
    : t === "object" ? typeof v === "object" && v !== null && !Array.isArray(v)
    : false;
  if (types.length && !types.some(is)) return `${path} 는 ${types.join(" · ")} 이어야 함`;
  if (s.enum && !s.enum.includes(v)) return `${path} 는 ${s.enum.join(" · ")} 중 하나`;
  if (typeof v === "string" && s.maxLength !== undefined && v.length > s.maxLength) return `${path} 가 너무 김 (${s.maxLength}자 이하)`;
  if (typeof v === "number") {
    if (s.minimum !== undefined && v < s.minimum) return `${path} 는 ${s.minimum} 이상`;
    if (s.maximum !== undefined && v > s.maximum) return `${path} 는 ${s.maximum} 이하`;
  }
  if (Array.isArray(v)) {
    if (s.minItems !== undefined && v.length < s.minItems) return `${path} 는 ${s.minItems}개 이상`;
    if (s.maxItems !== undefined && v.length > s.maxItems) return `${path} 는 ${s.maxItems}개 이하`;
    if (s.items) for (let i = 0; i < v.length; i++) { const e = checkSchema(s.items, v[i], `${path}[${i}]`); if (e) return e; }
  }
  if (typeof v === "object" && v !== null && !Array.isArray(v)) {
    const o = v as Record<string, unknown>;
    for (const r of s.required ?? []) {
      if (o[r] === undefined || o[r] === null || o[r] === "") return `${path}.${r} 가 필요함`;
    }
    for (const [k, sub] of Object.entries(s.properties ?? {})) {
      if (o[k] !== undefined && o[k] !== null) { const e = checkSchema(sub, o[k], `${path}.${k}`); if (e) return e; }
    }
  }
  return null;
}

// ---------------------------------------------------------------- 스키마 조각
const str = (description: string, maxLength = 2000): Schema => ({ type: "string", description, maxLength });
const strList = (description: string, maxItems = 20): Schema => ({ type: "array", items: { type: "string", maxLength: 1000 }, description, maxItems });
const STYLE: Schema = {
  type: "string", enum: THEME_NAMES,
  description: "색 테마: light(흰 바탕 · 파랑, 기본) · dark · navy · warm(주황) · green · purple · teal · rose(분홍) · mono(노랑 강조) · midnight · forest · ultron(검붉은). 주제 분위기에 맞게 고른다.",
};
const DOC_ID: Schema = { type: "string", description: "방금 만든 결과물을 고칠 때 그 doc_id (도구 결과에 나온 값). 새로 만들 때는 비운다.", maxLength: 40 };
const SOURCES: Schema = strList("출처 (사이트 이름 + 주소). 검색했으면 넣는다", 10);
const CHART: Schema = {
  type: "object",
  description: "차트 (숫자 비교 · 변화 · 비율을 보여 줄 때만)",
  properties: {
    type: { type: "string", enum: ["bar", "line", "pie"], description: "bar = 비교, line = 시간에 따른 변화, pie = 비율" },
    title: str("차트 제목", 100),
    labels: strList("항목 이름들 (가로축)", 24),
    series: {
      type: "array", maxItems: 6, description: "값 묶음들 (pie 는 하나)",
      items: { type: "object", properties: { name: str("묶음 이름", 60), values: { type: "array", items: { type: "number" }, maxItems: 24, description: "labels 순서대로 값" } }, required: ["name", "values"] },
    },
  },
  required: ["type", "labels", "series"],
};
const TABLE: Schema = {
  type: "object",
  description: "표 (작은 비교표, 10줄 이하)",
  properties: { columns: strList("열 이름들", 8), rows: { type: "array", maxItems: 12, items: { type: "array", items: { type: ["string", "number"] }, maxItems: 8 } } },
  required: ["columns", "rows"],
};
const SLIDE: Schema = {
  type: "object",
  properties: {
    title: str("장 제목", 200),
    bullets: strList("요점 3~6개 (짧은 명사형 문장). 차트 · 표만 보여 줄 장이면 비워도 된다", 12),
    notes: str("발표 대본 (선택)", 3000),
    chart: CHART,
    table: TABLE,
  },
  required: ["title", "bullets"],
};
const OUTLINE: Schema = {
  type: "array", minItems: 2, maxItems: 40,
  items: { type: "object", properties: { heading: str("소제목 / 장 제목", 200), brief: str("이 부분에 쓸 내용 · 요점 · 숫자 · 출처를 구체적으로 (작가는 이것만 보고 쓴다)", 3000) }, required: ["heading", "brief"] },
};

// ---------------------------------------------------------------- 도구 정의
const tool = (name: string, description: string, input_schema: Schema): Anthropic.Beta.BetaTool =>
  ({ name, description, input_schema: input_schema as Anthropic.Beta.BetaTool["input_schema"] });

export const WORK_TOOLS: Anthropic.Beta.BetaTool[] = [
  tool("make_document",
    "보고서 · 정리 · 글 · 안내문 · 가정통신문 · 학습지 · 계획서 같은 문서를 만든다. 한글(HWPX) · 워드(DOCX) · PDF 로 저장할 수 있다. " +
    "content 는 마크다운(## 소제목, - 목록, 1. 번호, **굵게**, | 표 |)으로 쓰고 제목은 title 에만. 출처가 있으면 끝에 '## 출처'. " +
    "길고 소제목이 5개 이상인 보고서는 write_long_document 가 훨씬 빠르다.",
    {
      type: "object",
      properties: {
        title: str("문서 제목", 200),
        content: str("본문 (마크다운)", 200000),
        file: { type: "string", enum: ["hwpx", "docx", "pdf"], description: "사용자가 형식을 말했으면: 한글 · 한컴 · hwp → hwpx, 워드 · 구글 문서 · 독스 → docx, PDF → pdf" },
        doc_id: DOC_ID,
      },
      required: ["title", "content"],
    }),
  tool("make_presentation",
    "발표 자료(PPT)를 만든다. PPTX 로 저장되어 파워포인트 · 구글 슬라이드 · 한쇼에서 열린다. 표지는 자동으로 붙으니 slides 에는 본문 장만. " +
    "숫자를 보여 줄 장에는 chart, 비교표는 table 을 넣는다. 사용자가 장 수를 말하면 그대로. 6장 이상이면 write_long_presentation 이 훨씬 빠르다.",
    {
      type: "object",
      properties: {
        title: str("발표 제목", 200),
        subtitle: str("표지 부제 (발표자 · 반 · 날짜 등)", 200),
        style: STYLE,
        slides: { type: "array", minItems: 1, maxItems: 60, items: SLIDE, description: "본문 장들" },
        doc_id: DOC_ID,
      },
      required: ["title", "slides"],
    }),
  tool("make_spreadsheet",
    "표(엑셀)를 만든다. XLSX 로 저장되어 엑셀 · 구글 스프레드시트 · 한셀에서 열린다. 시간표 · 가계부 · 명단 · 비교표 · 성적표처럼 칸으로 정리할 때. " +
    "숫자는 단위 없이 숫자만 넣고 단위는 열 이름에 (예: '금액(원)').",
    {
      type: "object",
      properties: {
        title: str("표 제목 (파일 이름)", 200),
        sheets: {
          type: "array", minItems: 1, maxItems: 20, description: "시트들 (보통 하나)",
          items: {
            type: "object",
            properties: {
              name: str("시트 이름", 60),
              columns: strList("열 이름들", 100),
              rows: { type: "array", maxItems: 5000, items: { type: "array", items: { type: ["string", "number"] }, maxItems: 100 }, description: "행들 (열 순서대로)" },
            },
            required: ["name", "columns", "rows"],
          },
        },
        doc_id: DOC_ID,
      },
      required: ["title", "sheets"],
    }),
  tool("make_cardnews",
    "인스타그램 · 블로그용 카드뉴스(정사각형 그림 여러 장)를 바로 그린다. 표지와 마무리 장은 자동. 카드 한 장에 요점 2~4개, 짧게. " +
    "highlight 는 그 장의 한 줄 핵심 (선택).",
    {
      type: "object",
      properties: {
        title: str("표지 제목 (짧고 강하게)", 120),
        subtitle: str("표지 위 작은 꼬리표 (예: 환경 상식, 3학년 2반)", 60),
        cards: {
          type: "array", minItems: 1, maxItems: 12, description: "내용 카드들",
          items: { type: "object", properties: { title: str("카드 제목", 120), bullets: strList("요점 2~4개", 6), highlight: str("한 줄 핵심 (선택)", 120) }, required: ["title", "bullets"] },
        },
        closing: str("마지막 장 문구 (첫 줄 크게, 다음 줄 작게)", 300),
        sources: SOURCES,
        style: STYLE,
        doc_id: DOC_ID,
      },
      required: ["title", "cards"],
    }),
  tool("make_poster",
    "포스터 · 홍보물 · 안내문 · 행사 공지를 A4 세로 그림으로 바로 그린다. 구역(sections)은 1~6개.",
    {
      type: "object",
      properties: {
        title: str("큰 제목", 120),
        subtitle: str("부제", 200),
        highlight: str("가장 중요한 한 줄 (일시 · 장소 · 표어 등)", 120),
        sections: {
          type: "array", minItems: 1, maxItems: 6,
          items: { type: "object", properties: { heading: str("구역 제목", 60), bullets: strList("내용", 8) }, required: ["bullets"] },
        },
        footer: str("맨 아래 한 줄 (주최 · 문의)", 120),
        sources: SOURCES,
        style: STYLE,
        doc_id: DOC_ID,
      },
      required: ["title", "sections"],
    }),
  tool("write_long_document",
    "긴 보고서 · 문서를 여러 작가가 동시에 나눠 써서 빠르게 만든다. 당신은 기획자: 소제목별 개요(outline)와, 조사한 사실 · 숫자 · 출처(facts)만 넘기면 " +
    "작가들이 각 부분 본문을 동시에 쓴다. 소제목이 5개 이상이거나 분량이 많은 문서에 쓴다.",
    {
      type: "object",
      properties: {
        title: str("문서 제목", 200),
        outline: { ...OUTLINE, description: "소제목 순서대로" },
        facts: str("작가들이 같이 볼 사실 · 숫자 · 출처 · 대상 · 말투 · 분량 요구", 20000),
        file: { type: "string", enum: ["hwpx", "docx", "pdf"], description: "사용자가 형식을 말했으면" },
        doc_id: DOC_ID,
      },
      required: ["title", "outline"],
    }),
  tool("write_long_presentation",
    "발표 자료를 여러 작가가 동시에 나눠 써서 빠르게 만든다. 당신은 기획자: 장별 개요(outline)와 사실 · 숫자 · 출처(facts)만 넘기면 " +
    "작가들이 요점 · 발표 대본 · 차트 · 표를 동시에 쓴다. 6장 이상이면 이것을 쓴다.",
    {
      type: "object",
      properties: {
        title: str("발표 제목", 200),
        subtitle: str("표지 부제", 200),
        style: STYLE,
        outline: { ...OUTLINE, description: "본문 장 순서대로 (표지는 자동)" },
        facts: str("작가들이 같이 볼 사실 · 숫자 · 출처 · 대상 · 대본 필요 여부", 20000),
        doc_id: DOC_ID,
      },
      required: ["title", "outline"],
    }),
];

const SCHEMAS = new Map(WORK_TOOLS.map((t) => [t.name, t.input_schema as Schema]));
export const isWorkTool = (name: string) => SCHEMAS.has(name);

/** 차트 숫자 개수가 항목 수와 맞는지 같은, 스키마로 못 하는 검사 */
function extraCheck(name: string, i: Record<string, unknown>): string | null {
  const chartOk = (c?: Chart) => !c || (c.labels.length > 0 && c.series.length > 0 && c.series.every((s) => s.values.length === c.labels.length));
  if (name === "make_presentation") {
    for (const s of i.slides as DeckSlide[]) if (!chartOk(s.chart)) return `'${s.title}' 장의 차트: series 마다 values 개수가 labels 개수와 같아야 함`;
  }
  return null;
}

export function validateWork(name: string, input: unknown): string | null {
  const s = SCHEMAS.get(name);
  if (!s) return `모르는 도구: ${name}`;
  return checkSchema(s, input) ?? extraCheck(name, input as Record<string, unknown>);
}

// ---------------------------------------------------------------- 실행
const trimList = (xs: unknown) => ((xs as string[] | undefined) ?? []).map((x) => String(x).trim()).filter(Boolean);
const opt = (x: unknown) => (typeof x === "string" && x.trim() ? x.trim() : undefined);

function cleanSlide(s: DeckSlide): DeckSlide {
  return {
    title: s.title.trim(),
    bullets: trimList(s.bullets),
    ...(opt(s.notes) ? { notes: opt(s.notes) } : {}),
    ...(s.chart ? { chart: { ...s.chart, labels: s.chart.labels.map(String) } } : {}),
    ...(s.table ? { table: s.table } : {}),
  };
}

function report(made: { id: string; revised: boolean }, what: string, button: string): Outcome {
  const verb = made.revised ? "고쳤다" : "만들었다";
  return {
    content: `${what}을(를) ${verb}. doc_id: ${made.id}. 사용자 화면의 카드에서 '${button}'을 누르면 파일로 저장되고 알맞은 앱으로 열 수 있다. ` +
      "고쳐 달라고 하면 같은 도구에 이 doc_id 를 넣어 전체를 다시 보내라.",
  };
}

export async function runWork(name: string, input: unknown, host: WorkHost): Promise<Outcome> {
  const bad = validateWork(name, input);
  if (bad) return { content: JSON.stringify({ INVALID_INPUT: bad }), isError: true };
  const i = input as Record<string, unknown>;
  const title = String(i.title).trim();
  const docId = opt(i.doc_id);
  const style = opt(i.style);
  switch (name) {
    case "make_document": {
      const want = i.file as ExportFormat | undefined;
      const made = host.makeDoc({ kind: "doc", title, content: String(i.content), want, docId });
      host.docCard(made.id, title, made.revised ? "문서 · 고친 판" : "문서", want);
      return report(made, "문서", want === "hwpx" ? "한글 파일" : want === "docx" ? "워드 파일" : want === "pdf" ? "PDF" : "한글 · 워드 파일");
    }
    case "make_presentation": {
      const slides = (i.slides as DeckSlide[]).map(cleanSlide);
      const made = host.makeDoc({ kind: "slides", title, subtitle: opt(i.subtitle), style, slides, want: "pptx", docId });
      host.docCard(made.id, title, `발표 자료 · 표지 포함 ${slides.length + 1}장${made.revised ? " · 고친 판" : ""}`, "pptx");
      return report(made, `발표 자료(표지 포함 ${slides.length + 1}장)`, "PPT 파일");
    }
    case "make_spreadsheet": {
      const sheets = (i.sheets as SheetData[]).map((s) => ({ name: s.name.trim(), columns: s.columns.map((c) => String(c).trim()), rows: s.rows }));
      const made = host.makeDoc({ kind: "sheet", title, sheets, want: "xlsx", docId });
      const rows = sheets.reduce((a, s) => a + s.rows.length, 0);
      host.docCard(made.id, title, `표 · ${rows}줄${made.revised ? " · 고친 판" : ""}`, "xlsx");
      return report(made, `표(${rows}줄)`, "엑셀 파일");
    }
    case "make_cardnews": {
      const cards = (i.cards as CardData[]).map((c) => ({ title: c.title.trim(), bullets: trimList(c.bullets), ...(opt(c.highlight) ? { highlight: opt(c.highlight) } : {}) }));
      const made = host.makeDoc({ kind: "cardnews", title, subtitle: opt(i.subtitle), cards, closing: opt(i.closing), sources: trimList(i.sources), style, want: "png", docId });
      host.docCard(made.id, title, `카드뉴스 · ${cards.length + 2}장${made.revised ? " · 고친 판" : ""}`, "png");
      return report(made, `카드뉴스(${cards.length + 2}장)`, "그림 저장");
    }
    case "make_poster": {
      const sections = (i.sections as PosterSection[]).map((s) => ({ ...(opt(s.heading) ? { heading: opt(s.heading) } : {}), bullets: trimList(s.bullets) }));
      const made = host.makeDoc({
        kind: "poster", title, subtitle: opt(i.subtitle), highlight: opt(i.highlight), sections, footer: opt(i.footer),
        sources: trimList(i.sources), style, want: "png", docId,
      });
      host.docCard(made.id, title, `포스터 · A4${made.revised ? " · 고친 판" : ""}`, "png");
      return report(made, "포스터", "그림 저장");
    }
    case "write_long_document": {
      const outline = i.outline as Outline[];
      let done = 0;
      host.progress(`작가 ${Math.min(outline.length, 4)}명이 쓰는 중 · 0/${outline.length}`);
      const parts = await host.team.sections(title, outline, String(i.facts ?? ""), () => host.progress(`작가들이 쓰는 중 · ${++done}/${outline.length}`));
      const content = outline.map((o, k) => `## ${o.heading}\n\n${parts[k].trim()}`).join("\n\n");
      const want = i.file as ExportFormat | undefined;
      const made = host.makeDoc({ kind: "doc", title, content, want, docId });
      host.docCard(made.id, title, `문서 · 소제목 ${outline.length}개${made.revised ? " · 고친 판" : ""}`, want);
      return report(made, `문서(소제목 ${outline.length}개)`, want === "hwpx" ? "한글 파일" : want === "docx" ? "워드 파일" : "한글 · 워드 파일");
    }
    case "write_long_presentation": {
      const outline = i.outline as Outline[];
      let done = 0;
      host.progress(`작가들이 쓰는 중 · 0/${outline.length}장`);
      const slides = (await host.team.slides(title, outline, String(i.facts ?? ""), (n) => host.progress(`작가들이 쓰는 중 · ${(done += n)}/${outline.length}장`))).map(cleanSlide);
      const made = host.makeDoc({ kind: "slides", title, subtitle: opt(i.subtitle), style, slides, want: "pptx", docId });
      host.docCard(made.id, title, `발표 자료 · 표지 포함 ${slides.length + 1}장${made.revised ? " · 고친 판" : ""}`, "pptx");
      return report(made, `발표 자료(표지 포함 ${slides.length + 1}장)`, "PPT 파일");
    }
  }
  return { content: `모르는 도구: ${name}`, isError: true };
}
