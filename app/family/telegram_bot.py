"""Optional aiogram 3 bot for the trusted contact. Disabled when TELEGRAM_BOT_TOKEN is empty."""
import asyncio
import logging

from app.config import settings

log = logging.getLogger(__name__)
bot = None
dp = None


def _fmt(x: float) -> str:
    return f"{x:,.0f}".replace(",", " ") + " ₸"


async def start():
    global bot, dp
    if not settings.telegram_bot_token:
        log.info("TELEGRAM_BOT_TOKEN не задан — бот выключен, работает веб-страница родственника")
        return None
    from aiogram import Bot, Dispatcher, F
    from aiogram.filters import CommandObject, CommandStart
    from aiogram.types import CallbackQuery, Message

    from app.db import SessionLocal
    from app.family import service
    from app.models import Transfer, TrustedContact

    bot, dp = Bot(settings.telegram_bot_token), Dispatcher()

    @dp.message(CommandStart())
    async def on_start(message: Message, command: CommandObject):
        code = (command.args or "").strip().upper()
        with SessionLocal() as db:
            tc = db.query(TrustedContact).filter_by(link_code=code).first() if code else None
            if not tc:
                await message.answer("BCC Shield (демо). Отправьте /start <код> со страницы настроек клиента.")
                return
            tc.telegram_chat_id = message.chat.id
            db.commit()
        await message.answer(f"✅ Вы подключены как доверенное лицо ({tc.relation}). "
                             "Сюда будут приходить предупреждения и запросы на подтверждение переводов.")

    @dp.callback_query(F.data.startswith("dec:"))
    async def on_decision(cb: CallbackQuery):
        _, decision, tid = cb.data.split(":")
        with SessionLocal() as db:
            t = db.get(Transfer, int(tid))
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
