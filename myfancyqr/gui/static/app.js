/* MyFancyQR GUI logic.
 *
 * Talks to the Python Api object either through pywebview
 * (window.pywebview.api.*) or, in browser mode, through POST /api/<method>.
 * All rendering happens in Python (myfancyqr.core); this file only keeps
 * the UI state in sync and debounces render requests.
 */
"use strict";

// Browser mode: explicit ?mode=browser, or no pywebview bridge after a short wait (see the end of file).
let BROWSER_MODE = new URLSearchParams(location.search).get("mode") === "browser";
const STORAGE_KEY = "myfancyqr.params.v1";
const RENDER_DELAY_MS = 90;

// ------------------------------------------------------------------ bridge
const api = new Proxy({}, {
  get: (_, name) => (...args) => {
    if (!BROWSER_MODE && window.pywebview && window.pywebview.api) {
      return window.pywebview.api[name](...args);
    }
    return fetch(`/api/${name}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(args),
    }).then((r) => r.json());
  },
});

// ------------------------------------------------------------------- state
const $ = (id) => document.getElementById(id);
let params = {};
let appState = null;
let renderTimer = null;
let renderSeq = 0;
let lastInfo = null;

function storageGet() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || "null"); } catch { return null; }
}
function storageSet(value) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(value)); } catch { /* private mode */ }
}

function setParam(key, value, { immediate = false } = {}) {
  params[key] = value;
  syncControls();
  scheduleRender(immediate);
}

// ---------------------------------------------------------------- controls
function setPressed(group, value) {
  for (const b of group.querySelectorAll("button")) {
    b.setAttribute("aria-pressed", String(b.dataset.value === String(value)));
  }
}

function syncControls() {
  if (document.activeElement !== $("data")) $("data").value = params.data;
  for (const [key, color, hex] of [["fill", "fill", "fillHex"], ["back", "back", "backHex"]]) {
    if (document.activeElement !== $(hex)) $(hex).value = params[key];
    if (/^#[0-9a-f]{6}$/i.test(params[key])) $(color).value = params[key];
  }
  $("boxSize").value = params.boxSize;
  $("boxSizeOut").textContent = `${params.boxSize} px`;
  $("border").value = params.border;
  $("borderOut").textContent = params.border;
  $("logoScale").value = params.logoScale;
  $("logoScaleOut").textContent = `${params.logoScale} %`;
  for (const id of ["ecc", "logoBackdrop", "invertLogo", "format"]) setPressed($(id), params[id]);
  renderLogoPills();
  $("logoSection").classList.toggle("no-logo", !params.logo);
}

function renderLogoPills() {
  const box = $("logoPills");
  const items = [{ label: "None", value: null }];
  for (const name of appState.logos) items.push({ label: name, value: name });
  const isCustom = params.logo && !appState.logos.includes(params.logo);
  if (isCustom) items.push({ label: params.logoLabel || "Custom", value: params.logo, title: params.logo });
  items.push({ label: "Custom…", value: "__choose__" });

  box.replaceChildren(...items.map((it) => {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = it.label;
    if (it.title) b.title = it.title;
    b.setAttribute("aria-pressed", String(it.value === (params.logo || null)));
    b.addEventListener("click", () => (it.value === "__choose__" ? chooseLogo() : setParam("logo", it.value, { immediate: true })));
    return b;
  }));
}

function bindSegmented(id) {
  $(id).addEventListener("click", (e) => {
    const b = e.target.closest("button[data-value]");
    if (b) setParam($(id).dataset.key, b.dataset.value, { immediate: true });
  });
}

function bindControls() {
  $("data").addEventListener("input", (e) => setParam("data", e.target.value));
  for (const [key, color, hex] of [["fill", "fill", "fillHex"], ["back", "back", "backHex"]]) {
    $(color).addEventListener("input", (e) => setParam(key, e.target.value));
    $(hex).addEventListener("input", (e) => {
      const v = e.target.value.trim();
      if (v) setParam(key, v);
    });
    $(hex).addEventListener("blur", () => syncControls());
  }
  $("swap").addEventListener("click", () => {
    [params.fill, params.back] = [params.back, params.fill];
    syncControls();
    scheduleRender(true);
  });
  for (const key of ["boxSize", "border", "logoScale"]) {
    $(key).addEventListener("input", (e) => setParam(key, Number(e.target.value)));
  }
  for (const id of ["ecc", "logoBackdrop", "invertLogo", "format"]) bindSegmented(id);

  $("exportBtn").addEventListener("click", exportCode);
  $("copyBtn").addEventListener("click", copyImage);
  $("presetsBtn").addEventListener("click", togglePresets);
  $("presetForm").addEventListener("submit", savePreset);
  $("logoFile").addEventListener("change", uploadLogo);

  document.addEventListener("keydown", (e) => {
    const mod = e.metaKey || e.ctrlKey;
    if (mod && (e.key === "e" || e.key === "s")) { e.preventDefault(); exportCode(); }
    else if (mod && e.shiftKey && e.key.toLowerCase() === "c") { e.preventDefault(); copyImage(); }
    else if (e.key === "Escape") closePresets();
  });
  document.addEventListener("click", (e) => {
    if (!e.target.closest(".menu-anchor")) closePresets();
  });
}

// ---------------------------------------------------------------- rendering
function scheduleRender(immediate = false) {
  clearTimeout(renderTimer);
  $("preview").classList.add("stale");
  renderTimer = setTimeout(doRender, immediate ? 0 : RENDER_DELAY_MS);
}

async function doRender() {
  const seq = ++renderSeq;
  const res = await api.render({ ...params });
  if (seq !== renderSeq) return; // a newer request is in flight
  $("preview").classList.remove("stale");
  if (!res || !res.ok) {
    showError(res ? res.error : "Rendering failed.");
    markInvalidColours(res && res.error);
    return;
  }
  hideError();
  markInvalidColours(null);
  $("preview").src = res.image;
  lastInfo = res.info;
  updateDiagnostics(res);
  storageSet(params);
}

function markInvalidColours(error) {
  const bad = (v) => error && error.toLowerCase().includes(String(v).toLowerCase());
  $("fillHex").classList.toggle("invalid", Boolean(bad(params.fill)));
  $("backHex").classList.toggle("invalid", Boolean(bad(params.back)));
}

function showError(msg) {
  const box = $("errorBox");
  box.textContent = msg;
  box.hidden = false;
}
function hideError() { $("errorBox").hidden = true; }

function setChip(id, text, tone = "") {
  const el = $(id);
  el.textContent = text;
  el.className = `chip glass ${tone}`;
}

function updateDiagnostics(res) {
  const i = res.info;
  const fmt = String(params.format).toUpperCase();
  $("dataMeta").textContent = `${i.data_bytes} bytes · version ${i.version} · level ${i.error_correction}`;
  $("subtitle").textContent = `${i.pixel_size} × ${i.pixel_size} px · ${fmt}`;
  setChip("chipVersion", `Version ${i.version} · ${i.modules} × ${i.modules} modules`);
  setChip("chipSize", `${i.pixel_size} × ${i.pixel_size} px`);
  const c = i.contrast_ratio.toFixed(1);
  const tone = i.inverted || i.contrast_ratio < 4 ? "warn" : "ok";
  setChip("chipContrast", `Contrast ${c}:1${i.inverted ? " · inverted" : tone === "ok" ? " ✓" : ""}`, tone);
  if (res.decodes === true) setChip("chipDecode", "✓ Decodes", "ok");
  else if (res.decodes === false) setChip("chipDecode", "✕ Does not decode", "bad");
  else setChip("chipDecode", appState.scanAvailable ? "" : "Scan test off", "");
  $("warnings").replaceChildren(...i.warnings.map((w) => {
    const li = document.createElement("li");
    li.textContent = w;
    return li;
  }));
}

// ------------------------------------------------------------------ logos
async function chooseLogo() {
  if (BROWSER_MODE) { $("logoFile").click(); return; }
  const res = await api.choose_logo();
  if (!res.ok) return toast(res.error, { error: true });
  if (res.cancelled) return;
  params.logoLabel = res.name;
  setParam("logo", res.path, { immediate: true });
}

function uploadLogo(e) {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = async () => {
    const res = await api.upload_logo(file.name, reader.result);
    e.target.value = "";
    if (!res.ok) return toast(res.error, { error: true });
    params.logoLabel = res.name;
    setParam("logo", res.path, { immediate: true });
  };
  reader.readAsDataURL(file);
}

// ----------------------------------------------------------- export / copy
async function exportCode() {
  const res = await api.export({ ...params });
  if (!res.ok) return toast(res.error, { error: true });
  if (res.cancelled) return;
  if (res.download) {
    const a = document.createElement("a");
    a.href = res.download;
    a.download = res.filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    return toast(`Downloaded ${res.filename}`);
  }
  toast(`Saved ${res.path.split(/[\\/]/).pop()}`, {
    action: "Show in Finder",
    onAction: () => api.reveal(res.path),
  });
}

async function copyImage() {
  const res = await api.copy_image({ ...params });
  if (res.ok) return toast("Copied to clipboard");
  // Browser mode: try the async clipboard API with the PNG the server sent back.
  if (res.fallbackImage && navigator.clipboard && window.ClipboardItem) {
    try {
      const blob = await (await fetch(res.fallbackImage)).blob();
      await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
      return toast("Copied to clipboard");
    } catch { /* fall through */ }
  }
  toast(res.error || "Copy failed", { error: true });
}

// ----------------------------------------------------------------- presets
function closePresets() {
  $("presetsMenu").hidden = true;
  $("presetsBtn").setAttribute("aria-expanded", "false");
}

async function togglePresets() {
  const menu = $("presetsMenu");
  if (!menu.hidden) return closePresets();
  const res = await api.list_presets();
  fillPresetList(res.ok ? res.presets : {});
  menu.hidden = false;
  $("presetsBtn").setAttribute("aria-expanded", "true");
  $("presetName").focus();
}

function fillPresetList(presets) {
  const list = $("presetList");
  const names = Object.keys(presets).sort((a, b) => a.localeCompare(b));
  if (!names.length) {
    const li = document.createElement("li");
    li.className = "empty";
    li.textContent = "No saved styles yet";
    list.replaceChildren(li);
    return;
  }
  list.replaceChildren(...names.map((name) => {
    const li = document.createElement("li");
    const apply = document.createElement("button");
    apply.type = "button";
    apply.className = "cap apply";
    apply.textContent = name;
    apply.addEventListener("click", () => {
      params = { ...params, ...presets[name], data: params.data };
      syncControls();
      scheduleRender(true);
      closePresets();
    });
    const del = document.createElement("button");
    del.type = "button";
    del.className = "cap delete";
    del.textContent = "✕";
    del.setAttribute("aria-label", `Delete ${name}`);
    del.addEventListener("click", async () => {
      const r = await api.delete_preset(name);
      if (r.ok) fillPresetList(r.presets);
    });
    li.append(apply, del);
    return li;
  }));
}

async function savePreset(e) {
  e.preventDefault();
  const name = $("presetName").value.trim();
  if (!name) return $("presetName").focus();
  const res = await api.save_preset(name, { ...params });
  if (!res.ok) return toast(res.error, { error: true });
  $("presetName").value = "";
  fillPresetList(res.presets);
  toast(`Saved style “${name}”`);
}

// ------------------------------------------------------------------- toast
let toastTimer = null;
function toast(text, { error = false, action = null, onAction = null } = {}) {
  const el = $("toast");
  $("toastText").textContent = text;
  el.classList.toggle("error", error);
  const btn = $("toastAction");
  btn.hidden = !action;
  btn.textContent = action || "";
  btn.onclick = onAction ? () => { onAction(); el.hidden = true; } : null;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, action ? 6000 : 3000);
}

// -------------------------------------------------------------------- boot
function buildFormatBar() {
  $("format").replaceChildren(...appState.formats.map((f) => {
    const b = document.createElement("button");
    b.type = "button";
    b.dataset.value = f;
    b.textContent = f.toUpperCase();
    return b;
  }));
}

function applyChrome() {
  document.body.classList.toggle("browser", BROWSER_MODE);
  document.body.classList.toggle("unified", Boolean(appState.unifiedTitlebar));
}

async function boot() {
  appState = await api.get_state();
  const saved = storageGet() || {};
  params = { ...appState.defaults, ...saved };
  // A custom logo saved in a previous session may have been moved or deleted;
  // the first render will report it and the user can pick "None".
  buildFormatBar();
  applyChrome();
  bindControls();
  syncControls();
  scheduleRender(true);
  // The macOS title bar is merged asynchronously; pick up the final state.
  if (!BROWSER_MODE && appState.platform === "darwin") {
    setTimeout(async () => { appState.unifiedTitlebar = (await api.get_state()).unifiedTitlebar; applyChrome(); }, 400);
  }
}

window.mfqr = { api, get params() { return params; } };

let booted = false;
function bootOnce() {
  if (booted) return;
  booted = true;
  boot();
}

if (BROWSER_MODE || (window.pywebview && window.pywebview.api)) {
  document.addEventListener("DOMContentLoaded", bootOnce);
} else {
  window.addEventListener("pywebviewready", bootOnce);
  // Opened in a plain browser without ?mode=browser: fall back to HTTP calls.
  setTimeout(() => {
    if (!booted && !window.pywebview) {
      BROWSER_MODE = true;
      bootOnce();
    }
  }, 1500);
}
