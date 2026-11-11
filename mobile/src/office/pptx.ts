// 발표 자료(PPTX) 만들기 — 파워포인트 · 구글 슬라이드 · 한컴오피스 한쇼에서 열린다
// 색 테마는 카드뉴스 · 포스터와 같은 12가지. 장마다 요점 · 차트(막대 · 꺾은선 · 원) · 표를 넣을 수 있다.

import PptxGenJS from "pptxgenjs";
import type { DeckSlide } from "../store";
import { theme } from "./design";

export interface Deck {
  title: string;
  subtitle?: string;
  style?: string;
  slides: DeckSlide[];
}

const FONT = "맑은 고딕";
const hex = (c: string) => c.replace("#", "");
const PALETTE = ["2F5BEA", "E5702F", "2E9D63", "E0527A", "7C4DFF", "0E9AA7", "FFC400", "8B705E"];

/** 글이 많을수록 글자를 줄인다 (옆에 차트 · 표가 있으면 더) */
function bodySize(bullets: string[], narrow: boolean): number {
  const chars = bullets.join("").length * (narrow ? 1.8 : 1);
  const n = bullets.length;
  if (chars > 420 || n > 8) return 14;
  if (chars > 300 || n > 6) return 16;
  if (chars > 180) return 18;
  if (chars > 110 || n > 4) return 22;
  return 26;
}

export async function buildPptx(deck: Deck): Promise<Uint8Array> {
  const t = theme(deck.style);
  const p = new PptxGenJS();
  p.layout = "LAYOUT_WIDE";   // 16:9, 13.33 x 7.5 인치
  p.title = deck.title;
  p.author = "ULTRON";
  const accentFirst = [hex(t.accent), ...PALETTE.filter((c) => c !== hex(t.accent))];

  // 표지: 강조색 바탕
  const cover = p.addSlide();
  cover.background = { color: hex(t.accent) };
  cover.addShape("ellipse", { x: 9.4, y: 3.6, w: 6.2, h: 6.2, fill: { color: hex(t.onAccent), transparency: 88 }, line: { type: "none" } });
  cover.addShape("ellipse", { x: 10.6, y: -1.6, w: 3.4, h: 3.4, fill: { color: hex(t.onAccent), transparency: 92 }, line: { type: "none" } });
  cover.addText(deck.title, { x: 0.9, y: 2.0, w: 10.8, h: 2.0, fontFace: FONT, fontSize: 44, bold: true, color: hex(t.onAccent), valign: "bottom", fit: "shrink" });
  cover.addShape("rect", { x: 0.95, y: 4.2, w: 1.0, h: 0.08, fill: { color: hex(t.onAccent) }, line: { type: "none" } });
  if (deck.subtitle) cover.addText(deck.subtitle, { x: 0.9, y: 4.45, w: 10.8, h: 0.9, fontFace: FONT, fontSize: 20, color: hex(t.onAccent), valign: "top" });

  deck.slides.forEach((s, i) => {
    const sl = p.addSlide();
    sl.background = { color: hex(t.bg) };
    sl.addShape("ellipse", { x: 11.6, y: -1.2, w: 2.8, h: 2.8, fill: { color: hex(t.surface) }, line: { type: "none" } });
    sl.addText(String(i + 1).padStart(2, "0"), { x: 0.6, y: 0.35, w: 1.2, h: 0.5, fontFace: FONT, fontSize: 20, bold: true, color: hex(t.accent) });
    sl.addText(s.title, { x: 0.6, y: 0.8, w: 11.4, h: 0.9, fontFace: FONT, fontSize: 30, bold: true, color: hex(t.title), valign: "middle", fit: "shrink" });
    sl.addShape("rect", { x: 0.62, y: 1.78, w: 0.8, h: 0.06, fill: { color: hex(t.accent) }, line: { type: "none" } });

    const visual = s.chart || s.table;
    const hasText = s.bullets.length > 0;
    const textBox = { x: 0.8, y: 2.1, w: visual ? 5.4 : 11.8, h: 4.8 };
    const visBox = hasText ? { x: 6.6, y: 2.0, w: 6.2, h: 4.9 } : { x: 0.8, y: 2.0, w: 11.8, h: 4.9 };
    if (hasText) {
      sl.addText(
        s.bullets.map((b) => ({ text: b, options: { bullet: { indent: 18 }, breakLine: true } })),
        { ...textBox, fontFace: FONT, fontSize: bodySize(s.bullets, !!visual), color: hex(t.text), valign: "top", paraSpaceAfter: 10, lineSpacingMultiple: 1.15, fit: "shrink" },
      );
    }
    if (s.chart) {
      const c = s.chart;
      const type = c.type === "line" ? p.ChartType.line : c.type === "pie" ? p.ChartType.doughnut : p.ChartType.bar;
      const data = c.series.map((ser) => ({ name: ser.name, labels: c.labels, values: ser.values }));
      sl.addChart(type, data, {
        ...visBox,
        chartColors: c.type === "pie" ? accentFirst.slice(0, c.labels.length) : accentFirst.slice(0, c.series.length),
        showLegend: c.series.length > 1 || c.type === "pie", legendPos: "b", legendFontFace: FONT, legendColor: hex(t.text),
        showTitle: !!c.title, title: c.title, titleFontFace: FONT, titleColor: hex(t.title), titleFontSize: 16,
        catAxisLabelFontFace: FONT, catAxisLabelColor: hex(t.text), valAxisLabelColor: hex(t.muted), valAxisLabelFontFace: FONT,
        valGridLine: { color: hex(t.soft), size: 0.5 }, catGridLine: { style: "none" },
        showValue: c.type !== "line", dataLabelColor: c.type === "pie" ? "FFFFFF" : hex(t.text), dataLabelFontSize: 11,
        showPercent: c.type === "pie", holeSize: 55, barGapWidthPct: 60, lineSize: 3, lineDataSymbolSize: 8,
      });
    } else if (s.table) {
      const head = s.table.columns.map((h) => ({ text: h, options: { bold: true, color: hex(t.onAccent), fill: { color: hex(t.accent) } } }));
      const rows = s.table.rows.map((r, ri) => s.table!.columns.map((_, ci) => ({
        text: String(r[ci] ?? ""), options: { color: hex(t.text), fill: { color: ri % 2 ? hex(t.surface) : hex(t.bg) } },
      })));
      const n = rows.length + 1;
      sl.addTable([head, ...rows], {
        x: visBox.x, y: visBox.y, w: visBox.w, rowH: Math.min(0.55, visBox.h / n), fontFace: FONT, fontSize: n > 10 ? 11 : n > 6 ? 13 : 15, border: { type: "solid", pt: 0.5, color: hex(t.soft) },
        valign: "middle", autoPage: false,
      });
    }
    sl.addText(`${i + 2}`, { x: 12.3, y: 6.95, w: 0.8, h: 0.4, fontFace: FONT, fontSize: 11, color: hex(t.muted), align: "right" });
    if (s.notes) sl.addNotes(s.notes);
  });

  const out = await p.write({ outputType: "uint8array" });
  return out as Uint8Array;
}
