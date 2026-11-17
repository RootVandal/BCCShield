// Trusted contact's cabinet: the same code runs on /relative (web, personal ?rk= link) and /tg (Telegram Mini App,
// signed by Telegram). Shows open requests, every transfer of the protected person and the family rules.
const F = { wards: [], idx: 0, tab: "requests", shieldOff: {}, loaded: false, busy: false, invite: null };
const ROOT = () => document.getElementById("app");
const ward = () => F.wards[F.idx];
const haptic = (kind) => { try { TG?.HapticFeedback?.notificationOccurred(kind); } catch (_) {} if (!TG) vibrate(kind === "error" ? [300, 100, 300] : 60); };
const initialsOf = (name) => (name || "?").split(" ").filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase();
const firstName = (name) => (name || "").split(" ")[0];

function familyHeader() {
  const w = ward();
  const switcher = F.wards.length > 1 ? `<div class="flex gap-1.5 mt-3 overflow-x-auto">${F.wards.map((x, i) =>
    `<button class="chip ${i === F.idx ? "on" : ""}" onclick="F.idx=${i};renderFamily()">${esc(firstName(x.client.name))}</button>`).join("")}</div>` : "";
  return `<div class="flex items-center justify-between pt-1 pb-3">
      <div class="flex items-center gap-3"><div class="app-icon sm"><svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M12 2.5 4.5 5.3v6.1c0 4.6 3.1 8.6 7.5 10.1 4.4-1.5 7.5-5.5 7.5-10.1V5.3L12 2.5Z" fill="#1c1c1a"/><path d="M12 5.2v14.1c3.1-1.3 5.1-4.4 5.1-7.9V7.1L12 5.2Z" fill="#2fd27a"/></svg></div>
        <div><div class="text-[12px] muted">Семейный щит</div><div class="text-[15px] font-semibold">${w ? esc(w.me.name) : "Доверенное лицо"}</div></div></div>
      <span class="pill neutral">${TG ? "Telegram" : "веб-кабинет"}</span></div>${switcher}`;
}

function wardCard(w) {
  const c = w.client, call = F.calls?.[c.id];
  const off = F.shieldOff[c.id];
  return `<div class="card p-4 mt-2">
    <div class="flex items-center gap-3"><div class="avatar w-11 h-11 rounded-full grid place-items-center text-[13px] font-semibold" style="background:var(--accent-dim);color:var(--accent)">${esc(initialsOf(c.name))}</div>
      <div class="flex-1 min-w-0"><div class="text-[15px] font-medium truncate">${esc(c.name)}</div><div class="text-[12px] muted">${c.age} лет · вы: ${esc(w.me.relation)}</div></div>
      <a class="btn btn-sm" href="tel:${esc(c.phone)}" aria-label="Позвонить">📞</a></div>
    <div class="grid grid-cols-3 gap-2 mt-4 text-[12px]">
      <div class="card-2 p-2.5"><div class="muted">Щит</div><div class="mt-0.5 ${c.shield_enabled ? "text-[color:var(--accent)]" : ""}">${c.shield_enabled ? "включён" : "выключен"}</div></div>
      <div class="card-2 p-2.5"><div class="muted">Защита</div><div class="mt-0.5 ${c.protection_mode === "on" ? "text-[color:var(--danger)]" : ""}">${c.protection_mode === "on" ? "режим ON" : "обычный"}</div></div>
      <div class="card-2 p-2.5"><div class="muted">Звонок</div><div class="mt-0.5 num" style="color:${call ? riskColor(call.risk) : "var(--muted)"}">${call ? "риск " + pct(call.risk) : "нет"}</div></div></div>
    ${call && call.history?.length ? `<div class="mt-3">${sparkSVG(call.history.map((h) => h.score), 320, 36)}</div>` : ""}
    ${c.protection_mode === "on" ? `<button class="btn btn-sm btn-block mt-3" onclick="protectionOff(${c.id}, this)">Снять режим защиты (я поговорил с ней)</button>` : ""}
    ${off ? `<div class="mt-3 card-2 p-3 text-[12.5px]" style="border-color:rgba(242,179,61,.4)">${esc(firstName(c.name))} хочет отключить семейный щит. Если вы об этом не договаривались — позвоните ей.
      <div class="grid grid-cols-2 gap-2 mt-2"><button class="btn btn-sm" onclick="delete F.shieldOff[${c.id}];renderFamily()">Не разрешать</button>
      <button class="btn btn-sm btn-pale" onclick="confirmShieldOff(${c.id}, this)">Разрешить</button></div></div>` : ""}
  </div>`;
}

