// 한글(HWPX) 파일 만들기
//
// HWPX 는 한컴오피스의 열린 문서 형식(OWPML, KS X 6101)으로, XML 파일들을 ZIP 으로 묶은 것이다.
// 바탕 틀(hwpx/ 폴더)은 python-hwpx(Apache-2.0)의 빈 문서 Skeleton.hwpx 에서 가져왔다 — hwpx/LICENSE-python-hwpx 참고.
// 그 틀의 글자 모양(charPr) · 문단 모양(paraPr) · 테두리(borderFill) 목록에 울트론 문서용 모양을 덧붙이고, 본문(section0)에 문단을 채운다.

import JSZip from "jszip";
import { parseBlocks, plain, type Block, type Run } from "./blocks";
import HEADER from "./hwpx/header.xml?raw";
import SECTION from "./hwpx/section0.xml?raw";
import CONTENT from "./hwpx/content.hpf?raw";
import CONTAINER from "./hwpx/container.xml?raw";
import CONTAINER_RDF from "./hwpx/container.rdf?raw";
import MANIFEST from "./hwpx/manifest.xml?raw";
import SETTINGS from "./hwpx/settings.xml?raw";
import VERSION from "./hwpx/version.xml?raw";

const esc = (s: string) =>
  s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!)
    // XML 1.0 에 넣을 수 없는 제어 문자
    .replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, "");

// ---------------------------------------------------------------- 글자 모양
interface CharSpec { size: number; bold?: boolean; italic?: boolean; gothic?: boolean; color?: string }

// 바탕 틀에 이미 0~6 번이 있으므로 7 번부터
const CHAR: Record<string, CharSpec> = {
  body: { size: 11 },
  bodyB: { size: 11, bold: true },
  bodyI: { size: 11, italic: true },
  bodyBI: { size: 11, bold: true, italic: true },
  title: { size: 20, bold: true, gothic: true },
  h1: { size: 16, bold: true, gothic: true },
  h2: { size: 13, bold: true, gothic: true, color: "#8E1B26" },
  h3: { size: 11.5, bold: true, gothic: true },
  quote: { size: 10.5, color: "#555555" },
  code: { size: 9.5, gothic: true, color: "#333333" },
  th: { size: 10, bold: true, gothic: true },
  td: { size: 10 },
  tdB: { size: 10, bold: true },
};
const CHAR_ID: Record<string, number> = {};
Object.keys(CHAR).forEach((k, i) => (CHAR_ID[k] = 7 + i));

function charPr(template: string, id: number, s: CharSpec): string {
  const font = s.gothic ? "0" : "1";   // 0 = 함초롬돋움, 1 = 함초롬바탕
  let x = template
    .replace(/ id="\d+"/, ` id="${id}"`)
    .replace(/height="\d+"/, `height="${Math.round(s.size * 100)}"`)
    .replace(/textColor="#[0-9A-Fa-f]{6}"/, `textColor="${s.color ?? "#000000"}"`)
    .replace(/<hh:fontRef [^>]*\/>/, `<hh:fontRef hangul="${font}" latin="${font}" hanja="${font}" japanese="${font}" other="${font}" symbol="${font}" user="${font}"/>`);
  // 스키마 순서: offset 다음에 italic, bold
  const marks = (s.italic ? "<hh:italic/>" : "") + (s.bold ? "<hh:bold/>" : "");
  if (marks) x = x.replace(/(<hh:offset [^>]*\/>)/, `$1${marks}`);
  return x;
}

// ---------------------------------------------------------------- 문단 모양
interface ParaSpec { align: "JUSTIFY" | "LEFT" | "CENTER"; left?: number; intent?: number; prev?: number; next?: number; line?: number; keepNext?: boolean }

const PARA: Record<string, ParaSpec> = {
  body: { align: "JUSTIFY", next: 600, line: 160 },
  title: { align: "CENTER", next: 1600, line: 130 },
  h1: { align: "LEFT", prev: 1800, next: 600, line: 130, keepNext: true },
  h2: { align: "LEFT", prev: 1200, next: 400, line: 130, keepNext: true },
  h3: { align: "LEFT", prev: 800, next: 300, line: 130, keepNext: true },
  list: { align: "LEFT", left: 1800, intent: -1100, next: 200, line: 150 },
  quote: { align: "LEFT", left: 1500, next: 400, line: 150 },
  code: { align: "LEFT", left: 800, next: 0, line: 130 },
  cell: { align: "LEFT", line: 130 },
};
const PARA_ID: Record<string, number> = {};
Object.keys(PARA).forEach((k, i) => (PARA_ID[k] = 20 + i));   // 바탕 틀에 0~19 번이 있다

