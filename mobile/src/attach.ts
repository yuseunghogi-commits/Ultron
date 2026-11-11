// 사진 · PDF 첨부: 울트론에게 보여 주고 일을 시킨다 ("이 사진 표로 정리해", "이 PDF 요약해서 PPT 로")
// 사진은 Claude 가 읽기 좋은 크기(긴 변 1568px)로 줄여 보낸다 — 크면 느리고 비싸기만 하다.

export interface Attachment {
  kind: "image" | "pdf";
  name: string;
  mediaType: "image/jpeg" | "image/png" | "image/webp" | "image/gif" | "application/pdf";
  data: string;        // base64
  preview?: string;    // 사진 미리 보기 (data URL)
}

const MAX_SIDE = 1568;
const MAX_PDF = 20 * 1024 * 1024;

function b64(buf: ArrayBuffer): string {
  const bytes = new Uint8Array(buf);
  let s = "";
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(s);
}

async function shrinkImage(file: File): Promise<{ data: string; mediaType: Attachment["mediaType"]; preview: string }> {
  const bmp = await createImageBitmap(file);
  const k = Math.min(1, MAX_SIDE / Math.max(bmp.width, bmp.height));
  const w = Math.max(1, Math.round(bmp.width * k));
  const h = Math.max(1, Math.round(bmp.height * k));
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  const ctx = c.getContext("2d")!;
  ctx.fillStyle = "#fff";   // 투명한 PNG 는 흰 바탕으로
  ctx.fillRect(0, 0, w, h);
  ctx.drawImage(bmp, 0, 0, w, h);
  bmp.close?.();
  const url = c.toDataURL("image/jpeg", 0.85);
  return { data: url.slice(url.indexOf(",") + 1), mediaType: "image/jpeg", preview: url };
}

export async function readAttachment(file: File): Promise<Attachment> {
  if (file.type === "application/pdf" || /\.pdf$/i.test(file.name)) {
    if (file.size > MAX_PDF) throw new Error("PDF 가 너무 크다 (20MB 이하)");
    return { kind: "pdf", name: file.name, mediaType: "application/pdf", data: b64(await file.arrayBuffer()) };
  }
  if (file.type.startsWith("image/")) {
    const r = await shrinkImage(file);
    return { kind: "image", name: file.name, ...r };
  }
  throw new Error("사진이나 PDF 만 보낼 수 있다");
}

/** Claude 에게 보낼 내용 블록 */
export function attachmentBlocks(list: Attachment[]): unknown[] {
  return list.map((a) =>
    a.kind === "pdf"
      ? { type: "document", source: { type: "base64", media_type: a.mediaType, data: a.data }, title: a.name }
      : { type: "image", source: { type: "base64", media_type: a.mediaType, data: a.data } });
}
