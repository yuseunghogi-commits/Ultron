// 울트론 모바일 — 화면과 흐름을 잇는 곳
import "./style.css";
import { Brain, BrainError } from "./brain";
import { Emblem, type Mode } from "./emblem";
import {
  clockText, dateText, findWake, forSpeech, localCommand, sayDuration, splitSentences, stripWake,
} from "./hearing";
import { renderMarkdown } from "./md";
import { CHAT_OFF_LINES, CHAT_ON_LINES, GLITCH_LINES, GREETINGS, pickLine } from "./persona";
import {
  MODEL_LABELS, loadChatMode, loadDocs, loadMemory, loadSettings, loadTimers, saveChatMode, saveDocs, saveMemory,
  saveSettings, saveTimers, uid, type Doc, type ExportFormat, type ModelId, type Settings, type Timer,
} from "./store";
import type { ActionCard, ToolHost } from "./tools";
import { FORMAT_LABEL, buildFile, downloadFile, formatsFor } from "./office/export";
import { deckMarkdown, sheetsMarkdown } from "./office/outline";
import { Speaker, canListen, koreanVoices, listenForever, listenOnce } from "./voice";
import {
  cancelTimerNotice, isNative, nativeCopy, openNativeFile, saveNativeFile, shareNativeFile, nativeKeepAwake, nativeShare, nativeVibrate, onBackButton, onResume, scheduleTimerNotice,
} from "./native";

const $ = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;

// ---------------------------------------------------------------- 상태
let settings: Settings = loadSettings();
let chatMode = loadChatMode();
let memory = loadMemory();
let docs = loadDocs();
let timers = loadTimers();
let state: Mode = "boot";
let stopListening: (() => void) | null = null;
let stopHandsFree: (() => void) | null = null;
let abort: AbortController | null = null;
let lastViaVoice = false;
let lastGlitch = "";
let audio: AudioContext | null = null;

const brain = new Brain();
const emblem = new Emblem($<HTMLCanvasElement>("emblem"));
const speaker = new Speaker(() => ({ voiceName: settings.voiceName, pitch: settings.pitch, rate: settings.rate }));

const STATUS: Record<Mode, string> = {
  boot: "BOOT", standby: "STANDBY", listening: "LISTENING", thinking: "THINKING", speaking: "SPEAKING", offline: "OFFLINE",
};
const HINT: Record<Mode, string> = {
  boot: "눌러서 깨우기", standby: "눌러서 말하기", listening: "듣는 중 — 다 말하면 멈춘다", thinking: "생각 중 — 누르면 취소",
  speaking: "누르면 조용히", offline: "오프라인",
};

function setState(m: Mode, detail = ""): void {
  state = m;
  emblem.mode = m;
  $("status").textContent = detail || STATUS[m];
  $("hint").textContent = HINT[m];
  document.body.dataset.state = m;
  if (m === "standby") syncHandsFree();
}

// ---------------------------------------------------------------- 화면: 대화 기록
const feed = $("feed");

function addLine(who: "user" | "ultron" | "system", text: string): HTMLElement {
  const el = document.createElement("div");
  el.className = `line ${who}`;
  el.textContent = text;
  feed.appendChild(el);
  while (feed.children.length > 60) feed.firstElementChild?.remove();
  scrollFeed();
  return el;
}

function scrollFeed(): void {
  document.body.classList.toggle("talking", feed.childElementCount > 0);
  feed.scrollTop = feed.scrollHeight;
}

const CARD_ICON: Record<ActionCard["kind"], string> = {
  call: '<path d="M6.5 3.5h3l1.5 4-2 1.5a11 11 0 0 0 6 6l1.5-2 4 1.5v3a2 2 0 0 1-2 2A16.5 16.5 0 0 1 4.5 5.5a2 2 0 0 1 2-2Z"/>',
  sms: '<path d="M4 5h16v11H9l-5 4Z"/>',
  link: '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
  map: '<path d="M12 21s-6.5-6-6.5-11a6.5 6.5 0 0 1 13 0c0 5-6.5 11-6.5 11Z"/><circle cx="12" cy="10" r="2.3"/>',
  share: '<circle cx="6" cy="12" r="2.3"/><circle cx="18" cy="6" r="2.3"/><circle cx="18" cy="18" r="2.3"/><path d="m8 11 8-4M8 13l8 4"/>',
  doc: '<path d="M6 3h8l4 4v14H6Z"/><path d="M14 3v4h4M9 12h6M9 16h6"/>',
};
const CARD_VERB: Record<ActionCard["kind"], string> = { call: "걸기", sms: "문자 앱 열기", link: "열기", map: "지도 열기", share: "공유", doc: "문서 보기" };

