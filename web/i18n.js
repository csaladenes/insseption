const SUPPORTED = ["ro", "en", "hu"];

export function detectLang() {
  const saved = localStorage.getItem("insseption.lang");
  if (saved && SUPPORTED.includes(saved)) return saved;
  const nav = (navigator.language || "ro").slice(0, 2).toLowerCase();
  return SUPPORTED.includes(nav) ? nav : "ro";
}

export async function loadStrings(lang) {
  const res = await fetch(`./i18n/${lang}.json`);
  if (!res.ok) throw new Error("i18n load failed");
  return res.json();
}

export function t(dict, key) {
  return dict[key] || key;
}

export { SUPPORTED };
