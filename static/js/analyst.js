// Analyst dashboard: live feed, call monitor, explainable transfer cards, drop-network graph, antifraud journal.
const A = { feed: [], calls: {}, metrics: {}, graph: null, nodes: null, edges: null, nodeMap: {}, chain: null,
  selected: null, threshold: 40, positions: {} };

const FEATURE_RU = {
  uniq_senders_24h: "Уникальных отправителей за 24 ч", uniq_senders_7d: "Уникальных отправителей за 7 дн",
  stranger_share: "Доля входящих от незнакомых", median_dwell_min: "Медиана «вход → выход», мин",
  transit_ratio: "Транзит за 24 ч (выход/вход)", account_age_days: "Возраст счёта, дней", under_call_share: "Доля входящих «под звонком»",
  complaints: "Жалобы", pagerank_pct: "PageRank (перцентиль)", community: "Сообщество (Louvain)", in_sum: "Входящие, ₸", out_sum: "Исходящие, ₸",
  in_count: "Входящих переводов", out_count: "Исходящих переводов", bcc_senders: "Разных клиентов БЦК", from_risky_share: "Доля денег от дропперов",
};
const CONTRIB_RU = {
  senders: "Много отправителей", stranger: "Незнакомые отправители", dwell: "Быстрый вывод", transit: "Транзит", young: "Новый счёт",
  under_call: "Входящие «под звонком»", pagerank: "Центральность", bcc_senders: "Много клиентов БЦК", from_risky: "Деньги от дропперов",
};
const RULE_RU = { call_risk: "Звонок", recent_loan: "Кредит → перевод", risky_recipient: "Получатель в графе", new_recipient: "Новый получатель",
  unusual_amount: "Нетипичная сумма", night_time: "Ночь", elderly: "Возраст 60+", pasted: "Вставка из буфера", rushed: "Спешка",
  protection_mode: "Режим защиты", telecom_signal: "Сигнал оператора", remote_app: "Удалённый доступ", cash_out: "Снятие наличных", deposit_early: "Закрытие депозита",
  family_amount: "Правило семьи: сумма", family_new: "Правило семьи: новый получатель", answer_on_call: "Ответ: идёт звонок", answer_safe_account: "Ответ: «безопасный счёт»", answer_impersonation: "Ответ: «банк/полиция»", shield_off: "Щит выключен" };

// ---------- metrics -----------------------------------------------------------------------------------
function renderMetrics(flash) {
  const m = A.metrics;
  const tiles = [
    ["Сохранено", fmt(m.saved || 0), "saved", m.saved > 0 ? "var(--accent)" : null],
    ["Остановлено операций", m.stopped ?? 0, "stopped"],
    ["На паузе сейчас", m.paused_now ?? 0, "paused", m.paused_now ? "var(--warn)" : null],
    ["Звонков с риском", m.risky_calls ?? 0, "calls", m.risky_calls ? "var(--danger)" : null],
    ["Поймано приманкой", `${m.decoy_cards ?? 0} карт`, "decoy", m.decoy_cards ? "var(--accent)" : null],
    ["Найдено дропперов", m.droppers_found ?? 0, "drops"],
    ["Precision графа", (m.precision ?? 0).toFixed(2), "p"],
    ["Recall графа", (m.recall ?? 0).toFixed(2), "r"],
    // honest number from the evaluation set (app/eval.py) instead of a rate counted on three demo calls
    A.eval ? ["Ложные тревоги проверки речи", pct(A.eval.normal.rate), "fp", null,
      `на ${A.eval.normal.total} обычных · словарь без LLM ловит ${pct(A.eval.scam.rate)} из ${A.eval.scam.total} схем`]
      : ["Ложные паузы", pct(m.false_pause_rate || 0), "fp"],
  ];
  $("#metrics").innerHTML = tiles.map(([l, v, k, c, sub]) => `<div class="metric ${flash === k ? "flash" : ""}" ${sub ? `title="${esc(sub)}"` : ""}><div class="label leading-snug">${l}</div>
    <div class="v num" ${c ? `style="color:${c}"` : ""}>${v}</div>${sub ? `<div class="text-[10.5px] faint leading-snug mt-0.5">${esc(sub)}</div>` : ""}</div>`).join("");
}
async function loadMetrics(flash) {
  const prev = A.metrics.saved;
  A.metrics = await api("/api/metrics");
  renderMetrics(flash || (A.metrics.saved > (prev ?? A.metrics.saved) ? "saved" : null));
}