function addCard(c: ActionCard): void {
  const el = document.createElement("div");
  el.className = `card ${c.kind}`;
  const icon = `<svg viewBox="0 0 24 24" aria-hidden="true">${CARD_ICON[c.kind]}</svg>`;
  const info = document.createElement("div");
  info.className = "card-info";
  const t = document.createElement("strong");
  t.textContent = c.title;
  const d = document.createElement("span");
  d.textContent = c.detail;
  info.append(t, d);
  if (c.kind === "doc" && c.docId) {
    const id = c.docId;
    const btns = document.createElement("div");
    btns.className = "card-btns";
    if (c.want) btns.append(cardButton(FORMAT_LABEL[c.want], () => void exportDoc(id, c.want!)));
    btns.append(cardButton("보기", () => openDoc(id), !!c.want));
    el.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true">${CARD_ICON.doc}</svg>`;
    el.append(info, btns);
    feed.appendChild(el);
    scrollFeed();
    return;
  }
  let btn: HTMLAnchorElement | HTMLButtonElement;
  if (c.href) {
    const a = document.createElement("a");
    a.href = c.href;
    if (/^https?:/i.test(c.href)) { a.target = "_blank"; a.rel = "noopener noreferrer"; }
    btn = a;
  } else {
    btn = document.createElement("button");
    btn.type = "button";
    btn.addEventListener("click", () => {
      if (c.kind === "doc" && c.docId) openDoc(c.docId);
      else if (c.kind === "share" && c.text) void shareText(c.title, c.text);
    });
  }
  btn.className = "card-btn";
  btn.textContent = CARD_VERB[c.kind];
  el.innerHTML = icon;
  el.append(info, btn);
  feed.appendChild(el);
  scrollFeed();
}

function cardButton(label: string, fn: () => void, ghost = false): HTMLButtonElement {
  const b = document.createElement("button");
  b.type = "button";
  b.className = ghost ? "card-btn ghost-btn" : "card-btn";
  b.textContent = label;
  b.addEventListener("click", fn);
  return b;
}

function toast(text: string, ms = 2600): void {
  const t = $("toast");
  t.textContent = text;
  t.hidden = false;
  clearTimeout((toast as unknown as { h: number }).h);
  (toast as unknown as { h: number }).h = window.setTimeout(() => (t.hidden = true), ms);
}

// ---------------------------------------------------------------- 말하기
function say(text: string, show = true): void {
  if (show) addLine("ultron", text);
  if (!settings.speak || !speaker.available) return;
  setState("speaking");
  speaker.say(forSpeech(text));
}

speaker.setHandlers(
  () => {
    if (state !== "speaking") return;
    setState("standby");
    // 대화 모드에서 목소리로 말하고 있었다면 바로 다시 듣는다
    if (chatMode && settings.autoListen && lastViaVoice) setTimeout(() => state === "standby" && listen(), 250);
  },
  () => { emblem.level = 0.55 + Math.random() * 0.45; },
);

// ---------------------------------------------------------------- 듣기
function listen(): void {
  if (!canListen()) {
    toast("이 브라우저는 음성 인식이 안 된다. 키보드의 마이크 버튼을 써라.");
    $("text").focus();
    return;
  }
  pauseHandsFree();
  setState("listening");
  const interim = addLine("user", "…");
  interim.classList.add("interim");
  stopListening = listenOnce({
    onSpeech: () => { emblem.level = 0.8; },
    onInterim: (t) => { interim.textContent = t || "…"; emblem.level = 0.5 + Math.random() * 0.5; scrollFeed(); },
    onFinal: (t) => {
      stopListening = null;
      interim.remove();
      if (state !== "listening") return;
      if (!t) { setState("standby"); return; }
      void handle(t, true);
    },
    onError: (kind) => {
      stopListening = null;
      interim.remove();
      setState("standby");
      if (kind === "denied") toast("마이크 권한이 필요하다. 브라우저 설정에서 마이크를 허용해라.");
      else if (kind === "network") toast("음성 인식에 인터넷이 필요하다.");
      else toast("못 들었다. 다시 눌러라.");
    },
  });
}

