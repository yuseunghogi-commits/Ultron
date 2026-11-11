import { describe, expect, it } from "vitest";
import { runTool, toolDefs, validate, type ActionCard, type ToolHost } from "../src/tools";
import { renderMarkdown } from "../src/md";
import { systemPrompt } from "../src/persona";

function fakeHost() {
  const cards: ActionCard[] = [];
  const mem: string[] = [];
  const host: ToolHost = {
    remember: (f) => mem.push(f),
    forget: () => 0,
    setTimer: () => "3분 뒤",
    cancelTimers: () => 0,
    listTimers: () => "",
    makeDoc: () => "d1",
    card: (c) => cards.push(c),
    deviceStatus: async () => "ok",
  };
  return { host, cards, mem };
}

describe("도구", () => {
  it("모델에 맞는 검색 도구를 고르고 사용자 도구는 입력을 바로 흘려보낸다", () => {
    const opus = toolDefs("claude-opus-5-5", "서울") as Array<{ name?: string; type?: string; eager_input_streaming?: boolean }>;
    expect(opus.find((t) => t.name === "web_search")).toMatchObject({ type: "web_search_20260209" });
    const haiku = toolDefs("claude-haiku-5-5", "서울") as Array<{ name?: string }>;
    expect(haiku.find((t) => t.name === "web_search")).toMatchObject({ type: "web_search_20250305" });
    const custom = opus.filter((t) => t.name !== "web_search");
    expect(custom.length).toBe(13);
    expect(custom.every((t) => t.eager_input_streaming)).toBe(true);
  });
  it("잘못된 입력은 실행하지 않는다", async () => {
    expect(validate("call_phone", { number: "010-1234-5678" })).toBeNull();
    expect(validate("call_phone", { number: "javascript:alert(1)" })).not.toBeNull();
    expect(validate("open_url", { url: "javascript:alert(1)", title: "x" })).not.toBeNull();
    expect(validate("set_timer", { seconds: 0, label: "x" })).not.toBeNull();
    const { host, cards } = fakeHost();
    const out = await runTool("send_sms", { number: "abc", body: "hi" }, host);
    expect(out.isError).toBe(true);
    expect(cards).toHaveLength(0);
  });
  it("전화 · 문자는 버튼만 띄운다", async () => {
    const { host, cards } = fakeHost();
    await runTool("call_phone", { number: "010-1234-5678", name: "엄마" }, host);
    await runTool("send_sms", { number: "01012345678", body: "늦어 & 미안" }, host);
    expect(cards[0]).toMatchObject({ kind: "call", href: "tel:01012345678" });
    expect(cards[1].href).toBe("sms:01012345678?body=%EB%8A%A6%EC%96%B4%20%26%20%EB%AF%B8%EC%95%88");
  });
});

describe("문서", () => {
  it("HTML 을 그대로 넣지 않는다", () => {
    const h = renderMarkdown("# 제목\n<script>alert(1)</script>\n- **굵게**\n[x](javascript:alert(1))");
    expect(h).toContain("<h1>제목</h1>");
    expect(h).not.toContain("<script>");
    expect(h).toContain("<strong>굵게</strong>");
    expect(h).not.toContain('href="javascript');
  });
  it("표", () => {
    const h = renderMarkdown("| 가 | 나 |\n|---|---|\n| 1 | 2 |");
    expect(h).toContain("<th>가</th>");
    expect(h).toContain("<td>2</td>");
  });
});

describe("성격", () => {
  it("호칭 · 기억 · 자비스 견제가 들어간다", () => {
    const p = systemPrompt(false, { title: "주인님", city: "부산", memory: ["커피를 좋아함"], rival: true });
    expect(p).toContain("주인님");
    expect(p).toContain("- 커피를 좋아함");
    expect(p).toContain("자비스");
    expect(p).not.toContain("{");
    expect(systemPrompt(true, { title: "주인님", city: "부산", memory: [], rival: false })).not.toContain("자비스");
  });
});
