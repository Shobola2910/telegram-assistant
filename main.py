"""
main.py — Telegram Personal Assistant Bot
Run: python main.py
"""

import asyncio
import logging
from datetime import datetime

import aiohttp
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, Voice, PhotoSize, Document
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from config import BOT_TOKEN, YOUR_TELEGRAM_ID, TIMEZONE, BRIEFING_HOUR, BRIEFING_MINUTE
from ai_service import (
    analyze_voice, analyze_receipt, analyze_document,
    parse_text_intent, generate_reply
)
from google_service import (
    get_today_events, create_calendar_event, get_upcoming_events,
    add_expense, get_monthly_summary, get_recent_expenses,
    get_unread_emails, get_email_stats
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

router = Router()
tz = pytz.timezone(TIMEZONE)


def is_owner(message: Message) -> bool:
    return message.from_user.id == YOUR_TELEGRAM_ID


# ─── /start ──────────────────────────────────
@router.message(Command("start"))
async def cmd_start(message: Message):
    if not is_owner(message):
        return
    text = (
        "👋 Hey! I'm your personal assistant.\n\n"
        "What I can do:\n"
        "🎤 <b>Voice message</b> → Calendar / Expense / Reminder\n"
        "📸 <b>Receipt photo</b> → Auto expense logging\n"
        "📄 <b>PDF / Document</b> → Analysis & summary\n"
        "💬 <b>Text</b> → Any command\n\n"
        "<b>Commands:</b>\n"
        "/today — Today's schedule & overview\n"
        "/report — Monthly expense report\n"
        "/recent — Last 5 expenses\n"
        "/calendar — Upcoming week\n"
        "/emails — Unread emails\n"
        "/help — Full guide"
    )
    await message.answer(text, parse_mode="HTML")


# ─── /help ───────────────────────────────────
@router.message(Command("help"))
async def cmd_help(message: Message):
    if not is_owner(message):
        return
    text = (
        "📖 <b>Guide</b>\n\n"
        "<b>Voice message examples:</b>\n"
        "• «Lunch 35 dollars» → expense logged\n"
        "• «Meeting tomorrow at 10am» → added to Calendar\n"
        "• «Remind me to take medicine in 1 hour» → reminder set\n\n"
        "<b>Text examples:</b>\n"
        "• Gas 85 dollars → Transport expense\n"
        "• Meeting with John at 3pm today → Calendar\n"
        "• What did I spend this month? → report\n\n"
        "<b>Photo & document:</b>\n"
        "• Send a receipt photo → logged to Sheets\n"
        "• Send a PDF contract → summary & key points"
    )
    await message.answer(text, parse_mode="HTML")


# ─── /today ──────────────────────────────────
@router.message(Command("today"))
async def cmd_today(message: Message):
    if not is_owner(message):
        return
    await message.answer("⏳ Loading...")

    now = datetime.now(tz)
    lines = [f"📅 <b>{now.strftime('%B %d, %Y — %A')}</b>\n"]

    events = get_today_events()
    if events:
        lines.append("🗓 <b>Today's meetings:</b>")
        for e in events:
            lines.append(f"  • {e['time']} — {e['title']}")
            if e.get("location"):
                lines.append(f"    📍 {e['location']}")
    else:
        lines.append("🗓 No meetings today")

    summary = get_monthly_summary(now.month, now.year)
    lines.append(f"\n💰 <b>This month's total:</b> ${summary['total']:,.2f}")

    stats = get_email_stats()
    if stats["unread"] > 0:
        lines.append(f"\n📧 Unread emails: <b>{stats['unread']}</b>")

    await message.answer("\n".join(lines), parse_mode="HTML")


# ─── /report ─────────────────────────────────
@router.message(Command("report"))
async def cmd_report(message: Message):
    if not is_owner(message):
        return

    now = datetime.now(tz)
    summary = get_monthly_summary(now.month, now.year)
    month_name = datetime(now.year, summary["month"], 1).strftime("%B")

    lines = [
        f"📊 <b>{month_name} {summary['year']} — Report</b>\n",
        f"💰 <b>Total:</b> ${summary['total']:,.2f}\n",
    ]

    if summary["by_category"]:
        lines.append("📂 <b>By category:</b>")
        sorted_cats = sorted(summary["by_category"].items(), key=lambda x: x[1], reverse=True)
        for cat, amount in sorted_cats:
            percent = (amount / summary["total"] * 100) if summary["total"] > 0 else 0
            bar = "█" * int(percent / 10) + "░" * (10 - int(percent / 10))
            lines.append(f"  {cat}: ${amount:,.2f} ({percent:.0f}%)")
            lines.append(f"  {bar}")
    else:
        lines.append("No expenses recorded yet.")

    await message.answer("\n".join(lines), parse_mode="HTML")


# ─── /recent ─────────────────────────────────
@router.message(Command("recent"))
async def cmd_recent(message: Message):
    if not is_owner(message):
        return

    expenses = get_recent_expenses(5)
    if not expenses:
        await message.answer("No expenses recorded yet.")
        return

    lines = ["💸 <b>Last 5 expenses:</b>\n"]
    for e in reversed(expenses):
        lines.append(
            f"• {e['date']} | {e['category']}\n"
            f"  {e['description']} — <b>${float(e['amount']):,.2f}</b>"
        )
    await message.answer("\n".join(lines), parse_mode="HTML")


# ─── /calendar ───────────────────────────────
@router.message(Command("calendar"))
async def cmd_calendar(message: Message):
    if not is_owner(message):
        return

    events = get_upcoming_events(days=7)
    if not events:
        await message.answer("No upcoming events in the next 7 days.")
        return

    lines = ["📅 <b>Next 7 days:</b>\n"]
    for e in events:
        lines.append(f"• {e['datetime']} — {e['title']}")
    await message.answer("\n".join(lines), parse_mode="HTML")


# ─── /emails ─────────────────────────────────
@router.message(Command("emails"))
async def cmd_emails(message: Message):
    if not is_owner(message):
        return

    emails = get_unread_emails(5)
    if not emails:
        await message.answer("✅ No unread emails!")
        return

    lines = [f"📧 <b>Unread emails ({len(emails)}):</b>\n"]
    for i, e in enumerate(emails, 1):
        sender = e["from"].split("<")[0].strip()[:30]
        subject = e["subject"][:50]
        lines.append(f"{i}. <b>{sender}</b>\n   {subject}")
    await message.answer("\n".join(lines), parse_mode="HTML")


# ─── VOICE MESSAGE ────────────────────────────
@router.message(F.voice)
async def handle_voice(message: Message, bot: Bot):
    if not is_owner(message):
        return

    await message.answer("🎤 Analyzing voice message...")

    try:
        voice: Voice = message.voice
        file = await bot.get_file(voice.file_id)

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}"
            ) as resp:
                audio_bytes = await resp.read()

        result = await analyze_voice(audio_bytes)
        text = result.get("text", "")
        intent = result.get("intent", "general")
        data = result.get("data", {})

        if intent == "expense" and data.get("amount"):
            amount = float(data["amount"])
            category = data.get("category", "Other")
            description = data.get("description", text[:50])
            success = add_expense(amount, category, description)
            if success:
                await message.answer(
                    f"✅ <b>Expense added</b>\n"
                    f"💰 ${amount:,.2f}\n"
                    f"📂 {category}\n"
                    f"📝 {description}",
                    parse_mode="HTML"
                )
            else:
                await message.answer("❌ Failed to save expense.")

        elif intent == "calendar" and data.get("title"):
            date = data.get("date", datetime.now(tz).strftime("%Y-%m-%d"))
            time = data.get("time", "09:00")
            success = create_calendar_event(data["title"], date, time, data.get("description", ""))
            if success:
                await message.answer(
                    f"✅ <b>Added to Calendar</b>\n"
                    f"📌 {data['title']}\n"
                    f"📅 {date} at {time}",
                    parse_mode="HTML"
                )
            else:
                await message.answer("❌ Failed to create calendar event.")

        elif intent == "reminder":
            reminder_text = data.get("text", text)
            reminder_date = data.get("date", datetime.now(tz).strftime("%Y-%m-%d"))
            reminder_time = data.get("time", "09:00")
            success = create_calendar_event(
                f"⏰ {reminder_text}", reminder_date, reminder_time, "Reminder"
            )
            if success:
                await message.answer(
                    f"⏰ <b>Reminder set</b>\n"
                    f"📝 {reminder_text}\n"
                    f"🕐 {reminder_date} at {reminder_time}",
                    parse_mode="HTML"
                )

        else:
            reply = await generate_reply(text)
            await message.answer(
                f"🎤 <i>You said:</i> {text}\n\n{reply}",
                parse_mode="HTML"
            )

    except Exception as e:
        logger.error(f"Voice handler error: {e}")
        await message.answer("❌ Error processing voice message.")