// ---------- calls -------------------------------------------------------------------------------------
function renderCalls() {
  const calls = Object.values(A.calls);
  $("#calls-n").textContent = calls.length ? `${calls.length} live` : "";
  $("#calls").innerHTML = calls.length ? calls.map((c) => `<div class="px-4 py-3 border-b hair fade-in">
      <div class="flex items-center justify-between"><div class="flex items-center gap-2"><span class="live" style="width:7px;height:7px;border-radius:9px;background:${riskColor(c.risk)};display:inline-block"></span>
        <span class="text-[13.5px]">${esc(c.client || "Клиент #" + c.client_id)}</span></div>
        <span class="num text-[18px] font-semibold" style="color:${riskColor(c.risk)}">${pct(c.risk)}</span></div>
      <div class="mt-1.5">${sparkSVG((c.history || []).map((h) => h.score), 300, 34)}</div>
      ${c.phone ? `<div class="text-[12px] muted mt-1">📱 ${esc(c.phone.summary.ru)}</div>` : ""}
      ${c.scheme ? `<div class="text-[12px] muted mt-1">Схема: ${esc(c.scheme)}</div>` : ""}
      <div class="flex flex-wrap gap-1 mt-1.5">${(c.matched_phrases || []).slice(-6).map((p) => `<span class="pill high">${esc(p)}</span>`).join("")}</div>
      ${c.llm?.explanation_ru ? `<div class="text-[12px] muted mt-1.5">LLM: ${esc(c.llm.explanation_ru)}</div>` : ""}</div>`).join("")
    : `<div class="px-4 py-4 text-[12.5px] faint">Нет активных звонков под защитой</div>`;
}

// ---------- feed --------------------------------------------------------------------------------------
function feedRow(t) {
  const top = t.reasons?.[0];
  return `<div class="feed-row feed-item ${A.selected?.type === "transfer" && A.selected.id === t.id ? "sel" : ""}" onclick="openTransfer(${t.id})">
    <div class="flex items-center justify-between gap-2"><span class="text-[12.5px] truncate">${esc(t.from.name.split(" ").slice(0, 2).join(" "))} ${t.kind && t.kind !== "transfer" ? `· ${esc(t.title)}` : `→ ${esc(t.to.bank)} ${esc(t.to.card)}`}</span>
      <span class="num text-[13px] font-medium whitespace-nowrap">${fmt(t.amount)}</span></div>
    <div class="flex items-center gap-1.5 mt-1.5"><span class="text-[11px] faint mono">${timeHM(t.created_at)}</span>${levelPill(t.risk_level, t.risk_score)}${t.status !== "completed" ? statusPill(t.status) : ""}
      ${t.false_positive ? '<span class="pill neutral">ложное</span>' : ""}</div>
    ${top && t.risk_level !== "low" ? `<div class="text-[11.5px] muted mt-1 truncate">${esc(top.ru)}</div>` : ""}</div>`;
}
function renderFeed() { $("#feed").innerHTML = A.feed.map(feedRow).join("") || `<div class="px-4 py-4 text-[12.5px] faint">Операций пока нет</div>`; }
function upsertFeed(t) {
  const i = A.feed.findIndex((x) => x.id === t.id);
  if (i >= 0) A.feed[i] = t; else A.feed.unshift(t);
  A.feed = A.feed.slice(0, 80);
  renderFeed();
  if (A.selected?.type === "transfer" && A.selected.id === t.id) renderTransfer(t);
}

