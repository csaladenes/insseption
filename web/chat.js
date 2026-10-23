/**
 * Public explore UI at / — plain-language, trilingual (RO/HU/EN).
 * Agent: ${origin}/agent  · skill: insseption-agents
 */

import {
  detectLang,
  loadStrings,
  setLang,
  SUPPORTED,
  NAMES,
  t as tr,
} from "./i18n.js";

const AGENT_BASE =
  (typeof window !== "undefined" && window.INSSEPTION_AGENT_BASE) ||
  `${location.origin}/agent`;

const SESSION_KEY = "insseption.session_id";
const HISTORY_KEY = "insseption.chat_history";
const ACTIVITY_KEY = "insseption.chat_active_at";
const SESSION_TTL_MS = 30 * 60 * 1000;

function loadClientHistory() {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    const arr = raw ? JSON.parse(raw) : [];
    return Array.isArray(arr) ? arr.slice(-16) : [];
  } catch (_) {
    return [];
  }
}

function saveClientHistory(history) {
  localStorage.setItem(HISTORY_KEY, JSON.stringify((history || []).slice(-16)));
  localStorage.setItem(ACTIVITY_KEY, String(Date.now()));
}

function touchActivity() {
  localStorage.setItem(ACTIVITY_KEY, String(Date.now()));
}

function clientSessionExpired() {
  const ts = Number(localStorage.getItem(ACTIVITY_KEY) || 0);
  return ts > 0 && Date.now() - ts > SESSION_TTL_MS;
}

function getSessionId() {
  if (clientSessionExpired()) {
    localStorage.removeItem(SESSION_KEY);
    localStorage.removeItem(HISTORY_KEY);
    return null;
  }
  return localStorage.getItem(SESSION_KEY) || null;
}

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

function formatNum(n, lang = "en") {
  try {
    return Number(n).toLocaleString(lang === "ro" ? "ro-RO" : lang === "hu" ? "hu-HU" : "en-US");
  } catch (_) {
    return String(n);
  }
}

/** mapbox8 palette: green → yellow → magenta/red (low → high), 5 quintiles */
const MAP_QUINTILE_COLORS = [
  "#239f69",
  "#8fbf4a",
  "#f5d232",
  "#c52b69",
  "#850237",
];

function assignQuintiles(features) {
  const items = [];
  for (const f of features || []) {
    const v = f.properties?.value;
    if (typeof v === "number" && Number.isFinite(v)) items.push({ f, v });
    else if (f.properties) f.properties.qbin = null;
  }
  items.sort((a, b) => a.v - b.v);
  const n = items.length;
  for (let i = 0; i < n; i++) {
    const bin = Math.min(4, Math.floor((i * 5) / n));
    items[i].f.properties.qbin = bin;
  }
}

function buildMapLegend(ranges, lang, title) {
  const wrap = el("div", { className: "insse-map-legend" });
  if (title) {
    wrap.appendChild(el("div", { className: "insse-map-legend-title", text: title }));
  }
  const row = el("div", { className: "insse-map-legend-row" });
  for (const r of ranges) {
    const item = el("div", { className: "insse-map-legend-item" });
    item.appendChild(
      el("span", {
        className: "insse-map-legend-swatch",
        style: `background:${r.color}`,
      })
    );
    const label =
      r.lo === r.hi
        ? formatNum(r.lo, lang)
        : `${formatNum(r.lo, lang)} – ${formatNum(r.hi, lang)}`;
    item.appendChild(el("span", { className: "insse-map-legend-label", text: label }));
    row.appendChild(item);
  }
  wrap.appendChild(row);
  return wrap;
}

