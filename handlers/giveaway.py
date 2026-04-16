"""
Giveaway / Raffle system
.giveaway [sure] [kazanan_sayisi] [odul]
.gend  — aktif cekilis bitis
.greroll — kazanani yeniden sec
"""
import random
import time
import html

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters,
)

from utils import require_admin, mention, parse_time, fmt_time, dot_filter
from database import (
    create_giveaway, get_giveaway, join_giveaway,
    get_giveaway_participants, end_giveaway, get_active_giveaway,
)


def _giveaway_text(prize: str, winners_count: int, end_time: int, count: int) -> str:
    remaining = max(0, end_time - int(time.time()))
    return (
        f"🎉 <b>CEKİLİS!</b>\n\n"
        f"🏆 Odul: <b>{html.escape(prize)}</b>\n"
        f"👥 Kazanan sayisi: {winners_count}\n"
        f"⏱ Bitis: {fmt_time(remaining)}\n"
        f"🎫 Katilimci: {count} kisi\n\n"
        f"Katilmak icin asagidaki butona tikla!"
    )


def _enter_kb(gid: int, count: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(f"🎉 Katıl! ({count} kişi)", callback_data=f"gj_{gid}")
    ]])


async def giveaway_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not await require_admin(update, context): return

    args = context.args
    if not args or len(args) < 2:
        return await msg.reply_text(
            "Kullanim: .giveaway <sure> <kazanan> <odul>\n"
            "Ornek: .giveaway 1h 1 Nitro\n"
            "Ornek: .giveaway 30m 3 Premium Uyelik"
        )

    duration_secs = parse_time(args[0])
    if not duration_secs:
        return await msg.reply_text("Gecersiz sure. Ornek: 1h, 30m, 1d")

    try:
        winners_count = int(args[1])
    except ValueError:
        return await msg.reply_text("Kazanan sayisi rakam olmali.")

    prize = " ".join(args[2:]) if len(args) > 2 else "Surpriz Odul"
    end_time = int(time.time()) + duration_secs
    chat_id = update.effective_chat.id

    # Check if there's already an active giveaway
    existing = await get_active_giveaway(chat_id)
    if existing:
        return await msg.reply_text(
            "Bu grupta zaten aktif bir cekilis var!\n"
            ".gend ile bitir, sonra yenisini baslat."
        )

    text = _giveaway_text(prize, winners_count, end_time, 0)
    sent = await msg.reply_text(text, parse_mode="HTML",
                                 reply_markup=_enter_kb(0, 0))

    gid = await create_giveaway(
        chat_id, sent.message_id, prize, winners_count, end_time,
        update.effective_user.id,
    )

    # Update button with real gid
    await sent.edit_reply_markup(_enter_kb(gid, 0))

    # Schedule auto-end
    context.job_queue.run_once(
        _auto_end_giveaway, duration_secs,
        data={"gid": gid, "chat_id": chat_id},
        name=f"giveaway_{gid}",
    )

    await msg.reply_text(
        f"Cekilis baslatildi! {fmt_time(duration_secs)} sonra biter."
    )


async def _auto_end_giveaway(context: ContextTypes.DEFAULT_TYPE):
    data    = context.job.data
    gid     = data["gid"]
    chat_id = data["chat_id"]
    await _finish_giveaway(context, gid, chat_id)


async def _finish_giveaway(context: ContextTypes.DEFAULT_TYPE, gid: int, chat_id: int):
    giveaway = await get_giveaway(gid)
    if not giveaway or giveaway["ended"]:
        return

    await end_giveaway(gid)
    participants = await get_giveaway_participants(gid)

    if not participants:
        await context.bot.send_message(
            chat_id, "🎉 Cekilis bitti ama hic katilimci yoktu!"
        )
        return

    winners_count = min(giveaway["winners_count"], len(participants))
    winners = random.sample(participants, winners_count)

    winner_text = "\n".join(
        f"  🏆 {mention(w['user_id'], w['user_name'])}" for w in winners
    )

    await context.bot.send_message(
        chat_id,
        f"🎉 <b>CEKİLİS BITTI!</b>\n\n"
        f"Odul: <b>{html.escape(giveaway['prize'])}</b>\n\n"
        f"Kazananlar:\n{winner_text}\n\n"
        f"Tebrikler!",
        parse_mode="HTML",
    )

    # Edit original message
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=giveaway["message_id"],
            text=(
                f"🏁 <b>CEKİLİS BITTI</b>\n\n"
                f"Odul: <b>{html.escape(giveaway['prize'])}</b>\n"
                f"Katilimci: {len(participants)}\n\n"
                f"Kazananlar:\n{winner_text}"
            ),
            parse_mode="HTML",
        )
    except Exception:
        pass


async def gend_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context): return
    chat_id = update.effective_chat.id
    giveaway = await get_active_giveaway(chat_id)
    if not giveaway:
        return await update.effective_message.reply_text("Aktif cekilis yok.")
    await _finish_giveaway(context, giveaway["id"], chat_id)


async def greroll_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pick new winners from last giveaway."""
    if not await require_admin(update, context): return
    chat_id = update.effective_chat.id

    import aiosqlite
    from config import DATABASE_PATH
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT id,prize,winners_count FROM giveaways WHERE chat_id=? AND ended=1 "
            "ORDER BY id DESC LIMIT 1", (chat_id,)
        ) as cur:
            row = await cur.fetchone()

    if not row:
        return await update.effective_message.reply_text("Bitmis cekilis bulunamadi.")

    gid, prize, winners_count = row
    participants = await get_giveaway_participants(gid)
    if not participants:
        return await update.effective_message.reply_text("Katilimci yoktu.")

    winners_count = min(winners_count, len(participants))
    winners = random.sample(participants, winners_count)
    winner_text = "\n".join(
        f"  🏆 {mention(w['user_id'], w['user_name'])}" for w in winners
    )
    await update.effective_message.reply_text(
        f"🎲 Yeniden cekis!\n\nOdul: <b>{html.escape(prize)}</b>\n\nYeni kazananlar:\n{winner_text}",
        parse_mode="HTML",
    )


async def giveaway_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    data = q.data  # gj_{gid}
    gid  = int(data.split("_")[1])
    user = update.effective_user

    giveaway = await get_giveaway(gid)
    if not giveaway:
        return await q.answer("Bu cekilis artik gecerli degil.", show_alert=True)
    if giveaway["ended"]:
        return await q.answer("Bu cekilis bitmis!", show_alert=True)
    if int(time.time()) > giveaway["end_time"]:
        return await q.answer("Bu cekilis suresi doldu!", show_alert=True)

    joined = await join_giveaway(gid, user.id, user.first_name)
    if not joined:
        return await q.answer("Zaten katildiniz!", show_alert=True)

    await q.answer("Katildiniz! Iyi sanslar 🎉", show_alert=True)

    # Update button count
    participants = await get_giveaway_participants(gid)
    count = len(participants)
    try:
        await q.edit_message_reply_markup(_enter_kb(gid, count))
    except Exception:
        pass


def register_giveaway_handlers(app):
    for cmd, handler in [
        ("giveaway", giveaway_cmd), ("gend", gend_cmd), ("greroll", greroll_cmd),
    ]:
        app.add_handler(CommandHandler(cmd, handler))
        app.add_handler(MessageHandler(filters.TEXT & dot_filter(cmd), handler))

    app.add_handler(CallbackQueryHandler(giveaway_join, pattern=r"^gj_"))
