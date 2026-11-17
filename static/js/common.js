// Shared helpers for all pages: API, WebSocket, formatting, i18n, small charts.
const DEMO_CLIENT_ID = 1; // Сауле Ахметова, the main demo client

// The client this page shows: /client?c=7 opens another (e.g. a freshly created) account; remembered per browser.
const CLIENT_ID = (() => {
  const q = new URLSearchParams(location.search), fromUrl = parseInt(q.get("c"), 10);
  if (location.pathname.startsWith("/client")) {
    if (fromUrl > 0) { try { localStorage.setItem("bcc.clientId", String(fromUrl)); } catch (_) {} return fromUrl; }
    try { const v = parseInt(localStorage.getItem("bcc.clientId"), 10); if (v > 0) return v; } catch (_) {}
  }
  return DEMO_CLIENT_ID;
})();

// Telegram Mini App: every request carries Telegram's signed initData, the server checks the signature.
const TG = window.Telegram?.WebApp?.initData ? window.Telegram.WebApp : null;

// Access keys from a personal link: ?key=… (presenter/analyst) and ?rk=… (trusted contact).
// They are kept in this browser and removed from the address bar so they don't show on the projector.
const KEYS = (() => {
  const store = { get: (k) => { try { return localStorage.getItem(k) || ""; } catch (_) { return ""; } },
    set: (k, v) => { try { localStorage.setItem(k, v); } catch (_) {} } };
  const q = new URLSearchParams(location.search);
  let changed = false;
  for (const [param, name] of [["key", "bcc.adminKey"], ["rk", "bcc.relativeKey"]]) {
    if (q.has(param)) { store.set(name, q.get(param)); q.delete(param); changed = true; }
  }
  if (changed) history.replaceState(null, "", location.pathname + (q.toString() ? "?" + q : "") + location.hash);
  return { admin: store.get("bcc.adminKey"), relative: store.get("bcc.relativeKey") };
})();

async function api(path, opts = {}) {
  const init = { method: opts.method || (opts.body !== undefined ? "POST" : "GET"), headers: {} };
  if (KEYS.admin) init.headers["X-Admin-Key"] = KEYS.admin;
  if (KEYS.relative) init.headers["X-Relative-Key"] = KEYS.relative;
  if (TG) init.headers["X-Telegram-Init-Data"] = TG.initData;
  if (opts.method) init.method = opts.method;
  if (opts.body instanceof FormData) init.body = opts.body;
  else if (opts.body !== undefined) { init.headers["Content-Type"] = "application/json"; init.body = JSON.stringify(opts.body); }
  const res = await fetch(path, init);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) { const err = new Error(data.detail?.[0]?.msg || data.detail || `Ошибка ${res.status}`); err.status = res.status; throw err; }
  return data;
}

function connectWS(onMessage, onStatus) {
  let ws, timer;
  const open = () => {
    ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
    ws.onopen = () => { onStatus?.(true); timer = setInterval(() => ws.readyState === 1 && ws.send("ping"), 20000); };
    ws.onmessage = (e) => { try { const m = JSON.parse(e.data); onMessage(m.type, m.data); } catch (err) { console.error(err); } };
    ws.onclose = () => { onStatus?.(false); clearInterval(timer); setTimeout(open, 1500); };
  };
  open();
}

const fmt = (n) => Math.round(n).toLocaleString("ru-RU").replace(/,/g, " ") + " ₸";
const fmtShort = (n) => n >= 1e6 ? (n / 1e6).toFixed(n >= 1e7 ? 0 : 1).replace(".", ",") + " млн ₸" : fmt(n);
const pct = (x) => Math.round(x * 100) + "%";
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const $ = (sel, root = document) => root.querySelector(sel);
const timeHM = (iso) => new Date(iso).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
const dateShort = (iso) => new Date(iso).toLocaleDateString("ru-RU", { day: "numeric", month: "short" });

function ago(iso) {
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "только что";
  if (s < 3600) return `${Math.floor(s / 60)} мин назад`;
  if (s < 86400) return `${Math.floor(s / 3600)} ч назад`;
  return dateShort(iso);
}

