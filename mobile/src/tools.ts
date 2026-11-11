// 휴대폰에서 울트론이 쓰는 도구들
//
// 웹 앱은 다른 앱을 직접 조작하거나 전화를 몰래 걸 수 없다. 전화 · 문자 · 링크 · 지도 · 공유는 화면에 버튼(카드)을 띄우고,
// 사용자가 그 버튼을 눌러야 실제로 일어난다 — 그것이 PC 판의 승인 카드 역할을 한다.

import type Anthropic from "@anthropic-ai/sdk";
import type { DeckSlide, DocKind, ExportFormat, ModelId, SheetData } from "./store";

type Tool = Anthropic.Beta.BetaToolUnion;

export interface ActionCard {
  kind: "call" | "sms" | "link" | "map" | "share" | "doc";
  title: string;
  detail: string;
  href?: string;     // tel: · sms: · https: 링크
  text?: string;     // 공유할 글
  docId?: string;    // 문서 보기
  want?: ExportFormat; // 문서 카드: 바로 만들 파일 형식
}

export interface NewDoc {
  kind: DocKind;
  title: string;
  content?: string;
  subtitle?: string;
  style?: "light" | "dark";
  slides?: DeckSlide[];
  sheets?: SheetData[];
  want?: ExportFormat;
}

/** 도구가 앱에 부탁하는 일 (main.ts 가 구현한다) */
export interface ToolHost {
  remember(fact: string): void;
  forget(query: string): number;
  setTimer(seconds: number, label: string): string;
  cancelTimers(label?: string): number;
  listTimers(): string;
  makeDoc(d: NewDoc): string;   // 문서 id
  card(c: ActionCard): void;
  deviceStatus(): Promise<string>;
}

export interface ToolOutcome {
  content: string;
  isError?: boolean;
}

const str = { type: "string" } as const;

