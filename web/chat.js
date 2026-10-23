/**
 * Ask TEMPO chat — docs-shell UI at /chat.
 * Agent: ${origin}/agent  · skill: insseption-agents
 */
const AGENT_BASE =
  (typeof window !== "undefined" && window.INSSEPTION_AGENT_BASE) ||
  `${location.origin}/agent`;

function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "className") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (k.startsWith("on") && typeof v === "function")
      node.addEventListener(k.slice(2).toLowerCase(), v);
    else if (v != null) node.setAttribute(k, v);
  }
  for (const child of [].concat(children)) {
    if (child == null) continue;
    node.appendChild(
      typeof child === "string" ? document.createTextNode(child) : child
    );
  }
  return node;
}

function sanitizeHtml(html) {
  return String(html || "")
    .replace(/<script[\s\S]*?>[\s\S]*?<\/script>/gi, "")
    .replace(/\son\w+="[^"]*"/gi, "")
    .replace(/\son\w+='[^']*'/gi, "");
}

function downloadBlob(filename, blob) {
  const a = el("a", {
    href: URL.createObjectURL(blob),
    download: filename,
  });
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}

function tableToCsv(table) {
  const cols = table?.columns || ["label", "value"];
  const rows = table?.rows || [];
  const esc = (v) => {
    const s = String(v ?? "");
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [cols.map(esc).join(","), ...rows.map((r) => r.map(esc).join(","))].join(
    "\n"
  );
}

function lerpColor(a, b, t) {
  const p = (hex) => [
    parseInt(hex.slice(1, 3), 16),
    parseInt(hex.slice(3, 5), 16),
    parseInt(hex.slice(5, 7), 16),
  ];
  const A = p(a),
    B = p(b);
  const c = A.map((x, i) => Math.round(x + (B[i] - x) * t));
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}

function normName(s) {
  return String(s || "")
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .toLowerCase()
    .replace(/municipiul\s+/g, "")
    .replace(/bucuresti|bucharest/g, "bucharest")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

async function renderChoropleth(host, chart) {
  if (!window.L || !window.topojson) {
    host.textContent = "Map libraries not loaded.";
    return null;
  }
  const mapDiv = el("div", { className: "insse-chat-map" });
  host.appendChild(mapDiv);
  const map = window.L.map(mapDiv, {
    zoomControl: true,
    attributionControl: true,
  }).setView([45.9, 25.0], 6);
  window.L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
    attribution: "&copy; OSM &copy; CARTO",
    maxZoom: 12,
  }).addTo(map);

  const geoUrl = chart.geo || "/geo/romania-counties.json";
  const topo = await fetch(geoUrl).then((r) => r.json());
  const obj = chart.object || Object.keys(topo.objects)[0];
  const geo = window.topojson.feature(topo, topo.objects[obj]);
  const values = chart.values || {};
  const lookup = {};
  for (const [k, v] of Object.entries(values)) lookup[normName(k)] = v;
  const nums = Object.values(values).filter((v) => typeof v === "number");
  const lo = Math.min(...nums);
  const hi = Math.max(...nums);
  const prop = chart.name_property || "NAME_1";
  const low = chart.color_low || "#0b1019";
  const high = chart.color_high || "#7096C2";

  const layer = window.L.geoJSON(geo, {
    style(feat) {
      const name = feat.properties?.[prop] || "";
      const val = lookup[normName(name)];
      const t = val == null || hi === lo ? 0 : (val - lo) / (hi - lo);
      return {
        color: "#35577D",
        weight: 1,
        fillColor: val == null ? "#1C2331" : lerpColor(low, high, t),
        fillOpacity: 0.85,
      };
    },
    onEachFeature(feat, lyr) {
      const name = feat.properties?.[prop] || "";
      const val = lookup[normName(name)];
      lyr.bindTooltip(
        `${name}: ${val == null ? "—" : val.toLocaleString("en-US")}`,
        { sticky: true }
      );
    },
  }).addTo(map);
  try {
    map.fitBounds(layer.getBounds(), { padding: [12, 12] });
  } catch (_) {
    /* ignore */
  }
  setTimeout(() => map.invalidateSize(), 80);
  return { map, mapDiv };
}

const EXAMPLES = [
  "What is Romania's usually resident population (POP105A)?",
  "Show recent INSSE TEMPO updates",
  "Average number of employees by county — latest year",
];