function paraPr(template: string, id: number, s: ParaSpec): string {
  const v = (name: string) => new RegExp(`<hc:${name} value="-?\\d+" unit="HWPUNIT"/>`, "g");
  return template
    .replace(/ id="\d+"/, ` id="${id}"`)
    .replace(/<hh:align horizontal="\w+"/, `<hh:align horizontal="${s.align}"`)
    .replace(/keepWithNext="\d"/, `keepWithNext="${s.keepNext ? 1 : 0}"`)
    .replace(v("intent"), `<hc:intent value="${s.intent ?? 0}" unit="HWPUNIT"/>`)
    .replace(v("left"), `<hc:left value="${s.left ?? 0}" unit="HWPUNIT"/>`)
    .replace(v("prev"), `<hc:prev value="${s.prev ?? 0}" unit="HWPUNIT"/>`)
    .replace(v("next"), `<hc:next value="${s.next ?? 0}" unit="HWPUNIT"/>`)
    .replace(/<hh:lineSpacing type="PERCENT" value="\d+"/g, `<hh:lineSpacing type="PERCENT" value="${s.line ?? 160}"`);
}

// ---------------------------------------------------------------- 표 테두리
const BORDER_TABLE = 3;
const BORDER_HEAD = 4;
function borderFills(): string {
  const sides = ["left", "right", "top", "bottom"].map((s) => `<hh:${s}Border type="SOLID" width="0.12 mm" color="#7F7F7F"/>`).join("");
  const base = (id: number, fill: string) =>
    `<hh:borderFill id="${id}" threeD="0" shadow="0" centerLine="NONE" breakCellSeparateLine="0">` +
    `<hh:slash type="NONE" Crooked="0" isCounter="0"/><hh:backSlash type="NONE" Crooked="0" isCounter="0"/>${sides}` +
    `<hh:diagonal type="SOLID" width="0.1 mm" color="#000000"/>${fill}</hh:borderFill>`;
  return base(BORDER_TABLE, "") +
    base(BORDER_HEAD, `<hc:fillBrush><hc:winBrush faceColor="#F2E6E8" hatchColor="#999999" alpha="0"/></hc:fillBrush>`);
}

/** 바탕 틀의 header.xml 에 울트론 문서용 모양을 덧붙인다 */
export function buildHeader(): string {
  let h = HEADER;
  const char0 = h.match(/<hh:charPr id="0"[\s\S]*?<\/hh:charPr>/)![0];
  const para0 = h.match(/<hh:paraPr id="0"[\s\S]*?<\/hh:paraPr>/)![0];
  const chars = Object.entries(CHAR).map(([k, s]) => charPr(char0, CHAR_ID[k], s)).join("");
  const paras = Object.entries(PARA).map(([k, s]) => paraPr(para0, PARA_ID[k], s)).join("");
  const count = (tag: string) => Number(h.match(new RegExp(`<hh:${tag} itemCnt="(\\d+)"`))![1]);
  const nChar = count("charProperties"), nPara = count("paraProperties"), nBorder = count("borderFills");
  if (nChar !== 7 || nPara !== 20 || nBorder !== 2) throw new Error("HWPX 바탕 틀이 예상과 다르다");
  h = h
    .replace(`<hh:charProperties itemCnt="${nChar}">`, `<hh:charProperties itemCnt="${nChar + Object.keys(CHAR).length}">`)
    .replace("</hh:charProperties>", `${chars}</hh:charProperties>`)
    .replace(`<hh:paraProperties itemCnt="${nPara}">`, `<hh:paraProperties itemCnt="${nPara + Object.keys(PARA).length}">`)
    .replace("</hh:paraProperties>", `${paras}</hh:paraProperties>`)
    .replace(`<hh:borderFills itemCnt="${nBorder}">`, `<hh:borderFills itemCnt="${nBorder + 2}">`)
    .replace("</hh:borderFills>", `${borderFills()}</hh:borderFills>`);
  return h;
}

// ---------------------------------------------------------------- 본문
let nextId = 1;
const pid = () => nextId++;

function runXml(runs: Run[], base: "body" | "td"): string {
  if (!runs.length) return `<hp:run charPrIDRef="${CHAR_ID[base]}"><hp:t/></hp:run>`;
  return runs.map((r) => {
    const key = base === "td" ? (r.bold ? "tdB" : "td") : r.bold && r.italic ? "bodyBI" : r.bold ? "bodyB" : r.italic ? "bodyI" : "body";
    return `<hp:run charPrIDRef="${CHAR_ID[key]}"><hp:t>${esc(r.text)}</hp:t></hp:run>`;
  }).join("");
}

function para(paraKey: string, inner: string): string {
  return `<hp:p id="${pid()}" paraPrIDRef="${PARA_ID[paraKey]}" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">${inner}</hp:p>`;
}

const textRun = (charKey: string, text: string) =>
  `<hp:run charPrIDRef="${CHAR_ID[charKey]}">${text ? `<hp:t>${esc(text)}</hp:t>` : "<hp:t/>"}</hp:run>`;