// 사용자 도구 (스트리밍 요청이므로 eager_input_streaming 을 켜고, 받은 입력은 아래 validate 로 직접 검사한다)
const CLIENT_TOOLS: Anthropic.Beta.BetaTool[] = [
  {
    name: "remember",
    description: "사용자에 대해 기억할 사실을 저장한다. 다음 대화부터도 기억한다. 예: 'OO는 매운 음식을 못 먹는다'.",
    input_schema: { type: "object", properties: { fact: { ...str, description: "기억할 사실 한 문장" } }, required: ["fact"] },
  },
  {
    name: "forget",
    description: "기억하고 있는 사실 중 query 가 들어간 것을 지운다.",
    input_schema: { type: "object", properties: { query: { ...str, description: "지울 기억에 들어 있는 낱말" } }, required: ["query"] },
  },
  {
    name: "set_timer",
    description: "N초 뒤에 울리는 타이머 · 알림을 맞춘다.",
    input_schema: {
      type: "object",
      properties: {
        seconds: { type: "integer", description: "몇 초 뒤 (1 ~ 86400)" },
        label: { ...str, description: "울릴 때 말할 내용. 예: '라면 다 됐다', '회의 시작'" },
      },
      required: ["seconds", "label"],
    },
  },
  {
    name: "cancel_timer",
    description: "타이머를 취소한다. label 을 비우면 모두 취소한다. 남은 타이머 목록이 필요하면 label 에 '?' 를 넣는다.",
    input_schema: { type: "object", properties: { label: { ...str, description: "취소할 타이머 이름 일부 (비우면 전부, '?' 면 목록)" } }, required: [] },
  },
  {
    name: "call_phone",
    description: "전화 걸기 버튼을 화면에 띄운다. 사용자가 눌러야 걸린다.",
    input_schema: {
      type: "object",
      properties: { number: { ...str, description: "전화번호 (숫자 · + · - 만)" }, name: { ...str, description: "받는 사람 이름 (있으면)" } },
      required: ["number"],
    },
  },
  {
    name: "send_sms",
    description: "문자 보내기 버튼을 화면에 띄운다 (내용이 미리 채워진 문자 앱이 열림). 사용자가 눌러야 열린다.",
    input_schema: {
      type: "object",
      properties: { number: { ...str, description: "받는 번호" }, body: { ...str, description: "보낼 내용" } },
      required: ["number", "body"],
    },
  },
  {
    name: "open_url",
    description: "웹 페이지 열기 버튼을 화면에 띄운다. 사이트 · 유튜브 검색 결과 · 길찾기 등.",
    input_schema: {
      type: "object",
      properties: { url: { ...str, description: "https:// 로 시작하는 주소" }, title: { ...str, description: "버튼에 쓸 짧은 이름" } },
      required: ["url", "title"],
    },
  },
  {
    name: "open_map",
    description: "지도에서 장소나 길찾기를 여는 버튼을 띄운다.",
    input_schema: {
      type: "object",
      properties: { query: { ...str, description: "장소 이름이나 주소" }, directions: { type: "boolean", description: "길찾기면 true" } },
      required: ["query"],
    },
  },
  {
    name: "share_text",
    description: "글을 다른 앱(카카오톡, 메모 등)으로 보내는 공유 버튼을 띄운다.",
    input_schema: {
      type: "object",
      properties: { text: { ...str, description: "공유할 글" }, title: { ...str, description: "짧은 제목" } },
      required: ["text"],
    },
  },
  {
    name: "make_document",
    description:
      "보고서 · 정리 · 글 · 계획표 · 가정통신문 같은 문서를 만든다. 사용자는 앱에서 열어 보고, 한글(HWPX) · 워드(DOCX) 파일로 " +
      "저장하거나 한컴오피스 · 구글 문서 · 워드 앱으로 열 수 있다. content 는 마크다운(## 소제목, - 목록, 1. 번호, **굵게**, | 표 |)으로 쓰고 " +
      "제목은 title 에만 쓴다. 출처가 있으면 끝에 '## 출처' 로 적는다.",
    input_schema: {
      type: "object",
      properties: {
        title: { ...str, description: "문서 제목" },
        content: { ...str, description: "문서 본문 (마크다운)" },
        file: { type: "string", enum: ["hwpx", "docx", "pdf"], description: "사용자가 파일 형식을 말했으면: 한글 · 한컴 · hwp → hwpx, 워드 · 구글 문서 · 독스 → docx, PDF → pdf" },
      },
      required: ["title", "content"],
    },
  },
  {
    name: "make_presentation",
    description:
      "발표 자료(PPT)를 만든다. 파워포인트 · 구글 슬라이드 · 한컴오피스 한쇼에서 열리는 PPTX 로 저장된다. 표지는 자동으로 붙으니 slides 에는 본문 장만 넣는다. " +
      "한 장에 요점 3~6개, 요점은 짧은 명사형 문장으로. 사용자가 장 수를 말하면 그대로 따른다. 발표 대본이 필요하면 notes 에 쓴다.",
    input_schema: {
      type: "object",
      properties: {
        title: { ...str, description: "발표 제목" },
        subtitle: { ...str, description: "표지 부제 (발표자 · 반 · 날짜 등, 없으면 비움)" },
        style: { type: "string", enum: ["light", "dark"], description: "light = 흰 바탕(기본), dark = 검붉은 울트론 바탕" },
        slides: {
          type: "array",
          description: "본문 장들",
          items: {
            type: "object",
            properties: {
              title: { ...str, description: "장 제목" },
              bullets: { type: "array", items: { type: "string" }, description: "요점들" },
              notes: { ...str, description: "발표 대본 (선택)" },
            },
            required: ["title", "bullets"],
          },
        },
      },
      required: ["title", "slides"],
    },
  },
  {
    name: "make_spreadsheet",
    description:
      "표(엑셀)를 만든다. 엑셀 · 구글 스프레드시트 · 한컴오피스 한셀에서 열리는 XLSX 로 저장된다. 시간표 · 가계부 · 명단 · 비교표처럼 칸으로 정리할 때 쓴다. " +
      "숫자는 단위 없이 숫자만 넣고 단위는 열 이름에 쓴다 (예: '금액(원)').",
    input_schema: {
      type: "object",
      properties: {
        title: { ...str, description: "표 제목 (파일 이름)" },
        sheets: {
          type: "array",
          description: "시트들 (보통 하나)",
          items: {
            type: "object",
            properties: {
              name: { ...str, description: "시트 이름" },
              columns: { type: "array", items: { type: "string" }, description: "열 이름들" },
              rows: { type: "array", items: { type: "array", items: { type: ["string", "number"] } }, description: "행들 (각 행은 열 순서대로)" },
            },
            required: ["name", "columns", "rows"],
          },
        },
      },
      required: ["title", "sheets"],
    },
  },
  {
    name: "device_status",
    description: "이 휴대폰의 배터리 · 충전 여부 · 네트워크 상태 · 남은 타이머를 확인한다.",
    input_schema: { type: "object", properties: {}, required: [] },
  },
];

export function toolDefs(model: ModelId, city: string): Tool[] {
  const tools: Tool[] = CLIENT_TOOLS.map((t) => ({ ...t, eager_input_streaming: true }));
  const location = {
    type: "approximate" as const,
    city,
    country: "KR",
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "Asia/Seoul",
  };
  // 동적 필터링 검색은 Opus · Sonnet 에서만. Haiku 는 기본 검색.
  if (model === "claude-haiku-5-5") {
    tools.push({ type: "web_search_20250305", name: "web_search", max_uses: 5, user_location: location });
  } else {
    tools.push({ type: "web_search_20260209", name: "web_search", max_uses: 5, user_location: location });
  }
  return tools;
}