function alertCards(w) {
  return w.alerts.slice().reverse().slice(0, 2).map((a) => `<div class="mt-3 rounded-[18px] p-4 fade-in" role="alert" style="background:linear-gradient(180deg,#3a0f0a,#24100d);border:1px solid rgba(255,92,77,.45)">
    <div class="flex items-start gap-3"><div class="text-[22px] leading-none">⚠️</div><div class="flex-1">
      <div class="text-[15px] font-semibold text-white leading-snug">${esc(firstName(a.client))} сейчас звонят мошенники</div>
      <div class="text-[13px] text-white/75 mt-1">Схема: ${esc(a.scheme.ru)} · риск ${pct(F.calls?.[a.client_id]?.risk ?? a.risk)}${F.calls?.[a.client_id] ? " сейчас" : ""} · ${timeHM(a.at)}</div></div></div>
    <a class="btn btn-block mt-3" style="background:#fff;color:#7a1109;border:0;font-weight:600" href="tel:${esc(a.phone)}">📞 Позвонить</a></div>`).join("");
}

function decisionRow(kind, id) {
  return `<div class="grid grid-cols-2 gap-px bg-[color:var(--line)] border-t hair">
    <button class="h-12 bg-[color:var(--surface)] hover:bg-[color:var(--surface-2)] text-[13.5px]" style="color:var(--accent)" onclick="decide('${kind}',${id},'approve',this)">✅ ${kind === "contact" ? "Разрешить" : "Подтвердить"}</button>
    <button class="h-12 bg-[color:var(--surface)] hover:bg-[color:var(--surface-2)] text-[13.5px] font-semibold" style="color:var(--danger)" onclick="decide('${kind}',${id},'reject',this)">❌ ${kind === "contact" ? "Не разрешать" : "Отклонить"}</button></div>`;
}

function transferRequest(t) {
  const left = t.cooling_until ? Math.max(0, Math.round((new Date(t.cooling_until) - Date.now()) / 1000)) : 0;
  return `<div class="rounded-[18px] overflow-hidden bg-[color:var(--surface)] border fade-in" style="border-color:rgba(242,179,61,.45)">
    <div class="p-4"><div class="flex justify-between items-start"><div><div class="text-[12px] muted">${esc(firstName(t.from.name))} переводит</div>
      <div class="text-[26px] font-semibold num mt-0.5">${fmt(t.amount)}</div></div>${statusPill(t.status)}</div>
      <div class="flex justify-between text-[13px] mt-3 gap-3"><span class="muted">Кому</span><span class="text-right">${esc(t.to.name)} · ${esc(t.to.bank)} ${esc(t.to.card)}</span></div>
      <div class="flex justify-between text-[13px] mt-1.5"><span class="muted">Риск</span>${levelPill(t.risk_level, t.risk_score)}</div>
      <div class="flex justify-between text-[13px] mt-1.5"><span class="muted">Без ответа выполнится через</span><span class="num mono cd" data-until="${t.cooling_until}">${String(Math.floor(left / 60)).padStart(2, "0")}:${String(left % 60).padStart(2, "0")}</span></div>
      <div class="label mt-4 mb-1.5">Почему на паузе</div>
      <ul class="text-[13px] flex flex-col gap-1">${t.reasons.slice(0, 6).map((r) => `<li class="flex gap-2"><span style="color:var(--danger)">•</span><span>${esc(r.ru)}</span></li>`).join("")}</ul></div>
    ${t.status === "pending_relative" ? decisionRow("transfer", t.id) : ""}</div>`;
}

function loanRequest(l, w) {
  return `<div class="rounded-[18px] overflow-hidden bg-[color:var(--surface)] border fade-in" style="border-color:rgba(242,179,61,.45)">
    <div class="p-4"><div class="text-[12px] muted">${esc(firstName(w.client.name))} оформляет кредит</div>
      <div class="text-[26px] font-semibold num mt-0.5">${fmt(l.amount)}</div>
      <p class="text-[13px] muted mt-2 leading-relaxed">Мошенники часто заставляют взять кредит и сразу перевести деньги. Позвоните и уточните, что это её решение.</p></div>
    ${decisionRow("loan", l.id)}</div>`;
}