// ---------- detail: transfer --------------------------------------------------------------------------
function renderTransfer(t) {
  A.selected = { type: "transfer", id: t.id };
  $("#detail-h").textContent = `Операция #${t.id}`;
  const maxPts = Math.max(30, ...t.reasons.map((r) => r.points));
  const ctx = t.context || {};
  $("#detail").innerHTML = `<div class="fade-in">
    <div class="flex items-start justify-between"><div><div class="num text-[26px] font-semibold">${fmt(t.amount)}</div>
      <div class="text-[12.5px] muted mt-0.5">${esc(t.from.name)} → ${esc(t.to.name)}</div></div>
      <div class="text-right"><div class="num text-[26px] font-semibold" style="color:${riskColor(t.risk_score / 100)}">${Math.round(t.risk_score)}</div><div class="text-[11px] muted">risk score</div></div></div>
    <div class="flex flex-wrap gap-1.5 mt-3">${levelPill(t.risk_level)}${statusPill(t.status)}${t.decided_by ? `<span class="pill neutral">${esc(t.decided_by)}</span>` : ""}</div>
    <div class="card-2 p-3 mt-4 grid grid-cols-2 gap-2 text-[12px]">
      <div><div class="muted">Отправитель</div><div>BCC ${esc(t.from.card)}${t.from.age ? ` · ${t.from.age} лет` : ""}</div></div>
      <div><div class="muted">Получатель</div><div><a class="link" onclick="openAccount(${t.to.id}, true)">${esc(t.to.bank)} ${esc(t.to.card)}</a> · граф ${Math.round(t.to.risk_score)}</div></div>
      <div><div class="muted">Звонок</div><div>${ctx.call_active ? (ctx.call_risk != null ? "да, риск " + pct(ctx.call_risk) : "да") : "нет"}</div></div>
      <div><div class="muted">Кредит</div><div>${ctx.loan_minutes_ago != null ? Math.round(ctx.loan_minutes_ago) + " мин назад" : "—"}</div></div></div>
    <div class="label mt-5 mb-2">Вклад правил</div>
    <div class="flex flex-col gap-2">${t.reasons.map((r) => `<div><div class="flex justify-between text-[12px]"><span>${esc(RULE_RU[r.code] || r.code)}</span><span class="num muted">+${r.points}</span></div>
      <div class="bar mt-1"><i style="width:${(r.points / maxPts) * 100}%;background:${r.points >= 25 ? "var(--danger)" : r.points >= 10 ? "var(--warn)" : "var(--accent)"}"></i></div></div>`).join("") || '<div class="text-[12.5px] faint">Ни одно правило не сработало</div>'}</div>
    <div class="label mt-5 mb-2">Объяснение</div>
    <p class="text-[13px] leading-relaxed">${t.reasons.length ? esc(t.reasons.map((r) => r.ru).join(". ")) + "." : "Обычная операция: знакомый получатель, типичная сумма."}</p>
    <div class="grid grid-cols-2 gap-2 mt-5">
      <button class="btn btn-sm" onclick="markFalse(${t.id}, this)" ${t.false_positive ? "disabled" : ""}>Ложное срабатывание</button>
      <button class="btn btn-sm" onclick="freeze(${t.to.id}, this)">Заморозить счёт</button>
      <button class="btn btn-sm" onclick="sendSignal(${t.to.id}, this)">Отправить в Антифрод-центр</button>
      <button class="btn btn-sm" onclick="openAccount(${t.to.id}, true)">Получатель в графе</button></div></div>`;
  renderFeed();
}
async function openTransfer(id) { renderTransfer(await api(`/api/transfers/${id}`)); }