// ---------------------------------------------------------------- 입력 검사
type Input = Record<string, unknown>;
const isStr = (v: unknown, max = 20000): v is string => typeof v === "string" && v.trim().length > 0 && v.length <= max;

export function validate(name: string, input: unknown): string | null {
  if (typeof input !== "object" || input === null || Array.isArray(input)) return "입력이 객체가 아님";
  const i = input as Input;
  switch (name) {
    case "remember": return isStr(i.fact, 500) ? null : "fact 가 비었거나 너무 김";
    case "forget": return isStr(i.query, 200) ? null : "query 가 비었음";
    case "set_timer": {
      const s = i.seconds;
      if (typeof s !== "number" || !Number.isFinite(s) || s < 1 || s > 86400) return "seconds 는 1 ~ 86400";
      return isStr(i.label, 200) ? null : "label 이 비었음";
    }
    case "cancel_timer": return i.label === undefined || typeof i.label === "string" ? null : "label 은 글이어야 함";
    case "call_phone": return phoneOk(i.number) ? null : "전화번호 형식이 아님";
    case "send_sms": return phoneOk(i.number) && isStr(i.body, 2000) ? null : "번호나 내용이 올바르지 않음";
    case "open_url": return isStr(i.url, 2000) && /^https?:\/\//i.test(i.url as string) && isStr(i.title, 100) ? null : "url 은 http(s):// 로 시작해야 함";
    case "open_map": return isStr(i.query, 300) ? null : "query 가 비었음";
    case "share_text": return isStr(i.text, 20000) ? null : "text 가 비었음";
    case "make_document":
      if (!isStr(i.title, 200) || !isStr(i.content, 200000)) return "title · content 가 필요함";
      return i.file === undefined || ["hwpx", "docx", "pdf"].includes(i.file as string) ? null : "file 은 hwpx · docx · pdf";
    case "make_presentation": {
      if (!isStr(i.title, 200)) return "title 이 필요함";
      if (i.subtitle !== undefined && typeof i.subtitle !== "string") return "subtitle 은 글이어야 함";
      if (i.style !== undefined && i.style !== "light" && i.style !== "dark") return "style 은 light · dark";
      if (!Array.isArray(i.slides) || !i.slides.length || i.slides.length > 60) return "slides 는 1 ~ 60장";
      for (const s of i.slides as unknown[]) {
        const o = s as Input;
        if (typeof o !== "object" || !o || !isStr(o.title, 300) || !Array.isArray(o.bullets) || o.bullets.length > 20 ||
          !(o.bullets as unknown[]).every((b) => typeof b === "string") || (o.notes !== undefined && typeof o.notes !== "string")) {
          return "각 장은 title · bullets(글 목록, 20개 이하) · notes(선택)";
        }
      }
      return null;
    }
    case "make_spreadsheet": {
      if (!isStr(i.title, 200)) return "title 이 필요함";
      if (!Array.isArray(i.sheets) || !i.sheets.length || i.sheets.length > 20) return "sheets 는 1 ~ 20개";
      for (const s of i.sheets as unknown[]) {
        const o = s as Input;
        const cellOk = (c: unknown) => typeof c === "string" || (typeof c === "number" && Number.isFinite(c));
        if (typeof o !== "object" || !o || typeof o.name !== "string" || !Array.isArray(o.columns) || !o.columns.length ||
          o.columns.length > 100 || !(o.columns as unknown[]).every((c) => typeof c === "string") ||
          !Array.isArray(o.rows) || o.rows.length > 5000 ||
          !(o.rows as unknown[]).every((r) => Array.isArray(r) && r.length <= 100 && r.every(cellOk))) {
          return "각 시트는 name · columns(글 목록) · rows(행 목록, 칸은 글이나 숫자)";
        }
      }
      return null;
    }
    case "device_status": return null;
    default: return `모르는 도구: ${name}`;
  }
}

function phoneOk(v: unknown): v is string {
  return typeof v === "string" && /^\+?[\d\s()-]{2,20}$/.test(v) && /\d{2,}/.test(v.replace(/\D/g, ""));
}

const cleanNumber = (n: string) => n.replace(/[^\d+]/g, "");