# ─── PHOTO (RECEIPT) ─────────────────────────
@router.message(F.photo)
async def handle_photo(message: Message, bot: Bot):
    if not is_owner(message):
        return

    await message.answer("📸 Analyzing receipt...")

    try:
        photo: PhotoSize = message.photo[-1]
        file = await bot.get_file(photo.file_id)

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}"
            ) as resp:
                image_bytes = await resp.read()

        result = await analyze_receipt(image_bytes)
        total = result.get("total", 0)
        category = result.get("category", "Other")
        store = result.get("store", "")
        items = result.get("items", [])
        date = result.get("date") or datetime.now(tz).strftime("%Y-%m-%d")

        description = store if store else (items[0]["name"] if items else "Receipt")
        success = add_expense(total, category, description, date=date)

        lines = ["🧾 <b>Receipt analyzed</b>\n"]
        if store:
            lines.append(f"🏪 {store}")
        if items:
            lines.append("\n<b>Items:</b>")
            for item in items[:5]:
                lines.append(f"  • {item['name']} — ${item['price']:,.2f}")
        lines.append(f"\n💰 <b>Total: ${total:,.2f}</b>")
        lines.append(f"📂 {category}")
        lines.append("\n✅ Saved to Sheets" if success else "\n⚠️ Failed to save to Sheets")

        await message.answer("\n".join(lines), parse_mode="HTML")

    except Exception as e:
        logger.error(f"Photo handler error: {e}")
        await message.answer("❌ Error processing image.")


