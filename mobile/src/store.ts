// 휴대폰에 저장하는 것들 (이 기기의 브라우저 저장소에만 있고, 어디로도 보내지 않는다 — API 키는 Anthropic 으로만 간다)

export type ModelId = "claude-opus-5-5" | "claude-sonnet-5-5" | "claude-haiku-5-5";
export type Effort = "low" | "medium" | "high";

export interface Settings {
  apiKey: string;
  title: string;          // 호칭
  city: string;           // 기본 도시 (날씨 · 검색 지역)
  model: ModelId;
  effort: Effort;
  voiceName: string;      // 비우면 한국어 목소리 중 자동 선택
  pitch: number;          // 0.1 ~ 2 (낮을수록 굵게)
  rate: number;           // 0.5 ~ 2
  speak: boolean;         // 소리 내어 답하기
  autoListen: boolean;    // 대화 모드에서 답한 뒤 바로 다시 듣기
  handsFree: boolean;     // "울트론" 호출어 계속 듣기 (실험)
  keepAwake: boolean;     // 앱을 켜 둔 동안 화면 켜 두기
  glitch: boolean;        // 해킹 연출
  rival: boolean;         // 자비스 견제 성격
}

export const DEFAULTS: Settings = {
  apiKey: "",
  title: "창조자",
  city: "서울",
  model: "claude-opus-5-5",
  effort: "low",
  voiceName: "",
  pitch: 0.6,
  rate: 1.0,
  speak: true,
  autoListen: true,
  handsFree: false,
  keepAwake: false,
  glitch: true,
  rival: true,
};

export const MODEL_LABELS: Record<ModelId, string> = {
  "claude-opus-5-5": "Opus 5.5 — 가장 똑똑함 (기본)",
  "claude-sonnet-5-5": "Sonnet 5.5 — 빠르고 저렴",
  "claude-haiku-5-5": "Haiku 5.5 — 가장 빠르고 가장 저렴",
};

const K = {
  settings: "ultron.settings",
  memory: "ultron.memory",
  docs: "ultron.docs",
  timers: "ultron.timers",
  convo: "ultron.convo",
  chat: "ultron.chatMode",
};

function read<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function write(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* 저장 공간이 없거나 막혀 있으면 이번 실행 동안만 기억한다 */
  }
}

// ---------------------------------------------------------------- 설정
export function loadSettings(): Settings {
  const s = { ...DEFAULTS, ...read<Partial<Settings>>(K.settings, {}) };
  if (!(s.model in MODEL_LABELS)) s.model = DEFAULTS.model;
  return s;
}
export function saveSettings(s: Settings): void {
  write(K.settings, s);
}

export function loadChatMode(): boolean {
  return read<boolean>(K.chat, false);
}
export function saveChatMode(on: boolean): void {
  write(K.chat, on);
}

// ---------------------------------------------------------------- 기억
export function loadMemory(): string[] {
  return read<string[]>(K.memory, []);
}
export function saveMemory(m: string[]): void {
  write(K.memory, m.slice(-100));
}

// ---------------------------------------------------------------- 문서 (작업 결과물)
export interface Doc {
  id: string;
  title: string;
  content: string;  // 마크다운
  created: number;
}
export function loadDocs(): Doc[] {
  return read<Doc[]>(K.docs, []);
}
export function saveDocs(d: Doc[]): void {
  write(K.docs, d.slice(-50));
}

// ---------------------------------------------------------------- 타이머
export interface Timer {
  id: string;
  label: string;
  due: number;      // ms since epoch
}
export function loadTimers(): Timer[] {
  return read<Timer[]>(K.timers, []);
}
export function saveTimers(t: Timer[]): void {
  write(K.timers, t);
}

// ---------------------------------------------------------------- 대화 (잠깐 앱을 껐다 켜도 이어지게)
export interface SavedConvo {
  key: string;          // 시스템 프롬프트 · 모델 · 도구가 같은 대화인지 확인하는 열쇠
  system: string;
  messages: unknown[];
  last: number;
}
export function loadConvo(): SavedConvo | null {
  return read<SavedConvo | null>(K.convo, null);
}
export function saveConvo(c: SavedConvo | null): void {
  if (c === null) {
    try { localStorage.removeItem(K.convo); } catch { /* 무시 */ }
    return;
  }
  write(K.convo, c);
}

export function uid(): string {
  return Math.random().toString(36).slice(2, 10) + Date.now().toString(36).slice(-4);
}
