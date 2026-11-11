// 발표 자료 · 표를 앱 안에서 보여 주고 한글 · 워드로 내보낼 때 쓰는 마크다운 개요 (무거운 라이브러리 없이)

import type { DeckSlide, SheetData } from "../store";

export interface Deck {
  title: string;
  subtitle?: string;
  slides: DeckSlide[];
}
type Cell = string | number;
type Sheet = SheetData;

/** 앱 안에서 보여 줄 개요 (그리고 한글 · 워드로 내보낼 때 쓰는 본문) */
export function deckMarkdown(deck: Deck): string {
  const parts = [`# ${deck.title}`];
  if (deck.subtitle) parts.push(deck.subtitle);
  deck.slides.forEach((s, i) => {
    parts.push(`## ${i + 1}. ${s.title}`);
    parts.push(s.bullets.map((b) => `- ${b}`).join("\n"));
    if (s.notes) parts.push(`> 발표 대본: ${s.notes}`);
  });
  return parts.join("\n\n");
}

/** 앱 안에서 보여 줄 표 (그리고 한글 · 워드로 내보낼 때 쓰는 본문) */
export function sheetsMarkdown(title: string, sheets: Sheet[]): string {
  const cell = (v: Cell) => String(v ?? "").replace(/\|/g, "/").replace(/\n/g, " ");
  const parts = [`# ${title}`];
  for (const s of sheets) {
    if (sheets.length > 1) parts.push(`## ${s.name}`);
    const cols = Math.max(1, s.columns.length);
    parts.push([
      `| ${s.columns.map(cell).join(" | ")} |`,
      `|${" --- |".repeat(cols)}`,
      ...s.rows.map((r) => `| ${Array.from({ length: cols }, (_, i) => cell(r[i] ?? "")).join(" | ")} |`),
    ].join("\n"));
  }
  return parts.join("\n\n");
}
