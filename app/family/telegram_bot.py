"""Telegram bot for trusted contacts (aiogram 3). Disabled when TELEGRAM_BOT_TOKEN is empty.

What it does:
- accepts invitations: /start CODE -> invitation card -> "Принять" -> the person shares their own phone number
  (Telegram vouches for it) -> it must match the number the client entered;
- sends call alerts, every transfer of the client (if the contact wants that), requests to confirm transfers, loans
  and new trusted contacts, with buttons;
- opens the Mini App (/tg) when PUBLIC_URL is an https address (Telegram requires https for Mini Apps).
"""
import asyncio
import logging

from app.config import settings

log = logging.getLogger(__name__)
bot = None
dp = None
bot_username: str | None = None  # filled at start, used for t.me deep links on the client screen
_pending_invite: dict[int, int] = {}  # chat_id -> contact id shown in the invitation card
_await_phone: dict[int, int] = {}     # chat_id -> contact id waiting for the shared phone number


def fmt(x: float) -> str:
    return f"{x:,.0f}".replace(",", " ") + " ₸"


def mini_app_url() -> str | None:
    return f"{settings.public_url}/tg" if settings.public_url.startswith("https://") else None


def _rules_text(tc) -> str:
    lines = [f"• переводы от {fmt(tc.amount_threshold)}"]
    if tc.confirm_new:
        lines.append("• переводы новым получателям")
    if tc.confirm_loans:
        lines.append("• кредиты и займы")
    see = "все её переводы" if tc.notify_all else "только рискованные операции"
    return "Вы будете подтверждать:\n" + "\n".join(lines) + f"\n\nВы будете видеть: {see}."


