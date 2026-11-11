// 발표 자료(PPTX) 만들기 — 파워포인트 · 구글 슬라이드 · 한컴오피스 한쇼에서 열린다

import PptxGenJS from "pptxgenjs";

export interface Slide {
  title: string;
  bullets: string[];
  notes?: string;
}

export interface Deck {
  title: string;
  subtitle?: string;
  style?: "light" | "dark";
  slides: Slide[];
}

const FONT = "맑은 고딕";
const THEMES = {
  light: { bg: "FFFFFF", text: "1F1F1F", sub: "666666", accent: "C8141F", band: "F6E9EA" },
  dark: { bg: "0B0204", text: "F1EEF0", sub: "B9A9AD", accent: "FF2D3F", band: "1E070C" },
};

/** 글이 많을수록 글자를 줄인다 */
function bodySize(bullets: string[]): number {
  const chars = bullets.join("").length;
  const n = bullets.length;
  if (chars > 420 || n > 8) return 14;
  if (chars > 300 || n > 6) return 16;
  if (chars > 180) return 18;
  if (chars > 110 || n > 4) return 22;
  return 26;
}

export async function buildPptx(deck: Deck): Promise<Uint8Array> {
  const t = THEMES[deck.style ?? "light"];
  const p = new PptxGenJS();
  p.layout = "LAYOUT_WIDE";   // 16:9, 13.33 x 7.5 인치
  p.title = deck.title;
  p.author = "ULTRON";

  // 표지
  const cover = p.addSlide();
  cover.background = { color: t.bg };
  cover.addShape("rect", { x: 0, y: 0, w: 0.28, h: 7.5, fill: { color: t.accent }, line: { color: t.accent } });
  cover.addText(deck.title, { x: 0.9, y: 2.3, w: 11.6, h: 1.6, fontFace: FONT, fontSize: 40, bold: true, color: t.text, valign: "bottom", fit: "shrink" });
  cover.addShape("line", { x: 0.95, y: 4.05, w: 2.2, h: 0, line: { color: t.accent, width: 3 } });
  if (deck.subtitle) cover.addText(deck.subtitle, { x: 0.9, y: 4.25, w: 11.6, h: 0.9, fontFace: FONT, fontSize: 20, color: t.sub, valign: "top" });

  deck.slides.forEach((s, i) => {
    const sl = p.addSlide();
    sl.background = { color: t.bg };
    sl.addShape("rect", { x: 0, y: 0, w: 13.33, h: 1.25, fill: { color: t.band }, line: { color: t.band } });
    sl.addShape("rect", { x: 0, y: 0, w: 0.18, h: 1.25, fill: { color: t.accent }, line: { color: t.accent } });
    sl.addText(s.title, { x: 0.6, y: 0.15, w: 12.1, h: 0.95, fontFace: FONT, fontSize: 28, bold: true, color: t.text, valign: "middle", fit: "shrink" });
    if (s.bullets.length) {
      sl.addText(
        s.bullets.map((b) => ({ text: b, options: { bullet: { indent: 18 }, breakLine: true } })),
        { x: 0.8, y: 1.6, w: 11.8, h: 5.3, fontFace: FONT, fontSize: bodySize(s.bullets), color: t.text, valign: "top", paraSpaceAfter: 10, lineSpacingMultiple: 1.15, fit: "shrink" },
      );
    }
    sl.addText(`${i + 2}`, { x: 12.3, y: 6.95, w: 0.8, h: 0.4, fontFace: FONT, fontSize: 11, color: t.sub, align: "right" });
    if (s.notes) sl.addNotes(s.notes);
  });

  const out = await p.write({ outputType: "uint8array" });
  return out as Uint8Array;
}
