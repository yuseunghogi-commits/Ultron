// 카드뉴스 · 포스터를 그림(PNG)으로 바로 그린다 — PC 판 jarvis/design.py 를 캔버스로 옮김
//   카드뉴스: 1080×1080 정사각형 (표지 · 내용 · 마무리), 포스터: A4 세로 1240×1754
// 색 테마는 PC 판 발표 자료와 같은 11가지. 글은 상자에 맞게 크기를 줄이고 띄어쓰기 단위로 줄을 바꾼다.

export interface Theme { bg: string; surface: string; title: string; text: string; muted: string; accent: string; soft: string; onAccent: string }

const T = (bg: string, surface: string, title: string, text: string, muted: string, accent: string, soft: string, onAccent: string): Theme =>
  ({ bg: `#${bg}`, surface: `#${surface}`, title: `#${title}`, text: `#${text}`, muted: `#${muted}`, accent: `#${accent}`, soft: `#${soft}`, onAccent: `#${onAccent}` });

export const THEMES: Record<string, Theme> = {
  light: T("FFFFFF", "F3F5F9", "16213A", "2A3346", "6B7487", "2F5BEA", "C9D6FF", "FFFFFF"),
  dark: T("15171D", "20242D", "F4F5F7", "D9DDE5", "9199A8", "FF4D5E", "5A2A30", "FFFFFF"),
  navy: T("0E2240", "173156", "FFFFFF", "DCE5F2", "A6B6CE", "4FC3F7", "1E4372", "0E2240"),
  warm: T("FFF8F1", "FCEBDA", "3A2417", "4B3425", "8B705E", "E5702F", "F7CFAE", "FFFFFF"),
  green: T("F4FAF6", "E1F0E6", "16392A", "23402F", "5C786A", "2E9D63", "BFE3CD", "FFFFFF"),
  purple: T("FFFFFF", "F5F1FF", "24173F", "32284A", "756C8F", "7C4DFF", "DCCFFF", "FFFFFF"),
  teal: T("F7FCFC", "E3F4F4", "0E3B43", "1F4A52", "5F8087", "0E9AA7", "B9E6EA", "FFFFFF"),
  rose: T("FFF9FA", "FDEBEF", "43202B", "55323D", "8E6B75", "E0527A", "F9CBD8", "FFFFFF"),
  mono: T("FFFFFF", "F3F3F3", "111111", "2B2B2B", "767676", "FFC400", "FFE89A", "111111"),
  midnight: T("12122B", "1D1D42", "FFFFFF", "DAD9F0", "9C9BC2", "9D7BFF", "3A3470", "12122B"),
  forest: T("10231B", "1A3327", "F3FAF5", "D5E7DC", "93AD9F", "6FCF97", "254D3A", "10231B"),
  ultron: T("0B0204", "1E070C", "F1EEF0", "E2D8DA", "B9A9AD", "FF2D3F", "4A0E16", "FFFFFF"),
};
export const THEME_NAMES = Object.keys(THEMES);
export const theme = (name?: string): Theme => THEMES[(name ?? "light").toLowerCase()] ?? THEMES.light;

export interface CardnewsData { title: string; subtitle?: string; cards: { title: string; bullets: string[]; highlight?: string }[]; closing?: string; sources?: string[]; theme?: string }
export interface PosterData { title: string; subtitle?: string; highlight?: string; sections: { heading?: string; bullets: string[] }[]; footer?: string; sources?: string[]; theme?: string }

const FONT = `"Apple SD Gothic Neo", "Noto Sans KR", "Noto Sans CJK KR", "Malgun Gothic", "Nanum Gothic", sans-serif`;
const font = (weight: "bold" | "regular", size: number) => `${weight === "bold" ? 700 : 400} ${Math.round(size)}px ${FONT}`;

function mix(a: string, b: string, t: number): string {
  const p = (h: string) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const [x, y] = [p(a), p(b)];
  return `rgb(${x.map((v, i) => Math.round(v + (y[i] - v) * t)).join(",")})`;
}

type Ctx = CanvasRenderingContext2D;

// ---------------------------------------------------------------- 글 배치
/** 띄어쓰기 단위로 줄을 바꾼다. 한 낱말이 너무 길면 글자 단위로 끊는다. */
export function wrap(ctx: Ctx, text: string, width: number): string[] {
  const lines: string[] = [];
  for (const para of String(text).split("\n")) {
    let cur = "";
    for (const word of para.split(" ")) {
      const trial = cur ? `${cur} ${word}` : word;
      if (ctx.measureText(trial).width <= width) { cur = trial; continue; }
      if (cur) lines.push(cur);
      if (ctx.measureText(word).width <= width) { cur = word; continue; }
      cur = "";
      for (const ch of word) {
        if (ctx.measureText(cur + ch).width <= width) cur += ch;
        else { lines.push(cur); cur = ch; }
      }
    }
    lines.push(cur);
  }
  const out = lines.filter((l) => l.trim());
  return out.length ? out : [""];
}

