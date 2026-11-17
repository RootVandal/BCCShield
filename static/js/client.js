// Client mobile app (Сауле). Single-page: screens + overlays, live via WebSocket.
const T = {
  ru: {
    hello: "Здравствуйте", balance: "Баланс", frozen: "заморожено до решения", transfer: "Перевод", loan: "Кредит",
    callGuard: "Защита звонка", shield: "Семейный щит", history: "История", all: "Все", back: "Назад",
    protectionOn: "Режим защиты включён: переводы — только с подтверждением", byCard: "По карте", byPhone: "По телефону",
    bank: "Банк получателя", card: "Номер карты", phone: "Телефон", amount: "Сумма", send: "Перевести",
    templates: "Шаблоны для демо", shieldOnNote: "Семейный щит включён", loanTitle: "Быстрый кредит",
    loanNote: "Одобрение за 1 минуту, деньги сразу на карте (демо)", getLoan: "Получить",
    callIdle: "Включите защиту, когда говорите по телефону на громкой связи. Приложение слушает собеседника и предупредит, если это мошенники.",
    startCall: "Включить защиту звонка", endCall: "Завершить звонок", risk: "Риск мошенничества",
    manual: "Фраза собеседника", sendPhrase: "Отправить", mic: "Микрофон", micOn: "Слушаю…", scenarios: "Готовые сценарии",
    feedEmpty: "Реплики собеседника появятся здесь", privacy: "Текст звонка не сохраняется — только оценка риска и сработавшие фразы.",
    mediumTitle: "Похоже на мошенников",
    mediumText: "Банк никогда не просит переводить деньги на «безопасный счёт» и не спрашивает коды.",
    hangup: "Положить трубку", imSafe: "Я в безопасности",
    highTitle: "СТОП. Вам звонят мошенники",
    highL1: "Банк никогда не просит переводить деньги на «безопасный счёт».",
    highL2: "Никому не называйте коды из СМС и не берите кредит по просьбе звонящего.",
    highL3: "Мы включили режим защиты: переводы — только с подтверждением", scheme: "Схема",
    checkBank: "Проверить: звонит ли мне банк?", close: "Закрыть",
    qTitle: "Пара вопросов перед переводом", qText: "Мошенники часто звонят от имени банка. Ответьте честно — это защитит ваши деньги.",
    q1: "Вам сейчас звонят?", q2: "Вас просят перевести деньги на «безопасный счёт»?", q3: "Звонящий представился сотрудником банка или полиции?",
    yes: "Да", no: "Нет", continue: "Продолжить", cancel: "Отменить",
    pausedTitle: "Перевод приостановлен для вашей безопасности", pausedSent: "Мы отправили запрос",
    pausedCooling: "Если ответа не будет, перевод выполнится через", whyPaused: "Почему",
    opPausedTitle: "Операция приостановлена для вашей безопасности", opPausedCooling: "Если ответа не будет, операция выполнится через",
    rejectedTitle: "Перевод отменён", rejectedText: "Ваши деньги в безопасности. Получатель передан в Антифрод-центр.",
    doneTitle: "Перевод выполнен", toHome: "На главную", blockedTitle: "Перевод заблокирован",
    blockedText: "Счёт получателя заморожен банком как мошеннический. Деньги не списаны.",
    loanDone: "Кредит зачислен", settings: "Настройки щита", trusted: "Доверенное лицо", threshold: "Порог суммы",
    tgLink: "Подключить Telegram родственника", shieldToggle: "Семейный щит", shieldOffNote: "Отключение — только с подтверждением доверенного лица или через 24 часа.",
    protection: "Режим защиты", on: "включён", off: "выключен", language: "Язык",
    loanWarn: "Если по телефону вас просят оформить кредит — это мошенники. Банк так не делает.",
    family: "Семейный щит", trustedList: "Доверенные лица", addTrusted: "Добавить доверенное лицо",
    familyEmpty: "Добавьте близкого человека. Он будет видеть ваши переводы и подтверждать крупные и подозрительные.",
    loanSent: "Заявка отправлена на подтверждение",
    cash: "Наличные", cashTitle: "Снять наличные", cashNote: "Получение в кассе отделения или в банкомате (демо)", cashGo: "Снять",
    cashWarn: "Если по телефону просят снять деньги и передать курьеру, «на хранение» или купить валюту — это мошенники.",
    deposit: "Депозит", depositTitle: "Депозит «Сенім»", depositNote: "14,5% годовых · до декабря 2027",
    depositClose: "Закрыть досрочно", depositLoss: "При досрочном закрытии начисленные проценты пропадут. Деньги придут на карту.",
    depositWarn: "Мошенники просят «перевести накопления в безопасное место». Банк так никогда не делает.",
    depositEmpty: "Депозит закрыт",
    cashDone: "Наличные выданы", depositDone: "Депозит закрыт", depositDoneText: "Деньги зачислены на карту",
    opRejected: "Операция отменена", opRejectedText: "Доверенное лицо остановило операцию. Ваши деньги на месте.",
    loanCooling: "Кредит заморожен", loanCoolingText: "Сейчас идёт подозрительный звонок. Деньги поступят через 5 минут, если не отмените.",
    telecom: "Оператор связи: вам звонят с номера из базы мошенников. Не переводите и не снимайте деньги.",
    q2cash: "Вас просят снять деньги и передать курьеру, «на хранение» или купить валюту?",
  },
  kk: {
    hello: "Сәлеметсіз бе", balance: "Теңгерім", frozen: "шешімге дейін тоқтатылған", transfer: "Аударым", loan: "Несие",
    callGuard: "Қоңырауды қорғау", shield: "Отбасы қалқаны", history: "Тарих", all: "Барлығы", back: "Артқа",
    protectionOn: "Қорғау режимі қосулы: аударымдар тек растаумен", byCard: "Карта бойынша", byPhone: "Телефон бойынша",
    bank: "Алушының банкі", card: "Карта нөмірі", phone: "Телефон", amount: "Сома", send: "Аудару",
    templates: "Демо үлгілері", shieldOnNote: "Отбасылық қалқан қосулы", loanTitle: "Жылдам несие",
    loanNote: "1 минутта мақұлдау, ақша бірден картада (демо)", getLoan: "Алу",
    callIdle: "Телефонмен қатты дауыста сөйлескенде қорғауды қосыңыз. Қосымша әңгімелесушіні тыңдап, алаяқтар болса ескертеді.",
    startCall: "Қоңырауды қорғауды қосу", endCall: "Қоңырауды аяқтау", risk: "Алаяқтық қаупі",
    manual: "Әңгімелесушінің сөзі", sendPhrase: "Жіберу", mic: "Микрофон", micOn: "Тыңдап тұрмын…", scenarios: "Дайын сценарийлер",
    feedEmpty: "Әңгімелесушінің сөздері осында шығады", privacy: "Қоңырау мәтіні сақталмайды — тек қауіп бағасы мен табылған сөздер.",
    mediumTitle: "Алаяқтарға ұқсайды",
    mediumText: "Банк ешқашан ақшаны «қауіпсіз шотқа» аударуды сұрамайды және кодтарды сұрамайды.",
    hangup: "Тұтқаны қою", imSafe: "Мен қауіпсіздікте",
    highTitle: "ТОҚТАҢЫЗ. Сізге алаяқтар қоңырау шалып тұр",
    highL1: "Банк ешқашан ақшаны «қауіпсіз шотқа» аударуды сұрамайды.",
    highL2: "СМС кодтарын ешкімге айтпаңыз және қоңырау шалушының өтінішімен несие алмаңыз.",
    highL3: "Біз қорғау режимін қостық: аударымдар тек растаумен —", scheme: "Схема",
    checkBank: "Тексеру: банк маған қоңырау шалып тұр ма?", close: "Жабу",
    qTitle: "Аударым алдында бірнеше сұрақ", qText: "Алаяқтар жиі банк атынан қоңырау шалады. Шынын айтыңыз — бұл ақшаңызды қорғайды.",
    q1: "Сізге қазір қоңырау шалып тұр ма?", q2: "Сізден ақшаны «қауіпсіз шотқа» аударуды сұрай ма?", q3: "Қоңырау шалушы банк немесе полиция қызметкері ретінде танысты ма?",
    yes: "Иә", no: "Жоқ", continue: "Жалғастыру", cancel: "Бас тарту",
    pausedTitle: "Аударым сіздің қауіпсіздігіңіз үшін тоқтатылды", pausedSent: "Біз сұраныс жібердік:",
    pausedCooling: "Жауап болмаса, аударым мына уақыттан кейін орындалады", whyPaused: "Себебі",
    opPausedTitle: "Операция сіздің қауіпсіздігіңіз үшін тоқтатылды", opPausedCooling: "Жауап болмаса, операция мына уақыттан кейін орындалады",
    rejectedTitle: "Аударым тоқтатылды", rejectedText: "Ақшаңыз қауіпсіз. Алушы Антифрод-орталығына жіберілді.",
    doneTitle: "Аударым орындалды", toHome: "Басты бетке", blockedTitle: "Аударым бұғатталды",
    blockedText: "Алушының шотын банк алаяқтық ретінде бұғаттады. Ақша есептен шығарылмады.",
    loanDone: "Несие есептелді", settings: "Қалқан баптаулары", trusted: "Сенімді адам", threshold: "Сома шегі",
    tgLink: "Туысқанның Telegram-ын қосу", shieldToggle: "Отбасылық қалқан", shieldOffNote: "Өшіру — тек сенімді адамның растауымен немесе 24 сағаттан кейін.",
    protection: "Қорғау режимі", on: "қосулы", off: "өшірулі", language: "Тіл",
    loanWarn: "Телефон арқылы несие рәсімдеуді сұраса — бұл алаяқтар. Банк олай істемейді.",
    family: "Отбасы қалқаны", trustedList: "Сенімді адамдар", addTrusted: "Сенімді адам қосу",
    familyEmpty: "Жақын адамыңызды қосыңыз. Ол аударымдарыңызды көріп, ірі және күдікті аударымдарды растайды.",
    loanSent: "Өтінім растауға жіберілді",
    cash: "Қолма-қол", cashTitle: "Қолма-қол ақша алу", cashNote: "Бөлімшенің кассасында немесе банкоматта (демо)", cashGo: "Алу",
    cashWarn: "Телефонмен ақшаны шешіп, курьерге беруді, «сақтауға» беруді немесе валюта сатып алуды сұраса — бұл алаяқтар.",
    deposit: "Депозит", depositTitle: "«Сенім» депозиті", depositNote: "Жылдық 14,5% · 2027 жылдың желтоқсанына дейін",
    depositClose: "Мерзімінен бұрын жабу", depositLoss: "Мерзімінен бұрын жапқанда пайыздар жойылады. Ақша картаға түседі.",
    depositWarn: "Алаяқтар «жинақты қауіпсіз жерге аударуды» сұрайды. Банк ешқашан олай істемейді.",
    depositEmpty: "Депозит жабылды",
    cashDone: "Ақша берілді", depositDone: "Депозит жабылды", depositDoneText: "Ақша картаға түсті",
    opRejected: "Операция тоқтатылды", opRejectedText: "Сенімді адам операцияны тоқтатты. Ақшаңыз орнында.",
    loanCooling: "Несие тоқтатылды", loanCoolingText: "Қазір күдікті қоңырау жүріп жатыр. Ақша 5 минуттан кейін түседі, егер бас тартпасаңыз.",
    telecom: "Байланыс операторы: сізге алаяқтар базасындағы нөмірден қоңырау шалуда. Ақша аудармаңыз және шешпеңіз.",
    q2cash: "Сізден ақшаны шешіп, курьерге, «сақтауға» беруді немесе валюта сатып алуды сұрай ма?",
  },
};