function contactRequest(p, w) {
  return `<div class="rounded-[18px] overflow-hidden bg-[color:var(--surface)] border fade-in" style="border-color:rgba(242,179,61,.45)">
    <div class="p-4"><div class="text-[12px] muted">${esc(firstName(w.client.name))} добавляет доверенное лицо</div>
      <div class="text-[18px] font-semibold mt-1">${esc(p.name)} <span class="muted font-normal text-[14px]">(${esc(p.relation)})</span></div>
      <div class="text-[13px] mono muted mt-0.5">${esc(p.phone)}</div>
      <p class="text-[13px] muted mt-2 leading-relaxed">Если вы не знаете этого человека — не разрешайте: так мошенники пытаются получить право подтверждать переводы.</p></div>
    ${decisionRow("contact", p.id)}</div>`;
}

function txLine(t) {
  const out = t.direction === "out", other = out ? t.to : t.from;
  return `<div class="flex items-center gap-3 py-3 border-b hair">
    <div class="avatar w-9 h-9 rounded-full grid place-items-center text-[12px] font-semibold" style="background:var(--surface-3)">${esc((other.name || "?")[0])}</div>
    <div class="flex-1 min-w-0"><div class="text-[14px] truncate">${esc(other.name)}</div>
      <div class="text-[12px] muted">${esc(other.bank)} ${esc(other.card)} · ${dateShort(t.created_at)} ${timeHM(t.created_at)}</div></div>
    <div class="text-right"><div class="num text-[14px] ${out ? "" : "text-[color:var(--accent)]"}">${out ? "−" : "+"}${fmt(t.amount)}</div>
      ${t.status !== "completed" ? statusPill(t.status) : t.risk_level !== "low" ? levelPill(t.risk_level) : ""}</div></div>`;
}

function rulesView(w) {
  const r = w.me.rules;
  const row = (k, label, note) => `<div class="flex items-center justify-between gap-3 py-3 border-b hair"><div><div class="text-[14px]">${label}</div><div class="text-[11.5px] muted mt-0.5">${note}</div></div>
    <button class="switch ${r[k] ? "on" : ""}" onclick="setRule('${k}', ${!r[k]})" aria-label="${label}"></button></div>`;
  const others = w.client.contacts.filter((p) => p.id !== w.me.id && ["active", "invited", "approval"].includes(p.status));
  return `<div class="card p-4"><div class="label">Вы подтверждаете</div>
      <div class="py-3 border-b hair"><div class="text-[14px]">Переводы от суммы</div>
        <div class="flex gap-1.5 mt-2 flex-wrap">${[50000, 100000, 200000, 500000].map((v) => `<button class="chip ${r.threshold === v ? "on" : ""}" onclick="setRule('threshold', ${v})">${fmtShort(v)}</button>`).join("")}</div></div>
      ${row("confirm_new", "Переводы новым получателям", "Главный признак схемы «безопасный счёт»")}
      ${row("confirm_loans", "Кредиты и займы", "Кредит по просьбе звонящего")}
      <div class="label mt-4">Вы видите</div>
      ${row("notify_all", "Все переводы", "Сообщения в Telegram о каждом переводе")}
      <p class="text-[11.5px] faint mt-3 leading-relaxed">${esc(firstName(w.client.name))} может только ужесточить эти правила. Ослабить их можете вы.</p></div>
    <div class="card p-4 mt-3"><div class="label mb-2">Другие доверенные лица</div>
      ${others.length ? others.map((p) => `<div class="flex items-center justify-between py-2 text-[13.5px]"><span>${esc(p.name)} <span class="muted">(${esc(p.relation)})</span></span>
        <span class="pill ${p.status === "active" ? "low" : "medium"}">${p.status === "active" ? "подключён" : p.status === "invited" ? "приглашён" : "ждёт разрешения"}</span></div>`).join("")
        : `<p class="text-[13px] muted">Вы единственное доверенное лицо.</p>`}</div>`;
}

