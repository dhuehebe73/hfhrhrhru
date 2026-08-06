"use strict";

/* ──────────────────────────────────────────────────────────────────────────
   app.js — Ana kontrolcu: gonderme, ayarlar, olay baglama
   ────────────────────────────────────────────────────────────────────── */

B.app = {

  /* ── Tekli gonderme ──────────────────────────────────────────── */
  async send(retryOf) {
    if (B.busy) return;
    const p = B.prov();
    if (!p || !p.key) { B.app.openSettings(); B.toast("Önce sağlayıcı ekle ve API anahtarını gir"); return; }

    let c = B.chat();
    if (!c) { c = B.newChat(); }

    const files = B.files.flush();

    if (!retryOf) {
      const text = $("#input").value.trim();
      if (!text && !files.length) return;
      $("#input").value = ""; B.ui.grow();
      const userMsg = { role: "user", content: text, files: files.length ? files : undefined };
      c.messages.push(userMsg);
      if (c.messages.length === 1) c.title = text.slice(0, 46) || "Dosya sohbeti";
      c.ts = Date.now();
      if (B.chats[0] !== c) { B.chats = B.chats.filter(x => x !== c); B.chats.unshift(c); }
      if ($("#thread").querySelector(".empty")) $("#thread").innerHTML = "";
      $("#thread").appendChild(B.ui.msgNode(c.messages[c.messages.length - 1]));
      B.saveChats(); B.ui.renderSessions(); B.ui.toBottom(true);
    }

    /* Paralel veya lider mod? */
    if (B.cfg.parallelMode === "parallel" && B.cfg.parallelProviders.length > 1) {
      await B.app.sendParallel(c, retryOf); return;
    }
    if (B.cfg.parallelMode === "leader" && B.cfg.leaderProvider) {
      await B.app.sendLeader(c, retryOf); return;
    }

    /* Tekli mod */
    const reply = { role: "ai", content: "", thinking: "", provider: B.cfg.active, elapsed: 0 };
    c.messages.push(reply);

    const node = document.createElement("div");
    node.className = "msg ai";
    node.innerHTML =
      '<details class="think hidden" open><summary class="pulse">✳ Düşünüyor…</summary><div class="inner"></div></details>' +
      '<div class="body"><span class="pulse" style="color:var(--faint)">…</span></div>';
    $("#thread").appendChild(node);
    B.ui.toBottom(true);

    const thinkEl = node.querySelector(".think");
    const thinkInner = node.querySelector(".think .inner");
    const bodyEl = node.querySelector(".body");
    let started = false, failed = null, frame = null;
    const t0 = Date.now();

    B.ui.setBusy(true);
    const req = B.buildRequest(B.cfg.active, c.messages.slice(0, -1), files);
    if (!req) { B.ui.setBusy(false); B.toast("Yapılandırma hatası"); return; }

    const paint = () => { frame = null; bodyEl.innerHTML = B.md(reply.content) || '<span class="pulse" style="color:var(--faint)">…</span>'; B.ui.bindCopies(); B.ui.toBottom(); };
    const schedule = () => { if (!frame) frame = requestAnimationFrame(paint); };

    const sink = {
      text(t) { if (!started) { started = true; thinkEl.querySelector("summary").classList.remove("pulse"); } reply.content += t; schedule(); },
      think(t) { reply.thinking += t; thinkEl.classList.remove("hidden"); thinkInner.textContent = reply.thinking; thinkInner.scrollTop = thinkInner.scrollHeight; B.ui.toBottom(); },
      fail(m) { failed = m; }
    };

    const provType = B.prov()?.type || "openai";
    const stream = B.openStream(req.url, req.headers, req.body,
      raw => B.parseChunk(raw, req.parser || provType, sink));
    B.busy = stream;

    try {
      await stream.promise;
      if (failed) throw new Error(failed);
    } catch (e) {
      const msg = String(e?.message || e);
      if (!/abort|cancel/i.test(msg)) reply.error = B.friendlyErr(msg);
    } finally {
      B.busy = null; B.ui.setBusy(false);
      reply.elapsed = Date.now() - t0;
      if (frame) cancelAnimationFrame(frame);
      B.app.finishReply(node, reply, thinkEl, bodyEl);
      c.ts = Date.now(); B.saveChats(); B.ui.renderSessions(); B.ui.toBottom();
    }
  },

  /* ── Paralel gonderme ──────────────────────────────────────── */
  async sendParallel(c, retryOf) {
    const userText = c.messages[c.messages.length - 1].content;
    const files = c.messages[c.messages.length - 1].files || [];
    const parallelMsg = { role: "parallel", results: {}, content: "" };
    c.messages.push(parallelMsg);

    const node = document.createElement("div");
    node.className = "msg parallel";
    node.innerHTML = '<div class="body"><span class="pulse" style="color:var(--faint)">Paralel çalışıyor…</span></div>';
    $("#thread").appendChild(node);
    B.ui.toBottom(true);
    B.ui.setBusy(true);

    await B.parallel.runAll(
      userText, files,
      (names, results) => { parallelMsg.results = results; },
      (name, results) => { parallelMsg.results = { ...results }; node.innerHTML = B.ui.parallelView(parallelMsg); B.ui.bindCopies(); B.ui.toBottom(); },
      (err, results) => {
        B.ui.setBusy(false);
        if (err) { node.innerHTML = '<div class="err">' + B.esc(err) + '</div>'; }
        else { parallelMsg.results = results; node.innerHTML = B.ui.parallelView(parallelMsg); B.ui.bindCopies(); }
        c.ts = Date.now(); B.saveChats(); B.ui.renderSessions(); B.ui.toBottom();
      }
    );
  },

  /* ── Lider mod ──────────────────────────────────────────────── */
  async sendLeader(c, retryOf) {
    const userText = c.messages[c.messages.length - 1].content;
    const files = c.messages[c.messages.length - 1].files || [];

    const reply = { role: "ai", content: "", thinking: "", provider: "Lider: " + B.cfg.leaderProvider };
    c.messages.push(reply);

    const node = document.createElement("div");
    node.className = "msg ai";
    node.innerHTML = '<div class="body"><span class="pulse" style="color:var(--faint)">Lider düşünüyor…</span></div>';
    $("#thread").appendChild(node);
    B.ui.toBottom(true);
    B.ui.setBusy(true);

    await B.parallel.runLeader(
      userText, files,
      () => {},
      (name, data) => {
        if (data.leader) {
          reply.content = data.leader.content;
          reply.thinking = data.leader.thinking || "";
          node.innerHTML = B.ui.aiMsgHtml(reply);
          B.ui.bindCopies();
          B.ui.toBottom();
        }
      },
      (err, results) => {
        B.ui.setBusy(false);
        if (err) { reply.error = err; }
        else if (results?.__leader__) {
          reply.content = results.__leader__.content;
          reply.thinking = results.__leader__.thinking || "";
        }
        node.innerHTML = B.ui.aiMsgHtml(reply);
        B.ui.bindMsgActions(node, reply);
        B.ui.bindCopies();
        c.ts = Date.now(); B.saveChats(); B.ui.renderSessions(); B.ui.toBottom();
      }
    );
  },

  finishReply(node, reply, thinkEl, bodyEl) {
    if (reply.error) {
      node.innerHTML = '<div class="err">' + B.esc(reply.error) + '</div>' +
        '<div class="acts"><button data-a="again">Tekrar dene</button></div>';
      node.querySelector('[data-a="again"]').onclick = () => B.app.regenerate(reply);
    } else {
      if (!reply.content && !reply.thinking) reply.content = "(boş yanıt)";
      if (!reply.thinking) thinkEl.classList.add("hidden");
      else { thinkEl.classList.remove("hidden"); thinkEl.open = false; thinkEl.querySelector("summary").textContent = "✳ Düşünce"; }
      bodyEl.innerHTML = B.md(reply.content);
      const provTag = reply.provider ? '<span class="ptag">' + B.esc(reply.provider) + '</span>' : '';
      const elapsed = reply.elapsed ? '<span class="etime">' + (reply.elapsed / 1000).toFixed(1) + 's</span>' : '';
      node.innerHTML = provTag +
        (reply.thinking ? '<details class="think"><summary>✳ Düşünce</summary><div class="inner">' + B.esc(reply.thinking) + '</div></details>' : '') +
        '<div class="body">' + B.md(reply.content) + '</div>' +
        '<div class="acts">' + elapsed + '<button data-a="copy">Kopyala</button><button data-a="again">Yeniden</button></div>';
      B.ui.bindMsgActions(node, reply);
      B.ui.bindCopies();
    }
  },

  regenerate(target) {
    if (B.busy) return;
    const c = B.chat(); if (!c) return;
    const i = c.messages.indexOf(target);
    if (i > 0) c.messages.splice(i);
    B.ui.render(); B.saveChats();
    B.app.send(true);
  },

  /* ── Ayarlar ─────────────────────────────────────────────────── */
  openSettings() {
    B.app.fillSettings();
    B.ui.openSheet("#settingsSheet");
  },

  fillSettings() {
    /* Saglayici listesi */
    const box = $("#plist");
    box.innerHTML = "";
    Object.keys(B.cfg.providers).forEach(name => {
      const p = B.cfg.providers[name];
      const el = document.createElement("div");
      el.className = "pitem" + (name === B.cfg.active ? " on" : "");
      el.innerHTML =
        '<div class="dot ' + (p.key ? "ok" : "no") + '"></div>' +
        '<div class="info"><div class="nm">' + B.esc(name) + '</div>' +
        '<div class="sub">' + B.esc(p.model || "?") + ' · ' + B.esc(p.type) + '</div></div>' +
        '<button style="color:var(--faint);padding:0 6px">✎</button>';
      el.querySelector(".info").onclick = () => {
        B.cfg.active = name; B.saveCfg(); B.app.fillSettings(); B.ui.syncChip(); B.toast(name + " seçildi");
      };
      el.querySelector("button").onclick = () => B.app.editProvider(name);
      box.appendChild(el);
    });

    /* Katalog */
    const catBox = $("#catalogList");
    catBox.innerHTML = "";
    B.CATALOG.forEach(cat => {
      const exists = Object.values(B.cfg.providers).some(p => p.base === cat.base && cat.base);
      const el = document.createElement("div");
      el.className = "catitem" + (exists ? " added" : "");
      el.innerHTML = '<span class="ci">' + cat.icon + '</span><div class="info"><div class="nm">' + B.esc(cat.name) + '</div>' +
        '<div class="sub">' + B.esc(cat.note) + '</div></div>';
      if (!exists) {
        el.onclick = () => {
          B.app.editProvider(null, cat);
        };
      }
      catBox.appendChild(el);
    });

    B.app.seg("#thinkSeg", B.cfg.thinking);
    B.app.seg("#modeSeg", B.cfg.parallelMode);
    $("#sysPrompt").value = B.cfg.system || "";
    $("#maxTok").value = B.cfg.maxTokens;

    B.app.renderParallelConfig();
  },

  renderParallelConfig() {
    const box = $("#parallelCfg");
    const show = B.cfg.parallelMode !== "off";
    box.classList.toggle("hidden", !show);
    if (!show) return;

    const names = Object.keys(B.cfg.providers);
    box.innerHTML = '<label>Paralel sağlayıcılar</label>' +
      '<div class="pchecks">' +
      names.map(n =>
        '<label class="pcheck"><input type="checkbox" value="' + B.esc(n) + '"' +
        (B.cfg.parallelProviders.includes(n) ? ' checked' : '') + '> ' + B.esc(n) + '</label>'
      ).join("") +
      '</div>' +
      (B.cfg.parallelMode === "leader" ?
        '<label style="margin-top:10px">Lider model</label>' +
        '<select id="leaderSel">' +
        names.map(n => '<option value="' + B.esc(n) + '"' + (B.cfg.leaderProvider === n ? ' selected' : '') + '>' + B.esc(n) + '</option>').join("") +
        '</select>' : '');

    box.querySelectorAll('input[type="checkbox"]').forEach(cb => {
      cb.onchange = () => {
        B.cfg.parallelProviders = [...box.querySelectorAll('input:checked')].map(c => c.value);
      };
    });
    const sel = box.querySelector("#leaderSel");
    if (sel) sel.onchange = () => { B.cfg.leaderProvider = sel.value; };
  },

  seg(sel, val) {
    $$(sel + " button").forEach(b => b.classList.toggle("on", b.dataset.v === val));
  },

  /* ── Saglayici duzenleme ─────────────────────────────────────── */
  _editing: null,

  editProvider(name, template) {
    B.app._editing = name;
    const p = name ? B.cfg.providers[name]
      : template ? { type: template.type, base: template.base, key: "", model: template.models?.[0] || "" }
      : { type: "openai", base: "", key: "", model: "" };

    $("#provTitle").textContent = name || (template ? template.name : "Yeni sağlayıcı");
    $("#pName").value = name || (template ? template.name : "");
    $("#pBase").value = p.base || "";
    $("#pKey").value = p.key || "";
    $("#pModel").value = p.model || "";
    B.app.seg("#pType", p.type || "openai");
    $("#pDelete").style.display = name && Object.keys(B.cfg.providers).length > 1 ? "block" : "none";

    /* Hazir model listesi */
    const mBox = $("#pModelList");
    const models = template?.models || [];
    if (models.length) {
      mBox.innerHTML = models.map(m =>
        '<button class="mopt" data-m="' + B.esc(m) + '">' + B.esc(m) + '</button>'
      ).join("");
      mBox.classList.remove("hidden");
      mBox.querySelectorAll(".mopt").forEach(b => {
        b.onclick = () => { $("#pModel").value = b.dataset.m; mBox.querySelectorAll(".mopt").forEach(x => x.classList.remove("on")); b.classList.add("on"); };
      });
    } else {
      mBox.classList.add("hidden");
      mBox.innerHTML = "";
    }

    B.ui.openSheet("#provSheet");
  },

  saveProvider() {
    const name = $("#pName").value.trim();
    if (!name) { B.toast("İsim gerekli"); return; }
    const type = document.querySelector("#pType button.on")?.dataset.v || "openai";
    let base = $("#pBase").value.trim().replace(/\/+$/, "").replace(/\/v1(\/messages|\/chat\/completions)?$/, "");
    if (base && !/^https?:\/\//i.test(base)) base = "https://" + base;
    if (B.app._editing && B.app._editing !== name) delete B.cfg.providers[B.app._editing];
    B.cfg.providers[name] = {
      type, base,
      key: $("#pKey").value.trim(),
      model: $("#pModel").value.trim() || "auto"
    };
    if (!B.cfg.active) B.cfg.active = name;
    B.saveCfg(); B.ui.syncChip(); B.app.fillSettings(); B.ui.openSheet("#settingsSheet"); B.toast("Kaydedildi");
  },

  deleteProvider() {
    if (!B.app._editing) return;
    delete B.cfg.providers[B.app._editing];
    if (B.cfg.active === B.app._editing) B.cfg.active = Object.keys(B.cfg.providers)[0] || null;
    B.saveCfg(); B.ui.syncChip(); B.app.fillSettings(); B.ui.openSheet("#settingsSheet");
  },

  /* ── Model secici ──────────────────────────────────────────── */
  async loadModels(force) {
    const p = B.prov();
    if (!p) return;
    const box = $("#mlist");
    const cacheKey = (p.base || "") + "|" + (p.type || "");
    let names = force ? null : B.modelCache[cacheKey];

    if (!names) {
      box.innerHTML = '<div style="padding:22px;text-align:center;color:var(--faint);font-size:13px" class="pulse">Liste alınıyor…</div>';
      try {
        let headers;
        if (p.type === "anthropic") {
          headers = { "x-api-key": p.key, "anthropic-version": "2023-06-01", "anthropic-dangerous-direct-browser-access": "true" };
        } else if (p.type === "gemini") {
          headers = {};
        } else {
          headers = { authorization: "Bearer " + p.key };
        }
        let url;
        if (p.type === "gemini") {
          url = p.base.replace(/\/+$/, "") + "/v1beta/models?key=" + p.key;
        } else {
          url = p.base.replace(/\/+$/, "") + "/v1/models";
        }
        const j = await B.httpGet(url, headers);
        const items = j.data || j.models || (Array.isArray(j) ? j : []);
        names = items.map(x => x.id || x.name || "").filter(Boolean)
          .map(n => n.replace(/^models\//, "")).sort();
        if (names.length) { B.modelCache[cacheKey] = names; B.store.set("b.models", B.modelCache); }
      } catch { names = null; }
    }

    if (!names || !names.length) {
      const cat = B.CATALOG.find(c => p.base?.includes(c.base?.replace(/https?:\/\//, "").split("/")[0]));
      names = cat?.models || ["model adını elle yaz"];
    }

    box.innerHTML = "";
    names.forEach(n => {
      const el = document.createElement("div");
      el.className = "mitem" + (n === p.model ? " on" : "");
      el.innerHTML = "<span style='flex:1;word-break:break-all'>" + B.esc(n) + "</span>" +
        (B.REASONING.test(n) ? '<span class="star">✳</span>' : "");
      el.onclick = () => { p.model = n; B.saveCfg(); B.ui.syncChip(); B.ui.closeAll(); B.toast(n); };
      box.appendChild(el);
    });
  },

  /* ── Baslangic ──────────────────────────────────────────────── */
  init() {
    /* Olaylar */
    $("#veil").onclick = () => B.ui.closeAll();
    $("#menuBtn").onclick = () => { B.ui.renderSessions(); B.ui.openDrawer(); };
    $("#newChat").onclick = () => { B.newChat(); B.ui.render(); B.ui.renderSessions(); B.ui.closeAll(); $("#input").focus(); };
    $("#openSettings").onclick = () => B.app.openSettings();
    $("#modelChip").onclick = () => { B.ui.openSheet("#modelSheet"); B.app.loadModels(false); };
    $("#refreshModels").onclick = () => B.app.loadModels(true);

    /* Dusunme segmenti */
    $$("#thinkSeg button").forEach(b => b.onclick = () => { B.cfg.thinking = b.dataset.v; B.app.seg("#thinkSeg", b.dataset.v); });
    /* Mod segmenti */
    $$("#modeSeg button").forEach(b => b.onclick = () => { B.cfg.parallelMode = b.dataset.v; B.app.seg("#modeSeg", b.dataset.v); B.app.renderParallelConfig(); });
    /* Saglayici tipi */
    $$("#pType button").forEach(b => b.onclick = () => B.app.seg("#pType", b.dataset.v));

    /* Kaydet */
    $("#saveSettings").onclick = () => {
      B.cfg.system = $("#sysPrompt").value.trim();
      B.cfg.maxTokens = Math.max(256, Math.min(128000, parseInt($("#maxTok").value, 10) || 4096));
      B.saveCfg(); B.ui.syncChip(); B.ui.closeAll(); B.toast("Kaydedildi");
    };

    /* Sil */
    $("#wipe").onclick = () => {
      if (!confirm("Tüm sohbetler, anahtarlar ve ayarlar silinecek. Emin misin?")) return;
      B.store.del("b.cfg"); B.store.del("b.chats"); B.store.del("b.active"); B.store.del("b.models");
      location.reload();
    };

    /* Saglayici kaydet/sil */
    $("#addProvider").onclick = () => B.app.editProvider(null);
    $("#pSave").onclick = () => B.app.saveProvider();
    $("#pDelete").onclick = () => B.app.deleteProvider();

    /* Dosya */
    $("#fileBtn").onclick = () => B.files.pick();

    /* Mikrofon */
    const micBtn = $("#micBtn");
    if (B.speech.available()) {
      micBtn.classList.remove("hidden");
      micBtn.onclick = () => B.speech.start();
    }

    /* Yazi alani */
    const input = $("#input");
    input.addEventListener("input", () => B.ui.grow());
    input.addEventListener("paste", (e) => B.files.handlePaste(e));
    input.addEventListener("keydown", e => {
      if (e.key === "Enter" && !e.shiftKey && window.matchMedia("(min-width:700px)").matches) {
        e.preventDefault(); B.app.send();
      }
    });

    /* Gonder */
    $("#send").onclick = () => {
      if (B.busy || Object.keys(B.busyMap).length) {
        B.parallel.cancelAll();
        B.ui.setBusy(false);
        B.toast("Durduruldu");
        return;
      }
      B.app.send();
    };

    /* Scroll */
    $("#scroll").addEventListener("scroll", () => {
      const s = $("#scroll");
      B.ui.stick = s.scrollHeight - s.scrollTop - s.clientHeight < 120;
    });

    /* Baslat */
    if (!B.chats.length) B.newChat();
    if (!B.chat()) { B.activeId = B.chats[0]?.id; B.store.set("b.active", B.activeId); }
    B.ui.render();
    B.ui.renderSessions();
    B.ui.syncChip();
    B.ui.grow();
    B.files.renderPending();
    if (!Object.keys(B.cfg.providers).length) setTimeout(() => B.app.openSettings(), 400);
  }
};

/* Sayfa yuklendiginde baslat */
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", () => B.app.init());
else B.app.init();