const S = {
  client: null, cfg: {}, lang: "ru", screen: "home", transfers: [], scenarios: [],
  call: null,              // {id, risk, level, history:[], feed:[], categories:{}, scheme}
  dismissed: {},           // per-call dismissed alert levels
  pending: null,           // transfer currently shown in paused overlay
  form: { mode: "card", bank: "Kaspi", card: "", phone: "", amount: "", pasted: false, openedAt: Date.now() },
  mic: { on: false, rec: null, stream: null },
};
const t = (k) => T[S.lang][k] ?? T.ru[k] ?? k;
const reasonText = (r) => (S.lang === "kk" ? r.kk : r.ru) || r.ru;
const initials = (name) => (name || "?").split(" ").filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase();
const activeContacts = () => (S.client?.contacts || []).filter((c) => c.status === "active");
const contactNames = () => activeContacts().map((c) => `${c.name} (${c.relation})`).join(", ");

const ICONS = {
  transfer: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M7 7h12l-3-3M17 17H5l3 3"/></svg>`,
  loan: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><rect x="3" y="6" width="18" height="12" rx="2"/><circle cx="12" cy="12" r="2.5"/></svg>`,
  call: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 4h3l2 5-2 1a11 11 0 0 0 6 6l1-2 5 2v3a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2Z"/></svg>`,
  shield: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"><path d="M12 3 5 5.7v5.7c0 4.3 2.9 8 7 9.6 4.1-1.6 7-5.3 7-9.6V5.7L12 3Z"/></svg>`,
  cash: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 8h16v9H4z"/><path d="M8 8V6h8v2M12 11v3M10.5 12.5h3"/></svg>`,
  deposit: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 10 12 4l9 6M5 10v8M9.5 10v8M14.5 10v8M19 10v8M3 20h18"/></svg>`,
  back: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="m15 18-6-6 6-6"/></svg>`,
  mic: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/></svg>`,
  play: `<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M7 4v16l13-8z"/></svg>`,
};

// ---------- rendering --------------------------------------------------------------------------------
function header(title) {
  return `<div class="flex items-center gap-2 px-4 pt-2 pb-3 sticky top-0 z-10 bg-[#0d0d0c]/90 backdrop-blur">
    <button class="w-9 h-9 grid place-items-center rounded-full hover:bg-white/5" onclick="go('home')" aria-label="${t("back")}">${ICONS.back}</button>
    <h2 class="text-[17px] font-semibold">${title}</h2></div>`;
}

function langToggle() {
  return `<div class="seg" role="group" aria-label="Язык"><button class="${S.lang === "ru" ? "on" : ""}" onclick="setLang('ru')">RU</button><button class="${S.lang === "kk" ? "on" : ""}" onclick="setLang('kk')">KZ</button></div>`;
}

function txRow(tx) {
  const dep = tx.kind === "deposit";
  const out = !dep && (tx.direction ? tx.direction === "out" : true);
  const other = dep || out ? tx.to : tx.from;
  const name = other.name.length > 22 ? other.name.slice(0, 21) + "…" : other.name;
  return `<div class="row">
    <div class="avatar">${esc(other.bank === "BCC" ? name.slice(0, 1) : other.bank.slice(0, 1))}</div>
    <div class="flex-1 min-w-0"><div class="text-[14px] truncate">${esc(name)}</div>
      <div class="text-[12px] muted">${esc(other.bank)} ${esc(other.card)} · ${dateShort(tx.created_at)} ${timeHM(tx.created_at)}</div></div>
    <div class="text-right"><div class="num text-[14px] ${out ? "" : "text-[color:var(--accent)]"}">${out ? "−" : "+"}${fmt(tx.amount)}</div>
      ${tx.status !== "completed" ? statusPill(tx.status) : ""}</div></div>`;
}