function renderFamily() {
  const root = ROOT();
  if (F.invite) return renderInvite();
  if (!F.loaded) { root.innerHTML = `${familyHeader()}<div class="card p-5 mt-3 text-[13px] muted">Загружаем…</div>`; return; }
  const w = ward();
  if (!w) return renderLocked();
  const pend = w.pending.transfers.length + w.pending.loans.length + w.pending.contacts.length;
  const tabs = [["requests", `Запросы${pend ? ` · ${pend}` : ""}`], ["feed", "Все переводы"], ["rules", "Правила"]];
  let body;
  if (F.tab === "requests") {
    body = [...w.pending.transfers.map(transferRequest), ...w.pending.loans.map((l) => loanRequest(l, w)),
      ...w.pending.contacts.map((p) => contactRequest(p, w))].join("") ||
      `<div class="card p-5 text-center text-[13px] muted leading-relaxed">Всё спокойно. Если ${esc(firstName(w.client.name))} попробует сделать рискованный перевод, взять кредит или добавить нового доверенного, запрос придёт сюда и в Telegram.</div>`;
    body = `<div class="flex flex-col gap-3">${body}</div>`;
  } else if (F.tab === "feed") {
    const out = w.transfers.filter((t) => t.direction === "out" && t.status === "completed").reduce((s, t) => s + t.amount, 0);
    body = `<div class="card px-4 pb-1 pt-3"><div class="flex justify-between text-[12px] muted"><span>Последние ${w.transfers.length} операций</span><span>списано ${fmtShort(out)}</span></div>
      ${w.transfers.map(txLine).join("") || `<p class="text-[13px] muted py-4">Переводов пока нет.</p>`}</div>`;
  } else body = rulesView(w);
  root.innerHTML = `${familyHeader()}${wardCard(w)}${alertCards(w)}
    <div class="seg mt-5 w-full" role="tablist">${tabs.map(([k, l]) => `<button class="flex-1 ${F.tab === k ? "on" : ""}" onclick="F.tab='${k}';renderFamily()">${l}</button>`).join("")}</div>
    <div class="mt-3 pb-8">${body}</div>`;
}

function renderLocked() {
  ROOT().innerHTML = `${familyHeader()}<div class="card p-5 mt-3"><div class="text-[15px] font-semibold">Вы пока не доверенное лицо</div>
    <p class="text-[13px] muted mt-2 leading-relaxed">${TG ? "Примите приглашение близкого человека: откройте ссылку-приглашение из его приложения и подтвердите свой номер в боте."
      : "Откройте кабинет по личной ссылке (<span class=\"mono\">/relative?rk=…</span>) из Telegram-бота или со стартовой страницы демо."}</p></div>`;
}

function renderInvite() {
  const inv = F.invite;
  const deep = inv.bot ? `https://t.me/${encodeURIComponent(inv.bot)}?start=${encodeURIComponent(inv.code)}` : "";
  const r = inv.contact.rules;
  ROOT().innerHTML = `${familyHeader()}<div class="card p-5 mt-3 fade-in">
    <div class="text-[13px] muted">Приглашение</div>
    <div class="text-[20px] font-semibold mt-1 leading-snug">${esc(inv.client)} приглашает вас стать доверенным лицом</div>
    <div class="text-[13px] muted mt-3 leading-relaxed">Вы будете подтверждать переводы от ${fmt(r.threshold)}${r.confirm_new ? ", переводы новым получателям" : ""}${r.confirm_loans ? " и кредиты" : ""}. ${r.notify_all ? "И видеть все её переводы." : ""}</div>
    ${inv.accepted ? `<div class="card-2 p-3 mt-4 text-[13px]" style="color:var(--accent)">✓ Приглашение уже принято</div>` : `
    ${deep ? `<a class="btn btn-accent btn-block btn-lg mt-5" href="${deep}" target="_blank" rel="noopener">Принять в Telegram</a>
      <p class="text-[11.5px] faint mt-2 leading-relaxed">В боте нужно будет подтвердить, что номер ${esc(inv.contact.phone)} — ваш.</p>` : ""}
    <button class="btn btn-block mt-3" onclick="acceptInWeb(this)">Принять в браузере (демо, без Telegram)</button>
    <div id="inv-err" class="text-[12.5px] mt-2" style="color:#ffb1a8"></div>`}</div>`;
}

async function acceptInWeb(btn) {
  btn.disabled = true;
  try {
    const r = await api(`/api/invites/${encodeURIComponent(F.invite.code)}/accept`, { body: {} });
    const rk = new URL(r.relative, location.origin).searchParams.get("rk");
    KEYS.relative = rk; try { localStorage.setItem("bcc.relativeKey", rk); } catch (_) {}
    F.invite = null; history.replaceState(null, "", location.pathname);
    haptic("success"); await loadFamily();
  } catch (e) { $("#inv-err").textContent = e.status === 403 ? "В браузере принять может только ведущий демо (этот компьютер). Остальные принимают в Telegram." : e.message; btn.disabled = false; }
}

