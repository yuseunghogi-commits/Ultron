// 표(XLSX) 만들기 — 엑셀 · 구글 스프레드시트 · 한컴오피스 한셀에서 열린다
// 글자는 셀 안에 바로 넣는(inlineStr) 가장 단순한 형식으로 직접 쓴다.

import JSZip from "jszip";

export type Cell = string | number;

export interface Sheet {
  name: string;
  columns: string[];
  rows: Cell[][];
}

const esc = (s: string) =>
  s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!)
    .replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, "");

/** 0 → A, 25 → Z, 26 → AA */
export function colName(i: number): string {
  let s = "";
  for (let n = i + 1; n > 0; n = Math.floor((n - 1) / 26)) s = String.fromCharCode(65 + ((n - 1) % 26)) + s;
  return s;
}

/** 시트 이름: 31자 이하, []:*?/\ 금지, 겹치지 않게 */
export function sheetNames(sheets: Sheet[]): string[] {
  const used = new Set<string>();
  return sheets.map((s, i) => {
    let base = (s.name || `시트${i + 1}`).replace(/[[\]:*?/\\]/g, " ").trim().slice(0, 31) || `시트${i + 1}`;
    let name = base;
    for (let k = 2; used.has(name.toLowerCase()); k++) name = `${base.slice(0, 28)} ${k}`;
    used.add(name.toLowerCase());
    return name;
  });
}

/** "1,234" · "12.5%" 처럼 숫자로 보이는 글은 숫자로 넣어야 엑셀에서 계산된다 */
function asNumber(v: Cell): number | null {
  if (typeof v === "number") return Number.isFinite(v) ? v : null;
  const t = v.trim();
  if (!/^-?[\d,]*\.?\d+$/.test(t) || /^0\d/.test(t)) return null;   // 전화번호 · 우편번호처럼 0 으로 시작하면 글자로 둔다
  const n = Number(t.replace(/,/g, ""));
  return Number.isFinite(n) ? n : null;
}

function cellXml(v: Cell, r: number, c: number, style: number): string {
  const ref = `${colName(c)}${r + 1}`;
  const n = asNumber(v);
  if (n !== null) return `<c r="${ref}" s="${style}"><v>${n}</v></c>`;
  const text = String(v ?? "");
  if (!text) return `<c r="${ref}" s="${style}"/>`;
  return `<c r="${ref}" s="${style}" t="inlineStr"><is><t xml:space="preserve">${esc(text)}</t></is></c>`;
}

function sheetXml(s: Sheet): string {
  const all: Cell[][] = [s.columns, ...s.rows];
  const cols = Math.max(1, s.columns.length, ...s.rows.map((r) => r.length));
  // 열 너비: 가장 긴 글 기준 (한글은 2칸으로 셈)
  const widths = Array.from({ length: cols }, (_, c) => {
    const len = Math.max(...all.map((r) => [...String(r[c] ?? "")].reduce((a, ch) => a + (/[ㄱ-힝]/.test(ch) ? 2 : 1), 0)));
    return Math.min(60, Math.max(8, len + 2));
  });
  const colsXml = `<cols>${widths.map((w, i) => `<col min="${i + 1}" max="${i + 1}" width="${w}" customWidth="1"/>`).join("")}</cols>`;
  const rowsXml = all.map((row, r) =>
    `<row r="${r + 1}">${Array.from({ length: cols }, (_, c) => cellXml(row[c] ?? "", r, c, r === 0 ? 1 : 0)).join("")}</row>`,
  ).join("");
  const last = `${colName(cols - 1)}${all.length}`;
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
    `<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">` +
    `<dimension ref="A1:${last}"/>` +
    `<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>` +
    `<sheetFormatPr defaultRowHeight="16.5"/>${colsXml}<sheetData>${rowsXml}</sheetData>` +
    `<autoFilter ref="A1:${last}"/>` +
    `</worksheet>`;
}

const STYLES = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="2"><font><sz val="11"/><name val="맑은 고딕"/><family val="3"/><charset val="129"/></font><font><b/><sz val="11"/><name val="맑은 고딕"/><family val="3"/><charset val="129"/></font></fonts>
<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FFF2E6E8"/><bgColor indexed="64"/></patternFill></fill></fills>
<borders count="2"><border><left/><right/><top/><bottom/><diagonal/></border><border><left style="thin"><color rgb="FFBFBFBF"/></left><right style="thin"><color rgb="FFBFBFBF"/></right><top style="thin"><color rgb="FFBFBFBF"/></top><bottom style="thin"><color rgb="FFBFBFBF"/></bottom><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1"/><xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"/></cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>`;

export async function buildXlsx(sheets: Sheet[]): Promise<Uint8Array> {
  const names = sheetNames(sheets);
  const zip = new JSZip();
  zip.file("[Content_Types].xml",
    `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">` +
    `<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>` +
    `<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>` +
    `<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>` +
    sheets.map((_, i) => `<Override PartName="/xl/worksheets/sheet${i + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>`).join("") +
    `</Types>`);
  zip.file("_rels/.rels",
    `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">` +
    `<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>`);
  zip.file("xl/workbook.xml",
    `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>` +
    names.map((n, i) => `<sheet name="${esc(n)}" sheetId="${i + 1}" r:id="rId${i + 1}"/>`).join("") +
    `</sheets>` +
    `</workbook>`);
  zip.file("xl/_rels/workbook.xml.rels",
    `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">` +
    sheets.map((_, i) => `<Relationship Id="rId${i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet${i + 1}.xml"/>`).join("") +
    `<Relationship Id="rId${sheets.length + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>`);
  zip.file("xl/styles.xml", STYLES);
  sheets.forEach((s, i) => zip.file(`xl/worksheets/sheet${i + 1}.xml`, sheetXml(s)));
  return zip.generateAsync({ type: "uint8array", compression: "DEFLATE", mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
}

/** CSV (엑셀에서 한글이 깨지지 않게 BOM 을 붙인다) */
export function buildCsv(sheet: Sheet): Uint8Array {
  const q = (v: Cell) => {
    const s = String(v ?? "");
    return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const text = [sheet.columns, ...sheet.rows].map((r) => r.map(q).join(",")).join("\r\n");
  return new TextEncoder().encode("﻿" + text);
}