function renderHome() {
  const c = S.client;
  const first = c.name.split(" ")[0];
  const callLive = !!S.call;
  return `<div class="px-4 pb-8 fade-in">
    <div class="flex items-center justify-between pt-1 pb-4">
      <div class="flex items-center gap-3"><div class="avatar" style="background:var(--accent-dim);color:var(--accent)">${esc(initials(c.name))}</div>
        <div><div class="text-[12px] muted">${t("hello")},</div><div class="text-[15px] font-semibold">${esc(first)}</div></div></div>
      ${langToggle()}
    </div>
    ${c.telecom_alert ? `<div class="w-full mb-2 px-3 py-2.5 rounded-xl text-[12.5px] flex gap-2 items-start" style="background:var(--danger-dim);color:#ffb1a8" role="alert">
      <span>📡</span><span>${t("telecom")}</span></div>` : ""}
    ${c.protection_mode === "on" ? `<button onclick="go('settings')" class="w-full text-left mb-3 px-3 py-2.5 rounded-xl text-[12.5px] flex gap-2 items-start" style="background:var(--danger-dim);color:#ffb1a8">
      <span class="mt-0.5">${ICONS.shield.replace("<svg", '<svg width="14" height="14"')}</span><span>${t("protectionOn")}: ${esc(contactNames() || "—")}</span></button>` : ""}
    <div class="bank-card">
      <div class="relative z-[1] flex justify-between items-start"><span class="text-[12px] text-white/70">${t("balance")}</span>
        <span class="text-[11px] text-white/60 mono">BCC Shield</span></div>
      <div class="relative z-[1] mt-2 text-[30px] font-semibold num tracking-tight">${fmt(c.balance)}</div>
      ${c.frozen > 0 ? `<div class="relative z-[1] text-[12px] mt-0.5" style="color:#ffd58a">${fmt(c.frozen)} ${t("frozen")}</div>` : ""}
      ${c.deposit > 0 ? `<div class="relative z-[1] text-[12px] mt-0.5 text-white/65">${t("deposit")}: <span class="num">${fmt(c.deposit)}</span></div>` : ""}
      <div class="absolute z-[1] bottom-4 left-[18px] right-[18px] flex justify-between items-end text-[12.5px] text-white/80">
        <span class="mono">${esc(c.card)}</span>
        <span class="flex items-center gap-1.5">${c.shield_enabled ? `<span class="dot" style="width:14px;height:14px">${SHIELD_DOT}</span> Shield` : "Shield off"}</span></div>
    </div>
    <div class="grid grid-cols-3 gap-2 mt-4">
      ${tile("transfer", t("transfer"), "transfer")}${tile("cash", t("cash"), "cash")}${tile("loan", t("loan"), "loan")}
      ${tile("deposit", t("deposit"), "deposit")}
      ${tile("call", t("callGuard"), "call", callLive ? `<span class="live absolute top-3 right-3"></span>` : "")}
      ${tile("shield", t("shield"), "settings")}
    </div>
    <div class="flex items-center justify-between mt-6 mb-1"><h3 class="text-[15px] font-semibold">${t("history")}</h3>
      <button class="text-[13px] muted" onclick="go('history')">${t("all")}</button></div>
    <div>${S.transfers.slice(0, 5).map(txRow).join("") || `<p class="muted text-[13px] py-4">—</p>`}</div>
  </div>`;
}

function tile(icon, label, screen, extra = "") {
  return `<button class="tile" onclick="go('${screen}')">${extra}<span class="ic">${ICONS[icon]}</span><span class="text-[13px] font-medium leading-tight text-left">${label}</span></button>`;
}

function renderTransfer() {
  const f = S.form;
  const banks = ["BCC", "Kaspi", "Halyk", "Freedom", "Jusan", "Forte"];
  return `${header(t("transfer"))}<div class="px-4 pb-8 fade-in">
    <div class="seg mb-4"><button class="${f.mode === "card" ? "on" : ""}" onclick="setMode('card')">${t("byCard")}</button>
      <button class="${f.mode === "phone" ? "on" : ""}" onclick="setMode('phone')">${t("byPhone")}</button></div>
    <div class="label mb-2">${t("bank")}</div>
    <div class="flex flex-wrap gap-1.5 mb-4">${banks.map((b) => `<button class="chip ${f.bank === b ? "on" : ""}" onclick="setBank('${b}')">${b}</button>`).join("")}</div>
    ${f.mode === "card"
      ? `<label class="label block mb-2" for="f-card">${t("card")}</label><input id="f-card" class="input mono" inputmode="numeric" placeholder="0000 0000 0000 0000" value="${esc(f.card)}">`
      : `<label class="label block mb-2" for="f-phone">${t("phone")}</label><input id="f-phone" class="input mono" inputmode="tel" placeholder="+7 7__ ___ __ __" value="${esc(f.phone)}">`}
    <label class="label block mb-2 mt-4" for="f-amount">${t("amount")}</label>
    <div class="relative"><input id="f-amount" class="input num text-[20px] h-[52px] pr-10" inputmode="numeric" placeholder="0" value="${esc(f.amount)}">
      <span class="absolute right-4 top-1/2 -translate-y-1/2 muted">₸</span></div>
    <div class="text-[12px] muted mt-2">${t("balance")}: <span class="num">${fmt(S.client.balance)}</span></div>
    <div class="label mt-6 mb-2">${t("templates")}</div>
    <div class="flex flex-col gap-1.5">
      <button class="card-2 text-left px-3 py-2.5 text-[13px] flex justify-between items-center" onclick="tpl('scam')"><span>Kaspi •• 4417 <span class="muted">· «безопасный счёт»</span></span><span class="num">2 000 000 ₸</span></button>
      <button class="card-2 text-left px-3 py-2.5 text-[13px] flex justify-between items-center" onclick="tpl('dtp')"><span>Halyk •• 5521 <span class="muted">· «сыну после ДТП»</span></span><span class="num">800 000 ₸</span></button>
      <button class="card-2 text-left px-3 py-2.5 text-[13px] flex justify-between items-center" onclick="tpl('son')"><span>Айдар (сын) <span class="muted">· BCC</span></span><span class="num">40 000 ₸</span></button>
      <button class="card-2 text-left px-3 py-2.5 text-[13px] flex justify-between items-center" onclick="tpl('medium')"><span>Halyk •• 7788 <span class="muted">· новая карта</span></span><span class="num">250 000 ₸</span></button>
    </div>
    <button class="btn btn-accent btn-lg btn-block mt-6" id="send-btn" onclick="submitTransfer()">${t("send")}</button>
    <p class="text-[11.5px] faint text-center mt-3">${S.client.shield_enabled ? "🛡 " + t("shieldOnNote") : ""}</p>
  </div>`;
}

function renderLoan() {
  const presets = [500000, 1500000, 3000000];
  S.loanAmount ??= 1500000;
  return `${header(t("loanTitle"))}<div class="px-4 pb-8 fade-in">
    <p class="text-[13px] muted mb-5">${t("loanNote")}</p>
    ${S.client.protection_mode === "on" || S.call?.risk >= 0.5 || S.client.telecom_alert ? `<div class="mb-4 px-3 py-2.5 rounded-xl text-[12.5px]" style="background:var(--danger-dim);color:#ffb1a8">⚠️ ${t("loanWarn")}</div>` : ""}
    <div class="card p-5 text-center"><div class="label">${t("amount")}</div>
      <div class="text-[34px] font-semibold num mt-1">${fmt(S.loanAmount)}</div>
      <div class="flex justify-center gap-1.5 mt-4">${presets.map((p) => `<button class="chip ${S.loanAmount === p ? "on" : ""}" onclick="S.loanAmount=${p};render()">${fmtShort(p)}</button>`).join("")}</div>
      <div class="grid grid-cols-2 gap-3 mt-5 text-left text-[12.5px]"><div class="card-2 p-3"><div class="muted">Срок</div><div class="mt-0.5">24 мес.</div></div>
        <div class="card-2 p-3"><div class="muted">Платёж</div><div class="mt-0.5 num">${fmt(S.loanAmount / 24 * 1.12)}</div></div></div>
    </div>
    <button class="btn btn-pale btn-lg btn-block mt-5" onclick="takeLoan(this)">${t("getLoan")} ${fmt(S.loanAmount)}</button>
  </div>`;
}

function dangerNote(key) {
  const c = S.client;
  return c.protection_mode === "on" || S.call?.risk >= 0.5 || c.telecom_alert
    ? `<div class="mb-4 px-3 py-2.5 rounded-xl text-[12.5px]" style="background:var(--danger-dim);color:#ffb1a8">⚠️ ${t(key)}</div>` : "";
}

