const API_BASE = "/api/v1";

async function api(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { Accept: "application/json", ...(options.headers || {}) },
    ...options,
  });
  const ct = res.headers.get("content-type") || "";
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body?.error?.message || detail;
    } catch (_) {}
    throw new Error(detail);
  }
  if (ct.includes("application/json")) return res.json();
  return res.text();
}

export const getMeta = () => api("/meta");
export const getHealth = () => api("/health");
export const getContext = (code, lang) =>
  api(code ? `/context/${encodeURIComponent(code)}?lang=${lang}` : `/context?lang=${lang}`);
export const getMatrix = (code, lang) =>
  api(`/matrices/${encodeURIComponent(code)}?lang=${lang}`);
export const queryMatrix = (code, body) =>
  api(`/matrices/${encodeURIComponent(code)}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
export const getNews = () => api("/news");
export const translate = (texts, target) =>
  api("/translate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ texts, target }),
  });

export function csvUrl(code) {
  return `${API_BASE}/matrices/${encodeURIComponent(code)}/query?format=csv`;
}
