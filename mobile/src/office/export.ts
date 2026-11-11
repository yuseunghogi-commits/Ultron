// 울트론이 만든 문서 · 발표 자료 · 표를 파일로 만든다.
// 파일 만드는 코드(docx · pptxgenjs 등)는 크기가 커서, 실제로 버튼을 눌렀을 때만 불러온다.

import type { Doc, ExportFormat } from "../store";
import { fileName } from "./blocks";

export const MIME: Record<Exclude<ExportFormat, "pdf">, string> = {
  hwpx: "application/hwp+zip",
  docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  pptx: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  csv: "text/csv",
};

export const FORMAT_LABEL: Record<ExportFormat, string> = {
  hwpx: "한글 파일",
  docx: "워드 파일",
  pptx: "PPT 파일",
  xlsx: "엑셀 파일",
  csv: "CSV",
  pdf: "PDF",
};

/** 문서 종류마다 만들 수 있는 파일 (앞의 것이 기본) */
export function formatsFor(doc: Doc): ExportFormat[] {
  switch (doc.kind ?? "doc") {
    case "slides": return ["pptx", "hwpx", "docx"];
    case "sheet": return ["xlsx", "csv", "hwpx", "docx"];
    default: return ["hwpx", "docx", "pdf"];
  }
}

export interface BuiltFile {
  name: string;
  mime: string;
  data: Uint8Array;
}

export async function buildFile(doc: Doc, format: Exclude<ExportFormat, "pdf">): Promise<BuiltFile> {
  const mime = MIME[format];
  switch (format) {
    case "hwpx": {
      const { buildHwpx } = await import("./hwpx");
      return { name: fileName(doc.title, "hwpx"), mime, data: await buildHwpx(doc.title, doc.content) };
    }
    case "docx": {
      const { buildDocx } = await import("./docx");
      return { name: fileName(doc.title, "docx"), mime, data: await buildDocx(doc.title, doc.content) };
    }
    case "pptx": {
      if (!doc.slides) throw new Error("발표 자료가 아니다");
      const { buildPptx } = await import("./pptx");
      const data = await buildPptx({ title: doc.title, subtitle: doc.subtitle, style: doc.style, slides: doc.slides });
      return { name: fileName(doc.title, "pptx"), mime, data };
    }
    case "xlsx": {
      if (!doc.sheets) throw new Error("표가 아니다");
      const { buildXlsx } = await import("./xlsx");
      return { name: fileName(doc.title, "xlsx"), mime, data: await buildXlsx(doc.sheets) };
    }
    case "csv": {
      if (!doc.sheets) throw new Error("표가 아니다");
      const { buildCsv } = await import("./xlsx");
      return { name: fileName(doc.title, "csv"), mime, data: buildCsv(doc.sheets[0]) };
    }
  }
}

/** 브라우저: 내려받기 */
export function downloadFile(f: BuiltFile): void {
  // File 로 만들면 이름이 함께 붙어 다녀서, download 속성을 무시하는 브라우저에서도 이름이 유지된다
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
}
