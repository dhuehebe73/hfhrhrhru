"use strict";

/* ──────────────────────────────────────────────────────────────────────────
   store.js — localStorage wrapper, config, chat persistence
   ────────────────────────────────────────────────────────────────────── */

window.B = window.B || {};

B.store = {
  get(k, d) { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch {} },
  del(k)    { try { localStorage.removeItem(k); } catch {} }
};

/* ── varsayilan ayarlar ─────────────────────────────────────────────── */
B.DEF_CFG = {
  active: null,
  providers: {},
  thinking: "orta",
  maxTokens: 4096,
  system: "",
  parallelMode: "off",        // off | parallel | leader
  parallelProviders: [],      // secili saglayici isimleri
  leaderProvider: null,       // lider saglayici
  longPasteThreshold: 2000,   // bu karakterden uzun yapistirilirsa dosya olarak gosterir
  autoScroll: true
};

B.THINK_BUDGET = { kapali: 0, az: 2000, orta: 6000, cok: 16000 };
B.THINK_EFFORT = { kapali: null, az: "low", orta: "medium", cok: "high" };
B.REASONING = /(opus|sonnet-4|thinking|^o\d|gpt-5|deepseek-r|qwq|reason)/i;

/* ── durum ────────────────────────────────────────────────────────── */
B.cfg      = Object.assign({}, B.DEF_CFG, B.store.get("b.cfg", {}));
B.chats    = B.store.get("b.chats", []);
B.activeId = B.store.get("b.active", null);
B.busy     = null;
B.busyMap  = {};   // paralel modda { provName: stream }
B.modelCache = B.store.get("b.models", {});

B.saveCfg   = () => B.store.set("b.cfg", B.cfg);
B.saveChats = () => B.store.set("b.chats", B.chats);

B.prov = (name) => {
  if (name) return B.cfg.providers[name];
  return B.cfg.providers[B.cfg.active] || Object.values(B.cfg.providers)[0];
};

B.chat = () => B.chats.find(c => c.id === B.activeId);

B.newChat = () => {
  const c = { id: "c" + Date.now(), title: "Yeni sohbet", ts: Date.now(), messages: [], files: [] };
  B.chats.unshift(c);
  B.activeId = c.id;
  B.saveChats();
  B.store.set("b.active", B.activeId);
  return c;
};
