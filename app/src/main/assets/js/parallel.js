"use strict";

/* ──────────────────────────────────────────────────────────────────────────
   parallel.js — Paralel calistirma ve lider mod motoru
   ────────────────────────────────────────────────────────────────────── */

B.parallel = {

  /* Secili saglayicilarin hepsine ayni anda gonderdikten sonra UI render */
  async runAll(userMsg, files, onStart, onUpdate, onDone) {
    const provNames = B.cfg.parallelProviders.filter(n => B.cfg.providers[n]);
    if (!provNames.length) { onDone("Paralel mod için en az bir sağlayıcı seç."); return; }

    const results = {};
    const streams = {};

    provNames.forEach(name => {
      results[name] = { content: "", thinking: "", error: null, done: false, elapsed: 0 };
    });

    onStart(provNames, results);
    const t0 = Date.now();

    const promises = provNames.map(name => {
      const p = B.prov(name);
      const c = B.chat();
      const history = (c ? c.messages.filter(m => m.role !== "system") : []);
      const msgs = [...history, { role: "user", content: userMsg, files }];
      const req = B.buildRequest(name, msgs, files);
      if (!req) { results[name].error = "Yapılandırma hatası"; results[name].done = true; return Promise.resolve(); }

      const sink = {
        text(t) { results[name].content += t; results[name].elapsed = Date.now() - t0; onUpdate(name, results); },
        think(t) { results[name].thinking += t; onUpdate(name, results); },
        fail(m) { results[name].error = m; }
      };

      const stream = B.openStream(req.url, req.headers, req.body,
        raw => B.parseChunk(raw, req.parser || p.type, sink));
      streams[name] = stream;
      B.busyMap[name] = stream;

      return stream.promise
        .catch(e => { if (!/abort|cancel/i.test(e.message)) results[name].error = B.friendlyErr(e.message); })
        .finally(() => { results[name].done = true; results[name].elapsed = Date.now() - t0; delete B.busyMap[name]; });
    });

    await Promise.allSettled(promises);
    onDone(null, results);
  },

  /* Lider mod: bir model yonetir, diger modellere is dagitir */
  async runLeader(userMsg, files, onStart, onUpdate, onDone) {
    const leaderName = B.cfg.leaderProvider;
    const workerNames = B.cfg.parallelProviders.filter(n => n !== leaderName && B.cfg.providers[n]);
    if (!leaderName || !B.cfg.providers[leaderName]) { onDone("Lider sağlayıcı seçilmedi."); return; }

    onStart([leaderName, ...workerNames], {});

    const leaderP = B.prov(leaderName);
    const c = B.chat();
    const history = c ? c.messages.filter(m => m.role !== "system") : [];

    /* 1. adim: lidere mesaji gonder, alt gorevleri belirlesin */
    const workerInfo = workerNames.map(n => {
      const p = B.prov(n);
      return n + " (" + p.model + ")";
    }).join(", ");

    const leaderSystem = (B.cfg.system ? B.cfg.system + "\n\n" : "") +
      "Sen bir lider AI'sın. Elinde şu çalışan modeller var: " + workerInfo + ".\n" +
      "Kullanıcının isteğini analiz et. İstersen çalışanlara görev dağıt, " +
      "istersen kendin yanıtla. Görev dağıtacaksan her görev için " +
      "şu formatı kullan:\n[GÖREV:model_adı] görev açıklaması [/GÖREV]\n" +
      "Görev yoksa doğrudan yanıtını ver.";

    const leaderResult = { content: "", thinking: "", error: null };
    const leaderMsgs = [
      { role: "system", content: leaderSystem },
      ...history.map(m => ({ role: m.role === "ai" ? "assistant" : "user", content: m.content })),
      { role: "user", content: userMsg }
    ];

    const leaderReq = B.buildRequest(leaderName, leaderMsgs.map(m =>
      ({ role: m.role === "system" ? "user" : m.role, content: m.content, files: m.files })), files);

    if (!leaderReq) { onDone("Lider yapılandırma hatası"); return; }

    /* Lider yanitini topla */
    const leaderSink = {
      text(t) { leaderResult.content += t; onUpdate("__leader__", { leader: leaderResult }); },
      think(t) { leaderResult.thinking += t; },
      fail(m) { leaderResult.error = m; }
    };

    const leaderStream = B.openStream(leaderReq.url, leaderReq.headers, leaderReq.body,
      raw => B.parseChunk(raw, leaderReq.parser || leaderP.type, leaderSink));
    B.busyMap["__leader__"] = leaderStream;

    try { await leaderStream.promise; } catch (e) {
      if (!/abort|cancel/i.test(e.message)) leaderResult.error = B.friendlyErr(e.message);
    }
    delete B.busyMap["__leader__"];

    if (leaderResult.error) { onDone(null, { __leader__: leaderResult }); return; }

    /* 2. adim: gorevleri ayristir */
    const taskRegex = /\[GÖREV:(\S+)\]\s*([\s\S]*?)\s*\[\/GÖREV\]/g;
    const tasks = [];
    let match;
    while ((match = taskRegex.exec(leaderResult.content)) !== null) {
      tasks.push({ worker: match[1].trim(), task: match[2].trim() });
    }

    if (!tasks.length) {
      /* Lider dogrudan yanitladi, gorev dagitmadi */
      onDone(null, { __leader__: leaderResult });
      return;
    }

    /* 3. adim: calisanlara paralel gonder */
    const workerResults = {};
    const workerPromises = tasks.map(t => {
      const wName = t.worker;
      const wp = B.prov(wName);
      if (!wp) { workerResults[wName] = { content: "", error: "Sağlayıcı bulunamadı: " + wName, done: true }; return Promise.resolve(); }

      workerResults[wName] = { content: "", thinking: "", error: null, done: false };

      const wMsgs = [{ role: "user", content: t.task }];
      const wReq = B.buildRequest(wName, wMsgs);
      if (!wReq) { workerResults[wName].error = "Yapılandırma hatası"; workerResults[wName].done = true; return Promise.resolve(); }

      const wSink = {
        text(txt) { workerResults[wName].content += txt; onUpdate(wName, { ...workerResults, __leader__: leaderResult }); },
        think(txt) { workerResults[wName].thinking += txt; },
        fail(m) { workerResults[wName].error = m; }
      };

      const wStream = B.openStream(wReq.url, wReq.headers, wReq.body,
        raw => B.parseChunk(raw, wReq.parser || wp.type, wSink));
      B.busyMap[wName] = wStream;

      return wStream.promise
        .catch(e => { if (!/abort|cancel/i.test(e.message)) workerResults[wName].error = B.friendlyErr(e.message); })
        .finally(() => { workerResults[wName].done = true; delete B.busyMap[wName]; });
    });

    await Promise.allSettled(workerPromises);

    /* 4. adim: sonuclari lidere geri gonder, sentezlesin */
    let synthesis = leaderResult.content + "\n\n---\n\n";
    for (const [wn, wr] of Object.entries(workerResults)) {
      synthesis += "**" + wn + ":**\n" + (wr.error || wr.content) + "\n\n";
    }

    onDone(null, { __leader__: { ...leaderResult, content: synthesis }, ...workerResults });
  },

  /* Tum aktif akislari durdur */
  cancelAll() {
    Object.entries(B.busyMap).forEach(([k, s]) => {
      try { s.abort(); } catch {}
      delete B.busyMap[k];
    });
    if (B.busy) { try { B.busy.abort(); } catch {} B.busy = null; }
  }
};

B.friendlyErr = function(m) {
  if (/HTTP 401|invalid.*api.?key|authentication/i.test(m)) return "Anahtar geçersiz.";
  if (/HTTP 404/i.test(m)) return "Adres bulunamadı.";
  if (/HTTP 429|rate.?limit/i.test(m)) return "Hız sınırı. Biraz bekle.";
  if (/model/i.test(m) && /not.?found|does not exist/i.test(m)) return "Model bulunamadı.";
  if (/unable to resolve|failed to connect|network|timeout/i.test(m)) return "İnternete ulaşılamadı.";
  return (m || "").slice(0, 400);
};