function renderCash() {
  const presets = [100000, 500000, 2000000];
  S.cashAmount ??= 500000;
  return `${header(t("cashTitle"))}<div class="px-4 pb-8 fade-in">
    <p class="text-[13px] muted mb-5">${t("cashNote")}</p>
    ${dangerNote("cashWarn")}
    <div class="card p-5 text-center"><div class="label">${t("amount")}</div>
      <div class="text-[34px] font-semibold num mt-1">${fmt(S.cashAmount)}</div>
      <div class="flex justify-center gap-1.5 mt-4">${presets.map((p) => `<button class="chip ${S.cashAmount === p ? "on" : ""}" onclick="S.cashAmount=${p};render()">${fmtShort(p)}</button>`).join("")}</div>
      <div class="text-[12px] muted mt-4">${t("balance")}: <span class="num">${fmt(S.client.balance)}</span></div></div>
    <button class="btn btn-accent btn-lg btn-block mt-5" onclick="submitTransfer({kind:'cash', amount:S.cashAmount, behavior:{fill_seconds:10}})">${t("cashGo")} ${fmt(S.cashAmount)}</button>
    <p class="text-[11.5px] faint text-center mt-3">${S.client.shield_enabled ? "🛡 " + t("shieldOnNote") : ""}</p>
  </div>`;
}

function renderDeposit() {
  const d = S.client.deposit || 0;
  return `${header(t("depositTitle"))}<div class="px-4 pb-8 fade-in">
    ${dangerNote("depositWarn")}
    <div class="card p-5"><div class="label">${t("deposit")}</div>
      <div class="text-[34px] font-semibold num mt-1">${d > 0 ? fmt(d) : "—"}</div>
      <div class="text-[13px] muted mt-1">${d > 0 ? t("depositNote") : t("depositEmpty")}</div></div>
    ${d > 0 ? `<p class="text-[12.5px] muted mt-4 leading-relaxed">${t("depositLoss")}</p>
      <button class="btn btn-block btn-lg mt-4" onclick="submitTransfer({kind:'deposit', behavior:{fill_seconds:10}})">${t("depositClose")}</button>` : ""}
  </div>`;
}

function renderCall() {
  if (!S.call) {
    return `${header(t("callGuard"))}<div class="px-5 pb-8 fade-in flex flex-col items-center text-center">
      <div class="app-icon mt-8" style="width:76px;height:76px;border-radius:20px">${SHIELD_SVG.replace("<svg", '<svg width="40" height="40"')}</div>
      <p class="text-[14px] muted mt-6 leading-relaxed">${t("callIdle")}</p>
      <button class="btn btn-accent btn-lg btn-block mt-8" onclick="startCall(this)">${t("startCall")}</button>
      <p class="text-[11.5px] faint mt-4">${t("privacy")}</p></div>`;
  }
  return `${header(t("callGuard"))}<div class="px-4 pb-8 fade-in">
    <div class="card p-4 flex flex-col items-center">
      <div id="gauge" class="w-full flex justify-center"></div>
      <div id="scheme" class="text-[12.5px] muted -mt-1 h-5"></div>
      <div class="w-full mt-2" id="spark"></div>
      <div id="cats" class="flex flex-wrap gap-1 justify-center mt-2"></div>
    </div>
    <div class="flex items-center justify-between mt-4 mb-2"><span class="label">Лента разговора</span>
      <span class="text-[11px] faint" id="llm-badge"></span></div>
    <div id="feed" class="card p-3 h-[190px] scroll flex flex-col gap-2 text-[13.5px] leading-snug"></div>
    <form class="flex gap-2 mt-3" onsubmit="sendPhrase(event)">
      <input id="phrase" class="input h-10 text-[14px]" placeholder="${t("manual")}…" autocomplete="off">
      <button class="btn btn-pale h-10" type="submit">${t("sendPhrase")}</button></form>
    <button id="mic-btn" class="btn btn-block mt-2" onclick="toggleMic()">${ICONS.mic}<span>${t("mic")}</span></button>
    <div class="label mt-5 mb-2">${t("scenarios")}</div>
    <div class="flex flex-col gap-1.5" id="scen"></div>
    <button class="btn btn-danger btn-block mt-5" onclick="endCall('ended')">${t("endCall")}</button>
    <p class="text-[11px] faint text-center mt-3">${t("privacy")}</p></div>`;
}

function renderScenarios() {
  const el = $("#scen");
  if (!el) return;
  const scam = S.scenarios.filter((s) => s.kind === "scam");
  const normal = S.scenarios.filter((s) => s.kind !== "scam");
  el.innerHTML = scam.map((s) => `<button class="card-2 text-left px-3 py-2.5 text-[13px] flex items-center gap-2.5" onclick="runScenario('${s.id}')">
      <span class="w-6 h-6 rounded-md grid place-items-center" style="background:var(--danger-dim);color:var(--danger)">${ICONS.play}</span>${esc(s.title)}</button>`).join("") +
    `<div class="card-2 px-3 py-2.5 text-[13px]"><div class="flex items-center gap-2.5"><span class="w-6 h-6 rounded-md grid place-items-center" style="background:var(--accent-dim);color:var(--accent)">${ICONS.play}</span>Обычный звонок</div>
      <div class="flex gap-1.5 mt-2 pl-[34px]">${normal.map((s) => `<button class="chip" onclick="runScenario('${s.id}')">${esc(s.title.split(": ")[1] || s.title)}</button>`).join("")}</div></div>`;
}

function updateCallView() {
  if (S.screen !== "call" || !S.call) return;
  const c = S.call;
  $("#gauge").innerHTML = gaugeSVG(c.risk, 230, t("risk"));
  $("#scheme").textContent = c.risk >= 0.5 && c.scheme_label ? `${t("scheme")}: ${S.lang === "kk" ? c.scheme_label.kk : c.scheme_label.ru}` : "";
  $("#spark").innerHTML = sparkSVG(c.history.map((h) => h.score), 320, 48);
  $("#cats").innerHTML = Object.values(c.categories || {}).map((l) => `<span class="pill high">${esc(S.lang === "kk" ? l.kk : l.ru)}</span>`).join("");
  $("#llm-badge").textContent = c.llm ? `LLM: ${pct(c.llm.is_scam_probability)}` : (S.cfg.llm_enabled ? "LLM: ожидание" : "ключевые слова");
  const feed = $("#feed");
  feed.innerHTML = c.feed.length ? c.feed.map((f) => `<div class="feed-item flex gap-2"><span class="text-[10px] mono faint mt-1 w-8 flex-none">${f.source === "mic" ? "MIC" : f.source === "scenario" ? "SCN" : "TXT"}</span>
    <span>${f.segments.map((s) => (s.hit ? `<mark class="hit">${esc(s.t)}</mark>` : esc(s.t))).join("")}</span></div>`).join("")
    : `<p class="faint text-[13px] m-auto">${t("feedEmpty")}</p>`;
  feed.scrollTop = feed.scrollHeight;
  const mb = $("#mic-btn");
  if (mb) { mb.classList.toggle("btn-pale", S.mic.on); mb.querySelector("span").textContent = S.mic.on ? t("micOn") : t("mic"); }
}

function renderHistory() {
  return `${header(t("history"))}<div class="px-4 pb-8 fade-in">${S.transfers.map(txRow).join("")}</div>`;
}

const STATUS_TC = { active: ["low", "подключён"], invited: ["medium", "ждёт принятия"], approval: ["medium", "ждёт разрешения"] };