// ---------------------------------------------------------------- 실행
export async function runTool(name: string, input: unknown, host: ToolHost): Promise<ToolOutcome> {
  const bad = validate(name, input);
  if (bad) return { content: JSON.stringify({ INVALID_INPUT: bad, input }), isError: true };
  const i = input as Input;
  switch (name) {
    case "remember":
      host.remember((i.fact as string).trim());
      return { content: "기억했다." };
    case "forget": {
      const n = host.forget(i.query as string);
      return { content: n ? `${n}개를 지웠다.` : "그런 기억은 없다." };
    }
    case "set_timer": {
      const due = host.setTimer(Math.round(i.seconds as number), (i.label as string).trim());
      return { content: `타이머를 맞췄다 (${due}).` };
    }
    case "cancel_timer": {
      const label = ((i.label as string | undefined) ?? "").trim();
      if (label === "?") return { content: host.listTimers() };
      const n = host.cancelTimers(label || undefined);
      return { content: n ? `${n}개를 취소했다.` : "취소할 타이머가 없다." };
    }
    case "call_phone": {
      const num = cleanNumber(i.number as string);
      host.card({ kind: "call", title: "전화 걸기", detail: `${(i.name as string) || ""} ${i.number}`.trim(), href: `tel:${num}` });
      return { content: "전화 걸기 버튼을 화면에 띄웠다. 사용자가 누르면 걸린다." };
    }
    case "send_sms": {
      const num = cleanNumber(i.number as string);
      const body = i.body as string;
      host.card({ kind: "sms", title: "문자 보내기", detail: `${i.number} · ${body}`, href: `sms:${num}?body=${encodeURIComponent(body)}` });
      return { content: "문자 보내기 버튼을 화면에 띄웠다. 사용자가 누르면 내용이 채워진 문자 앱이 열린다." };
    }
    case "open_url":
      host.card({ kind: "link", title: i.title as string, detail: i.url as string, href: i.url as string });
      return { content: "열기 버튼을 화면에 띄웠다." };
    case "open_map": {
      const q = encodeURIComponent(i.query as string);
      const href = i.directions
        ? `https://www.google.com/maps/dir/?api=1&destination=${q}`
        : `https://www.google.com/maps/search/?api=1&query=${q}`;
      host.card({ kind: "map", title: i.directions ? "길찾기" : "지도 열기", detail: i.query as string, href });
      return { content: "지도 버튼을 화면에 띄웠다." };
    }
    case "share_text":
      host.card({ kind: "share", title: (i.title as string) || "공유하기", detail: (i.text as string).slice(0, 80), text: i.text as string });
      return { content: "공유 버튼을 화면에 띄웠다." };
    case "make_document": {
      const want = i.file as ExportFormat | undefined;
      const id = host.makeDoc({ kind: "doc", title: (i.title as string).trim(), content: i.content as string, want });
      host.card({ kind: "doc", title: i.title as string, detail: "문서", docId: id, want });
      const how = want === "hwpx" ? "카드의 '한글 파일' 버튼" : want === "docx" ? "카드의 '워드 파일' 버튼" : want === "pdf" ? "카드의 'PDF' 버튼" : "카드에서 한글 · 워드 파일";
      return { content: `문서를 만들었다. 사용자 화면에 '${i.title}' 카드가 떴다. ${how}을 누르면 파일로 저장되고 한컴오피스 · 구글 문서 · 워드 같은 앱으로 열 수 있다. 기록 탭에도 저장됐다.` };
    }
    case "make_presentation": {
      const slides = (i.slides as Input[]).map((s) => ({
        title: (s.title as string).trim(),
        bullets: (s.bullets as string[]).map((b) => b.trim()).filter(Boolean),
        ...(typeof s.notes === "string" && s.notes.trim() ? { notes: s.notes.trim() } : {}),
      }));
      const id = host.makeDoc({
        kind: "slides", title: (i.title as string).trim(), subtitle: (i.subtitle as string | undefined)?.trim() || undefined,
        style: (i.style as "light" | "dark" | undefined) ?? "light", slides, want: "pptx",
      });
      host.card({ kind: "doc", title: i.title as string, detail: `발표 자료 · 표지 포함 ${slides.length + 1}장`, docId: id, want: "pptx" });
      return { content: `발표 자료를 만들었다 (표지 포함 ${slides.length + 1}장). 사용자 화면의 카드에서 'PPT 파일' 을 누르면 저장되고 파워포인트 · 구글 슬라이드 · 한쇼로 열 수 있다.` };
    }
    case "make_spreadsheet": {
      const sheets = (i.sheets as Input[]).map((s) => ({
        name: (s.name as string).trim(),
        columns: (s.columns as string[]).map((c) => c.trim()),
        rows: s.rows as (string | number)[][],
      }));
      const id = host.makeDoc({ kind: "sheet", title: (i.title as string).trim(), sheets, want: "xlsx" });
      const rows = sheets.reduce((a, s) => a + s.rows.length, 0);
      host.card({ kind: "doc", title: i.title as string, detail: `표 · ${rows}줄`, docId: id, want: "xlsx" });
      return { content: `표를 만들었다 (${rows}줄). 사용자 화면의 카드에서 '엑셀 파일' 을 누르면 저장되고 엑셀 · 구글 스프레드시트 · 한셀로 열 수 있다.` };
    }
    case "device_status":
      return { content: await host.deviceStatus() };
  }
  return { content: `모르는 도구: ${name}`, isError: true };
}