/** 상자에 들어가는 가장 큰 글자. 가장 작게 해도 넘치면 남는 줄을 '…' 로 줄인다. */
export function fit(ctx: Ctx, text: string, weight: "bold" | "regular", width: number, height: number, big: number, small: number, gap = 1.25, maxLines = 999) {
  let size = big;
  let lines: string[];
  for (;;) {
    ctx.font = font(weight, size);
    lines = wrap(ctx, text, width);
    if ((lines.length * size * gap <= height && lines.length <= maxLines) || size <= small) break;
    size = Math.max(small, size * 0.92);
  }
  const keep = Math.max(1, Math.min(lines.length, Math.floor(height / (size * gap)), maxLines));
  if (keep < lines.length) {
    lines = lines.slice(0, keep);
    while (lines[keep - 1] && ctx.measureText(lines[keep - 1] + "…").width > width) lines[keep - 1] = lines[keep - 1].slice(0, -1);
    lines[keep - 1] += "…";
  }
  return { lines, size, weight };
}

function textBlock(ctx: Ctx, x: number, y: number, f: { lines: string[]; size: number; weight: "bold" | "regular" }, color: string, gap = 1.25, align: "left" | "center" = "left", width = 0): number {
  ctx.font = font(f.weight, f.size);
  ctx.fillStyle = color;
  ctx.textBaseline = "top";
  f.lines.forEach((line, i) => {
    const lx = align === "center" ? x + (width - ctx.measureText(line).width) / 2 : x;
    ctx.fillText(line, lx, y + i * f.size * gap);
  });
  return f.lines.length * f.size * gap;
}

function bullets(ctx: Ctx, box: [number, number, number, number], items: string[], th: Theme, big: number, small: number, gap = 1.42): void {
  const [x0, y0, x1, y1] = box;
  const list = items.map((s) => s.replace(/^\s*(?:[•·▪*]\s*|[-–]\s+)/, "")).filter((s) => s.trim());
  if (!list.length) return;
  let size = big;
  let blocks: string[][];
  for (;;) {
    ctx.font = font("regular", size);
    const indent = size * 1.15;
    blocks = list.map((it) => wrap(ctx, it, x1 - x0 - indent));
    const total = blocks.reduce((a, b) => a + b.length, 0) * size * gap + (list.length - 1) * size * 0.55;
    if (total <= y1 - y0 || size <= small) break;
    size = Math.max(small, size * 0.93);
  }
  ctx.font = font("regular", size);
  ctx.textBaseline = "top";
  let y = y0;
  for (const lines of blocks) {
    if (y + size * gap > y1 + 1) break;
    ctx.fillStyle = th.accent;
    ctx.beginPath();
    ctx.arc(x0 + size * 0.2, y + size * 0.62, size * 0.17, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = th.text;
    for (const line of lines) {
      if (y + size * gap > y1 + 1) break;
      ctx.fillText(line, x0 + size * 1.15, y + size * 0.12);
      y += size * gap;
    }
    y += size * 0.55;
  }
}

function domain(ref: string): string {
  const m = ref.match(/https?:\/\/\S+/);
  if (!m) return ref.slice(0, 60);
  try {
    const host = new URL(m[0]).host.replace(/^www\./, "");
    const head = ref.slice(0, m.index).trim().replace(/[—\-:|\s]+$/, "");
    return head ? `${head} (${host})` : host;
  } catch { return ref.slice(0, 60); }
}

function canvas(w: number, h: number, bg: string): [HTMLCanvasElement, Ctx] {
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  const ctx = c.getContext("2d")!;
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, w, h);
  return [c, ctx];
}

const circle = (ctx: Ctx, cx: number, cy: number, r: number, color: string) => {
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.arc(cx, cy, r, 0, Math.PI * 2);
  ctx.fill();
};

function roundRect(ctx: Ctx, x0: number, y0: number, x1: number, y1: number, r: number) {
  ctx.beginPath();
  ctx.roundRect(x0, y0, x1 - x0, y1 - y0, r);
}

// ---------------------------------------------------------------- 카드뉴스
const CARD = 1080;

