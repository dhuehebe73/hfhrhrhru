"use strict";

/* ──────────────────────────────────────────────────────────────────────────
   files.js — Dosya yukleme, uzun yapi$tirma tespiti, dosya okuma
   ────────────────────────────────────────────────────────────────────── */

B.files = {
  /* su an ki sohbete ekli dosyalar (gonderilmemis) */
  pending: [],

  /* Native dosya secici ac */
  pick() {
    if (HasNative) {
      try { window.Native.pickFile(true); } catch {}
    } else {
      /* Tarayici fallback */
      const inp = document.createElement("input");
      inp.type = "file";
      inp.multiple = true;
      inp.accept = "*/*";
      inp.onchange = () => {
        for (const f of inp.files) B.files.readBrowserFile(f);
      };
      inp.click();
    }
  },

  /* Tarayicida dosya oku */
  readBrowserFile(file) {
    const reader = new FileReader();
    const isText = file.type.startsWith("text/") ||
      /\.(txt|md|py|js|ts|kt|java|c|cpp|h|go|rs|rb|php|css|html|sql|sh|yml|yaml|toml|ini|cfg|log|csv|tsv|json|xml)$/i.test(file.name);

    if (isText) {
      reader.onload = () => {
        B.files.add({ name: file.name, mime: file.type || "text/plain", type: "text", content: reader.result, size: file.size });
      };
      reader.readAsText(file);
    } else {
      reader.onload = () => {
        const b64 = reader.result.split(",")[1] || "";
        B.files.add({ name: file.name, mime: file.type, type: "binary", content: b64, size: file.size });
      };
      reader.readAsDataURL(file);
    }
  },

  /* Dosya ekle */
  add(fileData) {
    B.files.pending.push(fileData);
    B.files.renderPending();
    B.toast(fileData.name + " eklendi");
  },

  /* Bekleyen dosyalari goster */
  renderPending() {
    const box = document.getElementById("fileBar");
    if (!B.files.pending.length) { box.classList.add("hidden"); return; }
    box.classList.remove("hidden");
    box.innerHTML = B.files.pending.map((f, i) =>
      '<div class="fchip">' +
        '<span class="fn">' + B.esc(f.name.length > 20 ? f.name.slice(0, 17) + "…" : f.name) + '</span>' +
        '<span class="fs">' + B.fmtSize(f.size) + '</span>' +
        '<button class="fx" data-i="' + i + '">×</button>' +
      '</div>'
    ).join("");
    box.querySelectorAll(".fx").forEach(b => {
      b.onclick = () => { B.files.pending.splice(+b.dataset.i, 1); B.files.renderPending(); };
    });
  },

  /* Uzun yapistirma tespiti — input'a paste olayinda cagrilir */
  handlePaste(e) {
    const text = (e.clipboardData || window.clipboardData).getData("text");
    if (text && text.length > B.cfg.longPasteThreshold) {
      e.preventDefault();
      const lineCount = text.split("\n").length;
      const name = "paste_" + new Date().toISOString().slice(11, 19).replace(/:/g, "") + ".txt";
      B.files.add({
        name,
        mime: "text/plain",
        type: "text",
        content: text,
        size: text.length
      });
      B.toast(lineCount + " satır dosya olarak eklendi");
      return true;
    }
    return false;
  },

  /* Gonderdikten sonra temizle */
  flush() {
    const files = [...B.files.pending];
    B.files.pending = [];
    B.files.renderPending();
    return files;
  }
};

/* Native'den dosya geldiginde */
window.__native = (function(orig) {
  return function(id, type, payload) {
    if (id === "file") {
      if (type === "data") {
        try {
          const f = JSON.parse(payload);
          B.files.add(f);
        } catch {}
      } else if (type === "error") {
        B.toast("Dosya hatası: " + payload);
      }
      return;
    }
    if (id === "speech") {
      B.speech.handleNative(type, payload);
      return;
    }
    orig(id, type, payload);
  };
})(window.__native);
