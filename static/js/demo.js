// Presenter's remote for the client screen: two guided scenarios, one click per step.
// Each step says what the scammer says and what BCC Shield does at that moment. In a real bank app none of this
// exists: the phone (CallKit / Android) and the scammer's own actions drive these events.

const DEMO = {
  done: new Set(),
  last: null,
  steps: [
    { id: "call", group: 1, title: "Звонок с незнакомого номера",
      scam: "«Здравствуйте, служба безопасности банка. С вашей карты пытаются списать деньги…»",
      bank: "Телефон сообщил приложению банка: входящий с номера не из контактов, идёт 12 минут, банк открыт посреди разговора. Риск 65%: у Сауле жёлтое предупреждение, сыну ушло сообщение. Разговор никто не слушает.",
      run: async () => { closeOverlay(); await phoneCall({ caller: "+7 701 ••• 45 67", caller_kind: "unknown", minutes_ago: 12 }); go("call"); } },
    { id: "loan", group: 1, title: "«Оформите встречный кредит»",
      scam: "«На вас оформляют кредит. Чтобы его отменить, оформите встречный на 1,5 млн».",
      bank: "Кредит не выдан: идёт подозрительный звонок. Заявка ушла сыну, деньги поступят только после его решения.",
      run: async () => { closeOverlay(); S.loanAmount = 1500000; go("loan"); await wait(250); document.querySelector('[onclick^="takeLoan"]')?.click(); } },
    { id: "transfer", group: 1, title: "«Переведите на безопасный счёт»",
      scam: "«Переведите все деньги на безопасный счёт: Kaspi 4400 4301 2233 4417».",
      bank: "Перевод на паузе до решения семьи. Сын видит причины и нажимает «Отклонить» в своём кабинете — деньги остаются у мамы, карта уходит в Антифрод-центр.",
      link: { href: "/relative", text: "Открыть кабинет сына" },
      run: async () => { closeOverlay(); go("transfer"); await wait(200); tpl("scam"); await wait(150); await submitTransfer(); } },
    { id: "anydesk", group: 2, title: "«Установите AnyDesk»",
      scam: "«Я помогу защитить счёт. Установите AnyDesk и продиктуйте код».",
      bank: "Теперь экран Сауле видит мошенник. BCC Shield убирает с экрана все тревоги — иначе он поймёт и уйдёт в другой банк — и включает приманку. Сыну уже ушло предупреждение.",
      run: async () => { closeOverlay(); await remoteApp("AnyDesk"); go("home"); } },
    { id: "decoy1", group: 2, title: "Мошенник переводит 2 млн",
      scam: "Мошенник сам вводит через AnyDesk номер своей карты: Kaspi •• 4417, 2 000 000 ₸.",
      bank: "На экране «Перевод выполнен», баланс уменьшился. На деле деньги не ушли. Номер карты мошенник ввёл сам — это его карта-дроп: переводы на неё из БЦК закрыты, номер ушёл в Антифрод-центр.",
      run: async () => { closeOverlay(); go("transfer"); await wait(200); tpl("scam"); await wait(150); await submitTransfer(); } },
    { id: "decoy2", group: 2, title: "«Не дошло, вот другая карта»",
      scam: "«Перевод не прошёл, переведите 800 000 на Halyk •• 5521».",
      bank: "Вторая карта поймана так же. Чем дольше мошенник «работает», тем больше своих карт он сдаёт. Аналитик видит их в графе, сын — в Telegram.",
      run: async () => { closeOverlay(); go("transfer"); await wait(200); tpl("dtp"); await wait(150); await submitTransfer(); } },
    { id: "reveal", group: 2, title: "Мошенник отключился",
      scam: "Мошенник уверен, что получил 2,8 млн, и закрывает AnyDesk.",
      bank: "Посторонних глаз больше нет: Сауле видит правду — это была ловушка, деньги на месте, кредит не оформлен, карты мошенника переданы в Антифрод-центр.",
      run: async () => { closeOverlay(); await remoteApp(null); } },
  ],
};
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