function contactCard(tc) {
  const [cls, label] = STATUS_TC[tc.status] || ["neutral", tc.status];
  const r = tc.rules, bot = S.cfg.telegram_bot_username;
  const firstActive = activeContacts()[0];
  const rules = [`от ${fmt(r.threshold)}`, r.confirm_new && "новые получатели", r.confirm_loans && "кредиты"].filter(Boolean).join(" · ");
  let body = "";
  if (tc.status === "approval") {
    body = `<div class="text-[12.5px] muted mt-3 leading-relaxed">Добавить нового человека может разрешить только ${esc(firstActive ? firstActive.name : "текущее доверенное лицо")}: мы отправили ему запрос. Так мошенник не сможет «добавить сотрудника банка».</div>`;
  } else if (tc.link_code) {
    const deep = bot ? `https://t.me/${encodeURIComponent(bot)}?start=${encodeURIComponent(tc.link_code)}` : "";
    body = `<div class="mt-3 pt-3 border-t hair"><div class="text-[12.5px] muted">${tc.status === "invited" ? `Отправьте ${esc(tc.name)} приглашение — он примет его в Telegram и подтвердит свой номер:` : "Подключите Telegram:"}</div>
      ${deep ? `<a class="btn btn-sm btn-accent btn-block mt-2" target="_blank" rel="noopener" href="${deep}">Открыть @${esc(bot)}</a>
        <div class="text-[11.5px] muted mt-2 break-all select-all mono">${esc(deep)}</div>` : `<div class="text-[12px] faint mt-1">Бот выключен (нет TELEGRAM_BOT_TOKEN).</div>`}
      <div class="mono text-[12.5px] mt-2 card-2 px-3 py-2 select-all">/start ${esc(tc.link_code)}</div>
      ${tc.status === "invited" ? `<a class="link text-[12px] mt-2 inline-block" target="_blank" href="/relative?invite=${encodeURIComponent(tc.link_code)}">Принять в браузере (демо) ↗</a>` : ""}</div>`;
  }
  const cancel = tc.status !== "active" ? `<button class="btn btn-sm btn-ghost" onclick="cancelContact(${tc.id}, this)" aria-label="Отменить">✕</button>` : "";
  return `<div class="card p-4 fade-in"><div class="flex items-center gap-3"><div class="avatar" style="background:${tc.status === "active" ? "var(--accent-dim)" : "var(--surface-3)"};color:${tc.status === "active" ? "var(--accent)" : "var(--muted)"}">${esc(initials(tc.name))}</div>
      <div class="flex-1 min-w-0"><div class="text-[14px] font-medium truncate">${esc(tc.name)} <span class="muted font-normal">(${esc(tc.relation)})</span></div>
        <div class="text-[12px] muted mono">${esc(tc.phone)}</div></div><span class="pill ${cls}">${label}</span>${cancel}</div>
    <div class="text-[12px] muted mt-3">Подтверждает: <span class="text-[color:var(--text)]">${esc(rules)}</span></div>
    <div class="text-[12px] muted mt-1">Видит: <span class="text-[color:var(--text)]">${r.notify_all ? "все переводы" : "только рискованные"}</span>${tc.status === "active" ? ` · ${tc.telegram_linked ? "Telegram ✓" : "веб-кабинет"}` : ""}</div>
    ${body}</div>`;
}

function renderSettings() {
  const c = S.client, list = c.contacts || [];
  return `${header(t("family"))}<div class="px-4 pb-8 fade-in flex flex-col gap-3">
    <div class="card p-4 flex items-center justify-between gap-3"><div><div class="text-[14px] font-medium">${t("shieldToggle")}</div>
      <div class="text-[12px] muted mt-0.5">${t("shieldOffNote")}</div></div>
      <button class="switch ${c.shield_enabled ? "on" : ""}" onclick="toggleShield()" aria-label="${t("shieldToggle")}"></button></div>
    <div id="shield-msg"></div>
    <div class="flex items-center justify-between mt-2"><span class="label">${t("trustedList")}</span><span class="text-[12px] muted">${list.length}/5</span></div>
    ${list.length ? list.map(contactCard).join("") : `<div class="card p-5 text-center"><div class="w-14 h-14 mx-auto rounded-2xl grid place-items-center" style="background:var(--surface-3);color:var(--muted)">${ICONS.shield.replace("<svg", '<svg width="26" height="26"')}</div>
      <p class="text-[13px] muted mt-3 leading-relaxed">${t("familyEmpty")}</p></div>`}
    ${list.length < 5 ? `<button class="btn btn-accent btn-block btn-lg" onclick="go('addContact')">＋ ${t("addTrusted")}</button>` : ""}
    <div class="card p-4 flex justify-between items-center mt-2"><span class="text-[14px]">${t("protection")}</span>
      <span class="pill ${c.protection_mode === "on" ? "high" : "low"}">${c.protection_mode === "on" ? t("on") : t("off")}</span></div>
    <div class="card p-4 flex justify-between items-center"><span class="text-[14px]">${t("language")}</span>${langToggle()}</div>
  </div>`;
}

const REL = ["сын", "дочь", "внук", "внучка", "брат", "сестра", "муж", "жена", "друг", "другое"];
const NEW_TC = () => ({ name: "", relation: "сын", phone: "", threshold: 100000, confirm_new: true, confirm_loans: true, notify_all: true });

function renderAddContact() {
  const f = (S.newTc ||= NEW_TC());
  const toggle = (k, label, note) => `<div class="flex items-center justify-between gap-3 py-3 border-b hair"><div><div class="text-[14px]">${label}</div>${note ? `<div class="text-[11.5px] muted mt-0.5">${note}</div>` : ""}</div>
    <button type="button" class="switch ${f[k] ? "on" : ""}" onclick="S.newTc.${k}=!S.newTc.${k};render()" aria-label="${label}"></button></div>`;
  return `<div class="flex items-center gap-2 px-4 pt-2 pb-3 sticky top-0 z-10 bg-[#0d0d0c]/90 backdrop-blur">
      <button class="w-9 h-9 grid place-items-center rounded-full hover:bg-white/5" onclick="go('settings')" aria-label="${t("back")}">${ICONS.back}</button>
      <h2 class="text-[17px] font-semibold">${t("addTrusted")}</h2></div>
    <form class="px-4 pb-8 fade-in flex flex-col gap-3" onsubmit="saveContact(event)">
      <div><div class="label mb-1.5">Имя</div><input id="tc-name" class="input h-11 text-[15px]" required minlength="2" placeholder="Например, Айдар Ахметов" value="${esc(f.name)}" oninput="S.newTc.name=this.value"></div>
      <div><div class="label mb-1.5">Кем приходится</div><div class="flex flex-wrap gap-1.5">${REL.map((r) => `<button type="button" class="chip ${f.relation === r ? "on" : ""}" onclick="S.newTc.relation='${r}';render()">${r}</button>`).join("")}</div></div>
      <div><div class="label mb-1.5">Телефон (его номер в Telegram)</div><input id="tc-phone" class="input h-11 text-[15px] mono" required inputmode="tel" placeholder="+7 701 000 00 00" value="${esc(f.phone)}" oninput="S.newTc.phone=this.value"></div>
      <div class="card p-4 mt-1"><div class="label">Что подтверждает</div>
        <div class="py-3 border-b hair"><div class="text-[14px]">Переводы от суммы</div>
          <div class="flex gap-1.5 mt-2">${[50000, 100000, 200000, 500000].map((v) => `<button type="button" class="chip ${f.threshold === v ? "on" : ""}" onclick="S.newTc.threshold=${v};render()">${fmtShort(v)}</button>`).join("")}</div></div>
        ${toggle("confirm_new", "Переводы новым получателям", "Мошенники почти всегда просят перевести «на новый счёт»")}
        ${toggle("confirm_loans", "Кредиты и займы", "Кредит по просьбе звонящего — частая схема")}
        <div class="label mt-4">Что видит</div>
        ${toggle("notify_all", "Все переводы в реальном времени", "Обычные платежи проходят сразу, он просто видит их")}</div>
      <p class="text-[11.5px] faint leading-relaxed">Он примет приглашение в Telegram и подтвердит, что номер его. Ослабить правила или удалить доверенное лицо можно только с его согласия.</p>
      <button class="btn btn-accent btn-block btn-lg" type="submit" id="tc-save">Отправить приглашение</button>
      <div id="tc-err"></div></form>`;
}

