// Presenter's notes on the left of the client screen. Each numbered item is also a button: a click plays that step
// (in a real bank app these events come from the phone — CallKit / Android — and from the scammer's own actions).

const DEMO = {
  done: new Set(),
  steps: [
    { id: "call", html: '<b>Звонок с незнакомого номера.</b> Телефон сообщает банку о звонке — без микрофона. Жёлтый баннер у Сауле, сыну в Telegram: «подозрительный звонок».',
      run: async () => { closeOverlay(); await phoneCall({ caller: "+7 701 ••• 45 67", caller_kind: "unknown", minutes_ago: 12 }); go("call"); } },
    { id: "loan", html: '<b>Кредит</b> 1 500 000 ₸ «по просьбе банка»: деньги не выданы, заявка ушла Айдару.',
      run: async () => { closeOverlay(); S.loanAmount = 1500000; go("loan"); await wait(250); document.querySelector('[onclick^="takeLoan"]')?.click(); } },
    { id: "transfer", html: '<b>Перевод</b> на «безопасный счёт» Kaspi •• 4417: на паузе. Во вкладке родственника нажмите «Отклонить».',
      run: async () => { closeOverlay(); go("transfer"); await wait(200); tpl("scam"); await wait(150); await submitTransfer(); } },
    { id: "anydesk", html: '<b>Приманка:</b> «Установите AnyDesk» — экран видит мошенник, поэтому тревоги с экрана исчезают.',
      run: async () => { closeOverlay(); await remoteApp("AnyDesk"); go("home"); } },
    { id: "decoy1", html: 'Мошенник вводит <b>свою карту</b> Kaspi •• 4417: видит «Перевод выполнен», а деньги на месте, номер — в Антифрод-центре.',
      run: async () => { closeOverlay(); go("transfer"); await wait(200); tpl("scam"); await wait(150); await submitTransfer(); } },
    { id: "decoy2", html: '«Не дошло, вот <b>другая карта</b>» Halyk •• 5521 — ловим и её.',
      run: async () => { closeOverlay(); go("transfer"); await wait(200); tpl("dtp"); await wait(150); await submitTransfer(); } },
    { id: "reveal", html: '<b>AnyDesk закрыт</b> — Сауле видит правду: «Это была ловушка».',
      run: async () => { closeOverlay(); await remoteApp(null); } },
  ],
};
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

function renderDemo() {
  const el = document.getElementById("demo-panel");
  if (!el) return;
  el.innerHTML = `
    <div class="flex items-center gap-2 mb-5"><div class="app-icon sm"><svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M12 2.5 4.5 5.3v6.1c0 4.6 3.1 8.6 7.5 10.1 4.4-1.5 7.5-5.5 7.5-10.1V5.3L12 2.5Z" fill="#1c1c1a"/><path d="M12 5.2v14.1c3.1-1.3 5.1-4.4 5.1-7.9V7.1L12 5.2Z" fill="#2fd27a"/></svg></div><span class="text-[13px] text-[color:var(--text)]">BCC Shield (демо) · экран клиента</span></div>
    <ol>${DEMO.steps.map((s) => `<li class="step ${DEMO.done.has(s.id) ? "done" : ""}" role="button" tabindex="0" onclick="runDemo('${s.id}', this)" onkeydown="event.key==='Enter'&&runDemo('${s.id}', this)">${s.html}</li>`).join("")}</ol>
    <p class="mt-6 text-[12px] faint">Нажимайте пункты по порядку. Контроль: <span class="link" role="button" onclick="phoneCall({caller:'Айдар (сын)', caller_kind:'contact', minutes_ago:4});go('call')">звонит сын</span> — риск 0, перевод сыну проходит сразу.</p>
    <p class="mt-4 text-[12px]"><a class="link" href="/relative" target="_blank">Родственник ↗</a> &nbsp; <a class="link" href="/analyst" target="_blank">Аналитик ↗</a> &nbsp; <span class="link" role="button" onclick="resetDemo(this)">Начать заново</span></p>`;
}

async function runDemo(id, li) {
  if (li.dataset.busy) return;
  li.dataset.busy = "1";
  try {
    await DEMO.steps.find((s) => s.id === id).run();
    DEMO.done.add(id);
  } catch (e) { toast(esc(e.message || "Не получилось"), "danger"); }
  renderDemo();
}

async function resetDemo() {
  if (!KEYS.admin) return toast("Сброс доступен ведущему: откройте один раз панель аналитика по ссылке с ключом.", "danger", 6000);
  try { await api("/api/demo/reset", { body: {} }); } catch (e) { toast(esc(e.message), "danger"); }
}

renderDemo();