// ---------- detail: account ---------------------------------------------------------------------------
function fmtFeature(k, v) {
  if (v === null || v === undefined) return "—";
  if (k.endsWith("_share") || k === "pagerank_pct" || k === "transit_ratio") return pct(v);
  if (k === "in_sum" || k === "out_sum") return fmt(v);
  return v;
}
async function openAccount(id, highlight) {
  const a = await api(`/api/graph/account/${id}`);
  A.selected = { type: "account", id };
  $("#detail-h").textContent = a.external ? "Внешняя карта" : "Счёт БЦК";
  const f = a.features || {};
  const contrib = f.contrib || {};
  const maxC = Math.max(10, ...Object.values(contrib));
  const tags = [a.confirmed && ["high", "подтверждён"], a.frozen && ["high", "заморожен"], a.antifraud && ["high", "Антифрод-центр"],
    a.gt_drop && ["neutral", "синтетика: дроппер"], a.victim && ["neutral", "синтетика: жертва"], a.decoy && ["neutral", "синтетика: " + a.decoy]].filter(Boolean);
  const rows = Object.keys(FEATURE_RU).filter((k) => k in f);
  $("#detail").innerHTML = `<div class="fade-in">
    <div class="flex items-start justify-between gap-3"><div class="min-w-0"><div class="text-[18px] font-semibold">${esc(a.bank)} ${esc(a.card)}</div>
      <div class="text-[12.5px] muted truncate">${esc(a.owner)}${a.client ? " · клиент демо" : ""}</div></div>
      <div class="text-right"><div class="num text-[26px] font-semibold" style="color:${riskColor(a.risk / 100)}">${Math.round(a.risk)}</div><div class="text-[11px] muted">риск графа</div></div></div>
    <div class="bar mt-3"><i style="width:${a.risk}%;background:${riskColor(a.risk / 100)}"></i></div>
    <div class="flex flex-wrap gap-1.5 mt-3">${tags.map(([c, l]) => `<span class="pill ${c}">${esc(l)}</span>`).join("")}${a.is_dropper ? '<span class="pill high">дроппер</span>' : ""}</div>
    ${(f.reasons || []).length ? `<div class="label mt-5 mb-2">Почему</div><ul class="text-[13px] flex flex-col gap-1">${f.reasons.map((r) => `<li class="flex gap-2"><span style="color:var(--danger)">•</span>${esc(r)}</li>`).join("")}</ul>` : ""}
    ${Object.keys(contrib).length ? `<div class="label mt-5 mb-2">Вклад признаков</div><div class="flex flex-col gap-1.5">${Object.entries(contrib).sort((x, y) => y[1] - x[1]).map(([k, v]) => `<div>
      <div class="flex justify-between text-[12px]"><span>${esc(CONTRIB_RU[k] || k)}</span><span class="num muted">+${v}</span></div>
      <div class="bar mt-1"><i style="width:${(v / maxC) * 100}%;background:${v >= 15 ? "var(--danger)" : v >= 6 ? "var(--warn)" : "var(--accent)"}"></i></div></div>`).join("")}</div>` : ""}
    <div class="label mt-5 mb-2">Признаки</div><dl class="kv">${rows.map((k) => `<dt>${FEATURE_RU[k]}</dt><dd>${esc(fmtFeature(k, f[k]))}</dd>`).join("")}</dl>
    ${a.incoming.length ? `<div class="label mt-5 mb-2">Входящие</div>${a.incoming.slice(0, 5).map((r) => `<div class="flex justify-between text-[12px] py-1 border-b hair"><span class="truncate mr-2">${esc(r.other)} ${r.call ? "📞" : ""}</span><span class="num">${fmt(r.amount)}</span></div>`).join("")}` : ""}
    ${a.outgoing.length ? `<div class="label mt-4 mb-2">Исходящие</div>${a.outgoing.slice(0, 5).map((r) => `<div class="flex justify-between text-[12px] py-1 border-b hair"><span class="truncate mr-2">${esc(r.other)}</span><span class="num">${fmt(r.amount)}</span></div>`).join("")}` : ""}
    <div class="grid grid-cols-2 gap-2 mt-5">
      <button class="btn btn-sm" onclick="highlightChain(${id})">Подсветить цепочку</button>
      <button class="btn btn-sm" onclick="freeze(${id}, this)" ${a.frozen ? "disabled" : ""}>Заморозить счёт</button>
      <button class="btn btn-sm" onclick="sendSignal(${id}, this)">Отправить в Антифрод-центр</button>
      ${a.external ? `<button class="btn btn-sm" onclick="simulateSignal(this, ${id})">Входящий сигнал АФЦ</button>` : ""}</div></div>`;
  renderFeed();
  if (highlight) { highlightChain(id, a.chain); A.graph?.focus(id, { scale: 1.1, animation: { duration: 600 } }); }
}

