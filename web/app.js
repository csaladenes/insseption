import {
  getContext,
  getMatrix,
  getMeta,
  getNews,
  queryMatrix,
  translate,
} from "./api.js";
import { detectLang, loadStrings, t, SUPPORTED } from "./i18n.js";

const state = {
  uiLang: detectLang(),
  dataLang: "ro",
  strings: {},
  catalog: [],
  matrix: null,
  translateEnabled: false,
  treeStack: [], // parent codes for back navigation
};

const $ = (sel) => document.querySelector(sel);

function setStatus(msg, kind = "") {
  const el = $("#status");
  el.textContent = msg || "";
  el.className = `status ${kind}`;
}

function applyStrings() {
  const s = state.strings;
  document.title = `${s.brand} — ${s.tagline}`;
  $("#brand").textContent = s.brand;
  $("#tagline").textContent = s.tagline;
  $("#blurb").textContent = s.blurb;
  $("#search").placeholder = s.search_placeholder;
  $("#browse-title").textContent = s.browse;
  $("#news-title").textContent = s.news;
  $("#run").textContent = s.run_query;
  $("#csv").textContent = s.download_csv;
  $("#curl").textContent = s.copy_curl;
  $("#dims-title").textContent = s.dimensions;
  $("#results-title").textContent = s.results;
  $("#attr").textContent = s.attribution;
  $("#terms").textContent = s.terms;
  $("#docs").textContent = s.api_docs;
  $("#github").textContent = s.github;
  $("#data-lang-label").textContent = s.lang_data;
  document.querySelectorAll("[data-lang-btn]").forEach((btn) => {
    btn.setAttribute("aria-pressed", btn.dataset.langBtn === state.uiLang ? "true" : "false");
  });
}

async function initLang() {
  state.strings = await loadStrings(state.uiLang);
  applyStrings();
}

async function loadCatalog() {
  try {
    const res = await fetch("./catalog.json");
    if (res.ok) state.catalog = await res.json();
  } catch (_) {
    state.catalog = [];
  }
}

async function renderTree(parent = null, { push = true } = {}) {
  const box = $("#tree");
  box.innerHTML = `<li>${t(state.strings, "loading")}</li>`;
  try {
    const data = await getContext(parent, state.dataLang);
    const nodes = data.nodes || [];
    if (push) {
      if (parent == null) state.treeStack = [];
      else if (state.treeStack[state.treeStack.length - 1] !== parent) {
        state.treeStack.push(parent);
      }
    }
    box.innerHTML = "";
    if (state.treeStack.length) {
      const back = document.createElement("li");
      back.innerHTML = `<button type="button">←</button>`;
      back.querySelector("button").onclick = () => {
        state.treeStack.pop();
        const prev = state.treeStack[state.treeStack.length - 1] || null;
        renderTree(prev, { push: false });
      };
      box.appendChild(back);
    }
    for (const n of nodes) {
      const li = document.createElement("li");
      const label = n.name || n.code || "?";
      const isMatrix =
        (n.url || "").toLowerCase() === "matrix" ||
        /^[A-Z][A-Z0-9]{3,9}$/.test(n.code || "");
      li.innerHTML = `<button type="button"><span class="code">${n.code || ""}</span>${label}</button>`;
      li.querySelector("button").onclick = async () => {
        if (isMatrix && n.code) {
          await openMatrix(n.code);
          return;
        }
        if (n.code) renderTree(n.code);
      };
      box.appendChild(li);
    }
  } catch (err) {
    box.innerHTML = `<li class="status err">${err.message}</li>`;
  }
}

async function renderNews() {
  const box = $("#news");
  box.innerHTML = `<li>${t(state.strings, "loading")}</li>`;
  try {
    const data = await getNews();
    box.innerHTML = "";
    for (const item of (data.items || []).slice(0, 40)) {
      const li = document.createElement("li");
      li.innerHTML = `<button type="button"><span class="code">${item.code}</span>${item.date || ""} · ${item.domain || item.activity || ""}</button>`;
      li.querySelector("button").onclick = () => openMatrix(item.code);
      box.appendChild(li);
    }
  } catch (err) {
    box.innerHTML = `<li class="status err">${err.message}</li>`;
  }
}

