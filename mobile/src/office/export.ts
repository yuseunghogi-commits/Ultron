// 울트론이 만든 결과물을 파일로 만든다.
// 파일 만드는 코드(docx · pptxgenjs 등)는 크기가 커서, 실제로 쓸 때만 불러온다 (그리고 미리 데워 둘 수 있다).

import type { Doc, ExportFormat } from "../store";
import { fileName } from "./blocks";

type FileFormat = Exclude<ExportFormat, "pdf">;

export const MIME: Record<FileFormat, string> = {
  hwpx: "application/hwp+zip",
  docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  pptx: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  csv: "text/csv",
  png: "image/png",
};

export const FORMAT_LABEL: Record<ExportFormat, string> = {
  hwpx: "한글 파일",
  docx: "워드 파일",
  pptx: "PPT 파일",
  xlsx: "엑셀 파일",
  csv: "CSV",
  pdf: "PDF",
  png: "그림 저장",
};

/** 문서 종류마다 만들 수 있는 파일 (앞의 것이 기본) */
export function formatsFor(doc: Doc): ExportFormat[] {
  switch (doc.kind ?? "doc") {
    case "slides": return ["pptx", "hwpx", "docx"];
    case "sheet": return ["xlsx", "csv", "hwpx", "docx"];
    case "cardnews": return ["png", "hwpx", "docx"];
    case "poster": return ["png", "pdf"];
    default: return ["hwpx", "docx", "pdf"];
  }
}

export interface BuiltFile {
  name: string;
  mime: string;
  data: Uint8Array;
}

/** 그림 미리 보기 (카드뉴스 · 포스터) */
export async function renderImages(doc: Doc): Promise<HTMLCanvasElement[]> {
  const d = await import("./design");
  if (doc.kind === "cardnews" && doc.cards) {
    return d.renderCardnews({ title: doc.title, subtitle: doc.subtitle, cards: doc.cards, closing: doc.closing, sources: doc.sources, theme: doc.style });
  }
  if (doc.kind === "poster" && doc.sections) {
    return [d.renderPoster({ title: doc.title, subtitle: doc.subtitle, highlight: doc.highlight, sections: doc.sections, footer: doc.footer, sources: doc.sources, theme: doc.style })];
  }
  return [];
}

/** 파일 만들기. 카드뉴스는 장마다 그림 하나씩이라 여러 개가 나온다. */
export async function buildFiles(doc: Doc, format: FileFormat): Promise<BuiltFile[]> {
  const mime = MIME[format];
  switch (format) {
    case "hwpx": {
      const { buildHwpx } = await import("./hwpx");
      return [{ name: fileName(doc.title, "hwpx"), mime, data: await buildHwpx(doc.title, doc.content) }];
    }
    case "docx": {
      const { buildDocx } = await import("./docx");
      return [{ name: fileName(doc.title, "docx"), mime, data: await buildDocx(doc.title, doc.content) }];
    }
    case "pptx": {
      if (!doc.slides) throw new Error("발표 자료가 아니다");
      const { buildPptx } = await import("./pptx");
      const data = await buildPptx({ title: doc.title, subtitle: doc.subtitle, style: doc.style, slides: doc.slides });
      return [{ name: fileName(doc.title, "pptx"), mime, data }];
    }
    case "xlsx": {
      if (!doc.sheets) throw new Error("표가 아니다");
      const { buildXlsx } = await import("./xlsx");
      return [{ name: fileName(doc.title, "xlsx"), mime, data: await buildXlsx(doc.sheets) }];
    }
    case "csv": {
      if (!doc.sheets) throw new Error("표가 아니다");
      const { buildCsv } = await import("./xlsx");
      return [{ name: fileName(doc.title, "csv"), mime, data: buildCsv(doc.sheets[0]) }];
    }
    case "png": {
      const { canvasPng } = await import("./design");
      const imgs = await renderImages(doc);
      if (!imgs.length) throw new Error("그림이 없다");
      const base = fileName(doc.title, "png").replace(/\.png$/, "");
      return Promise.all(imgs.map(async (c, i) => ({
        name: imgs.length > 1 ? `${base} ${String(i + 1).padStart(2, "0")}.png` : `${base}.png`,
        mime, data: await canvasPng(c),
      })));
    }
  }
}

/** 버튼을 누르기 전에 그 형식의 코드를 미리 불러 둔다 (누르면 바로 만들어지게) */
export function warm(kind: Doc["kind"]): void {
  const load = (p: Promise<unknown>) => void p.catch(() => {});
  switch (kind ?? "doc") {
    case "slides": load(import("./pptx")); break;
    case "sheet": load(import("./xlsx")); break;
    case "cardnews": case "poster": load(import("./design")); break;
    default: load(import("./hwpx")); load(import("./docx"));
  }
}

/** 브라우저: 내려받기 (여러 개면 ZIP 하나로 묶는다 — 브라우저가 연달아 받기를 막기 때문) */
export async function downloadFiles(files: BuiltFile[], zipName: string): Promise<string> {
  let f = files[0];
  if (files.length > 1) {
    const { default: JSZip } = await import("jszip");
    const zip = new JSZip();
    for (const x of files) zip.file(x.name, x.data);
    f = { name: zipName, mime: "application/zip", data: await zip.generateAsync({ type: "uint8array" }) };
  }
  // File 로 만들면 이름이 함께 붙어 다닌다
  const file = new File([f.data as BlobPart], f.name, { type: f.mime });
  const url = URL.createObjectURL(file);
  const a = document.createElement("a");
  a.href = url;
  a.download = f.name;
  a.rel = "noopener";
  a.style.display = "none";
  document.body.appendChild(a);
  a.click();
  setTimeout(() => { a.remove(); URL.revokeObjectURL(url); }, 30_000);
  return f.name;
}