function syncHandsFree(): void {
  const want = settings.handsFree && state === "standby" && !document.hidden && canListen();
  if (want && !stopHandsFree) {
    stopHandsFree = listenForever(
      (heard) => {
        if (state !== "standby") return;
        const rest = findWake(heard);
        if (rest === null) return;
        pauseHandsFree();
        if (rest) void handle(rest, true);
        else { unlockAudio(); beep(880, 0.08); listen(); }
      },
      (kind) => {
        stopHandsFree = null;
        if (kind === "denied") toast("마이크 권한이 없어 호출어를 들을 수 없다.");
        else if (kind === "failing") toast("호출어 듣기가 자꾸 끊긴다. 화면을 눌러서 말해라.");
      },
    );
  } else if (!want) {
    pauseHandsFree();
  }
}

function pauseHandsFree(): void {
  stopHandsFree?.();
  stopHandsFree = null;
}

// ---------------------------------------------------------------- 한 마디 처리
async function handle(raw: string, viaVoice: boolean): Promise<void> {
  lastViaVoice = viaVoice;
  const { rest } = stripWake(raw);
  const text = rest || raw.trim();
  if (!text) return;
  addLine("user", text);

  const local = localCommand(text, chatMode);
  if (local) {
    switch (local.kind) {
      case "chat_on": setChat(true); say(pickLine(CHAT_ON_LINES)); return;
      case "chat_off": setChat(false); lastViaVoice = false; say(pickLine(CHAT_OFF_LINES)); return;
      case "time": say(`${clockText()}이다.`); return;
      case "date": say(`오늘은 ${dateText()}이다.`); return;
      case "stop": speaker.stop(); setState("standby"); return;
      case "reset": brain.reset(); say("기억을 비웠다. 새로 시작하지."); return;
      case "cancel_timers": { const n = host.cancelTimers(); say(n ? `타이머 ${n}개를 껐다.` : "꺼 둘 타이머가 없다."); return; }
      case "timer": host.setTimer(local.seconds, local.label); say(`${sayDuration(local.seconds)} 타이머를 맞췄다.`); return;
    }
  }

  if (!settings.apiKey) {
    say("API 키가 없어서 지금은 시간과 타이머 정도만 할 수 있다. 설정에서 키를 넣어라.");
    return;
  }

  pauseHandsFree();
  setState("thinking");
  abort = new AbortController();
  const bubble = addLine("ultron", "");
  bubble.classList.add("streaming");
  let pending = "";
  let spoke = false;
  const speakDone = (final: boolean) => {
    const { done, rest } = splitSentences(pending);
    const out = final ? [...done, rest].filter((s) => s.trim()) : done;
    pending = final ? "" : rest;
    if (!settings.speak || !speaker.available) return;
    for (const s of out) {
      const clean = forSpeech(s);
      if (!clean) continue;
      if (!spoke) { spoke = true; setState("speaking"); }
      speaker.say(clean);
    }
  };
  try {
    const answer = await brain.turn(text, settings, chatMode, memory, host, {
      signal: abort.signal,
      onStatus: (s) => { if (state === "thinking") $("status").textContent = s || STATUS.thinking; },
      onText: (d) => {
        bubble.textContent += d;
        pending += d;
        scrollFeed();
        speakDone(false);
      },
    });
    speakDone(true);
    bubble.classList.remove("streaming");
    if (!bubble.textContent?.trim()) {
      if (answer) bubble.textContent = answer;
      else bubble.remove();
    }
    if (!spoke) setState("standby");
  } catch (e) {
    bubble.remove();
    const err = e instanceof BrainError ? e : new BrainError(String(e), "뭔가 꼬였다.");
    console.warn("[ultron]", err.message);
    if (err.spoken) say(err.spoken);
    else setState("standby");
  } finally {
    abort = null;
  }
}

function setChat(on: boolean): void {
  chatMode = on;
  saveChatMode(on);
  const b = $("modeBtn");
  b.textContent = on ? "대화" : "명령";
  b.setAttribute("aria-pressed", String(on));
  document.body.classList.toggle("chat", on);
}

