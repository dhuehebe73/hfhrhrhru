"use strict";

/* ──────────────────────────────────────────────────────────────────────────
   providers.js — Saglayici katalog ve hazir sablonlar
   Ucretsiz + ucretli tum bilinen saglayicilar.
   ────────────────────────────────────────────────────────────────────── */

B.CATALOG = [
  {
    id: "openrouter-free", name: "OpenRouter (Ücretsiz)", type: "openai",
    base: "https://openrouter.ai/api",
    models: [
      "google/gemini-2.5-flash-preview-05-20:free",
      "deepseek/deepseek-chat-v3-0324:free",
      "meta-llama/llama-4-maverick:free",
      "meta-llama/llama-4-scout:free",
      "qwen/qwen3-235b-a22b:free",
      "qwen/qwen3-30b-a3b:free",
      "mistralai/mistral-small-3.2-24b-instruct:free",
      "google/gemma-3-27b-it:free",
      "deepseek/deepseek-r1-0528:free"
    ],
    note: "Ücretsiz modeller. openrouter.ai'den API key al.",
    icon: "🌐"
  },
  {
    id: "groq", name: "Groq", type: "openai",
    base: "https://api.groq.com/openai",
    models: [
      "llama-3.3-70b-versatile",
      "llama-3.1-8b-instant",
      "gemma2-9b-it",
      "mixtral-8x7b-32768",
      "deepseek-r1-distill-llama-70b"
    ],
    note: "Çok hızlı ücretsiz çıkarım. console.groq.com'dan key al.",
    icon: "⚡"
  },
  {
    id: "gemini", name: "Google Gemini", type: "gemini",
    base: "https://generativelanguage.googleapis.com",
    models: [
      "gemini-2.5-flash",
      "gemini-2.5-pro",
      "gemini-2.0-flash",
      "gemini-2.0-flash-lite"
    ],
    note: "Google AI Studio'dan ücretsiz API key. aistudio.google.com",
    icon: "💎"
  },
  {
    id: "mistral", name: "Mistral", type: "openai",
    base: "https://api.mistral.ai",
    models: [
      "mistral-large-latest",
      "mistral-medium-latest",
      "mistral-small-latest",
      "codestral-latest",
      "open-mistral-nemo"
    ],
    note: "console.mistral.ai'den key al. Ücretsiz tier mevcut.",
    icon: "🔷"
  },
  {
    id: "anthropic", name: "Anthropic", type: "anthropic",
    base: "https://api.anthropic.com",
    models: [
      "claude-sonnet-4-5",
      "claude-haiku-4-5",
      "claude-opus-4-5"
    ],
    note: "console.anthropic.com'dan API key al.",
    icon: "🟠"
  },
  {
    id: "openai", name: "OpenAI", type: "openai",
    base: "https://api.openai.com",
    models: [
      "gpt-4o",
      "gpt-4o-mini",
      "gpt-4.1",
      "gpt-4.1-mini",
      "o4-mini"
    ],
    note: "platform.openai.com'dan API key al.",
    icon: "🟢"
  },
  {
    id: "together", name: "Together AI", type: "openai",
    base: "https://api.together.xyz",
    models: [
      "meta-llama/Llama-3.3-70B-Instruct-Turbo",
      "deepseek-ai/DeepSeek-V3",
      "Qwen/Qwen2.5-72B-Instruct-Turbo",
      "mistralai/Mixtral-8x22B-Instruct-v0.1"
    ],
    note: "api.together.xyz'den key al. Ücretsiz kredi mevcut.",
    icon: "🤝"
  },
  {
    id: "custom", name: "Özel Sağlayıcı", type: "openai",
    base: "",
    models: [],
    note: "OpenAI uyumlu herhangi bir endpoint. Kendi sunucun, LM Studio, Ollama vb.",
    icon: "⚙️"
  }
];

