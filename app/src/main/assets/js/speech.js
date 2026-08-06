"use strict";

/* ──────────────────────────────────────────────────────────────────────────
   speech.js — Konusmadan metne cevirme
   ────────────────────────────────────────────────────────────────────── */

B.speech = {
  active: false,

  available() {
    if (HasNative) { try { return !!window.Native.hasSpeech && window.Native.hasSpeech(); } catch { return false; } }
    return !!(window.SpeechRecognition || window.webkitSpeechRecognition);
  },

  start() {
    if (B.speech.active) { B.speech.stop(); return; }
    B.speech.active = true;
    B.speech.updateBtn();

    if (HasNative) {
      try { window.Native.startSpeech(); } catch { B.speech.active = false; B.speech.updateBtn(); }
      return;
    }

    /* Web Speech API fallback */
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { B.toast("Ses tanıma desteklenmiyor"); B.speech.active = false; B.speech.updateBtn(); return; }

    const rec = new SR();
    rec.continuous = false;
    rec.interimResults = true;
    rec.lang = "tr-TR";

    rec.onresult = (e) => {
      let text = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        text += e.results[i][0].transcript;
      }
      if (e.results[e.resultIndex].isFinal) {
        const inp = document.getElementById("input");
        inp.value += (inp.value ? " " : "") + text;
        B.ui.grow();
      }
    };
    rec.onend = () => { B.speech.active = false; B.speech.updateBtn(); };
    rec.onerror = (e) => { B.speech.active = false; B.speech.updateBtn(); if (e.error !== "aborted") B.toast("Ses hatası: " + e.error); };
    rec.start();
    B.speech._rec = rec;
  },

  stop() {
    B.speech.active = false;
    B.speech.updateBtn();
    if (HasNative) { try { window.Native.stopSpeech(); } catch {} }
    else if (B.speech._rec) { try { B.speech._rec.stop(); } catch {} }
  },

  /* Native'den gelen olaylar */
  handleNative(type, payload) {
    if (type === "result" || type === "partial") {
      const inp = document.getElementById("input");
      if (type === "result") {
        inp.value += (inp.value ? " " : "") + payload;
        B.ui.grow();
      }
    } else if (type === "done") {
      B.speech.active = false;
      B.speech.updateBtn();
    } else if (type === "error") {
      B.toast(payload);
      B.speech.active = false;
      B.speech.updateBtn();
    } else if (type === "listening") {
      B.toast("Dinleniyor…");
    }
  },

  updateBtn() {
    const btn = document.getElementById("micBtn");
    if (!btn) return;
    btn.classList.toggle("recording", B.speech.active);
  }
};