// ---------------------------------------------------------------- 도구가 부탁하는 일
const host: ToolHost = {
  remember(fact) {
    memory = [...memory.filter((m) => m !== fact), fact];
    saveMemory(memory);
  },
  forget(query) {
    const before = memory.length;
    memory = memory.filter((m) => !m.includes(query));
    saveMemory(memory);
    return before - memory.length;
  },
  setTimer(seconds, label) {
    const t: Timer = { id: uid(), label, due: Date.now() + seconds * 1000 };
    if (isNative) {
      // 앱을 닫아 두어도 울리도록 휴대폰 알림으로도 예약한다
      t.notice = Math.floor(Math.random() * 2_000_000_000) + 1;
      void scheduleTimerNotice(t.notice, label, t.due).then((ok) => {
        if (!ok) toast("알림 권한이 없어 앱을 켜 둔 동안에만 울린다.");
      });
    }
    timers = [...timers, t].sort((a, b) => a.due - b.due);
    saveTimers(timers);
    renderTimerBar();
    return `${sayDuration(seconds)} 뒤${isNative ? "" : " (웹 판은 앱이 열려 있어야 제때 울린다)"}`;
  },
  cancelTimers(label) {
    const before = timers.length;
    const gone = label ? timers.filter((t) => t.label.includes(label)) : timers;
    removeTimers(gone);
    return before - timers.length;
  },
  listTimers() {
    if (!timers.length) return "남은 타이머가 없다.";
    return timers.map((t) => `${t.label}: ${sayDuration(Math.max(0, (t.due - Date.now()) / 1000))} 남음`).join("\n");
  },
  makeDoc(n) {
    const content =
      n.kind === "slides" && n.slides ? deckMarkdown({ title: n.title, subtitle: n.subtitle, slides: n.slides })
      : n.kind === "sheet" && n.sheets ? sheetsMarkdown(n.title, n.sheets)
      : n.content ?? "";
    const d: Doc = {
      id: uid(), title: n.title, content, created: Date.now(), kind: n.kind,
      subtitle: n.subtitle, style: n.style, slides: n.slides, sheets: n.sheets, want: n.want,
    };
    docs = [...docs, d];
    saveDocs(docs);
    return d.id;
  },
  card: addCard,
  async deviceStatus() {
    const parts: string[] = [];
    const nav = navigator as Navigator & { getBattery?: () => Promise<{ level: number; charging: boolean }> };
    try {
      if (nav.getBattery) {
        const b = await nav.getBattery();
        parts.push(`배터리 ${Math.round(b.level * 100)}%${b.charging ? " (충전 중)" : ""}`);
      } else parts.push("배터리: 이 브라우저는 알려 주지 않음");
    } catch { parts.push("배터리: 확인 실패"); }
    parts.push(navigator.onLine ? "인터넷 연결됨" : "인터넷 끊김");
    const conn = (navigator as Navigator & { connection?: { effectiveType?: string } }).connection;
    if (conn?.effectiveType) parts.push(`네트워크 ${conn.effectiveType}`);
    parts.push(host.listTimers());
    return parts.join("\n");
  },
};

// ---------------------------------------------------------------- 타이머
function removeTimers(gone: Timer[]): void {
  const ids = new Set(gone.map((t) => t.id));
  cancelTimerNotice(gone.map((t) => t.notice).filter((n): n is number => typeof n === "number"));
  timers = timers.filter((t) => !ids.has(t.id));
  saveTimers(timers);
  renderTimerBar();
}

function vibrate(pattern: number[]): void {
  if (isNative) nativeVibrate(pattern.filter((_, i) => i % 2 === 0).reduce((a, b) => a + b, 0));
  else navigator.vibrate?.(pattern);
}

function renderTimerBar(): void {
  const bar = $("timerBar");
  if (!timers.length) { bar.hidden = true; return; }
  const t = timers[0];
  const left = Math.max(0, Math.ceil((t.due - Date.now()) / 1000));
  const mm = Math.floor(left / 60), ss = left % 60;
  bar.hidden = false;
  bar.textContent = `${t.label} ${mm}:${String(ss).padStart(2, "0")}${timers.length > 1 ? ` 외 ${timers.length - 1}개` : ""}`;
}

function tickTimers(): void {
  if (!timers.length) return;
  const now = Date.now();
  const due = timers.filter((t) => t.due <= now);
  if (due.length) {
    timers = timers.filter((t) => t.due > now);
    saveTimers(timers);
    for (const t of due) {
      const late = now - t.due > 60_000;
      unlockAudio();
      beep(988, 0.18); setTimeout(() => beep(784, 0.18), 220); setTimeout(() => beep(988, 0.3), 440);
      vibrate([300, 120, 300, 120, 500]);
      say(late ? `${t.label} — 시간이 이미 지났다.` : `${t.label}. 시간이다.`);
    }
  }
  renderTimerBar();
}

// ---------------------------------------------------------------- 소리 (타이머 · 호출)
function unlockAudio(): void {
  try {
    if (!audio) audio = new AudioContext();
    if (audio.state === "suspended") void audio.resume();
  } catch { /* 소리 없이 진행 */ }
}