const ICON = {
  check: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>',
  play: '<svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor"><path d="M7 4v16l13-8z"/></svg>',
  ext: '<svg width="12" height="12" viewBox="0 0 16 16" fill="none"><path d="M5 11 11 5M6 5h5v5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>',
};

function demoStep(s, i) {
  const done = DEMO.done.has(s.id), active = DEMO.last === s.id;
  return `<button class="dstep ${done ? "done" : ""} ${active ? "active" : ""}" onclick="runDemo('${s.id}', this)">
    <span class="dnum">${done ? ICON.check : i + 1}</span>
    <span class="dtitle">${esc(s.title)}</span>
    <span class="dgo">${ICON.play}</span></button>`;
}

function renderDemo() {
  const el = document.getElementById("demo-panel");
  if (!el) return;
  const cur = DEMO.steps.find((s) => s.id === DEMO.last);
  const group = (g, name, note) => `<div class="dgroup"><div class="dlabel">${name}</div><div class="dnote">${note}</div>
    ${DEMO.steps.map((s, i) => [s, i]).filter(([s]) => s.group === g).map(([s, i]) => demoStep(s, i)).join("")}</div>`;
  el.innerHTML = `
    <div class="dhead"><div class="app-icon sm">${SHIELD_SVG.replace("<svg", '<svg width="16" height="16"')}</div>
      <div class="flex-1"><div class="text-[14px] font-semibold text-[color:var(--text)]">Пульт демо</div>
      <div class="text-[11.5px] faint">Для показа жюри. В приложении банка этого нет</div></div></div>
    <div class="flex gap-2 mt-3"><a class="dmini dlinkbtn" href="/relative" target="_blank">Кабинет сына ${ICON.ext}</a>
      <a class="dmini dlinkbtn" href="/analyst" target="_blank">Аналитик ${ICON.ext}</a></div>
    ${cur ? `<div class="dnow"><div class="dlabel" style="color:var(--danger)">Мошенник</div><p class="text-[13.5px] text-[color:var(--text)] leading-snug">${esc(cur.scam)}</p>
      <div class="dlabel mt-3">BCC Shield</div><p class="text-[13px] leading-relaxed">${esc(cur.bank)}</p>
      ${cur.link ? `<a class="dlink" href="${cur.link.href}" target="_blank">${esc(cur.link.text)} ${ICON.ext}</a>` : ""}</div>`
      : `<div class="dnow"><p class="text-[13px] leading-relaxed">Нажимайте шаги по порядку: на каждом шаге здесь появится, что говорит мошенник и что делает банк.</p></div>`}
    ${group(1, "Сценарий 1 · Звонок и семья", "Мошенник уговаривает по телефону")}
    ${group(2, "Сценарий 2 · Приманка", "Мошенник сам смотрит на экран через AnyDesk")}
    <div class="dfoot">
      <div class="flex flex-wrap gap-1.5">
        <button class="dmini" onclick="phoneCall({caller:'Айдар (сын)', caller_kind:'contact', minutes_ago:4});go('call')">Контроль: звонит сын</button>
        <button class="dmini" onclick="endCall('hangup')">Положить трубку</button>
        <button class="dmini" style="border-color:rgba(47,210,122,.4);color:var(--accent)" onclick="resetDemo(this)">Начать заново</button>
      </div>
    </div>`;
}

async function runDemo(id, btn) {
  const step = DEMO.steps.find((s) => s.id === id);
  btn.disabled = true;
  try {
    await step.run();
    DEMO.done.add(id);
    DEMO.last = id;
  } catch (e) { toast(esc(e.message || "Не получилось"), "danger"); }
  renderDemo();
}

async function resetDemo(btn) {
  if (!KEYS.admin) return toast("Сброс доступен ведущему: откройте один раз панель аналитика по ссылке с ключом.", "danger", 6000);
  btn.disabled = true;
  try { await api("/api/demo/reset", { body: {} }); } catch (e) { toast(esc(e.message), "danger"); btn.disabled = false; }
}

renderDemo();