function renderHits(q) {
  const box = $("#hits");
  const query = q.trim().toLowerCase();
  if (!query) {
    box.hidden = true;
    box.innerHTML = "";
    return;
  }
  const hits = state.catalog
    .filter(
      (x) =>
        (x.code || "").toLowerCase().includes(query) ||
        (x.name || "").toLowerCase().includes(query)
    )
    .slice(0, 30);
  box.hidden = false;
  box.innerHTML = "";
  for (const h of hits) {
    const li = document.createElement("li");
    li.innerHTML = `<button type="button"><span class="code">${h.code}</span>${h.name}</button>`;
    li.querySelector("button").onclick = () => {
      box.hidden = true;
      openMatrix(h.code);
    };
    box.appendChild(li);
  }
  if (!hits.length) {
    box.innerHTML = `<li>${t(state.strings, "empty")}</li>`;
  }
}

async function maybeTranslateLabels(labels) {
  if (state.uiLang !== "hu" || !state.translateEnabled) return labels;
  try {
    const out = await translate(labels, "hu");
    return out.texts || labels;
  } catch (_) {
    return labels;
  }
}

async function openMatrix(code) {
  setStatus(t(state.strings, "loading"));
  $("#matrix").hidden = false;
  try {
    const meta = await getMatrix(code, state.dataLang);
    state.matrix = meta;
    const labels = [meta.name, ...(meta.dimensions || []).map((d) => d.label)];
    const translated = await maybeTranslateLabels(labels);
    const name = translated[0] || meta.name;
    $("#matrix-title").textContent = `${meta.code} — ${name}`;
    if (state.uiLang === "hu" && state.translateEnabled) {
      $("#matrix-title").innerHTML += `<span class="badge">${t(state.strings, "machine_translated")}</span>`;
    }
    const crumbs = (meta.ancestors || [])
      .map((a) => a.name)
      .filter(Boolean)
      .join(" / ");
    $("#crumbs").textContent = crumbs;
    $("#definition").textContent = meta.definition || "";
    const dimsBox = $("#dims");
    dimsBox.innerHTML = "";
    (meta.dimensions || []).forEach((dim, idx) => {
      const wrap = document.createElement("div");
      wrap.className = "dim";
      const title = translated[idx + 1] || dim.label;
      wrap.innerHTML = `<label for="dim-${dim.dim_code}">${title}</label>`;
      const sel = document.createElement("select");
      sel.id = `dim-${dim.dim_code}`;
      sel.multiple = true;
      sel.dataset.dimCode = String(dim.dim_code);
      const lab = (dim.label || "").toLowerCase();
      const isYear = lab.includes("ani") || lab.includes("year") || lab.includes("perioad");
      dim.options.forEach((opt, i) => {
        const o = document.createElement("option");
        o.value = String(opt.nom_item_id);
        o.textContent = opt.label;
        if (isYear && i === dim.options.length - 1) o.selected = true;
        else if (!isYear && /^\s*total\s*$/i.test(opt.label || "")) o.selected = true;
        else if (!isYear && i === 0 && ![...dim.options].some((x) => /^\s*total\s*$/i.test(x.label || "")))
          o.selected = true;
        sel.appendChild(o);
      });
      wrap.appendChild(sel);
      dimsBox.appendChild(wrap);
    });
    $("#results").innerHTML = "";
    setStatus(`${meta.code}`, "ok");
    history.replaceState({}, "", `#${meta.code}`);
  } catch (err) {
    setStatus(err.message, "err");
  }
}

function currentSelections() {
  const selections = {};
  document.querySelectorAll("#dims select").forEach((sel) => {
    const vals = [...sel.selectedOptions].map((o) => Number(o.value));
    if (vals.length) selections[sel.dataset.dimCode] = vals;
  });
  return selections;
}

