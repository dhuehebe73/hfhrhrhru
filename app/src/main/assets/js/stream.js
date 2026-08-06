"use strict";

/* ──────────────────────────────────────────────────────────────────────────
   stream.js — Ag katmani (Native bridge + fetch fallback)
   ────────────────────────────────────────────────────────────────────── */

const HasNative = typeof window.Native !== "undefined" && !!window.Native.request;
const pending = new Map();
let reqSeq = 0;

window.__native = function(id, type, payload) {
  const h = pending.get(id);
  if (!h) return;
  if (type === "chunk")      h.onChunk(payload);
  else if (type === "error") { pending.delete(id); h.reject(new Error(payload)); }
  else if (type === "done")  { pending.delete(id); h.resolve(); }
};

function nativeStream(url, headers, body, onChunk) {
  const id = "r" + (++reqSeq);
  return {
    id,
    promise: new Promise((resolve, reject) => {
      pending.set(id, { onChunk, resolve, reject });
      try { window.Native.request(id, JSON.stringify({ url, headers, body })); }
      catch (e) { pending.delete(id); reject(e); }
    }),
    abort() { pending.delete(id); try { window.Native.cancel(id); } catch {} }
  };
}

function fetchStream(url, headers, body, onChunk) {
  const ctrl = new AbortController();
  const promise = (async () => {
    const r = await fetch(url, { method: body ? "POST" : "GET", headers, body, signal: ctrl.signal });
    if (!r.ok) throw new Error("HTTP " + r.status + " · " + (await r.text()).slice(0, 400));
    if (!body) { onChunk(await r.text()); return; }
    const rd = r.body.getReader(), dec = new TextDecoder();
    let buf = "";
    for (;;) {
      const { done, value } = await rd.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      const parts = buf.split("\n");
      buf = parts.pop();
      for (const line of parts) {
        const t = line.trim();
        if (t.startsWith("data:")) onChunk(t.slice(5).trim());
      }
    }
  })();
  return { promise, abort: () => ctrl.abort() };
}

B.openStream = function(url, headers, body, onChunk) {
  return HasNative ? nativeStream(url, headers, body, onChunk)
                   : fetchStream(url, headers, body, onChunk);
};

B.httpGet = async function(url, headers) {
  if (HasNative) {
    let out = "";
    const s = nativeStream(url, headers, null, c => { out += c; });
    await s.promise;
    return JSON.parse(out || "{}");
  }
  const r = await fetch(url, { headers });
  if (!r.ok) throw new Error("HTTP " + r.status);
  return r.json();
};
