// 받아쓴 말 다듬기 + 토큰 없이 바로 처리하는 명령 (PC 판 hearing.py · local_router.py 의 휴대폰 버전)

// 호출어: 뭉개져 적히는 경우까지 ('울트로', '울트롱', '올트론', '울투론' …)
const WAKE = /^\s*(?:헤이\s*|야\s*)?(?:[울올][트투]?[로론롱]+|ultron)(?:\s*(?:아|야|님))?[\s,.!?~]*/i;
const WAKE_ANYWHERE = /(?:[울올][트투][로론롱]+|ultron)/i;

/** 맨 앞의 "울트론(아)"를 떼어 낸다. 떼어 냈으면 woke=true. */
export function stripWake(text: string): { woke: boolean; rest: string } {
  const m = text.match(WAKE);
  if (!m) return { woke: false, rest: text.trim() };
  return { woke: true, rest: text.slice(m[0].length).trim() };
}

/** 계속 듣기(핸즈프리)에서 호출어가 들어 있는지. 들어 있으면 그 뒤의 말을 돌려준다. */
export function findWake(text: string): string | null {
  const m = text.match(WAKE_ANYWHERE);
  if (!m || m.index === undefined) return null;
  return stripWake(text.slice(m.index)).rest;
}

// ---------------------------------------------------------------- 한글 수 → 숫자
const DIGIT: Record<string, number> = {
  영: 0, 공: 0, 일: 1, 한: 1, 하나: 1, 이: 2, 두: 2, 둘: 2, 삼: 3, 세: 3, 셋: 3, 사: 4, 네: 4, 넷: 4,
  오: 5, 다섯: 5, 육: 6, 여섯: 6, 칠: 7, 일곱: 7, 팔: 8, 여덟: 8, 구: 9, 아홉: 9,
};
const TENS: Record<string, number> = { 열: 10, 스물: 20, 스무: 20, 서른: 30, 마흔: 40, 쉰: 50, 예순: 60 };

/** "삼십", "십오", "스물다섯", "세", "열" 같은 말을 숫자로. 못 읽으면 null. */
export function koreanNumber(word: string): number | null {
  const w = word.trim();
  if (!w) return null;
  if (/^\d+(?:\.\d+)?$/.test(w)) return Number(w);
  // 고유어: 스물다섯, 열두
  for (const [t, v] of Object.entries(TENS)) {
    if (w.startsWith(t)) {
      const rest = w.slice(t.length);
      if (!rest) return v;
      const d = DIGIT[rest];
      return d !== undefined ? v + d : null;
    }
  }
  if (w in DIGIT) return DIGIT[w];
  // 한자어: 삼십오, 십, 백이십
  let total = 0;
  let cur = 0;
  let matched = false;
  for (const ch of w) {
    if (ch === "백") { total += (cur || 1) * 100; cur = 0; matched = true; continue; }
    if (ch === "십") { total += (cur || 1) * 10; cur = 0; matched = true; continue; }
    const d = DIGIT[ch];
    if (d === undefined) return null;
    cur = d;
    matched = true;
  }
  return matched ? total + cur : null;
}

const NUM = String.raw`(\d+(?:\.\d+)?|[영공일이삼사오육칠팔구십백]+|(?:열|스물|스무|서른|마흔|쉰|예순)?(?:하나|한|둘|두|셋|세|넷|네|다섯|여섯|일곱|여덟|아홉)?)`;
const DURATION = new RegExp(
  `(?:${NUM}\\s*시간)?\\s*(?:${NUM}\\s*분)?\\s*(반)?\\s*(?:${NUM}\\s*초)?`,
);

/** "3분", "1시간 반", "삼십 초", "5분 30초" → 초. 시간 표현이 없으면 null. */
export function parseDuration(text: string): number | null {
  const re = new RegExp(DURATION.source, "g");
  let best: number | null = null;
  for (const m of text.matchAll(re)) {
    if (!m[0].trim()) continue;
    const [, h, mi, half, s] = m;
    const hv = h ? koreanNumber(h) : 0;
    const mv = mi ? koreanNumber(mi) : 0;
    const sv = s ? koreanNumber(s) : 0;
    if (hv === null || mv === null || sv === null) continue;
    if (!h && !mi && !s) continue;
    let sec = hv * 3600 + mv * 60 + sv;
    if (half) sec += mi ? 30 : h ? 1800 : 0;
    if (sec > 0) best = sec;
    break;
  }
  return best;
}

export function sayDuration(sec: number): string {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.round(sec % 60);
  const parts: string[] = [];
  if (h) parts.push(`${h}시간`);
  if (m) parts.push(`${m}분`);
  if (s || !parts.length) parts.push(`${s}초`);
  return parts.join(" ");
}