async function runQuery() {
  if (!state.matrix) return;
  const code = state.matrix.code;
  const body = { lang: state.dataLang, selections: currentSelections() };
  setStatus(t(state.strings, "loading"));
  $("#run").disabled = true;
  try {
    const data = await queryMatrix(code, body);
    const wrap = $("#results");
    if (!data.rows?.length) {
      wrap.innerHTML = `<p>${t(state.strings, "empty")}</p>`;
      setStatus("0 " + t(state.strings, "rows"), "ok");
      return;
    }
    const table = document.createElement("table");
    const thead = document.createElement("thead");
    thead.innerHTML = `<tr>${(data.columns || []).map((c) => `<th>${c}</th>`).join("")}</tr>`;
    const tbody = document.createElement("tbody");
    for (const row of data.rows.slice(0, 200)) {
      tbody.innerHTML += `<tr>${row.map((c) => `<td>${c ?? ""}</td>`).join("")}</tr>`;
    }
    table.append(thead, tbody);
    wrap.innerHTML = "";
    const scroller = document.createElement("div");
    scroller.className = "table-wrap";
    scroller.appendChild(table);
    wrap.appendChild(scroller);
    setStatus(`${data.row_count} ${t(state.strings, "rows")}`, "ok");
  } catch (err) {
    setStatus(err.message, "err");
  } finally {
    $("#run").disabled = false;
  }
}

async function downloadCsv() {
  if (!state.matrix) return;
  const code = state.matrix.code;
  const body = { lang: state.dataLang, selections: currentSelections() };
  const res = await fetch(`/api/v1/matrices/${encodeURIComponent(code)}/query?format=csv`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/csv" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("CSV failed");
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `${code}.csv`;
  a.click();
  URL.revokeObjectURL(a.href);
}

function copyCurl() {
  if (!state.matrix) return;
  const code = state.matrix.code;
  const body = { lang: state.dataLang, selections: currentSelections() };
  const curl = `curl -sS -X POST '${location.origin}/api/v1/matrices/${code}/query' \\\n  -H 'content-type: application/json' \\\n  -d '${JSON.stringify(body)}'`;
  navigator.clipboard.writeText(curl);
  setStatus("curl → clipboard", "ok");
}

async function boot() {
  await initLang();
  await loadCatalog();
  try {
    const meta = await getMeta();
    state.translateEnabled = !!meta.translate_enabled;
  } catch (_) {}

  document.querySelectorAll("[data-lang-btn]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      state.uiLang = btn.dataset.langBtn;
      localStorage.setItem("insseption.lang", state.uiLang);
      await initLang();
      if (state.matrix) openMatrix(state.matrix.code);
    });
  });

  $("#data-lang").value = state.dataLang;
  $("#data-lang").addEventListener("change", (e) => {
    state.dataLang = e.target.value;
    renderTree(null);
    renderNews();
    if (state.matrix) openMatrix(state.matrix.code);
  });

  $("#search").addEventListener("input", (e) => renderHits(e.target.value));
  $("#run").addEventListener("click", runQuery);
  $("#csv").addEventListener("click", () => downloadCsv().catch((e) => setStatus(e.message, "err")));
  $("#curl").addEventListener("click", copyCurl);

  // ensure lang buttons exist for all supported
  const switcher = $("#lang-switch");
  switcher.innerHTML = "";
  for (const lang of SUPPORTED) {
    const b = document.createElement("button");
    b.type = "button";
    b.dataset.langBtn = lang;
    b.textContent = lang.toUpperCase();
    b.setAttribute("aria-pressed", lang === state.uiLang ? "true" : "false");
    b.addEventListener("click", async () => {
      state.uiLang = lang;
      localStorage.setItem("insseption.lang", lang);
      await initLang();
      if (state.matrix) openMatrix(state.matrix.code);
    });
    switcher.appendChild(b);
  }

  await Promise.all([renderTree(null), renderNews()]);
  const hash = location.hash.replace("#", "").trim();
  if (hash) openMatrix(hash);
}

boot();