async function saveContact(e) {
  e.preventDefault();
  const btn = $("#tc-save");
  btn.disabled = true;
  try {
    const tc = await api(`/api/clients/${CLIENT_ID}/contacts`, { body: S.newTc });
    S.newTc = null;
    S.client = await api(`/api/clients/${CLIENT_ID}`);
    go("settings");
    toast(tc.status === "approval" ? `⏳ Нужно разрешение доверенного лица — запрос отправлен` : `✉️ Приглашение для ${esc(tc.name)} готово`, "neutral", 4500);
  } catch (err) {
    $("#tc-err").innerHTML = `<div class="card-2 px-4 py-3 text-[13px]" style="border-color:rgba(255,92,77,.4);color:#ffb1a8">${esc(err.message)}</div>`;
    btn.disabled = false;
  }
}

async function cancelContact(id, btn) {
  btn.disabled = true;
  try { await api(`/api/clients/${CLIENT_ID}/contacts/${id}`, { method: "DELETE" }); S.client = await api(`/api/clients/${CLIENT_ID}`); render(); }
  catch (err) { toast(esc(err.message), "danger"); btn.disabled = false; }
}

function render() {
  if (!S.client) return;
  const screens = { home: renderHome, transfer: renderTransfer, loan: renderLoan, call: renderCall, history: renderHistory, settings: renderSettings,
    addContact: renderAddContact, cash: renderCash, deposit: renderDeposit };
  let html = (screens[S.screen] || renderHome)();
  // Live updates re-render the same screen many times a second: play the appear animation only on a new screen,
  // otherwise every WebSocket event restarts it and the screen flashes empty.
  if (S.screen === S.shownScreen) html = html.replace(/\bfade-in\b/g, "");
  S.shownScreen = S.screen;
  $("#screen").innerHTML = html;
  if (S.screen === "call") { renderScenarios(); updateCallView(); }
  if (S.screen === "transfer") bindTransferForm();
}

function go(screen) {
  S.screen = screen;
  if (screen === "transfer") S.form.openedAt = Date.now();
  render();
  $("#body").scrollTop = 0;
}

// ---------- overlays ---------------------------------------------------------------------------------
function overlay(html) { $("#overlay").innerHTML = html; }
function closeOverlay() { overlay(""); }

function toast(text, kind = "neutral", ms = 4000) {
  const el = document.createElement("div");
  el.className = "toast";
  el.innerHTML = `<div class="card px-4 py-3 text-[13px] shadow-2xl" style="${kind === "danger" ? "border-color:rgba(255,92,77,.4)" : ""}">${text}</div>`;
  $("#phone").appendChild(el);
  setTimeout(() => el.remove(), ms);
}

function showMediumBanner() {
  vibrate([200, 100, 200]);
  overlay(`<div class="absolute left-3 right-3 top-[54px] z-50 rounded-2xl p-4 shake" style="background:#2b2208;border:1px solid rgba(242,179,61,.45)" role="alert">
    <div class="flex gap-3"><div class="text-[22px] leading-none">⚠️</div><div>
      <div class="text-[15px] font-semibold" style="color:var(--warn)">${t("mediumTitle")}</div>
      <div class="text-[13px] mt-1 text-[#f3e3bd] leading-snug">${t("mediumText")}</div></div></div>
    <div class="grid grid-cols-2 gap-2 mt-3"><button class="btn btn-danger btn-sm h-9" onclick="endCall('hangup')">${t("hangup")}</button>
      <button class="btn btn-sm h-9" onclick="dismissAlert('medium')">${t("imSafe")}</button></div></div>`);
}

function showHighScreen() {
  vibrate([500, 150, 500, 150, 800]);
  const sch = S.call?.scheme_label ? (S.lang === "kk" ? S.call.scheme_label.kk : S.call.scheme_label.ru) : "";
  const tc = S.client.trusted_contact;
  overlay(`<div class="overlay danger-screen px-6 pt-16 pb-8" role="alertdialog" aria-label="${t("highTitle")}">
    <div class="flex justify-between items-center"><div class="w-14 h-14 rounded-full grid place-items-center ring" style="background:var(--danger)">
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round"><path d="M12 8v5M12 16.5v.5"/><path d="M10.3 3.9 2.6 17.3A2 2 0 0 0 4.3 20h15.4a2 2 0 0 0 1.7-2.7L13.7 3.9a2 2 0 0 0-3.4 0Z"/></svg></div>
      ${langToggle()}</div>
    <h2 class="text-[28px] leading-[1.1] font-semibold mt-6 text-white">${t("highTitle")}</h2>
    <div class="mt-2 text-[13px] text-white/70">${t("risk")}: <b class="num text-white">${pct(S.call?.risk || 0)}</b>${sch ? ` · ${t("scheme")}: ${esc(sch)}` : ""}</div>
    <ul class="mt-6 flex flex-col gap-3 text-[14.5px] text-white/90 leading-snug">
      <li class="flex gap-2.5"><span>✋</span><span>${t("highL1")}</span></li>
      <li class="flex gap-2.5"><span>🔒</span><span>${t("highL2")}</span></li>
      <li class="flex gap-2.5"><span>🛡</span><span>${t("highL3")} ${esc(tc?.name || "")}${tc ? ` (${esc(tc.relation)})` : ""}.</span></li></ul>
    <div id="bank-check" class="mt-4"></div>
    <div class="mt-auto flex flex-col gap-2">
      <button class="btn btn-lg btn-block" style="background:#fff;color:#7a1109;border:0;font-weight:600" onclick="endCall('hangup')">📵 ${t("hangup")}</button>
      <button class="btn btn-block" style="background:rgba(255,255,255,.1);border-color:rgba(255,255,255,.2)" onclick="checkBank('#bank-check')">${t("checkBank")}</button>
      <button class="text-[13px] text-white/60 mt-1" onclick="dismissAlert('high')">${t("close")}</button></div></div>`);
}

async function checkBank(sel) {
  const r = await api(`/api/clients/${CLIENT_ID}/bank-call-check`);
  $(sel).innerHTML = `<div class="rounded-xl px-3 py-3 text-[14px] font-medium fade-in" style="background:rgba(0,0,0,.35);border:1px solid rgba(255,255,255,.15)">${esc(S.lang === "kk" ? r.kk : r.ru)}</div>`;
}

function dismissAlert(level) {
  if (S.call) S.dismissed[S.call.id] = { ...(S.dismissed[S.call.id] || {}), [level]: true, medium: true };
  closeOverlay();
}

function showQuestions(assessment, body) {
  S.answers = { on_call: null, safe_account: null, impersonation: null };
  const q = (k, label) => `<div class="flex items-center justify-between gap-3 py-3 border-b hair"><span class="text-[14px] leading-snug">${label}</span>
    <span class="yn" data-k="${k}"><button onclick="answer('${k}',true,this)">${t("yes")}</button><button onclick="answer('${k}',false,this)">${t("no")}</button></span></div>`;
  overlay(`<div class="scrim" onclick="closeOverlay()"></div><div class="sheet" role="dialog">
    <div class="w-10 h-1 rounded bg-white/20 mx-auto -mt-2 mb-4"></div>
    <div class="flex items-center gap-2">${levelPill("medium", assessment.score)}</div>
    <h3 class="text-[19px] font-semibold mt-3">${t("qTitle")}</h3>
    <p class="text-[13px] muted mt-1">${t("qText")}</p>
    <div class="mt-2">${q("on_call", t("q1"))}${q("safe_account", t(body.kind === "cash" ? "q2cash" : "q2"))}${q("impersonation", t("q3"))}</div>
    <button class="btn btn-block mt-4" onclick="checkBank('#q-bank')">📞 ${t("checkBank")}</button><div id="q-bank" class="mt-2"></div>
    <div class="grid grid-cols-2 gap-2 mt-3"><button class="btn" onclick="closeOverlay()">${t("cancel")}</button>
      <button class="btn btn-accent" onclick='submitTransfer(${JSON.stringify(body).replace(/'/g, "&#39;")}, true)'>${t("continue")}</button></div></div>`);
}