function beep(freq: number, dur: number): void {
  if (!audio) return;
  const o = audio.createOscillator();
  const g = audio.createGain();
  o.type = "square";
  o.frequency.value = freq;
  g.gain.setValueAtTime(0.0001, audio.currentTime);
  g.gain.exponentialRampToValueAtTime(0.12, audio.currentTime + 0.01);
  g.gain.exponentialRampToValueAtTime(0.0001, audio.currentTime + dur);
  o.connect(g).connect(audio.destination);
  o.start();
  o.stop(audio.currentTime + dur + 0.02);
}

// ---------------------------------------------------------------- 해킹 연출
function scheduleGlitch(): void {
  const wait = (6 + Math.random() * 9) * 60_000;   // 6 ~ 15분마다 한 번쯤
  setTimeout(() => { maybeGlitch(); scheduleGlitch(); }, wait);
}

function maybeGlitch(force = false): void {
  if (!force && (!settings.glitch || state !== "standby" || document.hidden)) return;
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const app = $("app");
  app.classList.remove("glitching");
  void app.offsetWidth;
  app.classList.add("glitching");
  if (audio) { beep(110, 0.25); setTimeout(() => beep(73, 0.35), 160); }
  vibrate([40, 60, 40]);
  setTimeout(() => {
    app.classList.remove("glitching");
    lastGlitch = pickLine(GLITCH_LINES, lastGlitch);
    say(lastGlitch);
  }, 1300);
}

// ---------------------------------------------------------------- 화면 켜 두기
let wakeLock: { release(): Promise<void> } | null = null;
async function syncWakeLock(): Promise<void> {
  if (isNative) { await nativeKeepAwake(settings.keepAwake); return; }
  const nav = navigator as Navigator & { wakeLock?: { request(t: "screen"): Promise<{ release(): Promise<void> }> } };
  if (settings.keepAwake && !document.hidden && nav.wakeLock && !wakeLock) {
    try { wakeLock = await nav.wakeLock.request("screen"); } catch { wakeLock = null; }
  } else if (!settings.keepAwake && wakeLock) {
    await wakeLock.release().catch(() => {});
    wakeLock = null;
  }
}

// ---------------------------------------------------------------- 공유 · 문서
async function shareText(title: string, text: string): Promise<void> {
  if (isNative) { await nativeShare(title, text); return; }
  if (navigator.share) {
    try { await navigator.share({ title, text }); return; } catch { /* 취소 */ return; }
  }
  await copyText(text);
}

async function copyText(text: string): Promise<void> {
  try {
    if (isNative) await nativeCopy(text);
    else await navigator.clipboard.writeText(text);
    toast("복사했다.");
  } catch {
    toast("복사하지 못했다.");
  }
}

let openDocId = "";
function openDoc(id: string): void {
  const d = docs.find((x) => x.id === id);
  if (!d) { toast("그 문서는 지워졌다."); return; }
  openDocId = id;
  $("docTitle").textContent = d.title;
  const body = $("docBody");
  body.innerHTML = "";
  if (d.kind === "slides" && d.slides) body.append(renderSlides(d));
  else body.innerHTML = renderMarkdown(d.content);
  // 파일로 만들기 버튼
  const files = $("docFiles");
  files.innerHTML = "";
  formatsFor(d).filter((f) => !(isNative && f === "pdf")).forEach((f, i) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = i === 0 ? "primary" : "ghost";
    b.textContent = FORMAT_LABEL[f];
    b.addEventListener("click", () => void exportDoc(d.id, f));
    files.appendChild(b);
  });
  $("docHint").textContent = isNative
    ? "파일 버튼을 누르면 '문서 › ULTRON' 폴더에 저장되고, 열 앱(한컴오피스 · 구글 문서 · 워드 · 엑셀)을 고를 수 있다."
    : "파일 버튼을 누르면 내려받는다. 구글 문서로 쓰려면 워드 파일을 구글 드라이브에 올리면 된다.";
  openSheet("docView");
}