function table(head: string[], rows: string[][]): string {
  const cols = Math.max(1, head.length);
  const width = 42520;   // A4 본문 폭 (바탕 틀의 여백 기준)
  const cw = Math.floor(width / cols);
  const all = [head, ...rows];
  const cell = (text: string, r: number, c: number) => {
    const header = r === 0;
    return `<hp:tc name="" header="${header ? 1 : 0}" hasMargin="0" protect="0" editable="0" dirty="0" borderFillIDRef="${header ? BORDER_HEAD : BORDER_TABLE}">` +
      `<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="CENTER" linkListIDRef="0" linkListNextIDRef="0" textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">` +
      para("cell", textRun(header ? "th" : "td", text)) +
      `</hp:subList><hp:cellAddr colAddr="${c}" rowAddr="${r}"/><hp:cellSpan colSpan="1" rowSpan="1"/>` +
      `<hp:cellSz width="${cw}" height="1000"/><hp:cellMargin left="510" right="510" top="141" bottom="141"/></hp:tc>`;
  };
  const trs = all.map((row, r) => `<hp:tr>${Array.from({ length: cols }, (_, c) => cell(row[c] ?? "", r, c)).join("")}</hp:tr>`).join("");
  const tbl =
    `<hp:tbl id="${pid()}" zOrder="0" numberingType="TABLE" textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" pageBreak="CELL" repeatHeader="1" rowCnt="${all.length}" colCnt="${cols}" cellSpacing="0" borderFillIDRef="${BORDER_TABLE}" noAdjust="0">` +
    `<hp:sz width="${cw * cols}" widthRelTo="ABSOLUTE" height="${1000 * all.length}" heightRelTo="ABSOLUTE" protect="0"/>` +
    `<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="COLUMN" vertAlign="TOP" horzAlign="LEFT" vertOffset="0" horzOffset="0"/>` +
    `<hp:outMargin left="0" right="0" top="0" bottom="0"/><hp:inMargin left="510" right="510" top="141" bottom="141"/>${trs}</hp:tbl>`;
  return para("body", `<hp:run charPrIDRef="${CHAR_ID.body}">${tbl}</hp:run>`);
}

function blockXml(b: Block): string {
  switch (b.type) {
    case "heading": return para(`h${b.level}`, textRun(`h${b.level}`, plain(b.runs)));
    case "para": return para("body", runXml(b.runs, "body"));
    case "bullet": return para("list", textRun("body", "•  ") + runXml(b.runs, "body"));
    case "number": return para("list", textRun("body", `${b.n}.  `) + runXml(b.runs, "body"));
    case "quote": return para("quote", textRun("quote", plain(b.runs)));
    case "code": return b.text.split("\n").map((l) => para("code", textRun("code", l))).join("");
    case "table": return table(b.head, b.rows);
    case "rule": return para("body", textRun("body", ""));
  }
}

export function buildSection(title: string, md: string): string {
  nextId = 1;
  const blocks = parseBlocks(md);
  // 본문 첫 줄이 제목과 같은 "# 제목" 이면 그것을 문서 제목으로 쓴다
  if (blocks[0]?.type === "heading" && blocks[0].level === 1 && plain(blocks[0].runs).trim() === title.trim()) blocks.shift();
  const body = para("title", textRun("title", title)) + blocks.map(blockXml).join("");
  // 바탕 틀의 첫 문단(쪽 설정이 들어 있음)은 그대로 두고 그 뒤에 붙인다
  return SECTION.replace("</hs:sec>", `${body}</hs:sec>`);
}

function contentHpf(title: string, now: Date): string {
  const iso = now.toISOString().replace(/\.\d{3}Z$/, "Z");
  return CONTENT
    .replace("<opf:title/>", `<opf:title>${esc(title)}</opf:title>`)
    .replaceAll("synthetic-fixture-author", "ULTRON")
    .replace(/(<opf:meta name="CreatedDate" content="text">)[^<]*/, `$1${iso}`)
    .replace(/(<opf:meta name="ModifiedDate" content="text">)[^<]*/, `$1${iso}`)
    .replace(/(<opf:meta name="date" content="text">)[^<]*/, `$1${esc(now.toLocaleString("ko-KR"))}`);
}

/** 제목과 마크다운 본문으로 .hwpx 파일을 만든다 */
export async function buildHwpx(title: string, md: string): Promise<Uint8Array> {
  const zip = new JSZip();
  // mimetype 은 맨 앞에, 압축하지 않고 (OCF 규칙)
  zip.file("mimetype", "application/hwp+zip", { compression: "STORE" });
  zip.file("version.xml", VERSION);
  zip.file("Contents/header.xml", buildHeader());
  zip.file("Contents/section0.xml", buildSection(title, md));
  zip.file("Preview/PrvText.txt", `${title}\r\n${md.replace(/[#*`>|]/g, "").slice(0, 1000)}`);
  zip.file("settings.xml", SETTINGS);
  zip.file("META-INF/container.rdf", CONTAINER_RDF);
  zip.file("Contents/content.hpf", contentHpf(title, new Date()));
  zip.file("META-INF/container.xml", CONTAINER);
  zip.file("META-INF/manifest.xml", MANIFEST);
  return zip.generateAsync({ type: "uint8array", compression: "DEFLATE", mimeType: "application/hwp+zip" });
}
