"use strict";

/* ──────────────────────────────────────────────────────────────────────────
   markdown.js — Markdown → HTML donusturucu
   ────────────────────────────────────────────────────────────────────── */

B.esc = s => String(s).replace(/[&<>"']/g, c => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;" }[c]));

B.md = function(src) {
  const blocks = [];
  let s = String(src).replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => {
    blocks.push({ lang: lang || "", code });
    return "\u0000B" + (blocks.length - 1) + "\u0000";
  });

  s = B.esc(s);
  s = s.replace(/`([^`\n]+)`/g, (_, c) => '<code class="il">' + c + "</code>");
  s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  s = s.replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>");
  s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');

  /* tablo */
  s = s.replace(/((?:\|[^\n]+\|\n?){2,})/g, (block) => {
    const rows = block.trim().split("\n").filter(r => r.includes("|"));
    if (rows.length < 2) return block;
    const parse = r => r.replace(/^\||\|$/g, "").split("|").map(c => c.trim());
    const hdr = parse(rows[0]);
    const isSep = r => /^[\s|:-]+$/.test(r);
    const startIdx = isSep(rows[1]) ? 2 : 1;
    let html = "<table><thead><tr>" + hdr.map(h => "<th>" + h + "</th>").join("") + "</tr></thead><tbody>";
    for (let i = startIdx; i < rows.length; i++) {
      if (isSep(rows[i])) continue;
      const cells = parse(rows[i]);
      html += "<tr>" + cells.map(c => "<td>" + c + "</td>").join("") + "</tr>";
    }
    return html + "</tbody></table>";
  });

  const out = [];
  let list = null, para = [];
  const flushP = () => { if (para.length) { out.push("<p>" + para.join("<br>") + "</p>"); para = []; } };
  const flushL = () => { if (list) { out.push("</" + list + ">"); list = null; } };

  for (const raw of s.split("\n")) {
    const line = raw.trimEnd();
    if (/^\u0000B\d+\u0000$/.test(line.trim())) { flushP(); flushL(); out.push(line.trim()); continue; }
    if (!line.trim()) { flushP(); flushL(); continue; }
    let m;
    if ((m = line.match(/^(#{1,3})\s+(.*)$/))) {
      flushP(); flushL(); out.push("<h" + m[1].length + ">" + m[2] + "</h" + m[1].length + ">"); continue;
    }
    if (/^(-{3,}|_{3,})$/.test(line.trim())) { flushP(); flushL(); out.push("<hr>"); continue; }
    if ((m = line.match(/^\s*(?:&gt;|>)\s?(.*)$/))) {
      flushP(); flushL(); out.push("<blockquote>" + m[1] + "</blockquote>"); continue;
    }
    if ((m = line.match(/^\s*[-*•]\s+(.*)$/))) {
      flushP(); if (list !== "ul") { flushL(); out.push("<ul>"); list = "ul"; }
      out.push("<li>" + m[1] + "</li>"); continue;
    }
    if ((m = line.match(/^\s*\d+[.)]\s+(.*)$/))) {
      flushP(); if (list !== "ol") { flushL(); out.push("<ol>"); list = "ol"; }
      out.push("<li>" + m[1] + "</li>"); continue;
    }
    flushL(); para.push(line);
  }
  flushP(); flushL();

  return out.join("").replace(/\u0000B(\d+)\u0000/g, (_, i) => {
    const b = blocks[+i];
    return '<div class="code"><div class="codeh"><span>' + B.esc(b.lang || "kod") +
      '</span><button class="cpb" data-code="' + B.esc(b.code) + '">KOPYALA</button></div><pre>' +
      B.esc(b.code.replace(/\n$/, "")) + "</pre></div>";
  });
};
