/**
 * Floating chat widget → insseption agent (GEM-style /api/query).
 * Served under Traefik PathPrefixStrip:/agent → http://insseption-agent:8000
 */
const AGENT_BASE =
  (typeof window !== "undefined" && window.INSSEPTION_AGENT_BASE) ||
  `${location.origin}/agent`;

function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "className") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2).toLowerCase(), v);
    else if (v != null) node.setAttribute(k, v);
  }
  for (const child of [].concat(children)) {
    if (child == null) continue;
    node.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
  }
  return node;
}

function sanitizeHtml(html) {
  return String(html || "")
    .replace(/<script[\s\S]*?>[\s\S]*?<\/script>/gi, "")
    .replace(/\son\w+="[^"]*"/gi, "")
    .replace(/\son\w+='[^']*'/gi, "");
}

const EXAMPLES = [
  "What is Romania's usually resident population (POP105A)?",
  "Show recent INSSE TEMPO updates",
  "Average number of employees by county — latest year",
];

export function mountChat() {
  if (document.getElementById("insse-chat-root")) return;

  const root = el("div", { id: "insse-chat-root", className: "insse-chat" });
  const fab = el("button", {
    type: "button",
    className: "insse-chat-fab",
    "aria-label": "Open insseption assistant",
    title: "Ask TEMPO",
    text: "✦",
  });
  const panel = el("div", {
    className: "insse-chat-panel",
    hidden: "true",
    role: "dialog",
    "aria-label": "insseption assistant",
  });

  const head = el("div", { className: "insse-chat-head" }, [
    el("div", {}, [
      el("strong", { text: "Ask TEMPO" }),
      el("span", { className: "insse-chat-sub", text: "insseption agent" }),
    ]),
    el("button", {
      type: "button",
      className: "insse-chat-close",
      "aria-label": "Close",
      text: "×",
    }),
  ]);

  const msgs = el("div", { className: "insse-chat-msgs", "aria-live": "polite" });
  const form = el("form", { className: "insse-chat-form" });
  const input = el("textarea", {
    rows: "2",
    placeholder: "Ask about Romanian statistics…",
    maxlength: "2000",
  });
  const send = el("button", { type: "submit", className: "btn", text: "Ask" });
  form.append(input, send);
  panel.append(head, msgs, form);
  root.append(fab, panel);
  document.body.appendChild(root);

  const addMsg = (role, html, chartCfg) => {
    const bubble = el("div", { className: `insse-chat-msg ${role}` });
    const body = el("div", { className: "insse-chat-html" });
    body.innerHTML = sanitizeHtml(html);
    bubble.appendChild(body);
    if (chartCfg?.config && window.Chart) {
      const canvas = el("canvas", { className: "insse-chat-chart" });
      bubble.appendChild(canvas);
      try {
        // eslint-disable-next-line no-new
        new window.Chart(canvas.getContext("2d"), chartCfg.config);
      } catch (_) {
        /* ignore chart errors */
      }
    }
    msgs.appendChild(bubble);
    msgs.scrollTop = msgs.scrollHeight;
  };

  addMsg(
    "bot",
    `<p>Hi — ask in RO / EN / HU. I query <code>insse.csaladen.es</code> TEMPO matrices and can sketch a chart.</p>
     <ul>${EXAMPLES.map((e) => `<li><button type="button" class="insse-chat-ex">${e}</button></li>`).join("")}</ul>`
  );
  msgs.querySelectorAll(".insse-chat-ex").forEach((btn) => {
    btn.addEventListener("click", () => {
      input.value = btn.textContent || "";
      input.focus();
    });
  });

  const setOpen = (open) => {
    if (open) {
      panel.removeAttribute("hidden");
      fab.setAttribute("aria-expanded", "true");
      input.focus();
    } else {
      panel.setAttribute("hidden", "true");
      fab.setAttribute("aria-expanded", "false");
    }
  };

  fab.addEventListener("click", () => setOpen(panel.hasAttribute("hidden")));
  head.querySelector(".insse-chat-close").addEventListener("click", () => setOpen(false));

  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const q = input.value.trim();
    if (!q || send.disabled) return;
    addMsg("user", `<p>${q.replace(/</g, "&lt;")}</p>`);
    input.value = "";
    send.disabled = true;
    send.textContent = "…";
    const thinking = el("div", {
      className: "insse-chat-msg bot pending",
      text: "Querying TEMPO…",
    });
    msgs.appendChild(thinking);
    msgs.scrollTop = msgs.scrollHeight;
    try {
      const res = await fetch(`${AGENT_BASE}/api/query`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ query: q, generate_chart: true }),
      });
      const data = await res.json();
      thinking.remove();
      if (!res.ok) {
        addMsg("bot", `<p>Agent error: ${(data.detail || res.statusText || "").toString()}</p>`);
      } else if (data.error && !data.answer) {
        addMsg("bot", `<p>${String(data.error).replace(/</g, "&lt;")}</p>`);
      } else {
        let html = data.answer || "<p>(empty answer)</p>";
        if (data.matrix) {
          html += `<p class="insse-chat-meta"><code>${data.matrix}</code></p>`;
        }
        addMsg("bot", html, data.chart);
      }
    } catch (err) {
      thinking.remove();
      addMsg("bot", `<p>Network error: ${String(err.message || err)}</p>`);
    } finally {
      send.disabled = false;
      send.textContent = "Ask";
    }
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", mountChat);
} else {
  mountChat();
}