function renderSlides(d: Doc): HTMLElement {
  const wrap = document.createElement("div");
  wrap.className = `slides ${d.style ?? "light"}`;
  const make = (title: string, items: string[], cls: string, notes?: string, sub?: string) => {
    const s = document.createElement("section");
    s.className = `slide ${cls}`;
    const h = document.createElement("h3");
    h.textContent = title;
    s.appendChild(h);
    if (sub) { const p = document.createElement("p"); p.textContent = sub; s.appendChild(p); }
    if (items.length) {
      const ul = document.createElement("ul");
      for (const it of items) { const li = document.createElement("li"); li.textContent = it; ul.appendChild(li); }
      s.appendChild(ul);
    }
    wrap.appendChild(s);
    if (notes) {
      const n = document.createElement("p");
      n.className = "notes";
      n.textContent = `대본 · ${notes}`;
      wrap.appendChild(n);
    }
  };
  make(d.title, [], "cover", undefined, d.subtitle);
  d.slides!.forEach((s) => make(s.title, s.bullets, "", s.notes));
  return wrap;
}

/** 문서를 파일로: 브라우저는 내려받기, 설치형 앱은 저장한 뒤 열 앱 고르기 */
async function exportDoc(id: string, format: ExportFormat): Promise<void> {
  const d = docs.find((x) => x.id === id);
  if (!d) { toast("그 문서는 지워졌다."); return; }
  if (format === "pdf") {
    if (isNative) { toast("PDF 는 한글이나 워드 앱에서 'PDF 로 저장'을 써라."); return; }
    if ($("docView").hidden || openDocId !== id) openDoc(id);
    setTimeout(() => window.print(), 200);
    return;
  }
  toast("파일 만드는 중…", 8000);
  try {
    const f = await buildFile(d, format);
    if (isNative) {
      const saved = await saveNativeFile(f.name, f.data);
      toast(saved.where ? `저장했다 — ${saved.where}` : "파일을 만들었다.", 4000);
      await openNativeFile(saved.uri, f.mime, d.title);
    } else {
      downloadFile(f);
      toast(`${f.name} 을 내려받았다.`, 4000);
    }
  } catch (e) {
    console.warn("[ultron] export", e);
    toast("파일을 만들지 못했다.");
  }
}

// ---------------------------------------------------------------- 시트 (설정 · 기록 · 문서)
function openSheet(id: string): void {
  $(id).hidden = false;
  document.body.classList.add("sheet-open");
}
function closeSheet(el: HTMLElement): void {
  el.hidden = true;
  if (!document.querySelector(".sheet:not([hidden])")) document.body.classList.remove("sheet-open");
}
document.querySelectorAll<HTMLElement>(".sheet").forEach((sheet) => {
  sheet.addEventListener("click", (e) => {
    const t = e.target as HTMLElement;
    if (t === sheet || t.closest("[data-close]")) {
      if (sheet.id === "settings") readSettingsForm();
      closeSheet(sheet);
    }
  });
});

function fillSettingsForm(): void {
  ($("sKey") as HTMLInputElement).value = settings.apiKey;
  const model = $("sModel") as HTMLSelectElement;
  model.innerHTML = "";
  for (const [id, label] of Object.entries(MODEL_LABELS)) model.add(new Option(label, id, false, id === settings.model));
  ($("sEffort") as HTMLSelectElement).value = settings.effort;
  ($("sTitle") as HTMLInputElement).value = settings.title;
  ($("sCity") as HTMLInputElement).value = settings.city;
  ($("sSpeak") as HTMLInputElement).checked = settings.speak;
  const voice = $("sVoice") as HTMLSelectElement;
  voice.innerHTML = "";
  voice.add(new Option("자동 (남성 목소리 우선)", ""));
  for (const name of koreanVoices()) voice.add(new Option(name, name, false, name === settings.voiceName));
  ($("sPitch") as HTMLInputElement).value = String(settings.pitch);
  ($("sRate") as HTMLInputElement).value = String(settings.rate);
  $("oPitch").textContent = settings.pitch.toFixed(2);
  $("oRate").textContent = settings.rate.toFixed(2);
  ($("sAuto") as HTMLInputElement).checked = settings.autoListen;
  ($("sHands") as HTMLInputElement).checked = settings.handsFree;
  ($("sAwake") as HTMLInputElement).checked = settings.keepAwake;
  ($("sGlitch") as HTMLInputElement).checked = settings.glitch;
  ($("sRival") as HTMLInputElement).checked = settings.rival;
  $("about").textContent =
    `음성 인식: ${canListen() ? "됨" : "안 됨 (키보드 마이크를 쓰세요)"} · 음성 합성: ${speaker.available ? `됨 (한국어 목소리 ${koreanVoices().length}개)` : "안 됨"}`;
}

