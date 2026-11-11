// 발표 자료 · 표를 앱 안에서 보여 주고 한글 · 워드로 내보낼 때 쓰는 마크다운 개요 (무거운 라이브러리 없이)

import type { DeckSlide, SheetData } from "../store";

export interface Deck {
  title: string;
  subtitle?: string;
  slides: DeckSlide[];
}
type Cell = string | number;
type Sheet = SheetData;

function table(head: Cell[], rows: Cell[][]): string {
  const cell = (v: Cell) => String(v ?? "").replace(/\|/g, "/").replace(/\n/g, " ");
  return [`| ${head.map(cell).join(" | ")} |`, `|${" --- |".repeat(head.length)}`, ...rows.map((r) => `| ${head.map((_, i) => cell(r[i] ?? "")).join(" | ")} |`)].join("\n");
}

/** 카드뉴스 · 포스터의 글 (한글 · 워드로 내보낼 때와 보기 화면의 글) */
export function cardnewsMarkdown(title: string, subtitle: string | undefined, cards: { title: string; bullets: string[]; highlight?: string }[], closing?: string, sources?: string[]): string {
  const parts = [`# ${title}`];
  if (subtitle) parts.push(subtitle);
  cards.forEach((c, i) => {
    parts.push(`## ${i + 1}. ${c.title}`);
    if (c.bullets.length) parts.push(c.bullets.map((b) => `- ${b}`).join("\n"));
    if (c.highlight) parts.push(`> ${c.highlight}`);
  });
  if (closing) parts.push(closing);
  if (sources?.length) parts.push(`## 출처\n${sources.map((s) => `- ${s}`).join("\n")}`);
  return parts.join("\n\n");
}

export function posterMarkdown(title: string, subtitle: string | undefined, highlight: string | undefined, sections: { heading?: string; bullets: string[] }[], footer?: string, sources?: string[]): string {
  const parts = [`# ${title}`];
  if (subtitle) parts.push(subtitle);
  if (highlight) parts.push(`**${highlight}**`);
  for (const s of sections) {
    if (s.heading) parts.push(`## ${s.heading}`);
    if (s.bullets.length) parts.push(s.bullets.map((b) => `- ${b}`).join("\n"));
  }
  if (footer) parts.push(footer);
  if (sources?.length) parts.push(`## 출처\n${sources.map((s) => `- ${s}`).join("\n")}`);
  return parts.join("\n\n");
}

/** 앱 안에서 보여 줄 개요 (그리고 한글 · 워드로 내보낼 때 쓰는 본문) */
export function deckMarkdown(deck: Deck): string {
  const parts = [`# ${deck.title}`];
  if (deck.subtitle) parts.push(deck.subtitle);
  deck.slides.forEach((s, i) => {
    parts.push(`## ${i + 1}. ${s.title}`);
    if (s.bullets.length) parts.push(s.bullets.map((b) => `- ${b}`).join("\n"));
    if (s.chart) {
      const c = s.chart;
      parts.push(`**${c.title || "차트"}**`);
      parts.push(table(["항목", ...c.series.map((x) => x.name)], c.labels.map((l, li) => [l, ...c.series.map((x) => x.values[li] ?? "")])));
    }
    if (s.table) parts.push(table(s.table.columns, s.table.rows));
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