export function mountChat() {
  const mount =
    document.getElementById("insse-chat-mount") || document.body;
  if (document.getElementById("insse-chat-root")) return;

  const root = el("div", { id: "insse-chat-root", className: "insse-chat" });
  const panel = el("div", {
    className: "insse-chat-panel",
    role: "main",
    "aria-label": "insseption assistant",
  });

  const head = el("div", { className: "insse-chat-head" }, [
    el("strong", { text: "Ask TEMPO" }),
    el("span", {
      className: "insse-chat-sub",
      text: "Natural language → INSSE matrices, charts, and county maps",
    }),
  ]);

  const msgs = el("div", {
    className: "insse-chat-msgs",
    "aria-live": "polite",
  });
  const form = el("form", { className: "insse-chat-form" });
  const input = el("textarea", {
    rows: "3",
    placeholder: "Ask about Romanian statistics in RO / EN / HU…",
    maxlength: "2000",
    autofocus: "true",
  });
  const send = el("button", { type: "submit", className: "btn", text: "Ask" });
  form.append(input, send);
  panel.append(head, msgs, form);
  root.append(panel);
  mount.appendChild(root);

  const addMsg = async (role, html, payload = {}) => {
    const bubble = el("div", { className: `insse-chat-msg ${role}` });
    const body = el("div", { className: "insse-chat-html" });
    body.innerHTML = sanitizeHtml(html);
    bubble.appendChild(body);

    const viz = el("div", { className: "insse-chat-viz" });
    let exportNode = null;
    const chart = payload.chart;
    if (chart?.type === "choropleth" || chart?.kind === "map") {
      exportNode = await renderChoropleth(viz, chart);
      bubble.appendChild(viz);
    } else if (chart?.config && window.Chart) {
      const wrap = el("div", { className: "insse-chat-chart-wrap" });
      const canvas = el("canvas", { className: "insse-chat-chart" });
      wrap.appendChild(canvas);
      viz.appendChild(wrap);
      bubble.appendChild(viz);
      try {
        // eslint-disable-next-line no-new
        new window.Chart(canvas.getContext("2d"), chart.config);
        exportNode = { canvas };
      } catch (_) {
        /* ignore */
      }
    }

    const table = payload.table;
    if (table?.rows?.length || exportNode) {
      const actions = el("div", { className: "insse-chat-actions" });
      if (table?.rows?.length) {
        actions.appendChild(
          el("button", {
            type: "button",
            className: "btn small",
            text: "Download CSV",
            onClick: () =>
              downloadBlob(
                `${payload.matrix || "tempo"}.csv`,
                new Blob([tableToCsv(table)], { type: "text/csv;charset=utf-8" })
              ),
          })
        );
      }
      actions.appendChild(
        el("button", {
          type: "button",
          className: "btn small",
          text: "Download PNG",
          onClick: async () => {
            const target =
              exportNode?.mapDiv ||
              exportNode?.canvas ||
              viz.querySelector(".insse-chat-map, canvas");
            if (!target) return;
            if (exportNode?.canvas?.toDataURL) {
              const a = el("a", {
                href: exportNode.canvas.toDataURL("image/png"),
                download: `${payload.matrix || "tempo"}.png`,
              });
              document.body.appendChild(a);
              a.click();
              a.remove();
              return;
            }
            if (window.html2canvas) {
              const shot = await window.html2canvas(target, {
                backgroundColor: "#0b1019",
                scale: 2,
              });
              downloadBlob(
                `${payload.matrix || "tempo"}.png`,
                await new Promise((res) =>
                  shot.toBlob((b) => res(b), "image/png")
                )
              );
            }
          },
        })
      );
      bubble.appendChild(actions);
    }

    msgs.appendChild(bubble);
    msgs.scrollTop = msgs.scrollHeight;
  };

  addMsg(
    "bot",
    `<p>Ask TEMPO in RO / EN / HU. Pipeline: <strong>1</strong> find dataset codes → <strong>2</strong> return the DB query → <strong>3</strong> clean/analyze → <strong>4</strong> table + chart.</p>
     <ul>${EXAMPLES.map(
       (e) =>
         `<li><button type="button" class="insse-chat-ex">${e}</button></li>`
     ).join("")}</ul>
     <p class="insse-chat-meta">JSON API guide: <a href="/docs">/docs</a> · agent: <code>/agent</code></p>`
  );
  msgs.querySelectorAll(".insse-chat-ex").forEach((btn) => {
    btn.addEventListener("click", () => {
      input.value = btn.textContent || "";
      input.focus();
    });
  });

  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const q = input.value.trim();
    if (!q || send.disabled) return;
    await addMsg("user", `<p>${q.replace(/</g, "&lt;")}</p>`);
    input.value = "";
    send.disabled = true;
    send.textContent = "…";
    const thinking = el("div", {
      className: "insse-chat-msg bot pending",
      text: "1·translate → 2·query → 3·analyze → 4·present…",
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
        await addMsg(
          "bot",
          `<p>Agent error: ${(
            data.detail ||
            res.statusText ||
            ""
          ).toString()}</p>`
        );
      } else if (data.error && !data.answer) {
        await addMsg(
          "bot",
          `<p>${String(data.error).replace(/</g, "&lt;")}</p>`
        );
      } else {
        let html = data.answer || "<p>(empty answer)</p>";
        const dq = data.db_query || data.plan;
        if (dq && !html.includes("insse-chat-query")) {
          const code = dq.matrix || data.matrix || "?";
          const note = dq.note ? ` — ${String(dq.note).replace(/</g, "&lt;")}` : "";
          html =
            `<p class="insse-chat-query"><strong>Query</strong> · <code>${code}</code>${note}</p>` +
            html;
        } else if (data.matrix && !html.includes(data.matrix)) {
          html += `<p class="insse-chat-meta"><code>${data.matrix}</code></p>`;
        }
        await addMsg("bot", html, data);
      }
    } catch (err) {
      thinking.remove();
      await addMsg(
        "bot",
        `<p>Network error: ${String(err.message || err)}</p>`
      );
    } finally {
      send.disabled = false;
      send.textContent = "Ask";
      input.focus();
    }
  });

  input.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" && !ev.shiftKey) {
      ev.preventDefault();
      form.requestSubmit();
    }
  });
  input.focus();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", mountChat);
} else {
  mountChat();
}