function readSettingsForm(): void {
  const v = (id: string) => ($(id) as HTMLInputElement).value;
  const c = (id: string) => ($(id) as HTMLInputElement).checked;
  settings = {
    ...settings,
    apiKey: v("sKey").trim(),
    model: v("sModel") as ModelId,
    effort: v("sEffort") as Settings["effort"],
    title: v("sTitle").trim() || "창조자",
    city: v("sCity").trim() || "서울",
    speak: c("sSpeak"),
    voiceName: v("sVoice"),
    pitch: Number(v("sPitch")),
    rate: Number(v("sRate")),
    autoListen: c("sAuto"),
    handsFree: c("sHands"),
    keepAwake: c("sAwake"),
    glitch: c("sGlitch"),
    rival: c("sRival"),
  };
  saveSettings(settings);
  if (state === "standby") syncHandsFree();
  void syncWakeLock();
}

["sPitch", "sRate"].forEach((id) =>
  $(id).addEventListener("input", () => {
    $(id === "sPitch" ? "oPitch" : "oRate").textContent = Number(($(id) as HTMLInputElement).value).toFixed(2);
  }),
);
$("sTest").addEventListener("click", () => {
  speaker.unlock();
  readSettingsForm();
  speaker.stop();
  speaker.say(`나는 울트론이다. ${settings.title}, 이 목소리면 되겠나?`);
});

function renderLog(): void {
  const docList = $("docList");
  docList.innerHTML = "";
  if (!docs.length) docList.innerHTML = '<li class="empty">아직 없다. "OO 정리해서 보고서 써 줘"라고 말해 봐라.</li>';
  for (const d of [...docs].reverse()) {
    const li = document.createElement("li");
    const open = document.createElement("button");
    open.type = "button";
    open.className = "item";
    open.textContent = d.title;
    const when = document.createElement("small");
    when.textContent = new Date(d.created).toLocaleString("ko-KR", { dateStyle: "short", timeStyle: "short" });
    open.appendChild(when);
    open.addEventListener("click", () => openDoc(d.id));
    li.append(open, delButton(() => { docs = docs.filter((x) => x.id !== d.id); saveDocs(docs); renderLog(); }));
    docList.appendChild(li);
  }
  const tl = $("timerList");
  tl.innerHTML = "";
  if (!timers.length) tl.innerHTML = '<li class="empty">없음</li>';
  for (const t of timers) {
    const li = document.createElement("li");
    const s = document.createElement("span");
    s.className = "item";
    s.textContent = `${t.label} · ${new Date(t.due).toLocaleTimeString("ko-KR", { hour: "numeric", minute: "2-digit" })}`;
    li.append(s, delButton(() => { removeTimers([t]); renderLog(); }));
    tl.appendChild(li);
  }
  const ml = $("memList");
  ml.innerHTML = "";
  if (!memory.length) ml.innerHTML = '<li class="empty">없음. "내가 매운 거 못 먹는다는 거 기억해"처럼 말해 봐라.</li>';
  for (const m of memory) {
    const li = document.createElement("li");
    const s = document.createElement("span");
    s.className = "item";
    s.textContent = m;
    li.append(s, delButton(() => { memory = memory.filter((x) => x !== m); saveMemory(memory); renderLog(); }));
    ml.appendChild(li);
  }
}

function delButton(fn: () => void): HTMLButtonElement {
  const b = document.createElement("button");
  b.type = "button";
  b.className = "icon del";
  b.setAttribute("aria-label", "지우기");
  b.innerHTML = '<svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6 6 18"/></svg>';
  b.addEventListener("click", fn);
  return b;
}

// ---------------------------------------------------------------- 버튼
function onCoreTap(): void {
  speaker.unlock();
  unlockAudio();
  if (state === "boot") { greet(); return; }
  if (state === "speaking") { speaker.stop(); setState("standby"); return; }
  if (state === "listening") { stopListening?.(); return; }
  if (state === "thinking") { abort?.abort(); return; }
  listen();
}

