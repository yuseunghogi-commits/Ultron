// 두뇌: Claude API 를 휴대폰에서 직접 부른다 (API 키는 이 기기에만 저장되고 Anthropic 으로만 보낸다)

import type Anthropic from "@anthropic-ai/sdk";

// Claude SDK 는 크기가 커서 처음 화면을 띄울 때는 불러오지 않는다 (preloadSdk 로 한가할 때 미리 불러 둔다)
type Sdk = typeof import("@anthropic-ai/sdk").default;
let SDK: Sdk | null = null;
let sdkLoading: Promise<Sdk> | null = null;
export function preloadSdk(): Promise<Sdk> {
  if (!sdkLoading) {
    sdkLoading = import("@anthropic-ai/sdk").then((m) => (SDK = m.default));
    sdkLoading.catch(() => { sdkLoading = null; });
  }
  return sdkLoading;
}
type ErrName = "APIError" | "AuthenticationError" | "PermissionDeniedError" | "RateLimitError" | "BadRequestError" | "APIConnectionError" | "InternalServerError";
const isErr = (e: unknown, name: ErrName): e is Error => !!SDK && e instanceof (SDK[name] as unknown as new (...a: unknown[]) => Error);
import { systemPrompt } from "./persona";
import { saveConvo, loadConvo, type Settings } from "./store";
import { runTool, toolDefs, type ToolHost } from "./tools";
import type { DeckSlide } from "./store";
import type { Outline, Team } from "./work";
import { clockText, dateText } from "./hearing";

type Msg = Anthropic.Beta.BetaMessageParam;
type Block = Anthropic.Beta.BetaContentBlock;

const IDLE_RESET_MS = 10 * 60 * 1000;   // 10분 동안 말이 없으면 새 대화
const MAX_MESSAGES = 60;                // 너무 길어지면 새 대화
const MAX_STEPS = 12;                   // 도구 사용 반복 한도
const MAX_TOKENS = 32000;

export interface TurnCallbacks {
  onText(delta: string): void;          // 답이 만들어지는 대로
  onStatus(text: string): void;         // "검색 중" 같은 진행 표시
  signal: AbortSignal;
  attachments?: unknown[];              // 사진 · PDF 내용 블록
}

export class BrainError extends Error {
  constructor(message: string, readonly spoken: string) {
    super(message);
  }
}

const TOOL_STATUS: Record<string, string> = {
  web_search: "검색 중",
  remember: "기억하는 중",
  forget: "기억 지우는 중",
  set_timer: "타이머 맞추는 중",
  cancel_timer: "타이머 정리 중",
  make_document: "문서 쓰는 중",
  make_presentation: "발표 자료 만드는 중",
  make_spreadsheet: "표 만드는 중",
  make_cardnews: "카드뉴스 그리는 중",
  make_poster: "포스터 그리는 중",
  write_long_document: "개요 짜는 중",
  write_long_presentation: "개요 짜는 중",
  add_calendar_event: "일정 준비 중",
  send_email: "메일 쓰는 중",
  device_status: "기기 확인 중",
};

export class Brain {
  private client: Anthropic | null = null;
  private clientKey = "";
  private messages: Msg[] = [];
  private system = "";
  private key = "";
  private last = 0;
  private fastOff = false;

  constructor() {
    const saved = loadConvo();
    if (saved && Date.now() - saved.last < IDLE_RESET_MS) {
      this.messages = saved.messages as Msg[];
      this.system = saved.system;
      this.key = saved.key;
      this.last = saved.last;
    }
  }

  reset(): void {
    this.messages = [];
    this.system = "";
    this.key = "";
    saveConvo(null);
  }

  get turns(): number {
    return this.messages.filter((m) => m.role === "user" && typeof m.content === "string").length;
  }

  /** 팀 도구가 쓸 작가들 (지금 설정 · 지금 하고 있는 일의 취소 신호를 따른다) */
  team(s: () => Settings, signal: () => AbortSignal | undefined): Team {
    return makeTeam(() => this.api(s()), s, signal);
  }