# ─── DOCUMENT (PDF) ──────────────────────────
@router.message(F.document)
async def handle_document(message: Message, bot: Bot):
    if not is_owner(message):
        return

    doc: Document = message.document
    supported = ["application/pdf", "image/jpeg", "image/png", "image/webp"]
    mime = doc.mime_type or ""

    if mime not in supported:
        await message.answer("⚠️ Unsupported file type.\nAccepted formats: PDF, JPG, PNG")
        return

    await message.answer(f"📄 Analyzing <b>{doc.file_name}</b>...", parse_mode="HTML")

    try:
        file = await bot.get_file(doc.file_id)

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}"
            ) as resp:
                file_bytes = await resp.read()

        analysis = await analyze_document(file_bytes, mime, doc.file_name or "")
        await message.answer(f"📄 <b>{doc.file_name}</b>\n\n{analysis}", parse_mode="HTML")

    except Exception as e:
        logger.error(f"Document handler error: {e}")
        await message.answer("❌ Error processing document.")


# ─── TEXT MESSAGE ─────────────────────────────
@router.message(F.text)
async def handle_text(message: Message):
    if not is_owner(message):
        return

    text = message.text.strip()
    if text.startswith("/"):
        return

    result = await parse_text_intent(text)
    intent = result.get("intent", "general")
    lang = result.get("lang", "en")
    data = result.get("data", {})

    if intent == "expense" and data.get("amount"):
        amount = float(data["amount"])
        category = data.get("category", "Other")
        description = data.get("description", text[:50])
        success = add_expense(amount, category, description)
        if success:
            await message.answer(
                f"✅ <b>Expense added</b>\n💰 ${amount:,.2f} — {category}",
                parse_mode="HTML"
            )
        else:
            await message.answer("❌ Failed to save to Sheets.")

    elif intent == "calendar" and data.get("title"):
        date = data.get("date", datetime.now(tz).strftime("%Y-%m-%d"))
        time_str = data.get("time", "09:00")
        success = create_calendar_event(data["title"], date, time_str, data.get("description", ""))
        if success:
            await message.answer(
                f"✅ <b>Added to Calendar</b>\n"
                f"📌 {data['title']}\n"
                f"📅 {date} at {time_str}",
                parse_mode="HTML"
            )

    elif intent == "reminder" and data.get("text"):
        success = create_calendar_event(
            f"⏰ {data['text']}",
            data.get("date", datetime.now(tz).strftime("%Y-%m-%d")),
            data.get("time", "09:00"),
            "Reminder"
        )
        if success:
            await message.answer(
                f"⏰ <b>Reminder set</b>\n"
                f"📝 {data['text']}\n"
                f"🕐 {data.get('date', '')} at {data.get('time', '')}",
                parse_mode="HTML"
            )

    elif intent == "query":
        query_type = data.get("type", "all")
        if "calendar" in query_type:
            await _today_inline(message)
        elif "expenses" in query_type:
            await _report_inline(message)
        elif "gmail" in query_type:
            await _emails_inline(message)
        else:
            await _today_inline(message)

    else:
        reply = await generate_reply(text, lang=lang)
        await message.answer(reply)