function answer(k, v, btn) {
  S.answers[k] = v;
  const wrap = btn.parentElement;
  wrap.querySelectorAll("button").forEach((b) => (b.className = ""));
  btn.className = v ? "on-yes" : "on-no";
}

function showPaused(tx) {
  S.pending = tx;
  const tc = S.client.trusted_contact;
  const toRelative = tx.status === "pending_relative";
  const op = tx.kind && tx.kind !== "transfer";
  overlay(`<div class="overlay px-6 pt-16 pb-8" style="background:#0d0d0c" role="dialog">
    <div class="w-14 h-14 rounded-2xl grid place-items-center" style="background:var(--warn-dim);color:var(--warn)">
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 3h12M6 21h12M7 3c0 5 5 6 5 9s-5 4-5 9M17 3c0 5-5 6-5 9s5 4 5 9"/></svg></div>
    <h2 class="text-[23px] leading-tight font-semibold mt-5">${t(op ? "opPausedTitle" : "pausedTitle")}</h2>
    ${toRelative ? `<p class="text-[14px] muted mt-2">${t("pausedSent")} <span class="text-[color:var(--text)]">${esc(contactNames())}</span>.</p>` : ""}
    <div class="card p-4 mt-5"><div class="flex justify-between text-[13px]"><span class="muted">${t("amount")}</span><span class="num font-semibold">${fmt(tx.amount)}</span></div>
      <div class="flex justify-between text-[13px] mt-2"><span class="muted">→</span><span>${tx.kind && tx.kind !== "transfer" ? esc(tx.title) : `${esc(tx.to.bank)} ${esc(tx.to.card)}`}</span></div>
      <div class="flex justify-between text-[13px] mt-2"><span class="muted">${t(op ? "opPausedCooling" : "pausedCooling")}</span><span class="num mono" id="cd">—</span></div></div>
    <div class="label mt-5 mb-2">${t("whyPaused")}</div>
    <ul class="flex flex-col gap-1.5 text-[13px]">${tx.reasons.slice(0, 5).map((r) => `<li class="flex gap-2"><span style="color:var(--danger)">•</span><span>${esc(reasonText(r))}</span></li>`).join("")}</ul>
    <div class="mt-auto pt-6"><button class="btn btn-block btn-lg" onclick="closePaused()">${t("toHome")}</button></div></div>`);
  tickCountdown();
}

function tickCountdown() {
  const el = $("#cd");
  if (!el || !S.pending?.cooling_until) return;
  const left = Math.max(0, Math.round((new Date(S.pending.cooling_until) - Date.now()) / 1000));
  el.textContent = `${String(Math.floor(left / 60)).padStart(2, "0")}:${String(left % 60).padStart(2, "0")}`;
}
setInterval(tickCountdown, 1000);

function closePaused() { S.pending = null; closeOverlay(); go("home"); }

function showDone(tx) {
  if (tx.kind === "cash") showResult("ok", t("cashDone"), t("cashNote"), tx.amount);
  else if (tx.kind === "deposit") showResult("ok", t("depositDone"), t("depositDoneText"), tx.amount);
  else showResult("ok", t("doneTitle"), `${esc(tx.to.name)} · ${esc(tx.to.bank)} ${esc(tx.to.card)}`, tx.amount);
}

function showResult(kind, title, text, amount) {
  const colors = { ok: ["var(--accent-dim)", "var(--accent)"], safe: ["var(--accent-dim)", "var(--accent)"], bad: ["var(--danger-dim)", "var(--danger)"] }[kind];
  const icon = kind === "bad" ? `<path d="M6 6l12 12M18 6 6 18"/>` : kind === "safe" ? `<path d="M12 3 5 5.7v5.7c0 4.3 2.9 8 7 9.6 4.1-1.6 7-5.3 7-9.6V5.7L12 3Z"/><path d="m9 12 2 2 4-4"/>` : `<path d="m5 12 5 5 9-10"/>`;
  overlay(`<div class="overlay px-6 pt-24 pb-8 items-center text-center" style="background:#0d0d0c">
    <div class="w-20 h-20 rounded-full grid place-items-center" style="background:${colors[0]};color:${colors[1]}">
      <svg width="38" height="38" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">${icon}</svg></div>
    <h2 class="text-[24px] font-semibold mt-6">${title}</h2>
    ${amount ? `<div class="num text-[30px] font-semibold mt-2">${fmt(amount)}</div>` : ""}
    <p class="text-[14px] muted mt-3 max-w-[290px]">${text}</p>
    <button class="btn btn-pale btn-lg btn-block mt-auto" onclick="closePaused()">${t("toHome")}</button></div>`);
}

// ---------- actions ----------------------------------------------------------------------------------
async function setLang(l) {
  S.lang = l;
  render();
  if ($("#overlay").innerHTML && S.call && S.call.level === "high" && !S.dismissed[S.call.id]?.high) showHighScreen();
  else if (S.pending) showPaused(S.pending);
  api(`/api/clients/${CLIENT_ID}/language`, { body: { language: l } }).catch(() => {});
}

function setMode(m) { readForm(); S.form.mode = m; render(); }
function setBank(b) { readForm(); S.form.bank = b; render(); }
function readForm() {
  const f = S.form;
  if ($("#f-card")) f.card = $("#f-card").value;
  if ($("#f-phone")) f.phone = $("#f-phone").value;
  if ($("#f-amount")) f.amount = $("#f-amount").value;
}
function bindTransferForm() {
  ["#f-card", "#f-phone"].forEach((s) => $(s)?.addEventListener("paste", () => (S.form.pasted = true)));
  $("#f-amount")?.addEventListener("input", (e) => {
    const d = e.target.value.replace(/\D/g, "");
    e.target.value = d ? Number(d).toLocaleString("ru-RU") : "";
  });
}

function tpl(kind) {
  const f = S.form;
  if (kind === "scam") Object.assign(f, { mode: "card", bank: "Kaspi", card: "4400 4301 2233 4417", amount: "2 000 000", pasted: true });
  if (kind === "dtp") Object.assign(f, { mode: "card", bank: "Halyk", card: "4405 6200 9876 5521", amount: "800 000", pasted: true });
  if (kind === "son") Object.assign(f, { mode: "phone", bank: "BCC", phone: "+7 701 555 12 02", amount: "40 000", pasted: false });
  if (kind === "medium") Object.assign(f, { mode: "card", bank: "Halyk", card: "4405 6200 1111 7788", amount: "250 000", pasted: true });
  f.openedAt = Date.now() - (kind === "son" ? 25000 : 3000);
  render();
}

