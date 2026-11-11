// 워드(DOCX) 파일 만들기 — 구글 문서 · 한컴오피스 · MS 워드 어디서나 열린다

import {
  AlignmentType, BorderStyle, Document, HeadingLevel, Packer, Paragraph, ShadingType, Table, TableCell, TableRow, TextRun, WidthType,
} from "docx";
import { parseBlocks, plain, type Block, type Run } from "./blocks";

const FONT = "맑은 고딕";
const ACCENT = "8E1B26";

const runs = (rs: Run[], size?: number) =>
  rs.map((r) => new TextRun({ text: r.text, bold: r.bold, italics: r.italic, font: FONT, size }));

function table(head: string[], rows: string[][]): Table {
  const border = { style: BorderStyle.SINGLE, size: 4, color: "7F7F7F" };
  const borders = { top: border, bottom: border, left: border, right: border };
  const cell = (text: string, header: boolean) =>
    new TableCell({
      borders,
      shading: header ? { type: ShadingType.CLEAR, color: "auto", fill: "F2E6E8" } : undefined,
      children: [new Paragraph({ children: [new TextRun({ text, bold: header, font: FONT, size: 20 })] })],
    });
  return new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    rows: [
      new TableRow({ tableHeader: true, children: head.map((h) => cell(h, true)) }),
      ...rows.map((r) => new TableRow({ children: head.map((_, i) => cell(r[i] ?? "", false)) })),
    ],
  });
}

function block(b: Block): (Paragraph | Table)[] {
  switch (b.type) {
    case "heading": {
      const level = [HeadingLevel.HEADING_1, HeadingLevel.HEADING_2, HeadingLevel.HEADING_3][b.level - 1];
      const size = [32, 26, 23][b.level - 1];
      return [new Paragraph({
        heading: level, spacing: { before: [360, 240, 160][b.level - 1], after: 120 }, keepNext: true,
        children: [new TextRun({ text: plain(b.runs), bold: true, font: FONT, size, color: b.level === 2 ? ACCENT : undefined })],
      })];
    }
    case "para": return [new Paragraph({ spacing: { after: 120, line: 360 }, children: runs(b.runs, 22) })];
    case "bullet": return [new Paragraph({ bullet: { level: 0 }, spacing: { after: 60 }, children: runs(b.runs, 22) })];
    case "number": return [new Paragraph({ indent: { left: 360, hanging: 260 }, spacing: { after: 60 }, children: [new TextRun({ text: `${b.n}. `, font: FONT, size: 22 }), ...runs(b.runs, 22)] })];
    case "quote": return [new Paragraph({ indent: { left: 400 }, border: { left: { style: BorderStyle.SINGLE, size: 12, color: ACCENT, space: 8 } }, children: [new TextRun({ text: plain(b.runs), color: "555555", font: FONT, size: 21 })] })];
    case "code": return b.text.split("\n").map((l) => new Paragraph({ indent: { left: 240 }, children: [new TextRun({ text: l, font: "Consolas", size: 19 })] }));
    case "table": return [table(b.head, b.rows), new Paragraph({ text: "" })];
    case "rule": return [new Paragraph({ border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "BFBFBF", space: 1 } }, children: [] })];
  }
}

export async function buildDocx(title: string, md: string): Promise<Uint8Array> {
  const blocks = parseBlocks(md);
  if (blocks[0]?.type === "heading" && blocks[0].level === 1 && plain(blocks[0].runs).trim() === title.trim()) blocks.shift();
  const doc = new Document({
    creator: "ULTRON",
    title,
    styles: { default: { document: { run: { font: FONT, size: 22 } } } },
    sections: [{
      properties: { page: { margin: { top: 1440, bottom: 1440, left: 1300, right: 1300 } } },
      children: [
        new Paragraph({
          heading: HeadingLevel.TITLE, alignment: AlignmentType.CENTER, spacing: { after: 360 },
          children: [new TextRun({ text: title, bold: true, font: FONT, size: 40 })],
        }),
        ...blocks.flatMap(block),
      ],
    }],
  });
  const buf = await Packer.toArrayBuffer(doc);
  return new Uint8Array(buf);
}