// ---------- graph -------------------------------------------------------------------------------------
function nodeColor(n) {
  if (n.client) return "#c9a7ff";
  if (n.external) return n.risk >= 60 ? "#b04a40" : n.risk >= 40 ? "#9a7a3a" : "#77756e";
  if (n.risk >= 60) return "#ff5c4d";
  if (n.risk >= 40) return "#f2b33d";
  return "#3f8f63";
}
function toVisNode(n) {
  const showLabel = n.client || n.external || n.risk >= 60;
  const c = nodeColor(n);
  const pos = A.positions[n.id];
  return {
    id: n.id, label: showLabel ? (n.client ? n.client.split(" ")[0] : n.label) : undefined,
    title: `${n.owner}\n${n.bank} ${n.card}\nриск ${Math.round(n.risk)}${n.confirmed ? " · подтверждён" : ""}`,
    shape: n.external ? "box" : n.client ? "diamond" : "dot", size: n.client ? 14 : 6 + n.risk / 9,
    color: { background: c, border: n.confirmed || n.frozen ? "#ffffff" : c, highlight: { background: c, border: "#fff" } },
    borderWidth: n.confirmed || n.frozen ? 2 : 1, base: c,
    font: { color: "#d8d6d0", size: 11, face: "Geist", strokeWidth: 3, strokeColor: "#0a0a09", ...(n.external ? { color: "#0a0a09", strokeWidth: 0 } : {}) },
    margin: n.external ? 5 : undefined, ...(pos ? { x: pos.x, y: pos.y } : {}),
  };
}
function edgeStyle(e) {
  const special = e.status === "rejected" ? "#ff5c4d" : e.status === "pending_relative" || e.status === "cooling" ? "#f2b33d" : null;
  return { id: e.id, from: e.from, to: e.to, arrows: { to: { enabled: true, scaleFactor: 0.4 } },
    width: Math.min(5, 0.6 + Math.log10(1 + e.amount / 50000)), dashes: !!special,
    color: { color: special || "rgba(200,198,190,0.22)", highlight: "#ecebe6" }, base: special || "rgba(200,198,190,0.22)",
    title: `${e.count} перевод(а) · ${fmt(e.amount)}${special ? " · " + (STATUS_RU[e.status] || e.status) : ""}`, smooth: false };
}

async function loadGraph(focus) {
  const data = await api(`/api/graph?min_risk=${A.threshold}`);
  if (A.graph) A.positions = A.graph.getPositions();
  A.nodeMap = Object.fromEntries(data.nodes.map((n) => [n.id, n]));
  const nodes = new vis.DataSet(data.nodes.map(toVisNode));
  A.edgeRaw = data.edges;
  const edges = new vis.DataSet(data.edges.map(edgeStyle));
  A.nodes = nodes; A.edges = edges;
  $("#graph-stats").textContent = `${data.nodes.length} узлов · ${data.edges.length} связей`;
  if (!A.graph) {
    A.graph = new vis.Network($("#graph"), { nodes, edges }, {
      physics: { solver: "forceAtlas2Based", forceAtlas2Based: { gravitationalConstant: -38, springLength: 70, avoidOverlap: 0.3 }, stabilization: { iterations: 220 } },
      interaction: { hover: true, tooltipDelay: 120 }, layout: { randomSeed: 7 },
    });
    A.graph.on("stabilizationIterationsDone", () => { A.graph.setOptions({ physics: false }); $("#graph-loading").style.display = "none"; });
    A.graph.on("click", (p) => { if (p.nodes.length) openAccount(p.nodes[0], false).then(() => highlightChain(p.nodes[0])); });
  } else {
    A.graph.setData({ nodes, edges });
    const fresh = data.nodes.some((n) => !A.positions[n.id]);
    if (fresh) { A.graph.setOptions({ physics: true }); A.graph.stabilize(120); }
  }
  if (A.chain) applyHighlight(A.chain);
  if (focus) openAccount(focus, true);
}

function applyHighlight(ch) {
  A.chain = ch;
  const inN = new Set(ch.nodes), inE = new Set(ch.edges);
  A.nodes.update(A.nodes.get().map((n) => ({ id: n.id, opacity: inN.has(n.id) ? 1 : 0.12 })));
  A.edges.update(A.edges.get().map((e) => ({ id: e.id, color: { color: inE.has(e.id) ? (e.base.startsWith("#") ? e.base : "#ecebe6") : "rgba(200,198,190,0.05)", highlight: "#fff" },
    width: inE.has(e.id) ? 2.4 : 0.6 })));
}
async function highlightChain(id, ch) {
  if (!A.nodes) return;
  ch = ch || (await api(`/api/graph/chain/${id}`));
  const missing = ch.nodes.filter((n) => !A.nodes.get(n));
  if (missing.length && A.threshold > 0) { A.chain = ch; }
  applyHighlight(ch);
}
function clearHighlight() {
  A.chain = null;
  if (!A.nodes) return;
  A.nodes.update(A.nodes.get().map((n) => ({ id: n.id, opacity: 1 })));
  A.edges.update(A.edgeRaw.map(edgeStyle));
}