async def start():
    global bot, dp, bot_username
    if not settings.telegram_bot_token:
        log.info("TELEGRAM_BOT_TOKEN не задан — бот выключен, работает веб-страница родственника")
        return None
    from aiogram import Bot, Dispatcher, F
    from aiogram.filters import Command, CommandObject, CommandStart
    from aiogram.types import (BotCommand, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton,
                               MenuButtonWebApp, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove, WebAppInfo)

    from app.db import SessionLocal
    from app.family import contacts, linking, service
    from app.models import Client, Loan, Transfer, TrustedContact
    from app.ws import hub

    bot, dp = Bot(settings.telegram_bot_token), Dispatcher()
    try:
        bot_username = (await bot.get_me()).username
    except Exception as e:  # wrong token or no network: the web relative page still works
        log.warning("Telegram: не удалось подключиться к боту (%s). Проверьте TELEGRAM_BOT_TOKEN.", e)
        await bot.session.close()
        bot = dp = None
        return None
    log.info("Telegram-бот: @%s", bot_username)
    app_url = mini_app_url()
    try:
        await bot.set_my_commands([BotCommand(command="start", description="Подключение и помощь"),
                                   BotCommand(command="app", description="Открыть семейный кабинет")])
        await bot.set_my_short_description("Семейная защита переводов: подтверждайте рискованные операции близких.")
        if app_url:
            await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text="Семья", web_app=WebAppInfo(url=app_url)))
            log.info("Telegram Mini App: %s", app_url)
        else:
            log.info("Mini App выключено: для него нужен PUBLIC_URL с https (Telegram открывает только https)")
    except Exception as e:
        log.warning("Telegram: не удалось настроить команды/меню: %s", e)

    def app_markup():
        if not app_url:
            return None
        return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📱 Открыть семейный кабинет",
                                                                           web_app=WebAppInfo(url=app_url))]])

    async def after_change(db, client_id: int):
        client = db.get(Client, client_id)
        if client:
            await service.push_client(db, client)
            await hub.broadcast("contacts_changed", {"client_id": client_id})

    @dp.message(CommandStart())
    async def on_start(message: Message, command: CommandObject):
        code = (command.args or "").strip()
        chat = message.chat.id
        with SessionLocal() as db:
            if not code:
                mine = contacts.by_chat(db, chat)
                if mine:
                    names = ", ".join(db.get(Client, c.client_id).name for c in mine)
                    await message.answer(f"Вы доверенное лицо: {names}.\nСюда приходят переводы и запросы на подтверждение.",
                                         reply_markup=app_markup())
                else:
                    await message.answer("BCC Shield — семейная защита переводов.\nЧтобы стать доверенным лицом, откройте "
                                         "приглашение из приложения близкого человека (или отправьте /start КОД).")
                return
            tc, err = linking.find_invite(db, chat, code)
            if err:
                await message.answer(err)
                return
            client = db.get(Client, tc.client_id)
            if tc.telegram_chat_id == chat and tc.status == "active":
                await message.answer(f"Вы уже доверенное лицо {client.name}.", reply_markup=app_markup())
                return
            _pending_invite[chat] = tc.id
            text = (f"👋 {client.name} приглашает вас стать доверенным лицом ({tc.relation}).\n\n{_rules_text(tc)}\n\n"
                    "Без вашего ответа рискованный перевод выполнится только после периода охлаждения.")
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Принять", callback_data=f"inv:y:{tc.id}"),
                                                    InlineKeyboardButton(text="Отказаться", callback_data=f"inv:n:{tc.id}")]])
        await message.answer(text, reply_markup=kb)

    async def finish_accept(message_or_cb, chat: int, tc_id: int):
        with SessionLocal() as db:
            tc = db.get(TrustedContact, tc_id)
            try:
                contacts.accept(db, tc, chat)
            except ValueError as e:
                return await bot.send_message(chat, str(e), reply_markup=ReplyKeyboardRemove())
            client = db.get(Client, tc.client_id)
            await after_change(db, client.id)
            name = client.name
        _pending_invite.pop(chat, None)
        _await_phone.pop(chat, None)
        await bot.send_message(chat, f"✅ Готово! Теперь вы доверенное лицо {name}.", reply_markup=ReplyKeyboardRemove())
        if app_url:
            await bot.send_message(chat, "Все переводы и запросы — в семейном кабинете:", reply_markup=app_markup())

    @dp.callback_query(F.data.startswith("inv:"))
    async def on_invite(cb: CallbackQuery):
        _, answer, tc_id = cb.data.split(":")
        chat, tc_id = cb.message.chat.id, int(tc_id)
        if _pending_invite.get(chat) != tc_id:
            return await cb.answer("Откройте приглашение заново", show_alert=True)
        await cb.message.edit_reply_markup(reply_markup=None)
        with SessionLocal() as db:
            tc = db.get(TrustedContact, tc_id)
            if answer == "n":
                contacts.remove(db, tc)
                await after_change(db, tc.client_id)
                _pending_invite.pop(chat, None)
                await cb.answer()
                return await cb.message.answer("Вы отказались от приглашения.")
            need_phone = tc.verify_phone and bool(contacts.digits(tc.phone))
        await cb.answer()
        if not need_phone:
            return await finish_accept(cb, chat, tc_id)
        _await_phone[chat] = tc_id
        kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📱 Подтвердить мой номер", request_contact=True)]],
                                 resize_keyboard=True, one_time_keyboard=True)
        await cb.message.answer("Последний шаг: подтвердите, что приглашение для вас. Нажмите кнопку ниже — "
                                "Telegram передаст ваш номер, и мы сверим его с номером из приглашения.", reply_markup=kb)

    @dp.message(F.contact)
    async def on_contact(message: Message):
        chat = message.chat.id
        tc_id = _await_phone.get(chat)
        if not tc_id:
            return
        ct = message.contact
        if not message.from_user or ct.user_id != message.from_user.id:
            return await message.answer("Нужно отправить свой собственный номер кнопкой «Подтвердить мой номер».")
        with SessionLocal() as db:
            tc = db.get(TrustedContact, tc_id)
            ok = contacts.digits(ct.phone_number) == contacts.digits(tc.phone)
            if not ok:
                linking.register_fail(chat)
        if not ok:
            _await_phone.pop(chat, None)
            _pending_invite.pop(chat, None)
            return await message.answer("Номер не совпадает с номером в приглашении. Попросите близкого проверить номер "
                                        "в приложении и отправить приглашение заново.", reply_markup=ReplyKeyboardRemove())
        await finish_accept(message, chat, tc_id)

    @dp.message(Command("app"))
    async def on_app(message: Message):
        if app_url:
            await message.answer("Семейный кабинет:", reply_markup=app_markup())
        else:
            await message.answer("Кабинет в Telegram доступен, когда демо опубликовано по https (PUBLIC_URL).")

    @dp.callback_query(F.data.regexp(r"^(dec|loan|cadd):(approve|reject):\d+$"))
    async def on_decision(cb: CallbackQuery):
        kind, decision, oid = cb.data.split(":")
        oid, chat = int(oid), cb.message.chat.id
        text = None
        with SessionLocal() as db:
            if kind == "dec":
                obj = db.get(Transfer, oid)
                client_id = linking.transfer_client(db, obj)
            elif kind == "loan":
                obj = db.get(Loan, oid)
                client_id = obj.client_id if obj else None
            else:
                obj = db.get(TrustedContact, oid)
                client_id = obj.client_id if obj else None
            me = linking.chat_contact(db, chat, client_id)
            if not obj or not me or (kind == "cadd" and me.id == obj.id):
                return await cb.answer("Решение может принять только доверенное лицо этого клиента", show_alert=True)
            by = f"relative:{me.id}"
            try:
                if kind == "dec":
                    await service.decide(db, obj, decision, by=by)
                elif kind == "loan":
                    await service.decide_loan(db, obj, decision, by=by)
                else:
                    contacts.decide_addition(db, obj, decision)
                    await after_change(db, obj.client_id)
                    text = ("✅ Вы разрешили добавить доверенное лицо. Ему осталось принять приглашение."
                            if decision == "approve" else "❌ Вы не разрешили добавить доверенное лицо.")
            except ValueError as e:
                text = str(e)
        await cb.message.edit_reply_markup(reply_markup=None)
        if text:
            await cb.message.answer(text)
        await cb.answer()

    return asyncio.create_task(dp.start_polling(bot, handle_signals=False))