  private async api(s: Settings): Promise<Anthropic> {
    const Sdk = await preloadSdk();
    if (!this.client || this.clientKey !== s.apiKey) {
      this.client = new Sdk({ apiKey: s.apiKey, dangerouslyAllowBrowser: true, maxRetries: 2 });
      this.clientKey = s.apiKey;
    }
    return this.client;
  }

  /** 같은 대화로 이어 가도 되는지: 모델 · 모드 · 호칭 · 도시 · 성격이 같고, 오래 쉬지 않았고, 너무 길지 않을 때.
   *  (대화 도중에는 시스템 프롬프트와 도구를 바꾸지 않는다 — 바꾸면 새 대화로 시작한다) */
  private ensureConvo(s: Settings, chat: boolean, memory: string[]): void {
    const key = JSON.stringify([s.model, chat, s.title, s.city, s.rival]);
    const stale = Date.now() - this.last > IDLE_RESET_MS || this.messages.length > MAX_MESSAGES;
    if (key !== this.key || stale || !this.system) {
      this.messages = [];
      this.key = key;
      this.system = systemPrompt(chat, { title: s.title, city: s.city, memory, rival: s.rival });
    }
  }

  /** 한 번의 말에 대한 답. 다 끝나면 화면에 보여 줄 전체 답을 돌려준다. */
  async turn(text: string, s: Settings, chat: boolean, memory: string[], host: ToolHost, cb: TurnCallbacks): Promise<string> {
    if (!s.apiKey) throw new BrainError("no key", "API 키가 없다. 설정에서 넣어 줘라.");
    this.ensureConvo(s, chat, memory);
    let client: Anthropic;
    try { client = await this.api(s); } catch { throw new BrainError("sdk", "두뇌를 불러오지 못했다. 인터넷을 확인해라."); }
    const tools = toolDefs(s.model, s.city);
    const start = this.messages.length;
    const now = new Date();
    const said = `(지금: ${dateText(now)} ${clockText(now)})\n${text}`;
    this.messages.push({
      role: "user",
      content: cb.attachments?.length
        ? [...(cb.attachments as Anthropic.Beta.BetaContentBlockParam[]), { type: "text", text: said }]
        : said,
    });

    let answer = "";
    let jsonRetries = 0;
    try {
      for (let step = 0; step < MAX_STEPS; step++) {
        let msg: Anthropic.Beta.BetaMessage;
        try {
          msg = await this.stream(client, s, tools, cb, (d) => (answer += d));
        } catch (e) {
          // 도구 입력이 깨진 JSON 이라 SDK 가 읽지 못한 경우만 한 번 더 시도한다 (API 오류는 그대로 올린다)
          if (isErr(e, "APIError") || cb.signal.aborted || jsonRetries >= 1) throw e;
          if (!(e instanceof SyntaxError) && !/json/i.test(String((e as Error)?.message))) throw e;
          jsonRetries++;
          continue;
        }
        this.messages.push({ role: "assistant", content: msg.content as unknown as Anthropic.Beta.BetaContentBlockParam[] });

        if (msg.stop_reason === "pause_turn") continue;   // 서버 검색이 길어져 잠시 멈춤 — 그대로 이어서 요청

        const uses = msg.content.filter((b: Block): b is Anthropic.Beta.BetaToolUseBlock => b.type === "tool_use");
        if (msg.stop_reason === "refusal") {
          // 거절로 끊긴 차례의 도구는 실행하지 않는다 (대화가 이어지도록 결과 자리만 채운다)
          if (uses.length) {
            this.messages.push({
              role: "user",
              content: uses.map((u) => ({ type: "tool_result" as const, tool_use_id: u.id, is_error: true, content: "실행하지 않음" })),
            });
          }
          if (!answer.trim()) answer = "그건 내가 다룰 수 없는 이야기다.";
          break;
        }
        if (!uses.length) break;

        const results: Anthropic.Beta.BetaToolResultBlockParam[] = [];
        if (msg.stop_reason === "max_tokens") {
          // 도구 입력이 중간에 잘렸다 — 실행하지 않고 다시 쓰게 한다
          for (const u of uses) {
            results.push({ type: "tool_result", tool_use_id: u.id, is_error: true, content: "입력이 길이 한도에서 잘렸다. 더 짧게 나눠서 다시 호출하라." });
          }
        } else {
          // 도구는 동시에 돌리고, 결과는 부른 순서대로 한 메시지에 담는다
          cb.onStatus(TOOL_STATUS[uses[0].name] ?? "작업 중");
          const outs = await Promise.all(uses.map((u) =>
            runTool(u.name, u.input, host).catch((e) => ({ content: `도구 실패: ${String((e as Error)?.message ?? e)}`, isError: true }))));
          if (cb.signal.aborted) throw new BrainError("aborted", "");
          uses.forEach((u, k) => results.push({ type: "tool_result", tool_use_id: u.id, content: outs[k].content, ...(outs[k].isError ? { is_error: true } : {}) }));
        }
        this.messages.push({ role: "user", content: results });
        if (answer && !/\s$/.test(answer)) answer += " ";
      }
    } catch (e) {
      this.messages.length = start;   // 이번 말은 없었던 일로 (앞의 대화는 그대로 둔다)
      if (cb.signal.aborted) throw new BrainError("aborted", "");
      throw toBrainError(e);
    }
    this.last = Date.now();
    saveConvo({ key: this.key, system: this.system, messages: this.messages, last: this.last });
    return answer.trim();
  }