$("emblemBtn").addEventListener("click", onCoreTap);
$("mic").addEventListener("click", () => {
  speaker.unlock();
  unlockAudio();
  if (state === "boot") setState("standby");
  if (state === "listening") { stopListening?.(); return; }
  if (state === "speaking") speaker.stop();
  if (state === "thinking") return;
  listen();
});
$("inputForm").addEventListener("submit", (e) => {
  e.preventDefault();
  speaker.unlock();
  unlockAudio();
  const input = $("text") as HTMLInputElement;
  const text = input.value.trim();
  if (!text || state === "thinking") return;
  input.value = "";
  if (state === "boot") setState("standby");
  if (state === "speaking") speaker.stop();
  if (state === "listening") stopListening?.();
  void handle(text, false);
});
$("modeBtn").addEventListener("click", () => {
  setChat(!chatMode);
  toast(chatMode ? "자유 대화 모드" : "명령 모드");
});
$("setBtn").addEventListener("click", () => { fillSettingsForm(); openSheet("settings"); });
$("logBtn").addEventListener("click", () => { renderLog(); openSheet("log"); });
$("newChat").addEventListener("click", () => { brain.reset(); feed.innerHTML = ""; scrollFeed(); closeSheet($("log")); toast("새 대화를 시작한다."); });
$("docShare").addEventListener("click", () => {
  const d = docs.find((x) => x.id === openDocId);
  if (d) void shareText(d.title, d.content);
});
$("docCopy").addEventListener("click", () => {
  const d = docs.find((x) => x.id === openDocId);
  if (d) void copyText(d.content);
});
$("docSendFile").addEventListener("click", async () => {
  const d = docs.find((x) => x.id === openDocId);
  if (!d) return;
  const f = formatsFor(d)[0];
  if (f === "pdf") return;
  try {
    const built = await buildFile(d, f);
    const saved = await saveNativeFile(built.name, built.data);
    await shareNativeFile(saved.uri, d.title);
  } catch { toast("파일을 보내지 못했다."); }
});

// 처음 설정
$("setupGo").addEventListener("click", () => {
  const key = ($("setupKey") as HTMLInputElement).value.trim();
  if (!key) { toast("API 키를 넣어라."); return; }
  settings = { ...settings, apiKey: key, title: ($("setupTitle") as HTMLInputElement).value.trim() || "창조자" };
  saveSettings(settings);
  closeSheet($("setup"));
  speaker.unlock();
  unlockAudio();
  greet();
});
$("setupLater").addEventListener("click", () => {
  settings = { ...settings, title: ($("setupTitle") as HTMLInputElement).value.trim() || "창조자" };
  saveSettings(settings);
  closeSheet($("setup"));
});

function greet(): void {
  setState("standby");
  say(pickLine(GREETINGS).replace("{title}", settings.title));
}

document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    pauseHandsFree();
    wakeLock = null;
  } else {
    tickTimers();
    if (state === "standby") syncHandsFree();
    void syncWakeLock();
  }
});

// ---------------------------------------------------------------- 시작
function boot(): void {
  const params = new URLSearchParams(location.search);
  if (params.has("icon")) {   // 아이콘 그리기용 (개발)
    document.body.className = "icon-only";
    emblem.still();
    return;
  }
  setChat(chatMode);
  emblem.start();
  setState("boot");
  renderTimerBar();
  setInterval(tickTimers, 1000);
  scheduleGlitch();
  void syncWakeLock();
  if (params.has("glitch")) setTimeout(() => maybeGlitch(true), 2500);
  if (brain.turns) addLine("system", "직전 대화를 이어 간다.");
  if (!settings.apiKey && !localStorage.getItem("ultron.setupSeen")) {
    try { localStorage.setItem("ultron.setupSeen", "1"); } catch { /* 무시 */ }
    ($("setupTitle") as HTMLInputElement).value = settings.title;
    openSheet("setup");
  }
  if (isNative) setupNative();
  else if ("serviceWorker" in navigator && import.meta.env.PROD) {
    navigator.serviceWorker.register("./sw.js").catch(() => {});
  }
}

// ---------------------------------------------------------------- 설치형 앱 전용
function setupNative(): void {
  document.body.classList.add("native");
  // 뒤로 가기: 열린 창부터 닫는다
  onBackButton(() => {
    const open = [...document.querySelectorAll<HTMLElement>(".sheet:not([hidden])")].pop();
    if (!open) return false;
    if (open.id === "settings") readSettingsForm();
    closeSheet(open);
    return true;
  });
  onResume(() => { tickTimers(); if (state === "standby") syncHandsFree(); });
  // 바깥 링크(https · tel · sms)는 앱 안이 아니라 휴대폰의 브라우저 · 전화 · 문자 앱으로 연다
  document.addEventListener("click", (e) => {
    const a = (e.target as HTMLElement).closest?.("a[href]") as HTMLAnchorElement | null;
    if (!a || !/^(https?:|tel:|sms:|mailto:)/i.test(a.href) || a.origin === location.origin) return;
    e.preventDefault();
    window.location.href = a.href;
  }, true);
}

boot();