/* Saglayici tipine gore istek olusturma */
B.buildRequest = function(provName, messages, files) {
  const p = B.prov(provName);
  if (!p) return null;
  const base = (p.base || "").replace(/\/+$/, "");
  const think = B.cfg.thinking !== "kapali";
  const sys = B.cfg.system || "";

  /* Dosya icerikleri mesaja ekle */
  let enriched = messages.map(m => {
    if (m.role === "user" && m.files && m.files.length) {
      let extra = m.files.map(f => {
        if (f.type === "text") return "\n\n📎 " + f.name + ":\n```\n" + f.content + "\n```";
        return "\n\n📎 " + f.name + " (" + f.mime + ", " + B.fmtSize(f.size) + ")";
      }).join("");
      return { ...m, content: m.content + extra };
    }
    return m;
  });

  if (p.type === "anthropic") {
    const body = {
      model: p.model,
      max_tokens: B.cfg.maxTokens,
      stream: true,
      messages: enriched.map(m => ({ role: m.role === "ai" ? "assistant" : "user", content: m.content }))
    };
    if (sys) body.system = sys;
    if (think && B.REASONING.test(p.model)) {
      body.thinking = { type: "enabled", budget_tokens: Math.min(B.THINK_BUDGET[B.cfg.thinking], Math.max(1024, B.cfg.maxTokens - 1024)) };
    }
    return {
      url: base + "/v1/messages",
      headers: {
        "content-type": "application/json",
        "x-api-key": p.key,
        "anthropic-version": "2023-06-01",
        "anthropic-dangerous-direct-browser-access": "true"
      },
      body: JSON.stringify(body)
    };
  }

  if (p.type === "gemini") {
    const contents = [];
    if (sys) contents.push({ role: "user", parts: [{ text: "[System: " + sys + "]" }] });
    enriched.forEach(m => {
      contents.push({ role: m.role === "ai" ? "model" : "user", parts: [{ text: m.content }] });
    });
    const body = {
      contents,
      generationConfig: { maxOutputTokens: B.cfg.maxTokens }
    };
    if (think && B.REASONING.test(p.model)) {
      body.generationConfig.thinkingConfig = { thinkingBudget: B.THINK_BUDGET[B.cfg.thinking] };
    }
    return {
      url: base + "/v1beta/models/" + p.model + ":streamGenerateContent?alt=sse&key=" + p.key,
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
      parser: "gemini"
    };
  }

  /* OpenAI uyumlu (varsayilan) */
  const msgs = enriched.map(m => ({ role: m.role === "ai" ? "assistant" : "user", content: m.content }));
  if (sys) msgs.unshift({ role: "system", content: sys });
  const body = { model: p.model, messages: msgs, stream: true };
  const eff = B.THINK_EFFORT[B.cfg.thinking];
  if (eff && B.REASONING.test(p.model)) {
    body.reasoning_effort = eff;
    body.max_completion_tokens = B.cfg.maxTokens;
  } else {
    body.max_tokens = B.cfg.maxTokens;
  }

  const headers = { "content-type": "application/json", authorization: "Bearer " + p.key };
  /* OpenRouter ozel header */
  if ((base || "").includes("openrouter")) {
    headers["HTTP-Referer"] = "https://baron.ai";
    headers["X-Title"] = "Baron AI";
  }

  return {
    url: base + "/v1/chat/completions",
    headers,
    body: JSON.stringify(body)
  };
};

/* SSE parcasini ayristir */
B.parseChunk = function(raw, type, sink) {
  if (!raw || raw === "[DONE]") return;
  let ev;
  try { ev = JSON.parse(raw); } catch { return; }

  if (type === "anthropic") {
    if (ev.type === "content_block_delta") {
      const d = ev.delta || {};
      if (d.type === "text_delta") sink.text(d.text);
      else if (d.type === "thinking_delta") sink.think(d.thinking);
    } else if (ev.type === "error") {
      sink.fail((ev.error && ev.error.message) || "Bilinmeyen hata");
    }
    return;
  }

  if (type === "gemini") {
    const parts = ev.candidates?.[0]?.content?.parts || [];
    for (const p of parts) {
      if (p.thought) sink.think(p.text || "");
      else if (p.text) sink.text(p.text);
    }
    return;
  }

  /* OpenAI uyumlu */
  if (ev.error) { sink.fail(ev.error.message || JSON.stringify(ev.error)); return; }
  const d = ((ev.choices || [])[0] || {}).delta || {};
  const r = d.reasoning_content || d.reasoning;
  if (r) sink.think(r);
  if (d.content) sink.text(d.content);
};

B.fmtSize = function(bytes) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / 1048576).toFixed(1) + " MB";
};