  private async stream(
    client: Anthropic,
    s: Settings,
    tools: Anthropic.Beta.BetaToolUnion[],
    cb: TurnCallbacks,
    onAnswer: (d: string) => void,
  ): Promise<Anthropic.Beta.BetaMessage> {
    const fallback = s.model === "claude-haiku-5-5"
      ? {}
      : { betas: ["server-side-fallback-2026-07-01"] as Anthropic.Beta.AnthropicBeta[], fallbacks: "default" as const };
    const fast = s.fast && s.model === "claude-opus-5-5" && !this.fastOff;
    const stream = client.beta.messages.stream(
      {
        model: s.model,
        max_tokens: MAX_TOKENS,
        // 도구 + 시스템 프롬프트, 그리고 지금까지의 대화 전체를 캐시한다 (다음 요청이 빨라지고 싸진다)
        system: [{ type: "text", text: this.system, cache_control: { type: "ephemeral" } }],
        cache_control: { type: "ephemeral" },
        messages: this.messages,
        tools,
        output_config: { effort: s.effort },
        ...(fast ? { speed: "fast" as const } : {}),
        ...fallback,
      },
      { signal: cb.signal },
    );
    let toolName = "";
    let toolChars = 0;
    let lastShown = 0;
    try {
      for await (const ev of stream) {
        if (ev.type === "content_block_start") {
          const b = ev.content_block;
          toolChars = 0;
          if (b.type === "server_tool_use") cb.onStatus("검색 중");
          else if (b.type === "tool_use") { toolName = b.name; cb.onStatus(TOOL_STATUS[b.name] ?? "작업 중"); }
          else if (b.type === "text") cb.onStatus("");
        } else if (ev.type === "content_block_delta" && ev.delta.type === "text_delta") {
          onAnswer(ev.delta.text);
          cb.onText(ev.delta.text);
        } else if (ev.type === "content_block_delta" && ev.delta.type === "input_json_delta") {
          // 긴 결과물을 쓰는 동안 얼마나 썼는지 보여 준다 (0.3초에 한 번)
          toolChars += ev.delta.partial_json.length;
          const now = performance.now();
          if (toolChars > 300 && now - lastShown > 300) {
            lastShown = now;
            cb.onStatus(`${TOOL_STATUS[toolName] ?? "작업 중"} · ${toolChars.toLocaleString()}자`);
          }
        }
      }
      return await stream.finalMessage();
    } catch (e) {
      // 빠른 모드가 막혀 있으면(한도 · 미지원) 이번 실행 동안은 끄고 보통 속도로 다시
      if (fast && (isErr(e, "RateLimitError") || isErr(e, "BadRequestError")) && !cb.signal.aborted) {
        this.fastOff = true;
        return this.stream(client, s, tools, cb, onAnswer);
      }
      throw e;
    }
  }
}

// ---------------------------------------------------------------- 팀: 긴 결과물을 여럿이 동시에 쓰기
const WRITERS = 4;   // 동시에 쓰는 작가 수