function cover(th: Theme, title: string, tag: string, total: number): HTMLCanvasElement {
  const [c, ctx] = canvas(CARD, CARD, th.accent);
  circle(ctx, 1010, 950, 390, mix(th.accent, th.onAccent, 0.14));
  circle(ctx, 1000, 0, 240, mix(th.accent, th.onAccent, 0.08));
  if (tag) {
    ctx.font = font("bold", 30);
    const tw = ctx.measureText(tag).width;
    ctx.strokeStyle = th.onAccent;
    ctx.lineWidth = 3;
    roundRect(ctx, 90, 110, 90 + tw + 56, 170, 30);
    ctx.stroke();
    ctx.fillStyle = th.onAccent;
    ctx.textBaseline = "middle";
    ctx.fillText(tag, 118, 141);
  }
  const f = fit(ctx, title, "bold", 880, 470, 118, 62, 1.18, 4);
  const h = f.lines.length * f.size * 1.18;
  textBlock(ctx, 90, 300 + (470 - h) / 2, f, th.onAccent, 1.18);
  ctx.fillStyle = th.onAccent;
  ctx.fillRect(90, 880, 80, 8);
  ctx.font = font("regular", 28);
  ctx.fillStyle = mix(th.onAccent, th.accent, 0.25);
  ctx.textBaseline = "top";
  ctx.fillText("옆으로 넘겨 보세요  →", 90, 910);
  const page = `1 / ${total}`;
  ctx.fillText(page, 990 - ctx.measureText(page).width, 910);
  return c;
}

function card(th: Theme, n: number, total: number, title: string, items: string[], highlight: string, brand: string): HTMLCanvasElement {
  const [c, ctx] = canvas(CARD, CARD, th.bg);
  circle(ctx, 1060, 20, 180, th.surface);
  ctx.font = font("bold", 96);
  ctx.fillStyle = th.accent;
  ctx.textBaseline = "top";
  ctx.fillText(String(n).padStart(2, "0"), 90, 80);
  ctx.fillRect(90, 205, 70, 7);
  const f = fit(ctx, title, "bold", 900, 190, 70, 44, 1.2, 3);
  const used = textBlock(ctx, 90, 240, f, th.title, 1.2);
  const bottom = highlight ? 775 : 930;
  bullets(ctx, [92, 240 + used + 40, 990, bottom], items, th, 46, 28);
  if (highlight) {
    ctx.fillStyle = th.surface;
    roundRect(ctx, 90, 800, 990, 950, 24);
    ctx.fill();
    ctx.fillStyle = th.accent;
    ctx.fillRect(90, 800, 12, 150);
    const hf = fit(ctx, highlight, "bold", 820, 120, 40, 26, 1.25, 2);
    textBlock(ctx, 130, 800 + (150 - hf.lines.length * hf.size * 1.25) / 2, hf, th.title, 1.25);
  }
  ctx.font = font("regular", 26);
  ctx.fillStyle = th.muted;
  ctx.textBaseline = "top";
  const page = `${n + 1} / ${total}`;
  ctx.fillText(page, 990 - ctx.measureText(page).width, 985);
  if (brand) ctx.fillText(brand.slice(0, 40), 90, 985);
  return c;
}

function closing(th: Theme, message: string, lines: string[], refs: string[], total: number): HTMLCanvasElement {
  const [c, ctx] = canvas(CARD, CARD, th.surface);
  circle(ctx, 80, 980, 340, th.soft);
  const f = fit(ctx, message || "감사합니다", "bold", 900, 330, 96, 52, 1.2, 3);
  const h = f.lines.length * f.size * 1.2;
  const y = 270 + (330 - h) / 2;
  textBlock(ctx, 90, y, f, th.title, 1.2, "center", 900);
  if (lines.length) {
    const sf = fit(ctx, lines.join(" "), "regular", 860, 150, 38, 26, 1.35, 3);
    textBlock(ctx, 110, y + h + 40, sf, th.text, 1.35, "center", 860);
  }
  ctx.textBaseline = "top";
  if (refs.length) {
    ctx.font = font("bold", 22);
    ctx.fillStyle = th.muted;
    ctx.fillText("출처", 90, 850);
    ctx.font = font("regular", 21);
    refs.slice(0, 3).forEach((r, i) => ctx.fillText(domain(r).slice(0, 60), 90, 885 + i * 30));
  }
  ctx.font = font("regular", 26);
  ctx.fillStyle = th.muted;
  const page = `${total} / ${total}`;
  ctx.fillText(page, 990 - ctx.measureText(page).width, 985);
  return c;
}

export function renderCardnews(d: CardnewsData): HTMLCanvasElement[] {
  const th = theme(d.theme);
  const total = d.cards.length + 2;
  const out = [cover(th, d.title, d.subtitle ?? "", total)];
  d.cards.forEach((c, i) => out.push(card(th, i + 1, total, c.title, c.bullets, c.highlight ?? "", d.subtitle || d.title)));
  const [first, ...rest] = (d.closing?.trim() ? d.closing.split("\n") : ["감사합니다"]);
  out.push(closing(th, first, rest.filter((x) => x.trim()), d.sources ?? [], total));
  return out;
}

