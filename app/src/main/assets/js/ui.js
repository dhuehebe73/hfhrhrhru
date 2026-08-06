"use strict";

/* ──────────────────────────────────────────────────────────────────────────
   ui.js — Arayuz islemleri
   ────────────────────────────────────────────────────────────────────── */

const $ = s => document.querySelector(s);
const $$ = s => document.querySelectorAll(s);

B.toast = function(msg) {
  const t = $("#toast");
  t.textContent = msg; t.classList.add("on");
  clearTimeout(B._toastT);
  B._toastT = setTimeout(() => t.classList.remove("on"), 2200);
};

B.copy = function(text) {
  const done = () => B.toast("Kopyalandı");
  if (navigator.clipboard) navigator.clipboard.writeText(text).then(done).catch(() => fallback());
  else fallback();
  function fallback() {
    const ta = document.createElement("textarea");
    ta.value = text; ta.style.cssText = "position:fixed;opacity:0";
    document.body.appendChild(ta); ta.select();
    try { document.execCommand("copy"); done(); } catch { B.toast("Kopyalanamadı"); }
    ta.remove();
  }
};

function when(ts) {
  const d = new Date(ts), now = new Date(), diff = now - d;
  if (diff < 864e5 && d.getDate() === now.getDate())
    return d.toLocaleTimeString("tr", { hour: "2-digit", minute: "2-digit" });
  if (diff < 6048e5) return ["Paz","Pzt","Sal","Çar","Per","Cum","Cmt"][d.getDay()];
  return d.toLocaleDateString("tr", { day: "numeric", month: "short" });
}