const SECTION_SYSTEM = `당신은 한국어 문서 작가입니다. 기획자가 넘긴 개요 중 맡은 부분의 본문만 씁니다.
- 마크다운으로 쓰되 맡은 부분의 소제목(##)은 쓰지 마세요 (앱이 붙입니다). 필요하면 ### 하위 제목, - 목록, 1. 번호, **굵게**, | 표 | 를 씁니다.
- 브리프와 공통 사실만 근거로 쓰고, 모르는 숫자나 출처는 지어내지 마세요. 다른 부분과 겹치는 내용은 피하세요.
- 문서 대상과 말투 요구가 있으면 따르세요. 없으면 보고서체(~다)로 씁니다. 머리말 · 맺음말 없이 본문만 출력하세요.`;

const SLIDES_SYSTEM = `당신은 발표 자료 작가입니다. 기획자가 넘긴 장 개요 중 맡은 장들의 내용을 씁니다.
- 각 장: bullets 3~6개 (짧은 명사형 문장, 한 줄 40자 안팎), 대본이 필요하면 notes 에 말하듯이 2~4문장.
- 숫자를 비교하거나 변화를 보여 줄 장에만 chart(bar · line · pie, series 마다 values 개수 = labels 개수), 비교표가 어울리면 table 을 넣습니다.
- 브리프와 공통 사실만 근거로 쓰고 숫자를 지어내지 마세요. 장 제목은 개요의 제목을 그대로 쓰세요.`;

const SLIDE_SCHEMA = {
  type: "object", additionalProperties: false, required: ["slides"],
  properties: {
    slides: {
      type: "array",
      items: {
        type: "object", additionalProperties: false, required: ["title", "bullets"],
        properties: {
          title: { type: "string" },
          bullets: { type: "array", items: { type: "string" } },
          notes: { type: "string" },
          chart: {
            type: "object", additionalProperties: false, required: ["type", "labels", "series"],
            properties: {
              type: { type: "string", enum: ["bar", "line", "pie"] },
              title: { type: "string" },
              labels: { type: "array", items: { type: "string" } },
              series: { type: "array", items: { type: "object", additionalProperties: false, required: ["name", "values"], properties: { name: { type: "string" }, values: { type: "array", items: { type: "number" } } } } },
            },
          },
          table: {
            type: "object", additionalProperties: false, required: ["columns", "rows"],
            properties: { columns: { type: "array", items: { type: "string" } }, rows: { type: "array", items: { type: "array", items: { type: "string" } } } },
          },
        },
      },
    },
  },
};

/** 일 목록을 최대 n 개씩 동시에 */
async function pool<T>(jobs: (() => Promise<T>)[], n: number): Promise<T[]> {
  const out: T[] = new Array(jobs.length);
  let next = 0;
  await Promise.all(Array.from({ length: Math.min(n, jobs.length) }, async () => {
    while (next < jobs.length) {
      const k = next++;
      out[k] = await jobs[k]();
    }
  }));
  return out;
}