const STATUS_RU = { completed: "Выполнен", pending_relative: "Ждёт родственника", cooling: "Охлаждение",
  rejected: "Отклонён", blocked: "Заблокирован" };
const LEVEL_RU = { low: "низкий", medium: "средний", high: "высокий" };
const statusPill = (s) => `<span class="pill ${s}">${STATUS_RU[s] || s}</span>`;
const levelPill = (l, score) => `<span class="pill ${l}">${LEVEL_RU[l] || l}${score !== undefined ? " · " + Math.round(score) : ""}</span>`;

function riskColor(v) { // v: 0..1
  if (v >= 0.8) return "var(--danger)";
  if (v >= 0.5) return "var(--warn)";
  return "var(--accent)";
}

// semicircle gauge; value 0..1
function gaugeSVG(value, size = 200, label = "") {
  const r = size / 2 - 14, c = Math.PI * r, off = c * (1 - Math.max(0, Math.min(1, value)));
  return `<svg viewBox="0 0 ${size} ${size / 2 + 14}" width="100%" style="max-width:${size}px" aria-label="Риск ${pct(value)}">
    <path d="M14 ${size / 2} A ${r} ${r} 0 0 1 ${size - 14} ${size / 2}" fill="none" stroke-width="12" stroke-linecap="round" class="gauge-track"/>
    <path d="M14 ${size / 2} A ${r} ${r} 0 0 1 ${size - 14} ${size / 2}" fill="none" stroke-width="12" stroke-linecap="round"
      class="gauge-val" stroke="${riskColor(value)}" stroke-dasharray="${c}" stroke-dashoffset="${off}"/>
    <text x="50%" y="${size / 2 - 4}" text-anchor="middle" fill="var(--text)" font-size="${size / 5.2}" font-weight="600" class="num">${pct(value)}</text>
    <text x="50%" y="${size / 2 + 12}" text-anchor="middle" fill="var(--muted)" font-size="11">${esc(label)}</text>
  </svg>`;
}

function sparkSVG(values, w = 300, h = 56) {
  if (!values.length) return `<svg viewBox="0 0 ${w} ${h}" width="100%" height="${h}"></svg>`;
  const pts = values.map((v, i) => [values.length === 1 ? w : (i / (values.length - 1)) * w, h - 4 - v * (h - 8)]);
  const d = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" ");
  const last = values[values.length - 1];
  const y50 = h - 4 - 0.5 * (h - 8), y80 = h - 4 - 0.8 * (h - 8);
  return `<svg viewBox="0 0 ${w} ${h}" width="100%" height="${h}" preserveAspectRatio="none">
    <line x1="0" x2="${w}" y1="${y50}" y2="${y50}" stroke="var(--warn)" stroke-opacity=".35" stroke-dasharray="3 4"/>
    <line x1="0" x2="${w}" y1="${y80}" y2="${y80}" stroke="var(--danger)" stroke-opacity=".35" stroke-dasharray="3 4"/>
    <path d="${d} L ${w} ${h} L 0 ${h} Z" fill="${riskColor(last)}" fill-opacity=".10"/>
    <path d="${d}" fill="none" stroke="${riskColor(last)}" stroke-width="2" vector-effect="non-scaling-stroke"/>
  </svg>`;
}

const SHIELD_SVG = `<svg viewBox="0 0 24 24" fill="none"><path d="M12 2.5 4.5 5.3v6.1c0 4.6 3.1 8.6 7.5 10.1 4.4-1.5 7.5-5.5 7.5-10.1V5.3L12 2.5Z" fill="#14532d"/><path d="m8.6 12.1 2.4 2.4 4.6-4.9" stroke="#bdf5d3" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
const SHIELD_DOT = `<svg viewBox="0 0 24 24" fill="none"><path d="m6.5 12.5 3.5 3.5 7.5-8" stroke="#062b15" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg>`;

function vibrate(p) { try { navigator.vibrate?.(p); } catch (_) {} }