async def stop(task):
    if task:
        task.cancel()
    if bot:
        await bot.session.close()


async def _send(chat_id: int | None, text: str, buttons: list[list[tuple[str, str]]] | None = None, with_app: bool = False):
    if not bot or not chat_id:
        return
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

    rows = [[InlineKeyboardButton(text=t, callback_data=d) for t, d in row] for row in (buttons or [])]
    if with_app and mini_app_url():
        rows.append([InlineKeyboardButton(text="📱 Подробнее в кабинете", web_app=WebAppInfo(url=mini_app_url()))])
    try:
        await bot.send_message(chat_id, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows) if rows else None)
    except Exception as e:
        log.warning("Telegram send failed: %s", e)


def _recipients(db, client_id: int, feed: bool = False, exclude: int | None = None) -> list[int]:
    from app.family import contacts

    return [c.telegram_chat_id for c in contacts.active_contacts(db, client_id)
            if c.telegram_chat_id and (not feed or c.notify_all) and c.id != exclude]


async def _broadcast(db, client_id: int, text: str, buttons=None, feed: bool = False, with_app: bool = False,
                     exclude: int | None = None):
    if not bot:
        return
    for chat in _recipients(db, client_id, feed, exclude):
        await _send(chat, text, buttons, with_app)


async def notify_call_alert(db, client, scheme_ru: str):
    await _broadcast(db, client.id, f"⚠️ {client.name.split()[0]} сейчас звонят мошенники. Схема: {scheme_ru}.\n"
                                    f"Позвоните: {client.phone}\nРиск растёт по ходу разговора — "
                                    "текущее значение в семейном кабинете.", with_app=True)