// ---------------------------------------------------------------- 포스터 (A4 세로, 150dpi)
export function renderPoster(d: PosterData): HTMLCanvasElement {
  const th = theme(d.theme);
  const W = 1240, H = 1754;
  const [c, ctx] = canvas(W, H, th.bg);
  const head = 620;
  ctx.fillStyle = th.accent;
  ctx.fillRect(0, 0, W, head);
  circle(ctx, 1170, 70, 310, mix(th.accent, th.onAccent, 0.12));
  circle(ctx, 1185, 475, 175, mix(th.accent, th.onAccent, 0.07));
  const tf = fit(ctx, d.title, "bold", 1040, 330, 128, 64, 1.15, 3);
  let block = tf.lines.length * tf.size * 1.15;
  const sf = d.subtitle ? fit(ctx, d.subtitle, "regular", 1040, 120, 42, 28, 1.3, 2) : null;
  if (sf) block += 26 + sf.lines.length * sf.size * 1.3;
  const room = head - (d.highlight ? 110 : 40) - 90;
  const top = 90 + Math.max(0, (room - block) / 2);
  const used = textBlock(ctx, 100, top, tf, th.onAccent, 1.15);
  if (sf) textBlock(ctx, 100, top + used + 26, sf, mix(th.onAccent, th.accent, 0.15), 1.3);
  let y = head + 50;
  if (d.highlight) {
    const hb = [100, head - 70, 1140, head + 110] as const;
    ctx.fillStyle = mix(th.bg, th.title, 0.1);
    roundRect(ctx, hb[0] + 8, hb[1] + 10, hb[2] + 8, hb[3] + 10, 28);
    ctx.fill();
    ctx.fillStyle = th.bg;
    roundRect(ctx, ...hb, 28);
    ctx.fill();
    ctx.strokeStyle = th.accent;
    ctx.lineWidth = 4;
    ctx.stroke();
    const hf = fit(ctx, d.highlight, "bold", 960, 140, 52, 30, 1.25, 2);
    textBlock(ctx, 140, hb[1] + (hb[3] - hb[1] - hf.lines.length * hf.size * 1.25) / 2, hf, th.accent, 1.25, "center", 960);
    y = hb[3] + 50;
  }
  const footTop = H - 150;
  const secs = d.sections.slice(0, 6);
  const cols = secs.length <= 2 ? 1 : 2;
  const rows = Math.max(1, Math.ceil(secs.length / cols));
  const gap = 34;
  const cw = (1040 - gap * (cols - 1)) / cols;
  const ch = secs.length ? (footTop - y - gap * (rows - 1)) / rows : 0;
  secs.forEach((sec, i) => {
    const r = Math.floor(i / cols), cc = i % cols;
    const x0 = 100 + cc * (cw + gap), y0 = y + r * (ch + gap);
    // 구역이 홀수면 마지막 구역은 한 줄을 다 쓴다
    const w = cols === 2 && i === secs.length - 1 && secs.length % 2 === 1 ? 1040 : cw;
    ctx.fillStyle = th.surface;
    roundRect(ctx, x0, y0, x0 + w, y0 + ch, 26);
    ctx.fill();
    ctx.fillStyle = th.accent;
    ctx.fillRect(x0 + 34, y0 + 34, 60, 7);
    let t = y0 + 60;
    if (sec.heading) {
      const hf = fit(ctx, sec.heading, "bold", w - 68, 120, 46, 30, 1.2, 2);
      t += textBlock(ctx, x0 + 34, t, hf, th.title, 1.2) + 18;
    }
    bullets(ctx, [x0 + 36, t, x0 + w - 34, y0 + ch - 30], sec.bullets, th, 36, 22);
  });
  ctx.fillStyle = th.soft;
  ctx.fillRect(100, footTop + 30, 1040, 3);
  ctx.textBaseline = "top";
  if (d.footer) {
    ctx.font = font("bold", 26);
    ctx.fillStyle = th.text;
    ctx.fillText(d.footer.slice(0, 60), 100, footTop + 55);
  }
  if (d.sources?.length) {
    const rf = fit(ctx, "출처: " + d.sources.slice(0, 3).map(domain).join(" · "), "regular", 1040, 60, 22, 18, 1.3, 2);
    textBlock(ctx, 100, footTop + 95, rf, th.muted, 1.3);
  }
  return c;
}

export function canvasPng(c: HTMLCanvasElement): Promise<Uint8Array> {
  return new Promise((resolve, reject) =>
    c.toBlob((b) => (b ? b.arrayBuffer().then((a) => resolve(new Uint8Array(a)), reject) : reject(new Error("PNG 실패"))), "image/png"),
  );
}
