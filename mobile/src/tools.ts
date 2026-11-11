// 휴대폰에서 울트론이 쓰는 도구들
//
// 웹 앱은 다른 앱을 직접 조작하거나 전화를 몰래 걸 수 없다. 전화 · 문자 · 링크 · 지도 · 공유는 화면에 버튼(카드)을 띄우고,
// 사용자가 그 버튼을 눌러야 실제로 일어난다 — 그것이 PC 판의 승인 카드 역할을 한다.

import type Anthropic from "@anthropic-ai/sdk";
import type { ExportFormat, ModelId } from "./store";
import { WORK_TOOLS, isWorkTool, runWork, validateWork, type WorkHost } from "./work";

type Tool = Anthropic.Beta.BetaToolUnion;

export interface ActionCard {
  kind: "call" | "sms" | "link" | "map" | "share" | "doc" | "calendar" | "mail";
  title: string;
  detail: string;
  href?: string;     // tel: · sms: · https: 링크
  text?: string;     // 공유할 글
  docId?: string;    // 문서 보기
  want?: ExportFormat; // 문서 카드: 바로 만들 파일 형식
}

/** 도구가 앱에 부탁하는 일 (main.ts 가 구현한다) */
export interface ToolHost {
  remember(fact: string): void;
  forget(query: string): number;
  setTimer(seconds: number, label: string): string;
  cancelTimers(label?: string): number;
  listTimers(): string;
  card(c: ActionCard): void;
  work: WorkHost;
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
    name: "add_calendar_event",
    description: "일정 추가 버튼을 띄운다 (구글 캘린더가 내용이 채워진 채로 열림). 사용자가 눌러서 저장해야 추가된다.",
    input_schema: {
      type: "object",
      properties: {
        title: { ...str, description: "일정 이름" },
        start: { ...str, description: "시작 'YYYY-MM-DDTHH:MM' (하루 종일이면 'YYYY-MM-DD')" },
        end: { ...str, description: "끝 (같은 형식, 모르면 비움 — 1시간으로)" },
        location: { ...str, description: "장소" },
        details: { ...str, description: "메모" },
      },
      required: ["title", "start"],
    },
  },
  {
    name: "send_email",
    description: "메일 쓰기 버튼을 띄운다 (받는 사람 · 제목 · 내용이 채워진 메일 앱이 열림). 사용자가 눌러서 보내야 간다.",
    input_schema: {
      type: "object",
      properties: {
        to: { ...str, description: "받는 사람 주소 (모르면 비움)" },
        subject: { ...str, description: "제목" },
        body: { ...str, description: "내용" },
      },
      required: ["subject", "body"],
    },
  },
  {
    name: "device_status",
    description: "이 휴대폰의 배터리 · 충전 여부 · 네트워크 상태 · 남은 타이머를 확인한다.",
    input_schema: { type: "object", properties: {}, required: [] },
  },
];

export function toolDefs(model: ModelId, city: string): Tool[] {
  const tools: Tool[] = [...CLIENT_TOOLS, ...WORK_TOOLS].map((t) => ({ ...t, eager_input_streaming: true }));
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
  if (isWorkTool(name)) return validateWork(name, input);
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
    case "add_calendar_event": {
      if (!isStr(i.title, 200) || !isStr(i.start, 20)) return "title · start 가 필요함";
      if (!DATE.test(i.start as string) || (i.end !== undefined && i.end !== "" && !DATE.test(String(i.end)))) return "날짜는 YYYY-MM-DD 또는 YYYY-MM-DDTHH:MM";
      return null;
    }
    case "send_email":
      if (!isStr(i.subject, 300) || !isStr(i.body, 20000)) return "subject · body 가 필요함";
      return i.to === undefined || i.to === "" || /^[^\s@,]+@[^\s@,]+\.[^\s@,]+$/.test(String(i.to)) ? null : "메일 주소 형식이 아님";
    case "device_status": return null;
    default: return `모르는 도구: ${name}`;
  }
}

function phoneOk(v: unknown): v is string {
  return typeof v === "string" && /^\+?[\d\s()-]{2,20}$/.test(v) && /\d{2,}/.test(v.replace(/\D/g, ""));
}

const DATE = /^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2})?$/;

/** 구글 캘린더 '일정 만들기' 주소 (시간은 휴대폰 시간대 기준) */
export function calendarUrl(title: string, start: string, end?: string, location?: string, details?: string): string {
  const allDay = !start.includes("T");
  const fmt = (d: Date) => allDay
    ? `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, "0")}${String(d.getDate()).padStart(2, "0")}`
    : d.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
  const s = new Date(allDay ? `${start}T00:00` : start);
  const e = end && DATE.test(end) ? new Date(allDay ? `${end}T00:00` : end) : new Date(s.getTime() + (allDay ? 86_400_000 : 3_600_000));
  if (allDay && e.getTime() <= s.getTime()) e.setTime(s.getTime() + 86_400_000);
  const p = new URLSearchParams({ action: "TEMPLATE", text: title, dates: `${fmt(s)}/${fmt(e)}` });
  if (location) p.set("location", location);
  if (details) p.set("details", details);
  return `https://calendar.google.com/calendar/render?${p.toString()}`;
}

const cleanNumber = (n: string) => n.replace(/[^\d+]/g, "");

// ---------------------------------------------------------------- 실행
export async function runTool(name: string, input: unknown, host: ToolHost): Promise<ToolOutcome> {
  if (isWorkTool(name)) return runWork(name, input, host.work);
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
    case "add_calendar_event": {
      const href = calendarUrl(i.title as string, i.start as string, i.end as string | undefined, i.location as string | undefined, i.details as string | undefined);
      host.card({ kind: "calendar", title: i.title as string, detail: `${String(i.start).replace("T", " ")}${i.location ? ` · ${i.location}` : ""}`, href });
      return { content: "일정 추가 버튼을 화면에 띄웠다. 사용자가 누르고 저장하면 캘린더에 들어간다." };
    }
    case "send_email": {
      const q = `subject=${encodeURIComponent(i.subject as string)}&body=${encodeURIComponent(i.body as string)}`;
      const href = `mailto:${i.to ? encodeURIComponent(String(i.to)) : ""}?${q}`;
      host.card({ kind: "mail", title: i.subject as string, detail: `${i.to || "받는 사람 미정"} · ${String(i.body).slice(0, 60)}`, href });
      return { content: "메일 쓰기 버튼을 화면에 띄웠다. 사용자가 누르면 내용이 채워진 메일 앱이 열린다." };
    }
    case "device_status":
      return { content: await host.deviceStatus() };
  }
  return { content: `모르는 도구: ${name}`, isError: true };
}
