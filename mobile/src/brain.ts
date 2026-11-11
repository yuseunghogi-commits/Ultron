// 두뇌: Claude API 를 휴대폰에서 직접 부른다 (API 키는 이 기기에만 저장되고 Anthropic 으로만 보낸다)

import Anthropic from "@anthropic-ai/sdk";
import { systemPrompt } from "./persona";
import { saveConvo, loadConvo, type Settings } from "./store";
import { runTool, toolDefs, type ToolHost } from "./tools";
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
  device_status: "기기 확인 중",
};

export class Brain {
  private client: Anthropic | null = null;
  private clientKey = "";
  private messages: Msg[] = [];
  private system = "";
  private key = "";
  private last = 0;

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

  private api(s: Settings): Anthropic {
    if (!this.client || this.clientKey !== s.apiKey) {
      this.client = new Anthropic({ apiKey: s.apiKey, dangerouslyAllowBrowser: true, maxRetries: 2 });
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
    const client = this.api(s);
    const tools = toolDefs(s.model, s.city);
    const start = this.messages.length;
    const now = new Date();
    this.messages.push({ role: "user", content: `(지금: ${dateText(now)} ${clockText(now)})\n${text}` });

    let answer = "";
    let jsonRetries = 0;
    try {
      for (let step = 0; step < MAX_STEPS; step++) {
        let msg: Anthropic.Beta.BetaMessage;
        try {
          msg = await this.stream(client, s, tools, cb, (d) => (answer += d));
        } catch (e) {
          // 도구 입력이 깨진 JSON 이라 SDK 가 읽지 못한 경우만 한 번 더 시도한다 (API 오류는 그대로 올린다)
          if (e instanceof Anthropic.APIError || cb.signal.aborted || jsonRetries >= 1) throw e;
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
          for (const u of uses) {
            cb.onStatus(TOOL_STATUS[u.name] ?? "작업 중");
            const out = await runTool(u.name, u.input, host);
            results.push({ type: "tool_result", tool_use_id: u.id, content: out.content, ...(out.isError ? { is_error: true } : {}) });
          }
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
    const stream = client.beta.messages.stream(
      {
        model: s.model,
        max_tokens: MAX_TOKENS,
        system: [{ type: "text", text: this.system, cache_control: { type: "ephemeral" } }],
        messages: this.messages,
        tools,
        output_config: { effort: s.effort },
        ...fallback,
      },
      { signal: cb.signal },
    );
    for await (const ev of stream) {
      if (ev.type === "content_block_start") {
        const b = ev.content_block;
        if (b.type === "server_tool_use") cb.onStatus("검색 중");
        else if (b.type === "tool_use") cb.onStatus(TOOL_STATUS[b.name] ?? "작업 중");
        else if (b.type === "text") cb.onStatus("");
      } else if (ev.type === "content_block_delta" && ev.delta.type === "text_delta") {
        onAnswer(ev.delta.text);
        cb.onText(ev.delta.text);
      }
    }
    return await stream.finalMessage();
  }
}

function toBrainError(e: unknown): BrainError {
  if (e instanceof BrainError) return e;
  if (e instanceof Anthropic.AuthenticationError) return new BrainError(e.message, "API 키가 맞지 않는다. 설정에서 다시 확인해라.");
  if (e instanceof Anthropic.PermissionDeniedError) return new BrainError(e.message, "이 키로는 그 모델을 쓸 수 없다. 설정에서 다른 모델을 골라라.");
  if (e instanceof Anthropic.RateLimitError) return new BrainError(e.message, "요청이 너무 많다. 잠시 뒤에 다시 말해라.");
  if (e instanceof Anthropic.BadRequestError) {
    if (/credit|balance|billing/i.test(e.message)) return new BrainError(e.message, "API 크레딧이 바닥났다. 콘솔에서 충전해라.");
    return new BrainError(e.message, "요청이 거절됐다. 새 대화로 다시 해 보자.");
  }
  if (e instanceof Anthropic.APIConnectionError) return new BrainError(e.message, "연결이 끊겼다. 인터넷을 확인해라.");
  if (e instanceof Anthropic.InternalServerError) return new BrainError(e.message, "저쪽 서버가 잠시 말을 듣지 않는다. 다시 해 봐라.");
  if (e instanceof Anthropic.APIError) return new BrainError(e.message, "뭔가 꼬였다. 다시 말해 봐라.");
  return new BrainError(String((e as Error)?.message ?? e), "뭔가 꼬였다. 다시 말해 봐라.");
}
