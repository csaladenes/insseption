/**
 * Public explore UI at / — plain-language statistics assistant.
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
  // Mapbox GL — same stack as ROEM html/panels/mapbox8.html
  const token =
    window.MAPBOX_ACCESS_TOKEN || window.INSSEPTION_MAPBOX_TOKEN || "";
  if (!window.mapboxgl || !window.topojson) {
    host.textContent = "Map libraries not loaded.";
    return null;
  }
  if (!token) {
    host.textContent = "Map is not configured (missing Mapbox token).";
    return null;
  }

  const mapDiv = el("div", { className: "insse-chat-map" });
  host.appendChild(mapDiv);

  window.mapboxgl.accessToken = token;
  const style =
    window.MAPBOX_STYLE ||
    "mapbox://styles/csaladenes/cku7ljfuy4axr17s9odnoqcaj";
  const map = new window.mapboxgl.Map({
    container: mapDiv,
    style,
    center: [25.1, 46.0],
    zoom: 5.6,
    maxZoom: 11,
    attributionControl: true,
    preserveDrawingBuffer: true, // PNG export
  });
  map.addControl(
    new window.mapboxgl.NavigationControl({ showCompass: false }),
    "top-right"
  );

  const geoUrl = chart.geo || "/geo/romania-counties.json";
  const topo = await fetch(geoUrl).then((r) => r.json());
  const obj = chart.object || Object.keys(topo.objects)[0];
  const geo = window.topojson.feature(topo, topo.objects[obj]);
  const values = chart.values || {};
  const lookup = {};
  for (const [k, v] of Object.entries(values)) lookup[normName(k)] = v;
  const nums = Object.values(values).filter((v) => typeof v === "number");
  const lo = nums.length ? Math.min(...nums) : 0;
  const hi = nums.length ? Math.max(...nums) : 1;
  const prop = chart.name_property || "NAME_1";
  const low = chart.color_low || "#0b1019";
  const high = chart.color_high || "#7096C2";

  for (const feat of geo.features || []) {
    const name = feat.properties?.[prop] || "";
    const val = lookup[normName(name)];
    feat.properties = feat.properties || {};
    feat.properties.value = typeof val === "number" ? val : null;
    feat.properties.label = name;
  }

  const popup = new window.mapboxgl.Popup({
    closeButton: false,
    closeOnClick: false,
    className: "insse-map-popup",
  });

  await new Promise((resolve) => {
    if (map.isStyleLoaded()) resolve();
    else map.once("load", resolve);
  });

  if (map.getSource("counties")) {
    map.removeLayer("counties-fill");
    map.removeLayer("counties-line");
    map.removeSource("counties");
  }
  map.addSource("counties", { type: "geojson", data: geo });
  map.addLayer({
    id: "counties-fill",
    type: "fill",
    source: "counties",
    paint: {
      "fill-color": [
        "case",
        ["==", ["typeof", ["get", "value"]], "number"],
        [
          "interpolate",
          ["linear"],
          ["get", "value"],
          lo,
          low,
          hi === lo ? lo + 1 : hi,
          high,
        ],
        "#1C2331",
      ],
      "fill-opacity": 0.88,
    },
  });
  map.addLayer({
    id: "counties-line",
    type: "line",
    source: "counties",
    paint: {
      "line-color": "#35577D",
      "line-width": 1,
    },
  });

  map.on("mousemove", "counties-fill", (e) => {
    map.getCanvas().style.cursor = "pointer";
    const f = e.features && e.features[0];
    if (!f) return;
    const name = f.properties.label || f.properties[prop] || "";
    const val = f.properties.value;
    const text =
      val == null || val === "null"
        ? `${name}: —`
        : `${name}: ${Number(val).toLocaleString("en-US")}`;
    popup.setLngLat(e.lngLat).setHTML(text).addTo(map);
  });
  map.on("mouseleave", "counties-fill", () => {
    map.getCanvas().style.cursor = "";
    popup.remove();
  });

  try {
    const bounds = new window.mapboxgl.LngLatBounds();
    for (const feat of geo.features || []) {
      const g = feat.geometry;
      if (!g) continue;
      const coords =
        g.type === "Polygon"
          ? g.coordinates[0]
          : g.type === "MultiPolygon"
            ? g.coordinates.flatMap((p) => p[0])
            : [];
      for (const c of coords) bounds.extend(c);
    }
    if (!bounds.isEmpty()) map.fitBounds(bounds, { padding: 28, maxZoom: 7.2 });
  } catch (_) {
    /* keep default Romania view */
  }

  setTimeout(() => map.resize(), 120);
  return { map, mapDiv };
}

