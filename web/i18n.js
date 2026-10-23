const SUPPORTED = ["ro", "hu", "en"];
const NAMES = { ro: "Română", hu: "Magyar", en: "English" };

export function detectLang() {
  const saved = localStorage.getItem("insseption.lang");
  if (saved && SUPPORTED.includes(saved)) return saved;
  const nav = (navigator.language || "ro").slice(0, 2).toLowerCase();
  return SUPPORTED.includes(nav) ? nav : "ro";
}

export async function loadStrings(lang) {
  const res = await fetch(`./i18n/${lang}.json`, { cache: "no-cache" });
  if (!res.ok) throw new Error("i18n load failed");
  return res.json();
}

export function t(dict, key, fallback = "") {
  return (dict && dict[key]) || fallback || key;
}

export function setLang(lang) {
  if (!SUPPORTED.includes(lang)) return;
  localStorage.setItem("insseption.lang", lang);
}

/** TEMPO data language: hu UI still queries ro labels upstream. */
export function dataLang(uiLang) {
  return uiLang === "en" ? "en" : "ro";
}

export { SUPPORTED, NAMES };