// ---------------------------------------------------------------- 대화 모드 (PC 판 brain.py 의 CHAT_ON / CHAT_OFF)
const MODE = String.raw`(?:자유\s*)?(?:대화\s*모드|[대태데때][화와하]?\s*모[드두]?)`;
export const CHAT_ON = new RegExp(
  String.raw`(?:자유\s*)?대화\s*모드(?:\s*(?:로|으로))?(?:\s*(?:켜|시작|시작해|전환|전환해|들어가|해|가자|on))?` +
    "|" + MODE + String.raw`(?:\s*(?:로|으로))?\s*(?:켜|시작|시작해|전환|전환해|들어가|가자|on)` +
    String.raw`|(?:우리\s*|나랑\s*|그냥\s*|잠깐\s*|심심한데\s*)*(?:얘기|이야기|대화|수다)\s*(?:좀\s*)?` +
    String.raw`(?:하자|할래|해|떨자|나누자|하고\s*싶어|할까|해\s*볼까)`,
  "i",
);
export const CHAT_OFF = new RegExp(
  String.raw`(?:자유\s*)?대화\s*모드\s*(?:꺼|끄|끝|끝내|종료|종료해|그만|나가|off)` +
    "|" + MODE + String.raw`\s*(?:꺼|끄|끝|끝내|종료|종료해|그만|나가|off)` +
    String.raw`|대화\s*(?:끝|끝내|종료|그만)(?:\s*(?:하자|할게|해|낼게))?` +
    String.raw`|(?:이제\s*)?그만\s*(?:얘기|이야기|대화)?\s*하자|잘\s*자|잘\s*있어|바이\s*바이` +
    String.raw`|다음에\s*(?:또\s*)?(?:얘기|이야기)\s*(?:하자|해)`,
  "i",
);

// ---------------------------------------------------------------- 바로 처리하는 명령
export type Local =
  | { kind: "chat_on" }
  | { kind: "chat_off" }
  | { kind: "time" }
  | { kind: "date" }
  | { kind: "timer"; seconds: number; label: string }
  | { kind: "cancel_timers" }
  | { kind: "stop" }
  | { kind: "reset" };

const SHORT = 28; // 이보다 긴 말은 뭔가 더 원하는 것이므로 Claude 에게 넘긴다

/** 토큰을 쓰지 않고 바로 처리할 수 있는 짧은 명령이면 돌려준다. chat=대화 모드인지. */
export function localCommand(text: string, chat: boolean): Local | null {
  const t = text.replace(/[.!?~]+$/g, "").trim();
  if (!t || t.length > SHORT) return null;
  if (CHAT_OFF.test(t) && (chat || /모드|대화/.test(t))) return { kind: "chat_off" };
  // "얘기하자" 같은 말은 짧을 때만 (길면 "OO 이야기해 줄래?"처럼 내용을 묻는 말일 수 있다)
  if (!chat && CHAT_ON.test(t) && !CHAT_OFF.test(t) && (t.length <= 14 || /모드/.test(t))) return { kind: "chat_on" };
  if (/^(?:그만|조용|닥쳐|멈춰|스톱|stop)(?:\s*해)?$/.test(t)) return { kind: "stop" };
  if (/^(?:새\s*대화|대화\s*(?:초기화|새로|지워)|처음부터(?:\s*다시)?)/.test(t)) return { kind: "reset" };
  if (/타이머\s*(?:다\s*)?(?:꺼|취소|없애|지워|멈춰)|알람\s*(?:꺼|취소)/.test(t)) return { kind: "cancel_timers" };
  if (/(?:몇\s*시|지금\s*시간|현재\s*시각|시간\s*(?:알려|좀))/.test(t) && !/뒤|후|있다가|동안/.test(t)) return { kind: "time" };
  if (/(?:며칠|몇\s*월\s*며칠|무슨\s*요일|오늘\s*날짜|날짜\s*(?:알려|좀))/.test(t)) return { kind: "date" };
  if (/타이머|뒤에\s*(?:알려|깨워|불러|말해)|후에\s*(?:알려|깨워|불러|말해)|알람/.test(t)) {
    const sec = parseDuration(t);
    if (sec && sec <= 24 * 3600) return { kind: "timer", seconds: sec, label: "타이머" };
  }
  return null;
}

// ---------------------------------------------------------------- 말로 읽기 좋게
/** 화면에는 그대로 두고, 읽을 때만 마크다운 · URL · 괄호 부연 · 이모지를 걷어 낸다. */
export function forSpeech(text: string): string {
  return text
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/https?:\/\/\S+/g, " ")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/[*_#>`|]+/g, " ")
    .replace(/\([^)]{0,60}\)/g, " ")
    .replace(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

/** 스트리밍으로 들어오는 글을 문장 단위로 끊는다. 다 끝난 문장들과 남은 꼬리를 돌려준다. */
export function splitSentences(buf: string): { done: string[]; rest: string } {
  const done: string[] = [];
  let start = 0;
  for (let i = 0; i < buf.length; i++) {
    const ch = buf[i];
    const next = buf[i + 1];
    const end =
      ch === "\n" ||
      ((ch === "." || ch === "!" || ch === "?" || ch === "。") && (next === undefined ? false : /\s/.test(next)));
    if (end) {
      // 소수점(3.5)이나 약어 중간에서 끊지 않는다
      if (ch === "." && /\d/.test(buf[i - 1] ?? "") && /\d/.test(next ?? "")) continue;
      const s = buf.slice(start, i + 1).trim();
      if (s) done.push(s);
      start = i + 1;
    }
  }
  return { done, rest: buf.slice(start) };
}

export function clockText(d = new Date()): string {
  const h = d.getHours();
  const m = d.getMinutes();
  const ampm = h < 12 ? "오전" : "오후";
  const h12 = h % 12 === 0 ? 12 : h % 12;
  return `${ampm} ${h12}시${m ? ` ${m}분` : ""}`;
}

export function dateText(d = new Date()): string {
  const w = "일월화수목금토"[d.getDay()];
  return `${d.getFullYear()}년 ${d.getMonth() + 1}월 ${d.getDate()}일 ${w}요일`;
}