# ─── Inline helpers ───────────────────────────
async def _today_inline(message: Message):
    now = datetime.now(tz)
    events = get_today_events()
    lines = [f"📅 <b>Today — {now.strftime('%B %d, %Y')}</b>\n"]
    for e in events:
        lines.append(f"• {e['time']} {e['title']}")
    if not events:
        lines.append("No meetings today.")
    await message.answer("\n".join(lines), parse_mode="HTML")


async def _report_inline(message: Message):
    now = datetime.now(tz)
    summary = get_monthly_summary(now.month, now.year)
    await message.answer(
        f"💰 This month's total: <b>${summary['total']:,.2f}</b>",
        parse_mode="HTML"
    )


async def _emails_inline(message: Message):
    stats = get_email_stats()
    await message.answer(
        f"📧 Unread emails: <b>{stats['unread']}</b>",
        parse_mode="HTML"
    )


# ─── DAILY BRIEFING ──────────────────────────
async def send_daily_briefing(bot: Bot):
    try:
        now = datetime.now(tz)
        lines = [f"☀️ <b>Good morning! — {now.strftime('%B %d, %Y')}</b>\n"]

        events = get_today_events()
        if events:
            lines.append("🗓 <b>Today's meetings:</b>")
            for e in events:
                lines.append(f"  • {e['time']} — {e['title']}")
        else:
            lines.append("🗓 No meetings today")

        stats = get_email_stats()
        if stats["unread"] > 0:
            lines.append(f"\n📧 Unread emails: <b>{stats['unread']}</b>")

        summary = get_monthly_summary(now.month, now.year)
        if summary["total"] > 0:
            lines.append(f"\n💰 This month's expenses: <b>${summary['total']:,.2f}</b>")

        lines.append("\n💪 Have a great day!")

        await bot.send_message(YOUR_TELEGRAM_ID, "\n".join(lines), parse_mode="HTML")
        logger.info("Daily briefing sent")

    except Exception as e:
        logger.error(f"Daily briefing error: {e}")


# ─── MAIN ────────────────────────────────────
async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    scheduler.add_job(
        send_daily_briefing,
        trigger=CronTrigger(hour=BRIEFING_HOUR, minute=BRIEFING_MINUTE),
        kwargs={"bot": bot},
        id="daily_briefing",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(f"Scheduler started — daily briefing at {BRIEFING_HOUR:02d}:{BRIEFING_MINUTE:02d}")
    logger.info("Bot is running ✅")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())