async def notify_call_context(db, client, summary_ru: str, level: str):
    """A phone call the bank app noticed (CallKit / Android), without audio: the family hears of it before any
    transfer — this is what Kaspi's trusted contact cannot do."""
    first = client.name.split()[0]
    head = (f"⚠️ {first} сейчас звонят мошенники" if level == "high"
            else f"⚠️ У {first} сейчас подозрительный звонок")
    await _broadcast(db, client.id, f"{head}: {summary_ru}.\nПозвоните ей: {client.phone}\n"
                                    "Пока звонок идёт, кредит и рискованные переводы будут ждать вашего решения.",
                     with_app=True)


VERB = {"transfer":"переводит", "cash": "снимает наличными", "deposit": "досрочно закрывает депозит на"}
# what the trusted contact should know about the scheme heard in the call
SCHEME_HINTS = {
    "relative_in_trouble": "📞 Звонящий выдаёт себя за родственника в беде. Если это не вы и не ваши близкие — "
                           "нажмите «Отклонить: это не я» и позвоните ей.",
    "safe_account": "📞 Схема «безопасный счёт»: банк никогда не просит переводить деньги.",
    "telecom_egov": "📞 Схема «оператор → eGov → вы дроппер»: дальше обычно просят снять наличные для курьера.",
}


async def notify_transfer_request(db, client, t: dict):
    reasons = "\n".join(f"• {r['ru']}" for r in t["reasons"][:6])
    kind = t.get("kind", "transfer")
    to = f"\nПолучатель: {t['to']['name']} · {t['to']['bank']} {t['to']['card']}" if kind == "transfer" else ""
    scheme = (t.get("context") or {}).get("call_scheme")
    hint = f"\n\n{SCHEME_HINTS[scheme]}" if scheme in SCHEME_HINTS else ""
    text = f"🛡 Нужно ваше решение\n{client.name} {VERB.get(kind, 'переводит')} {fmt(t['amount'])}{to}\n\nПричины:\n{reasons}{hint}"
    reject = "❌ Отклонить: это не я" if scheme == "relative_in_trouble" else "❌ Отклонить"
    await _broadcast(db, client.id, text, [[("✅ Подтвердить", f"dec:approve:{t['id']}"),
                                            (reject, f"dec:reject:{t['id']}")]], with_app=True)


async def notify_transfer_done(db, client, t: dict):
    level = {"low": "✓ обычный перевод", "medium": "⚠️ средний риск", "high": "⚠️ высокий риск"}.get(t["risk_level"], "")
    kind = t.get("kind", "transfer")
    head = {"cash": f"💵 {client.name.split()[0]}: снято наличными {fmt(t['amount'])}",
            "deposit": f"🏦 {client.name.split()[0]}: депозит закрыт, +{fmt(t['amount'])} на карту"}.get(
        kind, f"💸 {client.name.split()[0]}: −{fmt(t['amount'])}\n{t['to']['name']} · {t['to']['bank']} {t['to']['card']}")
    await _broadcast(db, client.id, f"{head}\n{level}", feed=True)


async def notify_loan_request(db, client, loan):
    why = "\n".join(f"• {r['ru']}" for r in (loan.reasons or []))
    await _broadcast(db, client.id, f"🏦 {client.name} оформляет кредит {fmt(loan.amount)}.\n"
                                    + (f"Деньги не выданы:\n{why}\n\n" if why else "")
                                    + "Мошенники часто заставляют брать кредиты по телефону. Подтвердить?",
                     [[("✅ Подтвердить", f"loan:approve:{loan.id}"), ("❌ Отклонить", f"loan:reject:{loan.id}")]],
                     with_app=True)


async def notify_contact_request(db, client, tc):
    await _broadcast(db, client.id, f"👥 {client.name} хочет добавить ещё одно доверенное лицо: {tc.name} ({tc.relation}), "
                                    f"{tc.phone}.\nЕсли вы не знаете этого человека — не разрешайте: мошенники так "
                                    "пытаются получить доступ к подтверждениям.",
                     [[("✅ Разрешить", f"cadd:approve:{tc.id}"), ("❌ Не разрешать", f"cadd:reject:{tc.id}")]],
                     exclude=tc.id)


async def notify_decision(db, client, text: str):
    await _broadcast(db, client.id, text)