const EXAMPLES = [
  "How many people live in Romania?",
  "How many employees are there in each county?",
  "What is the latest population figure for Bucharest?",
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
    el("strong", { text: "Explore statistics" }),
    el("span", {
      className: "insse-chat-sub",
      text: "Ask a question — get official figures, charts, and county maps",
    }),
  ]);

  const msgs = el("div", {
    className: "insse-chat-msgs",
    "aria-live": "polite",
  });
  const form = el("form", { className: "insse-chat-form" });
  const input = el("textarea", {
    rows: "3",
    placeholder: "Try: How many people live in Romania? (RO / EN / HU)",
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
        const cfg = chart.config || {};
        cfg.options = cfg.options || {};
        cfg.options.responsive = true;
        cfg.options.maintainAspectRatio = false;
        cfg.options.plugins = Object.assign(
          {
            legend: { labels: { color: "#F6F6F6", font: { family: "Roboto" } } },
          },
          cfg.options.plugins || {}
        );
        cfg.options.scales = cfg.options.scales || {};
        for (const axis of Object.values(cfg.options.scales)) {
          if (!axis || typeof axis !== "object") continue;
          axis.ticks = Object.assign({ color: "#7096C2" }, axis.ticks || {});
          axis.grid = Object.assign(
            { color: "rgba(112,150,194,0.12)" },
            axis.grid || {}
          );
        }
        new window.Chart(canvas.getContext("2d"), cfg);
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
            text: "Download table (CSV)",
            onClick: () =>
              downloadBlob(
                `${payload.matrix || "romania-statistics"}.csv`,
                new Blob([tableToCsv(table)], { type: "text/csv;charset=utf-8" })
              ),
          })
        );
      }
      actions.appendChild(
        el("button", {
          type: "button",
          className: "btn small",
          text: "Download chart (PNG)",
          onClick: async () => {
            const target =
              exportNode?.mapDiv ||
              exportNode?.canvas ||
              viz.querySelector(".insse-chat-map, canvas");
            if (!target) return;
            if (exportNode?.canvas?.toDataURL) {
              const a = el("a", {
                href: exportNode.canvas.toDataURL("image/png"),
                download: `${payload.matrix || "romania-statistics"}.png`,
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
                `${payload.matrix || "romania-statistics"}.png`,
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

  const fillExample = (text) => {
    input.value = text || "";
    input.focus();
  };

  // Hero suggestion pills (landing)
  const pills = document.getElementById("hero-pills");
  if (pills) {
    for (const ex of EXAMPLES) {
      pills.appendChild(
        el("button", {
          type: "button",
          className: "hero-pill",
          text: ex.length > 64 ? ex.slice(0, 61) + "…" : ex,
          title: ex,
          onClick: () => fillExample(ex),
        })
      );
    }
  }

  addMsg(
    "bot",
    `<p>Ask a question in <strong>Romanian, English or Hungarian</strong> — for example about population or jobs. I’ll find the official figures and show a chart or map when it helps.</p>
     <p class="insse-chat-meta">More detail: <a href="/docs">About the data</a> · <a href="/docs/reference">For developers</a></p>`
  );

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
      text: "Looking up the latest figures…",
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
          `<p>Sorry — something went wrong: ${(
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
        const html = data.answer || "<p>(empty answer)</p>";
        await addMsg("bot", html, data);
      }
    } catch (err) {
      thinking.remove();
      await addMsg(
        "bot",
        `<p>Could not reach the statistics service: ${String(err.message || err)}</p>`
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
