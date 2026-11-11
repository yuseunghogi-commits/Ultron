// 설치형 앱(Android)에서만 쓰는 기능들. 브라우저에서는 웹 기능으로 대신한다.
//
// 앱 안의 WebView 는 브라우저의 음성 인식 · 음성 합성 · 공유 · 인쇄를 못 쓰므로 Capacitor 플러그인으로 휴대폰 기능을 직접 쓴다.
// 덤으로 타이머는 휴대폰 알림으로 예약되어, 앱을 닫아 두어도 제때 울린다.

import { Capacitor } from "@capacitor/core";
import { App } from "@capacitor/app";
import { Clipboard } from "@capacitor/clipboard";
import { Haptics } from "@capacitor/haptics";
import { KeepAwake } from "@capacitor-community/keep-awake";
import { LocalNotifications } from "@capacitor/local-notifications";
import { Share } from "@capacitor/share";
import { SpeechRecognition } from "@capacitor-community/speech-recognition";
import { TextToSpeech, QueueStrategy } from "@capacitor-community/text-to-speech";

export const isNative = Capacitor.isNativePlatform();

// ---------------------------------------------------------------- 듣기
export type ListenError = "denied" | "network" | "other";

async function ensureMic(): Promise<boolean> {
  try {
    const p = await SpeechRecognition.checkPermissions();
    if (p.speechRecognition === "granted") return true;
    const r = await SpeechRecognition.requestPermissions();
    return r.speechRecognition === "granted";
  } catch {
    return false;
  }
}