async function renderChoropleth(host, chart, opts = {}) {
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

  host.innerHTML = "";
  const lang = opts.lang || "en";
  const titleText = chart.title || opts.mapTitle || "";
  if (titleText) {
    host.appendChild(el("div", { className: "insse-map-caption", text: titleText }));
  }

  const mapDiv = el("div", { className: "insse-chat-map" });
  // legend inserted above map after ranges known — placeholder first
  const legendHost = el("div", { className: "insse-map-legend-host" });
  host.appendChild(legendHost);
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
  const prop = chart.name_property || "NAME_1";
  const colors =
    Array.isArray(chart.colors) && chart.colors.length >= 5
      ? chart.colors.slice(0, 5)
      : MAP_QUINTILE_COLORS;

  for (const feat of geo.features || []) {
    const name = feat.properties?.[prop] || "";
    const val = lookup[normName(name)];
    feat.properties = feat.properties || {};
    feat.properties.value = typeof val === "number" ? val : null;
    feat.properties.label = name;
  }
  assignQuintiles(geo.features || []);
  const byBin = {};
  for (const feat of geo.features || []) {
    const b = feat.properties.qbin;
    if (b == null) continue;
    const v = feat.properties.value;
    if (!byBin[b]) byBin[b] = { color: colors[b] || MAP_QUINTILE_COLORS[b], lo: v, hi: v, count: 0 };
    byBin[b].lo = Math.min(byBin[b].lo, v);
    byBin[b].hi = Math.max(byBin[b].hi, v);
    byBin[b].count += 1;
  }
  const legendRanges = Object.keys(byBin)
    .map(Number)
    .sort((a, b) => a - b)
    .map((b) => byBin[b]);
  legendHost.appendChild(
    buildMapLegend(
      legendRanges,
      lang,
      opts.legendTitle || "Legend (quintiles)"
    )
  );

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

  const matchExpr = ["match", ["get", "qbin"]];
  for (let i = 0; i < 5; i++) matchExpr.push(i, colors[i] || MAP_QUINTILE_COLORS[i]);
  matchExpr.push("#1C2331");

  map.addLayer({
    id: "counties-fill",
    type: "fill",
    source: "counties",
    paint: {
      "fill-color": [
        "case",
        ["==", ["typeof", ["get", "qbin"]], "number"],
        matchExpr,
        "#1C2331",
      ],
      "fill-opacity": 0.9,
    },
  });
  map.addLayer({
    id: "counties-line",
    type: "line",
    source: "counties",
    paint: {
      "line-color": "#1a2433",
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
        : `${name}: ${formatNum(val, lang)}`;
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
  return { map, mapDiv, host };
}


const GLOBE = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><circle cx="12" cy="12" r="9.5"/><path d="M2.5 12h19M12 2.5c2.6 2.8 3.9 6 3.9 9.5s-1.3 6.7-3.9 9.5M12 2.5C9.4 5.3 8.1 8.5 8.1 12s1.3 6.7 3.9 9.5"/></svg>`;
const CHEVRON = `<svg class="chev" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M2 4.5l4 4 4-4"/></svg>`;

function fillTemplate(s, vars = {}) {
  return String(s || "").replace(/\{\{(\w+)\}\}/g, (_, k) => vars[k] ?? "");
}

function applyPageI18n(dict) {
  document.documentElement.lang = dict._lang || "en";
  if (dict.title) document.title = dict.title;
  const meta = document.querySelector('meta[name="description"]');
  if (meta && dict.description) meta.setAttribute("content", dict.description);

  document.querySelectorAll("[data-i18n]").forEach((node) => {
    const key = node.getAttribute("data-i18n");
    if (key && dict[key] != null) node.textContent = dict[key];
  });
  document.querySelectorAll("[data-i18n-html]").forEach((node) => {
    const key = node.getAttribute("data-i18n-html");
    if (key && dict[key] != null) node.innerHTML = dict[key];
  });
  document.querySelectorAll("[data-i18n-href]").forEach((node) => {
    const key = node.getAttribute("data-i18n-href");
    if (key && dict[key] != null) node.setAttribute("href", dict[key]);
  });
}

function renderLangSwitch(host, lang, onChange) {
  if (!host) return;
  const items = SUPPORTED.map(
    (code) =>
      `<li><a href="#${code}" hreflang="${code}" lang="${code}"${
        code === lang ? " aria-current=\"true\"" : ""
      }>${NAMES[code]}</a></li>`
  ).join("");
  host.innerHTML = `<details class="lang-switch"><summary aria-label="${tr(
    { lang_label: "Language" },
    "lang_label"
  )}: ${NAMES[lang]}">${GLOBE}<span>${lang.toUpperCase()}</span>${CHEVRON}</summary><ul>${items}</ul></details>`;
  // fix label with real dict via host dataset later; summary rebuilt in apply
  host.querySelectorAll("a[hreflang]").forEach((a) => {
    a.addEventListener("click", (ev) => {
      ev.preventDefault();
      const code = a.getAttribute("hreflang");
      const details = host.querySelector("details");
      if (details) details.open = false;
      onChange(code);
    });
  });
}

export 
let EXAMPLE_POOL = null;
async function loadExamplePool() {
  if (EXAMPLE_POOL) return EXAMPLE_POOL;
  try {
    const res = await fetch("/examples.json", { cache: "no-cache" });
    EXAMPLE_POOL = await res.json();
  } catch (_) {
    EXAMPLE_POOL = {};
  }
  return EXAMPLE_POOL;
}

function pickRandomExamples(pool, lang, n = 3) {
  const list = (pool && pool[lang]) || (pool && pool.en) || [];
  if (!list.length) return [];
  const copy = list.slice();
  for (let i = copy.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy.slice(0, Math.min(n, copy.length));
}

function wireSuggestionButtons(root, onSubmit) {
  if (!root || typeof onSubmit !== "function") return;
  const SUGGEST_RE =
    /(propun|suggest|recommend|ajánl|próbáld|try also|you could also|poți întreba|mai poți|related|încearcă|kerdezhet|kérdezhet)/i;

  const activate = (btn, text) => {
    btn.type = "button";
    btn.classList.add("insse-chat-suggest");
    btn.addEventListener("click", (ev) => {
      ev.preventDefault();
      onSubmit(text);
    });
  };

  root.querySelectorAll("button.insse-chat-suggest, button[data-suggest]").forEach((btn) => {
    const text = (btn.getAttribute("data-suggest") || btn.textContent || "").trim();
    if (text) activate(btn, text);
  });

  root.querySelectorAll("h3, h4, p, strong").forEach((h) => {
    if (!SUGGEST_RE.test(h.textContent || "")) return;
    let list = h.nextElementSibling;
    while (list && list.tagName !== "UL" && list.tagName !== "OL") {
      list = list.nextElementSibling;
    }
    if (!list) return;
    list.classList.add("insse-suggest-list");
    list.querySelectorAll(":scope > li").forEach((li) => {
      if (li.querySelector("button")) {
        const b = li.querySelector("button");
        activate(b, (b.textContent || "").trim());
        return;
      }
      const text = (li.textContent || "").trim();
      if (!text) return;
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "insse-chat-suggest";
      btn.textContent = text;
      li.textContent = "";
      li.appendChild(btn);
      activate(btn, text);
    });
  });
}

async function mountChat() {
  const mount =
    document.getElementById("insse-chat-mount") || document.body;
  if (document.getElementById("insse-chat-root")) return;

  let lang = detectLang();
  let dict = await loadStrings(lang);
  dict._lang = lang;

  const root = el("div", { id: "insse-chat-root", className: "insse-chat" });
  const panel = el("div", {
    className: "insse-chat-panel",
    role: "main",
    "aria-label": "insseption assistant",
  });

  const head = el("div", { className: "insse-chat-head" }, [
    el("strong", { className: "chat-title", text: "" }),
    el("span", { className: "insse-chat-sub chat-sub", text: "" }),
  ]);

  const msgs = el("div", {
    className: "insse-chat-msgs",
    "aria-live": "polite",
  });
  const form = el("form", { className: "insse-chat-form" });
  const input = el("textarea", {
    rows: "3",
    maxlength: "2000",
    autofocus: "true",
  });
  const send = el("button", { type: "submit", className: "btn", text: "" });
  form.append(input, send);
  panel.append(head, msgs, form);
  root.append(panel);
  mount.appendChild(root);

  const submitQuery = (text) => {
    const q = (text || "").trim();
    if (!q) return;
    input.value = q;
    form.requestSubmit();
  };

  const fillExample = (text) => {
    input.value = text || "";
    input.focus();
  };

  const renderPills = async () => {
    const pills = document.getElementById("hero-pills");
    if (!pills) return;
    pills.innerHTML = "";
    const pool = await loadExamplePool();
    let picked = pickRandomExamples(pool, lang, 3);
    if (!picked.length) {
      picked = [dict.ex1, dict.ex2, dict.ex3].filter(Boolean);
    }
    for (const ex of picked) {
      pills.appendChild(
        el("button", {
          type: "button",
          className: "hero-pill",
          text: ex.length > 64 ? ex.slice(0, 61) + "…" : ex,
          title: ex,
          onClick: () => submitQuery(ex),
        })
      );
    }
  };

  const showWelcome = () => {
    msgs.innerHTML = "";
    const meta = fillTemplate(dict.welcome_meta, {
      docs: dict.docs_path || "/docs/en",
      ref: dict.ref_path || "/docs/en/reference",
    });
    addMsg(
      "bot",
      `<p>${dict.welcome}</p><p class="insse-chat-meta">${meta}</p>`
    );
  };

  const applyChrome = () => {
    applyPageI18n(dict);
    head.querySelector(".chat-title").textContent = dict.chat_title || "";
    head.querySelector(".chat-sub").textContent = dict.chat_sub || "";
    input.placeholder = dict.placeholder || "";
    send.textContent = dict.ask || "Ask";
    renderPills();
    const langHost = document.getElementById("lang-switch");
    renderLangSwitch(langHost, lang, async (code) => {
      if (!SUPPORTED.includes(code) || code === lang) return;
      lang = code;
      setLang(lang);
      dict = await loadStrings(lang);
      dict._lang = lang;
      applyChrome();
      showWelcome();
    });
    // refresh aria label with translated lang_label
    const summary = langHost?.querySelector("summary");
    if (summary) {
      summary.setAttribute(
        "aria-label",
        `${dict.lang_label || "Language"}: ${NAMES[lang]}`
      );
    }
  };

  const addMsg = async (role, html, payload = {}) => {
    const bubble = el("div", { className: `insse-chat-msg ${role}` });
    const body = el("div", { className: "insse-chat-html" });
    body.innerHTML = sanitizeHtml(html);
    wireSuggestionButtons(body, submitQuery);
    bubble.appendChild(body);

    const viz = el("div", { className: "insse-chat-viz" });
    let exportNode = null;
    const chart = payload.chart;
    if (chart?.type === "choropleth" || chart?.kind === "map") {
      exportNode = await renderChoropleth(viz, chart, {
        lang,
        legendTitle: dict.map_legend || "Legend (quintiles)",
        mapTitle: chart.title || "",
      });
      bubble.appendChild(viz);
    } else if (chart?.config && window.Chart) {
      const wrap = el("div", { className: "insse-chat-chart-wrap" });
      const canvas = el("canvas", { className: "insse-chat-chart" });
      wrap.appendChild(canvas);
      viz.appendChild(wrap);
      bubble.appendChild(viz);
      try {
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
            text: dict.download_csv || "Download table (CSV)",
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
          text: dict.download_png || "Download chart (PNG)",
          onClick: async () => {
            const target =
              exportNode?.host ||
              exportNode?.mapDiv ||
              exportNode?.canvas ||
              viz.querySelector(".insse-chat-viz, .insse-chat-map, canvas") ||
              viz;
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

  applyChrome();
  showWelcome();

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
      text: dict.thinking || "…",
    });
    msgs.appendChild(thinking);
    msgs.scrollTop = msgs.scrollHeight;
    try {
      let history = loadClientHistory();
      if (clientSessionExpired()) {
        history = [];
        localStorage.removeItem(SESSION_KEY);
        localStorage.removeItem(HISTORY_KEY);
      }
      const payload = JSON.stringify({
        query: q,
        generate_chart: true,
        lang,
        session_id: getSessionId(),
        history,
      });
      let res;
      let data = {};
      for (let attempt = 0; attempt < 2; attempt++) {
        const ctl = new AbortController();
        const timer = setTimeout(() => ctl.abort(), 95000);
        try {
          res = await fetch(`${AGENT_BASE}/api/query`, {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: payload,
            signal: ctl.signal,
          });
        } finally {
          clearTimeout(timer);
        }
        const raw = await res.text();
        try {
          data = JSON.parse(raw);
        } catch (_) {
          data = { detail: "" };
        }
        if (![502, 503, 504, 524].includes(res.status)) break;
      }
      thinking.remove();
      if (data.session_id) localStorage.setItem(SESSION_KEY, data.session_id);
      // keep a light client history for resume / first hop
      const next = history.concat([
        { role: "user", content: q },
        {
          role: "assistant",
          content: String(data.answer || "")
            .replace(/<[^>]+>/g, " ")
            .replace(/\s+/g, " ")
            .trim()
            .slice(0, 800),
        },
      ]);
      saveClientHistory(next);
      touchActivity();
      if (!res.ok) {
        await addMsg(
          "bot",
          `<p>${dict.error_agent || "Error"}: ${(
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
        await addMsg("bot", data.answer || "<p>(…)</p>", data);
      }
    } catch (err) {
      thinking.remove();
      const msg =
        err && err.name === "AbortError"
          ? dict.error_timeout || "The query took too long."
          : dict.error_network || "Network error";
      await addMsg("bot", `<p>${msg}</p>`);
    } finally {
      send.disabled = false;
      send.textContent = dict.ask || "Ask";
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
  document.addEventListener("DOMContentLoaded", () => {
    mountChat().catch((err) => console.error(err));
  });
} else {
  mountChat().catch((err) => console.error(err));
}
