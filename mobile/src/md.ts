// 아주 작은 마크다운 → HTML (울트론이 만든 문서 보기용). 먼저 모든 글을 이스케이프하므로 HTML 은 끼어들 수 없다.

const esc = (s: string) => s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);

function inline(s: string): string {
  let h = esc(s);
  h = h.replace(/`([^`]+)`/g, "<code>$1</code>");
  h = h.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  h = h.replace(/(^|[^*])\*([^*\s][^*]*)\*/g, "$1<em>$2</em>");
  // 링크는 http(s) 만
  h = h.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, (_m, t, u) => `<a href="${u}" target="_blank" rel="noopener noreferrer">${t}</a>`);
  h = h.replace(/(^|\s)(https?:\/\/[^\s<]+)/g, (_m, p, u) => `${p}<a href="${u}" target="_blank" rel="noopener noreferrer">${u}</a>`);
  return h;
}

export function renderMarkdown(md: string): string {
  const lines = md.replace(/\r\n?/g, "\n").split("\n");
  const out: string[] = [];
  let list: "ul" | "ol" | null = null;
  let para: string[] = [];
  let i = 0;
  const flushPara = () => {
    if (para.length) out.push(`<p>${para.map(inline).join("<br>")}</p>`);
    para = [];
  };
  const closeList = () => {
    if (list) out.push(`</${list}>`);
    list = null;
  };
  while (i < lines.length) {
    const line = lines[i];
    const t = line.trim();
    if (t.startsWith("```")) {
      flushPara(); closeList();
      const code: string[] = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith("```")) code.push(lines[i++]);
      out.push(`<pre><code>${esc(code.join("\n"))}</code></pre>`);
      i++;
      continue;
    }
    if (/^\|.*\|$/.test(t) && i + 1 < lines.length && /^\|?\s*:?-{2,}/.test(lines[i + 1].trim())) {
      flushPara(); closeList();
      const cells = (r: string) => r.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
      const head = cells(t);
      i += 2;
      const rows: string[][] = [];
      while (i < lines.length && /^\|.*\|$/.test(lines[i].trim())) rows.push(cells(lines[i++]));
      out.push(
        `<div class="table"><table><thead><tr>${head.map((c) => `<th>${inline(c)}</th>`).join("")}</tr></thead><tbody>` +
          rows.map((r) => `<tr>${r.map((c) => `<td>${inline(c)}</td>`).join("")}</tr>`).join("") +
          `</tbody></table></div>`,
      );
      continue;
    }
    const h = t.match(/^(#{1,4})\s+(.*)$/);
    if (h) {
      flushPara(); closeList();
      const n = h[1].length;
      out.push(`<h${n}>${inline(h[2])}</h${n}>`);
    } else if (/^[-*•]\s+/.test(t)) {
      flushPara();
      if (list !== "ul") { closeList(); out.push("<ul>"); list = "ul"; }
      out.push(`<li>${inline(t.replace(/^[-*•]\s+/, ""))}</li>`);
    } else if (/^\d+[.)]\s+/.test(t)) {
      flushPara();
      if (list !== "ol") { closeList(); out.push("<ol>"); list = "ol"; }
      out.push(`<li>${inline(t.replace(/^\d+[.)]\s+/, ""))}</li>`);
    } else if (/^(-{3,}|\*{3,})$/.test(t)) {
      flushPara(); closeList();
      out.push("<hr>");
    } else if (t.startsWith(">")) {
      flushPara(); closeList();
      out.push(`<blockquote>${inline(t.replace(/^>\s?/, ""))}</blockquote>`);
    } else if (!t) {
      flushPara(); closeList();
    } else {
      closeList();
      para.push(t);
    }
    i++;
  }
  flushPara(); closeList();
  return out.join("\n");
}
