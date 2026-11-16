"""Optional aiogram 3 bot for the trusted contact. Disabled when TELEGRAM_BOT_TOKEN is empty."""
import asyncio
import logging

from app.config import settings

log = logging.getLogger(__name__)
bot = None
dp = None
bot_username: str | None = None  # filled at start, used for t.me deep links on the client screen


def _fmt(x: float) -> str:
    return f"{x:,.0f}".replace(",", " ") + " ₸"


async def start():
    global bot, dp, bot_username
    if not settings.telegram_bot_token:
        log.info("TELEGRAM_BOT_TOKEN не задан — бот выключен, работает веб-страница родственника")
        return None
    from aiogram import Bot, Dispatcher, F
    from aiogram.filters import CommandObject, CommandStart
    from aiogram.types import CallbackQuery, Message

    from app.db import SessionLocal
    from app.family import service
    from app.family.linking import chat_may_decide, link_chat
    from app.models import Transfer, TrustedContact
    from app.security import relative_key

    bot, dp = Bot(settings.telegram_bot_token), Dispatcher()
    try:
        bot_username = (await bot.get_me()).username
    except Exception as e:  # wrong token or no network: the web relative page still works
        log.warning("Telegram: не удалось подключиться к боту (%s). Проверьте TELEGRAM_BOT_TOKEN.", e)
        await bot.session.close()
        bot = dp = None
        return None
    log.info("Telegram-бот: @%s", bot_username)

    @dp.message(CommandStart())
    async def on_start(message: Message, command: CommandObject):
        code = (command.args or "").strip()
        if not code:
            await message.answer("BCC Shield (демо). Отправьте /start <код> со страницы настроек клиента "
                                 "или откройте ссылку оттуда.")
            return
        with SessionLocal() as db:
            ok, text = link_chat(db, message.chat.id, code)
            tc = db.query(TrustedContact).filter_by(telegram_chat_id=message.chat.id).first() if ok else None
        await message.answer(text)
        if tc and settings.public_url:
            await message.answer(f"Кабинет доверенного лица в браузере: {settings.public_url}/relative?rk={relative_key(tc.id)}\n"
                                 "Никому не пересылайте эту ссылку.")

    @dp.callback_query(F.data.startswith("dec:"))
    async def on_decision(cb: CallbackQuery):
        try:
            _, decision, tid = cb.data.split(":")
            tid = int(tid)
        except ValueError:
            await cb.answer("Неверный запрос")
            return
        with SessionLocal() as db:
            t = db.get(Transfer, tid)
            if not t or not chat_may_decide(db, cb.message.chat.id, t):
                await cb.answer("Решение может принять только доверенное лицо этого клиента", show_alert=True)
                return
            try:
                await service.decide(db, t, decision, by="relative_telegram")
                text = "✅ Перевод подтверждён" if decision == "approve" else "❌ Перевод отклонён, деньги в безопасности"
            except ValueError as e:
                text = str(e)
        await cb.message.edit_reply_markup(reply_markup=None)
        await cb.message.answer(text)
        await cb.answer()

    return asyncio.create_task(dp.start_polling(bot, handle_signals=False))


async def stop(task):
    if task:
        task.cancel()
    if bot:
        await bot.session.close()


async def _send(chat_id: int | None, text: str, buttons: list[list[tuple[str, str]]] | None = None):
    if not bot or not chat_id:
        return
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    markup = None
    if buttons:
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t, callback_data=d) for t, d in row] for row in buttons])
    try:
        await bot.send_message(chat_id, text, reply_markup=markup)
    except Exception as e:
        log.warning("Telegram send failed: %s", e)


async def send_call_alert(tc, client, scheme_ru: str):
    if tc:
        await _send(tc.telegram_chat_id, f"⚠️ {client.name.split()[0]} сейчас звонят мошенники. "
                                         f"Схема: {scheme_ru}. Позвоните ей: {client.phone}")


async def send_transfer_request(tc, t: dict, client):
    if not tc:
        return
    reasons = "\n".join(f"• {r['ru']}" for r in t["reasons"][:6])
    text = (f"🛡 Запрос на подтверждение перевода\n{client.name} переводит {_fmt(t['amount'])}\n"
            f"Получатель: {t['to']['bank']} {t['to']['card']}\n\nПричины риска:\n{reasons}")
    await _send(tc.telegram_chat_id, text, [[("✅ Подтвердить", f"dec:approve:{t['id']}"),
                                             ("❌ Отклонить", f"dec:reject:{t['id']}")]])
