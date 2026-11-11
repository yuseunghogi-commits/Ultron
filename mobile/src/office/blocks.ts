// 울트론이 쓴 마크다운을 파일 형식과 상관없는 "블록"으로 나눈다 (한글 · 워드 내보내기가 같이 쓴다)

export interface Run {
  text: string;
  bold?: boolean;
  italic?: boolean;
}

export type Block =
  | { type: "heading"; level: 1 | 2 | 3; runs: Run[] }
  | { type: "para"; runs: Run[] }
  | { type: "bullet"; runs: Run[] }
  | { type: "number"; n: number; runs: Run[] }
  | { type: "quote"; runs: Run[] }
  | { type: "code"; text: string }
  | { type: "table"; head: string[]; rows: string[][] }
  | { type: "rule" };

/** **굵게** · *기울임* · `코드` · [글](주소) 를 글 조각으로 */
export function parseRuns(src: string): Run[] {
  const runs: Run[] = [];
  const re = /\*\*([^*]+)\*\*|\*([^*\s][^*]*)\*|`([^`]+)`|\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g;
  let last = 0;
  for (const m of src.matchAll(re)) {
    if (m.index! > last) runs.push({ text: src.slice(last, m.index) });
    if (m[1] !== undefined) runs.push({ text: m[1], bold: true });
    else if (m[2] !== undefined) runs.push({ text: m[2], italic: true });
    else if (m[3] !== undefined) runs.push({ text: m[3] });
    else runs.push({ text: `${m[4]} (${m[5]})` });
    last = m.index! + m[0].length;
  }
  if (last < src.length) runs.push({ text: src.slice(last) });
  return runs.filter((r) => r.text.length > 0);
}

export const plain = (runs: Run[]) => runs.map((r) => r.text).join("");

function cells(row: string): string[] {
  return row.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim().replace(/\*\*([^*]+)\*\*/g, "$1"));
}

export function parseBlocks(md: string): Block[] {
  const lines = md.replace(/\r\n?/g, "\n").split("\n");
  const out: Block[] = [];
  let para: string[] = [];
  const flush = () => {
    if (para.length) out.push({ type: "para", runs: parseRuns(para.join(" ")) });
    para = [];
  };
  for (let i = 0; i < lines.length; i++) {
    const t = lines[i].trim();
    if (t.startsWith("```")) {
      flush();
      const code: string[] = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith("```")) code.push(lines[i++]);
      out.push({ type: "code", text: code.join("\n") });
      continue;
    }
    if (/^\|.*\|$/.test(t) && i + 1 < lines.length && /^\|?\s*:?-{2,}/.test(lines[i + 1].trim())) {
      flush();
      const head = cells(t);
      i += 2;
      const rows: string[][] = [];
      while (i < lines.length && /^\|.*\|$/.test(lines[i].trim())) {
        const r = cells(lines[i++]);
        while (r.length < head.length) r.push("");
        rows.push(r.slice(0, head.length));
      }
      i--;
      out.push({ type: "table", head, rows });
      continue;
    }
    let m: RegExpMatchArray | null;
    if ((m = t.match(/^(#{1,6})\s+(.*)$/))) {
      flush();
      out.push({ type: "heading", level: Math.min(3, m[1].length) as 1 | 2 | 3, runs: parseRuns(m[2]) });
    } else if ((m = t.match(/^[-*•]\s+(.*)$/))) {
      flush();
      out.push({ type: "bullet", runs: parseRuns(m[1]) });
    } else if ((m = t.match(/^(\d+)[.)]\s+(.*)$/))) {
      flush();
      out.push({ type: "number", n: Number(m[1]), runs: parseRuns(m[2]) });
    } else if (/^(-{3,}|\*{3,})$/.test(t)) {
      flush();
      out.push({ type: "rule" });
    } else if (t.startsWith(">")) {
      flush();
      out.push({ type: "quote", runs: parseRuns(t.replace(/^>\s?/, "")) });
    } else if (!t) {
      flush();
    } else {
      para.push(t);
    }
  }
  flush();
  return out;
}

/** 파일 이름으로 쓸 수 없는 글자를 걷어 낸다 */
export function fileName(title: string, ext: string): string {
  const base = title.replace(/[\\/:*?"<>|\n\r\t]+/g, " ").replace(/\s+/g, " ").trim().slice(0, 60) || "울트론 문서";
  return `${base}.${ext}`;
}