/** 휴대폰의 음성 인식기로 한 마디 듣기. 다 들으면 onFinal (못 알아들었으면 빈 글). */
export function nativeListenOnce(onFinal: (text: string) => void, onError: (kind: ListenError, detail: string) => void): () => void {
  let done = false;
  const finish = (fn: () => void) => { if (!done) { done = true; fn(); } };
  void (async () => {
    if (!(await ensureMic())) { finish(() => onError("denied", "permission")); return; }
    try {
      const r = await SpeechRecognition.start({ language: "ko-KR", maxResults: 1, partialResults: false, popup: false });
      finish(() => onFinal((r.matches?.[0] ?? "").trim()));
    } catch (e) {
      const msg = String((e as Error)?.message ?? e);
      // 아무 말도 없었거나 알아듣지 못한 경우는 오류가 아니라 '빈 말'
      if (/no match|no speech|speech timeout|didn't understand|^[67]$/i.test(msg)) finish(() => onFinal(""));
      else if (/permission/i.test(msg)) finish(() => onError("denied", msg));
      else if (/network|server/i.test(msg)) finish(() => onError("network", msg));
      else finish(() => onError("other", msg));
    }
  })();
  return () => { void SpeechRecognition.stop().catch(() => {}); };
}

/** 호출어 기다리기: 듣고 → 결과 넘기고 → 다시 듣기를 되풀이한다. */
export function nativeListenForever(onHeard: (text: string) => void, onError: (kind: string) => void): () => void {
  let stopped = false;
  let fails = 0;
  const loop = async () => {
    if (!(await ensureMic())) { onError("denied"); return; }
    while (!stopped) {
      try {
        const r = await SpeechRecognition.start({ language: "ko-KR", maxResults: 1, partialResults: false, popup: false });
        fails = 0;
        const t = (r.matches?.[0] ?? "").trim();
        if (t && !stopped) onHeard(t);
      } catch (e) {
        const msg = String((e as Error)?.message ?? e);
        if (!/no match|no speech|speech timeout|^[67]$/i.test(msg)) fails++;
        if (fails > 5) { if (!stopped) onError("failing"); return; }
        await new Promise((r) => setTimeout(r, fails ? 1000 : 200));
      }
    }
  };
  void loop();
  return () => {
    stopped = true;
    void SpeechRecognition.stop().catch(() => {});
  };
}

// ---------------------------------------------------------------- 말하기
let voices: { name: string; lang: string }[] = [];
let voicesLoaded: Promise<void> | null = null;

export function loadNativeVoices(): Promise<void> {
  if (!voicesLoaded) {
    voicesLoaded = TextToSpeech.getSupportedVoices()
      .then((r) => { voices = r.voices.map((v) => ({ name: v.name, lang: v.lang })); })
      .catch(() => { voices = []; });
  }
  return voicesLoaded;
}

/** 한국어 목소리 이름들 */
export function nativeKoreanVoices(): string[] {
  return voices.filter((v) => /^ko/i.test(v.lang)).map((v) => v.name);
}

/** 고른 목소리의 번호 (TextToSpeech 는 전체 목록의 번호로 고른다). 없으면 남성 목소리 → 기본 */
function voiceIndex(name: string): number | undefined {
  const ko = voices.map((v, i) => ({ ...v, i })).filter((v) => /^ko/i.test(v.lang));
  const pick = (name && ko.find((v) => v.name === name)) || ko.find((v) => /male|x-kod|x-koc/i.test(v.name) && !/female/i.test(v.name));
  return pick ? pick.i : undefined;
}

export function nativeSpeak(text: string, pitch: number, rate: number, voiceName: string): Promise<void> {
  return TextToSpeech.speak({
    text, lang: "ko-KR", pitch, rate, volume: 1, voice: voiceIndex(voiceName), queueStrategy: QueueStrategy.Add,
  });
}

export function nativeStopSpeaking(): void {
  void TextToSpeech.stop().catch(() => {});
}

export function onNativeWord(fn: () => void): void {
  void TextToSpeech.addListener("onRangeStart", fn).catch(() => {});
}

// ---------------------------------------------------------------- 타이머 알림
let channelReady = false;

async function ensureNotify(): Promise<boolean> {
  try {
    let p = await LocalNotifications.checkPermissions();
    if (p.display !== "granted") p = await LocalNotifications.requestPermissions();
    if (p.display !== "granted") return false;
    if (!channelReady) {
      await LocalNotifications.createChannel({
        id: "timers", name: "타이머", description: "울트론 타이머 · 알림", importance: 5, visibility: 1, vibration: true,
      });
      channelReady = true;
    }
    return true;
  } catch {
    return false;
  }
}

export async function scheduleTimerNotice(id: number, label: string, due: number): Promise<boolean> {
  if (!(await ensureNotify())) return false;
  try {
    await LocalNotifications.schedule({
      notifications: [{
        id, title: "U.L.T.R.O.N", body: `${label}. 시간이다.`, channelId: "timers",
        schedule: { at: new Date(due), allowWhileIdle: true },
      }],
    });
    return true;
  } catch {
    return false;
  }
}

export function cancelTimerNotice(ids: number[]): void {
  if (!ids.length) return;
  void LocalNotifications.cancel({ notifications: ids.map((id) => ({ id })) }).catch(() => {});
}

// ---------------------------------------------------------------- 그 밖에
export async function nativeShare(title: string, text: string): Promise<void> {
  try { await Share.share({ title, text, dialogTitle: title }); } catch { /* 취소 */ }
}

export async function nativeCopy(text: string): Promise<void> {
  await Clipboard.write({ string: text });
}

export function nativeVibrate(ms: number): void {
  void Haptics.vibrate({ duration: ms }).catch(() => {});
}

export async function nativeKeepAwake(on: boolean): Promise<void> {
  try { await (on ? KeepAwake.keepAwake() : KeepAwake.allowSleep()); } catch { /* 무시 */ }
}

/** 뒤로 가기: 열린 창이 있으면 닫고, 없으면 앱을 내린다 */
export function onBackButton(closeTop: () => boolean): void {
  void App.addListener("backButton", () => {
    if (!closeTop()) void App.minimizeApp();
  });
}

export function onResume(fn: () => void): void {
  void App.addListener("resume", fn);
}
