import random, time, asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, CallbackQueryHandler
from database import (create_giveaway, get_giveaway, get_active_giveaway,
                      join_giveaway, get_participants, end_giveaway)
from utils import require_admin, mention, dcmd, parse_time, fmt_duration, get_args


def _giveaway_kb(gid: int, count: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(f"🎉 Katıl ({count})", callback_data=f"gaw_join|{gid}"),
        InlineKeyboardButton("👥 Katılımcılar", callback_data=f"gaw_list|{gid}"),
    ]])


async def giveaway_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, ctx): return
    args = get_args(update, ctx)
    if len(args) < 2:
        await update.effective_message.reply_text(
            "Kullanım: /giveaway <süre> [kazanan_sayısı] <ödül>\n"
            "Örnek: /giveaway 1h 2 Nitro Boost"); return

    duration = parse_time(args[0])
    if not duration:
        await update.effective_message.reply_text(
            "Geçersiz süre. Örnek: 30m, 1h, 1d"); return

    if len(args) >= 3 and args[1].isdigit():
        winners_count = max(1, int(args[1]))
        prize = " ".join(args[2:])
    else:
        winners_count = 1
        prize = " ".join(args[1:])

    if not prize:
        await update.effective_message.reply_text("Ödül belirtin."); return

    end_time = int(time.time()) + duration
    chat = update.effective_chat
    user = update.effective_user

    text = (f"🎉 <b>ÇEKİLİŞ</b>\n\n"
            f"🏆 Ödül: {prize}\n"
            f"👑 Kazanan: {winners_count} kişi\n"
            f"⏱ Bitiş: {fmt_duration(duration)}\n\n"
            f"Katılmak için aşağıdaki butona tıkla!")

    msg = await update.effective_message.reply_text(text, parse_mode="HTML",
        reply_markup=_giveaway_kb(0, 0))

    gid = await create_giveaway(chat.id, msg.message_id, prize, winners_count,
                                end_time, user.id)

    await ctx.bot.edit_message_reply_markup(chat.id, msg.message_id,
        reply_markup=_giveaway_kb(gid, 0))

    asyncio.create_task(_auto_end(ctx, gid, chat.id, duration))


async def _auto_end(ctx, gid: int, chat_id: int, delay: float):
    await asyncio.sleep(delay)
    await _finish_giveaway(ctx, gid, chat_id)


async def _finish_giveaway(ctx, gid: int, chat_id: int):
    gaw = await get_giveaway(gid)
    if not gaw or gaw["ended"]: return
    await end_giveaway(gid)
    participants = await get_participants(gid)
    if not participants:
        try:
            await ctx.bot.send_message(chat_id,
                f"🎉 Çekiliş bitti ama katılımcı yoktu. 😢")
        except Exception: pass
        return
    n = min(gaw["winners_count"], len(participants))
    winners = random.sample(participants, n)
    winner_mentions = " ".join(mention(w["user_id"], w["user_name"]) for w in winners)
    text = (f"🎊 <b>ÇEKİLİŞ SONUÇLANDI!</b>\n\n"
            f"🏆 Ödül: {gaw['prize']}\n"
            f"🥳 Kazanan(lar): {winner_mentions}\n"
            f"👥 Toplam katılımcı: {len(participants)}")
    try:
        await ctx.bot.send_message(chat_id, text, parse_mode="HTML")
    except Exception: pass
    try:
        await ctx.bot.edit_message_reply_markup(chat_id, gaw["message_id"], reply_markup=None)
    except Exception: pass


async def gend_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, ctx): return
    gaw = await get_active_giveaway(update.effective_chat.id)
    if not gaw:
        await update.effective_message.reply_text("Aktif çekiliş yok."); return
    await _finish_giveaway(ctx, gaw["id"], update.effective_chat.id)

async def greroll_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, ctx): return
    chat = update.effective_chat
    from database import get_giveaway
    import aiosqlite
    from config import DB_PATH
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id FROM giveaways WHERE chat_id=? AND ended=1 ORDER BY id DESC LIMIT 1",
            (chat.id,)
        ) as c:
            row = await c.fetchone()
    if not row:
        await update.effective_message.reply_text("Tamamlanmış çekiliş bulunamadı."); return
    gaw = await get_giveaway(row[0])
    if not gaw: return
    participants = await get_participants(gaw["id"])
    if not participants:
        await update.effective_message.reply_text("Katılımcı yok."); return
    winner = random.choice(participants)
    await update.effective_message.reply_text(
        f"🔄 Yeni kazanan: {mention(winner['user_id'], winner['user_name'])}",
        parse_mode="HTML")


async def gaw_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user = query.from_user

    if data.startswith("gaw_join|"):
        gid = int(data.split("|")[1])
        gaw = await get_giveaway(gid)
        if not gaw or gaw["ended"]:
            await query.answer("Bu çekiliş sona erdi.", show_alert=True); return
        joined = await join_giveaway(gid, user.id, user.first_name)
        if joined:
            await query.answer("✅ Çekilişe katıldın!", show_alert=True)
        else:
            await query.answer("Zaten katıldın.", show_alert=True)
        participants = await get_participants(gid)
        try:
            await query.edit_message_reply_markup(
                reply_markup=_giveaway_kb(gid, len(participants)))
        except Exception: pass

    elif data.startswith("gaw_list|"):
        gid = int(data.split("|")[1])
        participants = await get_participants(gid)
        if not participants:
            await query.answer("Henüz katılımcı yok.", show_alert=True); return
        names = ", ".join(p["user_name"] for p in participants[:30])
        if len(participants) > 30: names += f" ve {len(participants)-30} kişi daha"
        await query.answer(f"Katılımcılar ({len(participants)}): {names}", show_alert=True)


def register(app):
    for cmd, h in [
        ("giveaway", giveaway_cmd), ("gend", gend_cmd), ("greroll", greroll_cmd),
    ]:
        app.add_handler(MessageHandler(dcmd(cmd), h), group=10)
    app.add_handler(CallbackQueryHandler(gaw_callback, pattern=r"^gaw_"), group=10)