// prev: a prepared body (cash/deposit buttons, or the questionnaire's "Continue" with answered=true)
async function submitTransfer(prev, answered = false) {
  let body = prev;
  if (!body) {
    readForm();
    const f = S.form;
    body = {
      bank: f.bank, amount: Number(String(f.amount).replace(/\D/g, "")),
      ...(f.mode === "card" ? { card: f.card } : { phone: f.phone }),
      behavior: { pasted: f.pasted, fill_seconds: Math.round((Date.now() - f.openedAt) / 1000) },
    };
    if (!body.amount) return toast("Введите сумму");
  } else if (answered) {
    body = { ...body, answers: Object.fromEntries(Object.entries(S.answers || {}).map(([k, v]) => [k, !!v])) };
  }
  const btn = $("#send-btn");
  if (btn) btn.disabled = true;
  try {
    const r = await api(`/api/clients/${CLIENT_ID}/${body.kind ? "operations" : "transfers"}`, { body });
    if (r.action === "questions") return showQuestions(r.assessment, body);
    if (!body.kind) S.form = { mode: "card", bank: "Kaspi", card: "", phone: "", amount: "", pasted: false, openedAt: Date.now() };
    if (r.action === "completed") showDone(r.transfer);
    else if (r.action === "blocked") showResult("bad", t("blockedTitle"), t("blockedText"), r.transfer.amount);
    else showPaused(r.transfer);
  } catch (e) {
    closeOverlay();
    toast(esc(e.message), "danger");
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function takeLoan(btn) {
  btn.disabled = true;
  try {
    const loan = await api(`/api/clients/${CLIENT_ID}/loans`, { body: { amount: S.loanAmount } });
    const why = (loan.reasons || []).map((r) => `• ${esc(reasonText(r))}`).join("<br>");
    if (loan.status === "pending_relative") showResult("safe", t("loanSent"), `${esc(contactNames())}. Деньги поступят после одобрения.${why ? "<br><br>" + why : ""}`, S.loanAmount);
    else if (loan.status === "cooling") showResult("safe", t("loanCooling"), `${t("loanCoolingText")}${why ? "<br><br>" + why : ""}`, S.loanAmount);
    else showResult("ok", t("loanDone"), t("loanNote"), S.loanAmount);
  } catch (e) { toast(esc(e.message), "danger"); }
  btn.disabled = false;
}

async function startCall(btn) {
  btn.disabled = true;
  const snap = await api("/api/calls", { body: { client_id: CLIENT_ID } });
  setCall(snap);
  render();
}

function setCall(snap) {
  S.call = { id: snap.call_id, risk: snap.risk, level: snap.level, history: snap.history || [], feed: S.call?.id === snap.call_id ? S.call.feed : [],
    categories: S.call?.id === snap.call_id ? S.call.categories : {}, llm: snap.llm, scheme_label: S.call?.scheme_label };
}

async function sendPhrase(e) {
  e.preventDefault();
  const v = $("#phrase").value.trim();
  if (!v || !S.call) return;
  $("#phrase").value = "";
  try { await api(`/api/calls/${S.call.id}/text`, { body: { text: v } }); } catch (err) { toast(esc(err.message), "danger"); }
}

async function runScenario(name) {
  if (!S.call) return;
  await api(`/api/calls/${S.call.id}/scenario`, { body: { name } });
  toast("▶ " + esc(S.scenarios.find((s) => s.id === name)?.title || name), "neutral", 2500);
}

async function endCall(outcome) {
  stopMic();
  if (S.call) await api(`/api/calls/${S.call.id}/end`, { body: { outcome } }).catch(() => {});
  S.call = null;
  closeOverlay();
  if (outcome === "hangup") toast("📵 Звонок завершён. Если нужно — позвоните в банк по номеру на карте.", "neutral", 5000);
  render();
}

async function toggleShield() {
  if (!S.client.shield_enabled) {
    await api(`/api/clients/${CLIENT_ID}/shield`, { body: { enabled: true } });
    return;
  }
  const r = await api(`/api/clients/${CLIENT_ID}/shield`, { body: { enabled: false } });
  $("#shield-msg").innerHTML = `<div class="card-2 px-4 py-3 text-[13px] fade-in" style="border-color:rgba(242,179,61,.35)">⏳ ${esc(r.message)}</div>`;
}

// ---------- microphone: ~5s standalone webm chunks ---------------------------------------------------
async function toggleMic() {
  if (S.mic.on) return stopMic();
  if (!S.cfg.stt_enabled) return toast("Распознавание речи недоступно: не задан OPENAI_API_KEY. Используйте ручной ввод или сценарии.", "danger", 5000);
  try {
    S.mic.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (e) { return toast("Нет доступа к микрофону: " + esc(e.message), "danger"); }
  S.mic.on = true;
  updateCallView();
  recordChunk();
}

function recordChunk() {
  if (!S.mic.on || !S.call) return;
  const mime = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "";
  const rec = new MediaRecorder(S.mic.stream, mime ? { mimeType: mime } : {});
  const parts = [];
  rec.ondataavailable = (e) => e.data.size && parts.push(e.data);
  rec.onstop = async () => {
    recordChunk(); // start the next chunk immediately, upload this one in parallel
    const blob = new Blob(parts, { type: rec.mimeType || "audio/webm" });
    if (!S.call || blob.size < 1500) return;
    const fd = new FormData();
    fd.append("file", blob, (rec.mimeType || "").includes("mp4") ? "chunk.mp4" : "chunk.webm");
    try { await api(`/api/calls/${S.call.id}/audio`, { body: fd }); } catch (e) { toast(esc(e.message), "danger"); stopMic(); }
  };
  S.mic.rec = rec;
  rec.start();
  setTimeout(() => rec.state === "recording" && rec.stop(), 5000);
}

function stopMic() {
  S.mic.on = false;
  try { S.mic.rec?.state === "recording" && S.mic.rec.stop(); } catch (_) {}
  S.mic.stream?.getTracks().forEach((tr) => tr.stop());
  S.mic.stream = null;
  updateCallView();
}

// ---------- live events ------------------------------------------------------------------------------
async function refreshTransfers() {
  S.transfers = await api(`/api/clients/${CLIENT_ID}/transfers`);
  if (["home", "history"].includes(S.screen)) render();
}

function onEvent(type, d) {
  if (type === "reset") return location.reload();
  if (type === "client_state" && d.id === CLIENT_ID) {
    const wasLang = S.lang;
    S.client = d;
    if (["home", "settings", "loan", "cash", "deposit"].includes(S.screen)) render();
    else if (S.screen === "transfer") { readForm(); render(); }
    if (wasLang !== S.lang) render();
    return;
  }
  if (type === "call_update" && d.client_id === CLIENT_ID) {
    if (!S.call || S.call.id !== d.call_id) setCall({ call_id: d.call_id, risk: d.risk, level: d.level, history: d.history });
    const c = S.call;
    Object.assign(c, { risk: d.risk, level: d.level, history: d.history, categories: d.categories, llm: d.llm, scheme_label: d.scheme_label });
    c.feed.push({ ...d.fragment, source: d.source });
    c.feed = c.feed.slice(-12);
    if (S.screen === "call") updateCallView(); else if (S.screen === "home") render();
    const dis = S.dismissed[c.id] || {};
    if (d.level === "high" && !dis.high && !S.pending) showHighScreen();
    else if (d.level === "medium" && !dis.medium && !$("#overlay").innerHTML) showMediumBanner();
    return;
  }
  if (type === "call_ended" && S.call && d.call_id === S.call.id) { S.call = null; stopMic(); if (S.screen === "call" || S.screen === "home") render(); return; }
  if (type === "transfer" && (d.from.client_id === CLIENT_ID)) {
    refreshTransfers();
    if (S.pending && d.id === S.pending.id && d.status !== S.pending.status) {
      S.pending = null;
      if (d.status === "rejected") {
        vibrate(200);
        if (d.kind && d.kind !== "transfer") showResult("safe", t("opRejected"), t("opRejectedText"), d.amount);
        else showResult("safe", t("rejectedTitle"), t("rejectedText"), d.amount);
      } else if (d.status === "completed") showDone(d);
    }
    return;
  }
  if (type === "client_warning" && d.client_id === CLIENT_ID) toast("⚠️ " + esc(S.lang === "kk" ? d.kk : d.ru), "danger", 9000);
  if (type === "loan" && d.client_id === CLIENT_ID && d.decided_by) {
    toast(d.status === "approved" ? `✅ Кредит ${fmt(d.amount)} зачислен${d.decided_by === "cooling_expired" ? " после охлаждения" : ""}` : `❌ Кредит ${fmt(d.amount)} отклонён доверенным лицом`, d.status === "approved" ? "neutral" : "danger", 6000);
  }
}

async function init() {
  startSand(document.getElementById("sand"), { density: 0.8, alpha: 0.75 });
  setInterval(() => ($("#clock").textContent = new Date().toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })), 1000);
  const [cfg, client, transfers, scenarios, calls] = await Promise.all([api("/api/config"), api(`/api/clients/${CLIENT_ID}`),
    api(`/api/clients/${CLIENT_ID}/transfers`), api("/api/scenarios"), api("/api/calls/active")]);
  Object.assign(S, { cfg, client, transfers, scenarios, lang: client.language === "kk" ? "kk" : "ru" });
  const mine = calls.find((c) => c.client_id === CLIENT_ID);
  if (mine) { setCall(mine); S.dismissed[mine.call_id] = { medium: true, high: true }; }
  render();
  connectWS(onEvent, (ok) => ($("#ws-dot").style.background = ok ? "var(--accent)" : "var(--danger)"));
}
init();