async function highlightFromVictim() {
  // The demo victim is Saule; if she has a rejected transfer, show that chain, otherwise the riskiest victim chain.
  const s = Object.values(A.nodeMap).find((n) => n.client === "Сауле Ахметова");
  const rejected = A.feed.find((t) => t.status === "rejected" && t.from.client_id === DEMO_CLIENT_ID);
  if (rejected) return openAccount(rejected.to.id, true);
  if (s && A.edges.get().some((e) => e.from === s.id && e.base === "#ff5c4d")) return highlightChain(s.id);
  const victim = Object.values(A.nodeMap).filter((n) => n.victim).sort((a, b) => b.risk - a.risk)[0];
  if (victim) { await openAccount(victim.id, false); highlightChain(victim.id); A.graph.focus(victim.id, { scale: 1, animation: true }); }
}

// ---------- journal -----------------------------------------------------------------------------------
async function loadJournal() {
  const rows = await api("/api/antifraud/signals");
  $("#journal").innerHTML = rows.map((s) => `<div class="px-4 py-2.5 border-b hair fade-in text-[12px]">
    <div class="flex justify-between"><span><span class="pill ${s.direction === "out" ? "medium" : "high"}">${s.direction === "out" ? "OUT → АФЦ" : "IN ← АФЦ"}</span>
      <a class="link ml-1.5" onclick="openAccount(${s.account_id}, true)">${esc(s.payload.bank)} ${esc(s.payload.card)}</a></span><span class="faint mono">${timeHM(s.created_at)}</span></div>
    <div class="muted mt-1 truncate">${esc(s.payload.reason)}</div><div class="faint mono text-[10.5px] mt-0.5">${esc(s.payload.ticket)}</div></div>`).join("")
    || `<div class="px-4 py-4 text-[12.5px] faint">Сигналов пока нет</div>`;
}

// ---------- actions -----------------------------------------------------------------------------------
async function withBtn(btn, fn) { if (btn) btn.disabled = true; try { await fn(); } catch (e) { alert(e.message); } finally { if (btn) btn.disabled = false; } }
const fastForward = (btn) => withBtn(btn, () => api("/api/cooling/fast-forward", { body: {} }));
const markFalse = (id, btn) => withBtn(btn, async () => { renderTransfer(await api(`/api/transfers/${id}/false-positive`, { body: {} })); loadMetrics(); });
const freeze = (id, btn) => withBtn(btn, () => api(`/api/accounts/${id}/freeze`, { body: {} }));
const sendSignal = (id, btn) => withBtn(btn, () => api("/api/antifraud/signal", { body: { account_id: id } }));
const simulateSignal = (btn, id) => withBtn(btn, async () => {
  const r = await api("/api/antifraud/simulate-incoming", { body: id ? { account_id: id } : {} });
  if (r.warned_clients.length) toastA(`📡 Сигнал АФЦ: ${esc(r.signal.payload.bank)} ${esc(r.signal.payload.card)}. Предупреждены клиенты: ${r.warned_clients.map((c) => esc(c.name)).join(", ")}`);
});
const phoneCallDemo = (btn) => withBtn(btn, async () => {
  const s = await api(`/api/clients/${DEMO_CLIENT_ID}/phone-call`, { body: { state: "start", caller: "+7 701 ••• 45 67", caller_kind: "unknown", minutes_ago: 12 } });
  toastA(`📱 Телефон Сауле: ${esc(s.phone.summary.ru)}. Риск по контексту ${pct(s.risk)} — без записи разговора.`);
});
const telecomSignal = (btn) => withBtn(btn, async () => {
  await api(`/api/clients/${DEMO_CLIENT_ID}/telecom-signal`, { body: {} });
  toastA("📶 Оператор связи сообщил банку: Сауле звонят с номера из базы мошенников. Включён режим защиты, доверенные лица уведомлены.");
});
const resetDemo = (btn) => withBtn(btn, () => api("/api/demo/reset", { body: {} }));
function toastA(html) {
  const d = document.createElement("div");
  d.className = "fixed right-4 top-16 z-50 card px-4 py-3 text-[13px] max-w-[420px] shadow-2xl fade-in"; d.innerHTML = html;
  document.body.appendChild(d); setTimeout(() => d.remove(), 6000);
}

