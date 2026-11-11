// 듣기(음성 인식)와 말하기(음성 합성) — 휴대폰 브라우저에 들어 있는 기능을 쓴다

// ---------------------------------------------------------------- 듣기
interface SRResult { isFinal: boolean; 0: { transcript: string } }
interface SREvent { resultIndex: number; results: ArrayLike<SRResult> }
interface SRErrorEvent { error: string }
interface SR {
  lang: string; continuous: boolean; interimResults: boolean; maxAlternatives: number;
  start(): void; stop(): void; abort(): void;
  onresult: ((e: SREvent) => void) | null;
  onerror: ((e: SRErrorEvent) => void) | null;
  onend: (() => void) | null;
  onspeechstart: (() => void) | null;
}
type SRCtor = new () => SR;

function ctor(): SRCtor | null {
  const w = window as unknown as { SpeechRecognition?: SRCtor; webkitSpeechRecognition?: SRCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export const canListen = (): boolean => ctor() !== null;

export interface ListenHandlers {
  onInterim(text: string): void;
  onSpeech(): void;
  onFinal(text: string): void;       // 빈 글이면 아무 말도 없었던 것
  onError(kind: "denied" | "network" | "other", detail: string): void;
}

/** 한 마디 듣기. 돌려준 함수를 부르면 그만 듣는다. */
export function listenOnce(h: ListenHandlers): () => void {
  const C = ctor();
  if (!C) {
    h.onError("other", "이 브라우저는 음성 인식을 지원하지 않는다");
    return () => {};
  }
  const r = new C();
  r.lang = "ko-KR";
  r.continuous = false;
  r.interimResults = true;
  r.maxAlternatives = 1;
  let finalText = "";
  let interim = "";
  let done = false;
  r.onspeechstart = () => h.onSpeech();
  r.onresult = (e) => {
    interim = "";
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const res = e.results[i];
      if (res.isFinal) finalText += res[0].transcript;
      else interim += res[0].transcript;
    }
    h.onInterim((finalText + interim).trim());
  };
  r.onerror = (e) => {
    if (e.error === "no-speech" || e.error === "aborted") return;
    done = true;
    if (e.error === "not-allowed" || e.error === "service-not-allowed") h.onError("denied", e.error);
    else if (e.error === "network") h.onError("network", e.error);
    else h.onError("other", e.error);
  };
  r.onend = () => {
    if (done) return;
    done = true;
    // 일부 휴대폰은 마지막 조각을 isFinal 로 주지 않고 끝낸다 — 그때는 듣던 글을 그대로 쓴다
    h.onFinal((finalText || interim).trim());
  };
  try {
    r.start();
  } catch (err) {
    h.onError("other", String(err));
  }
  return () => {
    try { r.stop(); } catch { /* 이미 끝남 */ }
  };
}

/** 호출어 기다리기 (핸즈프리). 들린 말을 계속 넘겨 주고, 끊기면 다시 시작한다. 돌려준 함수로 멈춘다. */
export function listenForever(onHeard: (text: string) => void, onError: (kind: string) => void): () => void {
  const C = ctor();
  if (!C) {
    onError("unsupported");
    return () => {};
  }
  let stopped = false;
  let r: SR | null = null;
  let fails = 0;
  const start = () => {
    if (stopped) return;
    r = new C();
    r.lang = "ko-KR";
    r.continuous = true;
    r.interimResults = false;
    r.onresult = (e) => {
      fails = 0;
      for (let i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) onHeard(e.results[i][0].transcript.trim());
      }
    };
    r.onerror = (e) => {
      if (e.error === "not-allowed" || e.error === "service-not-allowed") {
        stopped = true;
        onError("denied");
      } else if (e.error !== "no-speech" && e.error !== "aborted") {
        fails++;
      }
    };
    r.onend = () => {
      if (stopped) return;
      if (fails > 5) {
        stopped = true;
        onError("failing");
        return;
      }
      setTimeout(start, fails ? 1000 : 250);
    };
    try { r.start(); } catch { setTimeout(start, 1000); }
  };
  start();
  return () => {
    stopped = true;
    try { r?.abort(); } catch { /* 이미 끝남 */ }
  };
}

// ---------------------------------------------------------------- 말하기
export interface VoiceOpts { voiceName: string; pitch: number; rate: number }

export function koreanVoices(): SpeechSynthesisVoice[] {
  if (!("speechSynthesis" in window)) return [];
  return speechSynthesis.getVoices().filter((v) => /^ko/i.test(v.lang));
}

/** 울트론에게 어울리는 목소리: 이름을 고른 게 있으면 그것, 아니면 남성 목소리 → 아무 한국어 목소리 */
function pickVoice(name: string): SpeechSynthesisVoice | null {
  const ko = koreanVoices();
  if (name) {
    const v = ko.find((x) => x.name === name);
    if (v) return v;
  }
  return ko.find((v) => /male|남|injoon|minsu|hyunsu|jun/i.test(v.name) && !/female|여/i.test(v.name)) ?? ko[0] ?? null;
}

export class Speaker {
  private pending = 0;
  private onIdle: (() => void) | null = null;
  private onBoundary: (() => void) | null = null;
  private unlocked = false;

  constructor(private opts: () => VoiceOpts) {
    if ("speechSynthesis" in window) {
      speechSynthesis.getVoices();
      speechSynthesis.addEventListener?.("voiceschanged", () => speechSynthesis.getVoices());
    }
  }

  get available(): boolean {
    return "speechSynthesis" in window;
  }

  get speaking(): boolean {
    return this.pending > 0;
  }

  /** iOS 는 사용자가 화면을 누른 순간에 한 번 말해 둬야 그 뒤로도 말할 수 있다 */
  unlock(): void {
    if (this.unlocked || !this.available) return;
    this.unlocked = true;
    const u = new SpeechSynthesisUtterance(" ");
    u.volume = 0;
    speechSynthesis.speak(u);
  }

  setHandlers(onIdle: () => void, onBoundary: () => void): void {
    this.onIdle = onIdle;
    this.onBoundary = onBoundary;
  }

  say(text: string): void {
    if (!this.available || !text.trim()) return;
    const o = this.opts();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "ko-KR";
    const v = pickVoice(o.voiceName);
    if (v) u.voice = v;
    u.pitch = o.pitch;
    u.rate = o.rate;
    this.pending++;
    const finish = () => {
      this.pending = Math.max(0, this.pending - 1);
      if (this.pending === 0) this.onIdle?.();
    };
    u.onend = finish;
    u.onerror = finish;
    u.onboundary = () => this.onBoundary?.();
    speechSynthesis.speak(u);
    // 크롬 일부 버전은 오래 말하면 멈춘다 — 살짝 깨워 둔다
    if (speechSynthesis.paused) speechSynthesis.resume();
  }

  stop(): void {
    if (!this.available) return;
    const had = this.pending > 0;
    this.pending = 0;
    speechSynthesis.cancel();
    if (had) this.onIdle?.();
  }
}