export function makeTeam(client: () => Promise<Anthropic>, s: () => Settings, signal: () => AbortSignal | undefined): Team {
  const call = async (system: string, user: string, json: boolean): Promise<string> => {
    const st = s();
    const fallback = st.model === "claude-haiku-5-5" ? {} : { betas: ["server-side-fallback-2026-07-01"] as Anthropic.Beta.AnthropicBeta[], fallbacks: "default" as const };
    for (let attempt = 0; ; attempt++) {
      try {
        const stream = (await client()).beta.messages.stream({
          model: st.model, max_tokens: 16000, system, messages: [{ role: "user", content: user }],
          output_config: { effort: "low", ...(json ? { format: { type: "json_schema" as const, schema: SLIDE_SCHEMA } } : {}) },
          ...(st.fast && st.model === "claude-opus-5-5" ? { speed: "fast" as const } : {}),
          ...fallback,
        }, { signal: signal() });
        const msg = await stream.finalMessage();
        if (msg.stop_reason === "refusal") throw new BrainError("refusal", "그 부분은 쓸 수 없다.");
        return msg.content.filter((b): b is Anthropic.Beta.BetaTextBlock => b.type === "text").map((b) => b.text).join("");
      } catch (e) {
        if (attempt >= 1 || signal()?.aborted || isErr(e, "AuthenticationError") || e instanceof BrainError) throw e;
      }
    }
  };
  const outlineText = (outline: Outline[]) => outline.map((o, k) => `${k + 1}. ${o.heading}`).join("\n");
  return {
    async sections(title, outline, facts, onDone) {
      return pool(outline.map((o, k) => async () => {
        const text = await call(SECTION_SYSTEM,
          `문서 제목: ${title}\n\n전체 개요:\n${outlineText(outline)}\n\n공통 사실 · 요구:\n${facts || "(없음)"}\n\n` +
          `맡은 부분: ${k + 1}. ${o.heading}\n브리프: ${o.brief}`, false);
        onDone(1);
        return text.replace(/^##\s+.*\n+/, "");
      }), WRITERS);
    },
    async slides(title, outline, facts, onDone) {
      // 작가 한 명이 2~3장씩 (장이 많으면 더 많이), 최대 4명이 동시에
      const per = Math.max(2, Math.ceil(outline.length / WRITERS));
      const chunks: Outline[][] = [];
      for (let k = 0; k < outline.length; k += per) chunks.push(outline.slice(k, k + per));
      const parts = await pool(chunks.map((chunk, ci) => async () => {
        const start = ci * per;
        const raw = await call(SLIDES_SYSTEM,
          `발표 제목: ${title}\n\n전체 장 개요:\n${outlineText(outline)}\n\n공통 사실 · 요구:\n${facts || "(없음)"}\n\n` +
          `맡은 장 (이 순서 그대로 ${chunk.length}장):\n${chunk.map((o, j) => `${start + j + 1}. ${o.heading} — ${o.brief}`).join("\n")}`, true);
        let slides: DeckSlide[];
        try {
          slides = (JSON.parse(raw) as { slides: DeckSlide[] }).slides;
        } catch {
          slides = chunk.map((o) => ({ title: o.heading, bullets: [o.brief] }));
        }
        // 맡은 장 수와 제목을 개요에 맞춘다
        const fixed = chunk.map((o, j) => {
          const sl = slides[j] ?? { title: o.heading, bullets: [o.brief] };
          const rows = sl.table?.rows?.map((r) => r.map(String));
          const chart = sl.chart && sl.chart.series.every((x) => x.values.length === sl.chart!.labels.length) ? sl.chart : undefined;
          return { ...sl, title: o.heading, ...(chart ? { chart } : { chart: undefined }), ...(sl.table && rows ? { table: { columns: sl.table.columns, rows } } : {}) };
        });
        onDone(chunk.length);
        return fixed;
      }), WRITERS);
      return parts.flat();
    },
  };
}

function toBrainError(e: unknown): BrainError {
  if (e instanceof BrainError) return e;
  if (isErr(e, "AuthenticationError")) return new BrainError(e.message, "API 키가 맞지 않는다. 설정에서 다시 확인해라.");
  if (isErr(e, "PermissionDeniedError")) return new BrainError(e.message, "이 키로는 그 모델을 쓸 수 없다. 설정에서 다른 모델을 골라라.");
  if (isErr(e, "RateLimitError")) return new BrainError(e.message, "요청이 너무 많다. 잠시 뒤에 다시 말해라.");
  if (isErr(e, "BadRequestError")) {
    if (/credit|balance|billing/i.test(e.message)) return new BrainError(e.message, "API 크레딧이 바닥났다. 콘솔에서 충전해라.");
    return new BrainError(e.message, "요청이 거절됐다. 새 대화로 다시 해 보자.");
  }
  if (isErr(e, "APIConnectionError")) return new BrainError(e.message, "연결이 끊겼다. 인터넷을 확인해라.");
  if (isErr(e, "InternalServerError")) return new BrainError(e.message, "저쪽 서버가 잠시 말을 듣지 않는다. 다시 해 봐라.");
  if (isErr(e, "APIError")) return new BrainError(e.message, "뭔가 꼬였다. 다시 말해 봐라.");
  return new BrainError(String((e as Error)?.message ?? e), "뭔가 꼬였다. 다시 말해 봐라.");
}