// ---------- live --------------------------------------------------------------------------------------
let graphTimer;
function onEvent(type, d) {
  if (type === "reset") return location.reload();
  if (type === "metrics") { const prev = A.metrics.saved; A.metrics = d; renderMetrics(d.saved > prev ? "saved" : null); }
  if (type === "transfer") upsertFeed(d);
  if (type === "call_started" || type === "call_update") {
    const c = A.calls[d.call_id] || {};
    A.calls[d.call_id] = { ...c, ...d, client: c.client || (d.client_id === DEMO_CLIENT_ID ? "Сауле Ахметова" : null),
      matched_phrases: d.matches ? [...new Set([...(c.matched_phrases || []), ...d.matches.map((m) => m.phrase)])] : d.matched_phrases || c.matched_phrases,
      scheme: d.scheme_label && d.risk >= 0.5 ? d.scheme_label.ru : c.scheme };
    renderCalls();
  }
  if (type === "call_ended") { delete A.calls[d.call_id]; renderCalls(); }
  if (type === "antifraud_signal") loadJournal();
  if (type === "graph_updated") { clearTimeout(graphTimer); graphTimer = setTimeout(() => loadGraph(d.focus), 250); }
  if (type === "decoy") toastA(`🪤 Приманка: ${esc(d.client)} «перевела» ${fmt(d.amount)} на ${esc(d.card)} под ${esc(d.app)}. Мошенник видит «успешно», деньги на месте, карта заморожена. Поймано карт: ${d.cards.length}.`);
  if (type === "relative_alert" && d.source === "phone") toastA(`📱 ${esc(d.client)}: ${esc(d.summary?.ru || "")} · риск ${pct(d.risk)}. Доверенное лицо уведомлено ещё до перевода.`);
  else if (type === "relative_alert" && d.source !== "telecom" && d.source !== "decoy") toastA(`⚠️ Звонок с риском ${pct(d.risk)}: ${esc(d.client)} · схема ${esc(d.scheme.ru)}. Доверенное лицо уведомлено.`);
}

async function init() {
  const cfg = await api("/api/config");
  $("#cfg").innerHTML = `<span class="pill ${cfg.llm_enabled ? "low" : "neutral"}">${cfg.llm_enabled ? "LLM on" : "ключевые слова"}</span>
    <span class="pill ${cfg.telegram_enabled ? "low" : "neutral"}">${cfg.telegram_enabled ? "Telegram on" : "Telegram off"}</span>`;
  const [feed, calls] = await Promise.all([api("/api/transfers"), api("/api/calls/active")]);
  A.feed = feed;
  calls.forEach((c) => (A.calls[c.call_id] = { ...c, client: c.client_id === DEMO_CLIENT_ID ? "Сауле Ахметова" : null }));
  renderFeed(); renderCalls(); loadMetrics(); loadJournal();
  api("/api/eval").then((e) => { A.eval = e; renderMetrics(); }).catch(() => {});
  $("#detail").innerHTML = `<div class="text-[13px] muted leading-relaxed">Выберите операцию в ленте или узел графа.<br><br>
    <span class="faint">Граф строится по синтетическим переводам за 30 дней: ~430 счетов, ~5 300 переводов, 3 дроп-сети. Узлы с риском ≥ 60 считаются дропперами. Внешние карты других банков показаны серыми прямоугольниками.</span></div>`;
  $("#thr").addEventListener("input", (e) => ($("#thr-v").textContent = e.target.value));
  $("#thr").addEventListener("change", (e) => { A.threshold = Number(e.target.value); A.positions = {}; loadGraph(); });
  loadGraph();
  connectWS(onEvent, (ok) => ($("#ws-dot").style.background = ok ? "var(--accent)" : "var(--danger)"));
}
init();
