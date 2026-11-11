import { describe, expect, it } from "vitest";
import { findWake, forSpeech, koreanNumber, localCommand, parseDuration, sayDuration, splitSentences, stripWake } from "../src/hearing";

describe("호출어", () => {
  it("맨 앞의 울트론과 뭉개진 변형을 떼어 낸다", () => {
    expect(stripWake("울트론 날씨 알려 줘")).toEqual({ woke: true, rest: "날씨 알려 줘" });
    expect(stripWake("울트론아, 몇 시야")).toEqual({ woke: true, rest: "몇 시야" });
    expect(stripWake("울트롱 타이머")).toEqual({ woke: true, rest: "타이머" });
    expect(stripWake("오늘 날씨")).toEqual({ woke: false, rest: "오늘 날씨" });
  });
  it("계속 듣기에서 문장 중간의 호출어를 찾는다", () => {
    expect(findWake("음 울트론 불 꺼")).toBe("불 꺼");
    expect(findWake("울트론")).toBe("");
    expect(findWake("그냥 혼잣말")).toBeNull();
  });
});

describe("한글 수와 시간", () => {
  it("한자어 · 고유어 수", () => {
    expect(koreanNumber("삼십")).toBe(30);
    expect(koreanNumber("십오")).toBe(15);
    expect(koreanNumber("스물다섯")).toBe(25);
    expect(koreanNumber("세")).toBe(3);
    expect(koreanNumber("12")).toBe(12);
    expect(koreanNumber("사과")).toBeNull();
  });
  it("시간 길이", () => {
    expect(parseDuration("3분 타이머")).toBe(180);
    expect(parseDuration("타이머 오 분 맞춰 줘")).toBe(300);
    expect(parseDuration("1시간 반 뒤에 알려 줘")).toBe(5400);
    expect(parseDuration("2분 30초")).toBe(150);
    expect(parseDuration("삼십 초 뒤에 알려")).toBe(30);
    expect(parseDuration("라면 3분 반")).toBe(210);
    expect(parseDuration("타이머")).toBeNull();
  });
  it("말로 읽는 길이", () => {
    expect(sayDuration(5400)).toBe("1시간 30분");
    expect(sayDuration(45)).toBe("45초");
  });
});

describe("바로 처리하는 명령", () => {
  it("대화 모드", () => {
    expect(localCommand("대화 모드 켜 줘", false)).toEqual({ kind: "chat_on" });
    expect(localCommand("우리 얘기 좀 하자", false)).toEqual({ kind: "chat_on" });
    expect(localCommand("대모 꺼", true)).toEqual({ kind: "chat_off" });
    expect(localCommand("잘 자", true)).toEqual({ kind: "chat_off" });
  });
  it("시간 · 날짜 · 타이머", () => {
    expect(localCommand("지금 몇 시야", false)).toEqual({ kind: "time" });
    expect(localCommand("오늘 며칠이야", false)).toEqual({ kind: "date" });
    expect(localCommand("3분 타이머", false)).toEqual({ kind: "timer", seconds: 180, label: "타이머" });
    expect(localCommand("10분 뒤에 알려 줘", false)).toEqual({ kind: "timer", seconds: 600, label: "타이머" });
    expect(localCommand("타이머 꺼", false)).toEqual({ kind: "cancel_timers" });
  });
  it("길거나 다른 뜻이면 Claude 에게 넘긴다", () => {
    expect(localCommand("몇 시간 뒤에 비 와?", false)).toBeNull();
    expect(localCommand("오늘 날씨 어때", false)).toBeNull();
    expect(localCommand("인공지능의 역사에 대해 자세히 이야기해 줄 수 있어?", false)).toBeNull();
  });
});

describe("말하기 준비", () => {
  it("문장 단위로 끊는다", () => {
    expect(splitSentences("검색했다. 오늘은 맑다! 기온은")).toEqual({ done: ["검색했다.", "오늘은 맑다!"], rest: " 기온은" });
    expect(splitSentences("3.5도다. ")).toEqual({ done: ["3.5도다."], rest: " " });
  });
  it("읽을 때 마크다운과 URL 을 걷어 낸다", () => {
    expect(forSpeech("**좋다** https://a.com (참고) 끝")).toBe("좋다 끝");
  });
});