B.ui = {
  stick: true,

  /* ── Sohbet gorunumu ─────────────────────────────────────────── */
  render() {
    const c = B.chat();
    const thread = $("#thread");
    if (!c || !c.messages.length) { B.ui.renderEmpty(); return; }
    thread.innerHTML = "";
    c.messages.forEach(m => thread.appendChild(B.ui.msgNode(m)));
    B.ui.bindCopies();
    B.ui.toBottom(true);
  },

  renderEmpty() {
    const thread = $("#thread");
    thread.innerHTML =
      '<div class="empty"><div class="mark">B</div><h2>Baron AI</h2>' +
      '<p>Soru sor, dosya yükle, paralel modeli aç — gerisini Baron halleder.</p>' +
      '<div class="chips">' +
      ['Bir konuyu sıfırdan açıkla', 'Bu kodu incele ve iyileştir', 'Paralel modda tüm modelleri karşılaştır']
        .map(s => '<button data-s="' + B.esc(s) + '">' + B.esc(s) + '</button>').join("") +
      '</div></div>';
    thread.querySelectorAll(".chips button").forEach(b =>
      b.onclick = () => { $("#input").value = b.dataset.s; B.ui.grow(); B.app.send(); });
  },

  msgNode(m) {
    const el = document.createElement("div");
    el.className = "msg " + m.role;

    if (m.role === "user") {
      let html = '<div class="bubble">' + B.esc(m.content) + '</div>';
      if (m.files && m.files.length) {
        html += '<div class="flist">' + m.files.map(f =>
          '<span class="ftag">📎 ' + B.esc(f.name) + ' <small>' + B.fmtSize(f.size) + '</small></span>'
        ).join("") + '</div>';
      }
      el.innerHTML = html;
    } else if (m.role === "parallel") {
      el.innerHTML = B.ui.parallelView(m);
    } else {
      el.innerHTML = B.ui.aiMsgHtml(m);
      B.ui.bindMsgActions(el, m);
    }
    return el;
  },

  aiMsgHtml(m) {
    const thinkHtml = m.thinking
      ? '<details class="think"><summary>✳ Düşünce</summary><div class="inner">' + B.esc(m.thinking) + '</div></details>'
      : '';
    const bodyHtml = m.error
      ? '<div class="err">' + B.esc(m.error) + '</div>'
      : '<div class="body">' + B.md(m.content || "") + '</div>';
    const provTag = m.provider ? '<span class="ptag">' + B.esc(m.provider) + '</span>' : '';
    const elapsed = m.elapsed ? '<span class="etime">' + (m.elapsed / 1000).toFixed(1) + 's</span>' : '';
    return provTag + thinkHtml + bodyHtml +
      '<div class="acts">' + elapsed +
      '<button data-a="copy">Kopyala</button><button data-a="again">Yeniden</button></div>';
  },

  parallelView(m) {
    if (!m.results) return '<div class="err">Sonuç yok</div>';
    const names = Object.keys(m.results);
    let html = '<div class="ptabs">';
    html += names.map((n, i) => '<button class="ptab' + (i === 0 ? ' on' : '') + '" data-prov="' + B.esc(n) + '">' + B.esc(n) + '</button>').join("");
    html += '</div>';
    html += names.map((n, i) => {
      const r = m.results[n];
      const content = r.error ? '<div class="err">' + B.esc(r.error) + '</div>' :
        (r.thinking ? '<details class="think"><summary>✳ Düşünce</summary><div class="inner">' + B.esc(r.thinking) + '</div></details>' : '') +
        '<div class="body">' + B.md(r.content || "(boş)") + '</div>';
      const elapsed = r.elapsed ? '<span class="etime">' + (r.elapsed / 1000).toFixed(1) + 's</span>' : '';
      return '<div class="ppane' + (i === 0 ? '' : ' hidden') + '" data-prov="' + B.esc(n) + '">' +
        content + '<div class="acts">' + elapsed +
        '<button class="cpb" data-code="' + B.esc(r.content || r.error || "") + '">Kopyala</button></div></div>';
    }).join("");
    return html;
  },

  bindMsgActions(el, m) {
    const copyBtn = el.querySelector('[data-a="copy"]');
    if (copyBtn) copyBtn.onclick = () => B.copy(m.content || m.error || "");
    const againBtn = el.querySelector('[data-a="again"]');
    if (againBtn) againBtn.onclick = () => B.app.regenerate(m);
  },

  bindCopies() {
    $$("#thread .cpb").forEach(b => {
      b.onclick = () => B.copy(b.dataset.code);
    });
    /* Paralel tab degistirme */
    $$("#thread .ptab").forEach(tab => {
      tab.onclick = () => {
        const parent = tab.closest(".msg");
        parent.querySelectorAll(".ptab").forEach(t => t.classList.remove("on"));
        parent.querySelectorAll(".ppane").forEach(p => p.classList.add("hidden"));
        tab.classList.add("on");
        const pane = parent.querySelector('.ppane[data-prov="' + tab.dataset.prov + '"]');
        if (pane) pane.classList.remove("hidden");
      };
    });
  },

  toBottom(force) {
    const scroll = $("#scroll");
    if (force) B.ui.stick = true;
    if (B.ui.stick) scroll.scrollTop = scroll.scrollHeight;
  },

  grow() {
    const input = $("#input");
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 170) + "px";
    if (!B.busy) $("#send").disabled = !input.value.trim() && !B.files.pending.length;
  },

  /* ── Oturumlar ──────────────────────────────────────────────── */
  renderSessions() {
    const box = $("#sessions");
    if (!B.chats.length) {
      box.innerHTML = '<div style="padding:18px;color:var(--faint);font-size:13px">Henüz sohbet yok.</div>';
      return;
    }
    box.innerHTML = "";
    B.chats.forEach(c => {
      const el = document.createElement("div");
      el.className = "sess" + (c.id === B.activeId ? " on" : "");
      el.innerHTML = '<div class="t">' + B.esc(c.title) + '<div class="d">' + when(c.ts) + '</div></div>' +
        '<button class="x">×</button>';
      el.querySelector(".t").onclick = () => {
        B.activeId = c.id; B.store.set("b.active", B.activeId);
        B.ui.render(); B.ui.renderSessions(); B.ui.closeAll();
      };
      el.querySelector(".x").onclick = e => {
        e.stopPropagation();
        B.chats = B.chats.filter(x => x.id !== c.id);
        if (B.activeId === c.id) { B.activeId = B.chats[0]?.id || null; B.store.set("b.active", B.activeId); }
        B.saveChats(); B.ui.renderSessions();
        if (!B.chats.length) { B.newChat(); B.ui.render(); } else B.ui.render();
      };
      box.appendChild(el);
    });
  },

  /* ── Cekmece / Sayfalar ─────────────────────────────────────── */
  openLayer: null,
  setBack(on) { try { if (window.Native?.setBack) Native.setBack(!!on); } catch {} },

  openDrawer() { $("#drawer").classList.add("on"); $("#veil").classList.add("on"); B.ui.openLayer = "drawer"; B.ui.setBack(true); },
  openSheet(sel) {
    B.ui.closeAll();
    $(sel).classList.add("on"); $("#veil").classList.add("on"); B.ui.openLayer = sel; B.ui.setBack(true);
  },
  closeAll() {
    $("#drawer").classList.remove("on");
    $$(".sheet").forEach(s => s.classList.remove("on"));
    $("#veil").classList.remove("on");
    B.ui.openLayer = null; B.ui.setBack(false);
  },

  syncChip() {
    const p = B.prov();
    if (!p) { $("#modelChip").textContent = "model seç"; $("#hintL").textContent = ""; $("#hintR").textContent = "anahtar yok"; return; }
    const short = (p.model || "model").replace(/^claude-/, "").replace(/-latest$/, "");
    $("#modelChip").textContent = short;
    let hint = B.cfg.active || "";
    if (B.cfg.thinking !== "kapali") hint += " · düşünme " + B.cfg.thinking;
    if (B.cfg.parallelMode !== "off") hint += " · " + (B.cfg.parallelMode === "leader" ? "lider" : "paralel");
    $("#hintL").textContent = hint;
    $("#hintR").textContent = p.key ? "" : "anahtar yok";
  },

  setBusy(on) {
    const b = $("#send");
    b.classList.toggle("stop", on);
    b.disabled = on ? false : !$("#input").value.trim() && !B.files.pending.length;
    b.innerHTML = on
      ? '<svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><rect x="5" y="5" width="14" height="14" rx="2.5"/></svg>'
      : '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5M5 12l7-7 7 7"/></svg>';
  }
};

window.onAndroidBack = function() { if (B.ui.openLayer) { B.ui.closeAll(); return true; } return false; };