async function loadFamily() {
  try {
    const me = await api("/api/relative/me");
    const prevId = ward()?.client.id;
    F.wards = me.wards;
    F.idx = Math.max(0, F.wards.findIndex((w) => w.client.id === prevId));
  } catch (e) { if (e.status !== 403) throw e; F.wards = []; }
  F.loaded = true;
  const calls = await api("/api/calls/active").catch(() => []);
  F.calls = Object.fromEntries(calls.map((c) => [c.client_id, { risk: c.risk, history: c.history || [] }]));
  renderFamily();
}

let reloadTimer;
const reloadSoon = () => { clearTimeout(reloadTimer); reloadTimer = setTimeout(loadFamily, 250); };

async function decide(kind, id, decision, btn) {
  btn.parentElement.querySelectorAll("button").forEach((b) => (b.disabled = true));
  const url = { transfer: `/api/transfers/${id}/decision`, loan: `/api/loans/${id}/decision`, contact: `/api/contacts/${id}/decision` }[kind];
  try { await api(url, { body: { decision } }); haptic(decision === "reject" ? "warning" : "success"); }
  catch (e) { haptic("error"); alertInline(e.message); }
  await loadFamily();
}

async function setRule(k, v) {
  const w = ward();
  try { await api(`/api/contacts/${w.me.id}/rules`, { method: "PATCH", body: { [k]: v } }); haptic("success"); }
  catch (e) { haptic("error"); alertInline(e.message); }
  await loadFamily();
}

async function confirmShieldOff(clientId, btn) {
  btn.disabled = true;
  try { await api(`/api/clients/${clientId}/shield/confirm-off`, { body: {} }); delete F.shieldOff[clientId]; } catch (e) { alertInline(e.message); }
  await loadFamily();
}

async function protectionOff(clientId, btn) {
  btn.disabled = true;
  try { await api(`/api/clients/${clientId}/protection/off`, { body: {} }); } catch (e) { alertInline(e.message); }
  await loadFamily();
}

function alertInline(msg) {
  const el = document.createElement("div");
  el.className = "fixed left-1/2 -translate-x-1/2 bottom-6 z-50 card px-4 py-3 text-[13px] max-w-[340px]";
  el.style.borderColor = "rgba(255,92,77,.45)";
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 4500);
}

function onFamilyEvent(type, d) {
  if (type === "reset") return location.reload();
  const ids = new Set(F.wards.map((w) => w.client.id));
  const cid = d?.client_id ?? d?.id ?? d?.from?.client_id;
  if (type === "call_update" && ids.has(d.client_id)) { F.calls = { ...F.calls, [d.client_id]: { risk: d.risk, history: d.history } }; renderFamily(); return; }
  if (type === "call_ended" && ids.has(d.client_id)) { delete F.calls?.[d.client_id]; renderFamily(); return; }
  if (type === "shield_off_request" && ids.has(d.client_id)) { F.shieldOff[d.client_id] = d; haptic("warning"); renderFamily(); return; }
  if (type === "relative_alert" && ids.has(d.client_id)) { haptic("error"); reloadSoon(); return; }
  if (type === "transfer" && (ids.has(d.from?.client_id) || ids.has(d.to?.client_id))) {
    if (d.status === "pending_relative") haptic("warning");
    reloadSoon(); return;
  }
  if (["client_state", "loan", "contacts_changed"].includes(type) && (ids.has(cid) || !F.wards.length)) reloadSoon();
}

setInterval(() => {
  document.querySelectorAll(".cd").forEach((el) => {
    const left = Math.max(0, Math.round((new Date(el.dataset.until) - Date.now()) / 1000));
    el.textContent = `${String(Math.floor(left / 60)).padStart(2, "0")}:${String(left % 60).padStart(2, "0")}`;
  });
}, 1000);

async function startFamily(onWsStatus) {
  const code = new URLSearchParams(location.search).get("invite");
  if (code && !TG) {
    try { F.invite = { ...(await api(`/api/invites/${encodeURIComponent(code)}`)), code }; }
    catch (e) { F.invite = null; alertInline(e.message); }
  }
  if (!F.invite && !KEYS.relative && !TG) { // the presenter (this computer or ?key=…) gets Saule's trusted contact link
    try {
      const rk = new URL((await api("/api/demo/links")).relative, location.origin).searchParams.get("rk");
      if (rk) { KEYS.relative = rk; try { localStorage.setItem("bcc.relativeKey", rk); } catch (_) {} }
    } catch (_) {}
  }
  renderFamily();
  if (!F.invite) await loadFamily();
  connectWS(onFamilyEvent, onWsStatus || (() => {}));
}
