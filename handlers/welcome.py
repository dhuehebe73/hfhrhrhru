"""
Welcome / goodbye / captcha / autoban
Commands: setwelcome setgoodbye welcome autoban captcha
"""
import html, random, time

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, CommandHandler, MessageHandler, ChatMemberHandler,
    CallbackQueryHandler, filters,
)
from telegram.constants import ChatMemberStatus
from telegram.error import BadRequest

from utils import require_admin, mention, MUTE_PERMS, FULL_PERMS, dot_filter
from database import (
    get_welcome_row, set_welcome_field,
    mark_left, has_left_before, clear_left,
    get_chat_settings, update_chat_setting,
    set_captcha, get_captcha, clear_captcha,
)


# ─── Commands ─────────────────────────────────────────────────────────────────

async def setwelcome_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context): return
    text = " ".join(context.args) if context.args else ""
    if not text:
        return await update.effective_message.reply_text(
            "Karsilama mesaji yaz.\n"
            "Degiskenler: {name} {chat} {count} {id}\n"
            "Ornek: .setwelcome Hos geldin {name}! Simdi {count} uyemiz var."
        )
    await set_welcome_field(update.effective_chat.id, "welcome_msg", text)
    await update.effective_message.reply_text("Karsilama mesaji ayarlandi!")


async def setgoodbye_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context): return
    text = " ".join(context.args) if context.args else ""
    if not text:
        return await update.effective_message.reply_text(
            "Veda mesaji yaz.\nDegiskenler: {name} {chat}\n"
            "Ornek: .setgoodbye Gule gule {name}!"
        )
    await set_welcome_field(update.effective_chat.id, "goodbye_msg", text)
    await update.effective_message.reply_text("Veda mesaji ayarlandi!")


async def welcome_preview_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row = await get_welcome_row(update.effective_chat.id)
    user = update.effective_user
    chat = update.effective_chat
    try: count = await context.bot.get_chat_member_count(chat.id)
    except Exception: count = "?"

    wt = (row["welcome_msg"] or "Henuz karsilama mesaji ayarlanmamis.").format(
        name=html.escape(user.first_name),
        chat=html.escape(chat.title or ""),
        count=count, id=user.id,
    )
    await update.effective_message.reply_text(
        f"<b>Karsilama on izleme:</b>\n\n{wt}", parse_mode="HTML"
    )


async def autoban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context): return
    args = context.args
    chat_id = update.effective_chat.id
    settings = await get_chat_settings(chat_id)

    if args and args[0].lower() in ("on", "ac", "1", "aktif"):
        await update_chat_setting(chat_id, "auto_ban_leavers", 1)
        await update.effective_message.reply_text(
            "Oto-ban ACIK! Gruptan ayrilanlar otomatik banlanacak."
        )
    elif args and args[0].lower() in ("off", "kapat", "0", "pasif"):
        await update_chat_setting(chat_id, "auto_ban_leavers", 0)
        await update.effective_message.reply_text("Oto-ban KAPALI.")
    else:
        state = "ACIK" if settings["auto_ban_leavers"] else "KAPALI"
        await update.effective_message.reply_text(
            f"Oto-ban: {state}\n.autoban on / .autoban off"
        )


async def captcha_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context): return
    args = context.args
    chat_id = update.effective_chat.id

    if args and args[0].lower() in ("on", "ac", "1"):
        await set_welcome_field(chat_id, "captcha", 1)
        await update.effective_message.reply_text(
            "Captcha ACIK! Yeni uyeler matematik sorusu cozecek."
        )
    elif args and args[0].lower() in ("off", "kapat", "0"):
        await set_welcome_field(chat_id, "captcha", 0)
        await update.effective_message.reply_text("Captcha KAPALI.")
    else:
        row = await get_welcome_row(chat_id)
        state = "ACIK" if row["captcha"] else "KAPALI"
        await update.effective_message.reply_text(
            f"Captcha: {state}\n.captcha on / .captcha off"
        )


# ─── ChatMember update ───────────────────────────────────────────────────────

async def on_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.chat_member
    if not result:
        return

    chat    = result.chat
    user    = result.new_chat_member.user
    old_st  = result.old_chat_member.status
    new_st  = result.new_chat_member.status

    # ── JOINED ──
    if new_st == ChatMemberStatus.MEMBER and old_st in (
        ChatMemberStatus.LEFT, ChatMemberStatus.BANNED
    ):
        settings = await get_chat_settings(chat.id)

        # Auto-ban rejoiner
        if settings["auto_ban_leavers"] and await has_left_before(user.id, chat.id):
            try:
                await context.bot.ban_chat_member(chat.id, user.id)
                await context.bot.send_message(
                    chat.id,
                    f"{mention(user.id, user.first_name)} daha once gruptan ayrilmisti. Otomatik banlandı.",
                    parse_mode="HTML",
                )
                await clear_left(user.id, chat.id)
                return
            except Exception:
                pass

        # Captcha
        row = await get_welcome_row(chat.id)
        if row["captcha"]:
            await _send_captcha(context, chat.id, user, row["captcha_timeout"])
        else:
            # Welcome message
            if row["enabled"] and row["welcome_msg"]:
                try:
                    count = await context.bot.get_chat_member_count(chat.id)
                except Exception:
                    count = "?"
                text = row["welcome_msg"].format(
                    name=html.escape(user.first_name),
                    chat=html.escape(chat.title or ""),
                    count=count, id=user.id,
                )
                try:
                    await context.bot.send_message(chat.id, text, parse_mode="HTML")
                except Exception:
                    pass

    # ── LEFT ──
    elif new_st == ChatMemberStatus.LEFT and old_st == ChatMemberStatus.MEMBER:
        settings = await get_chat_settings(chat.id)

        if settings["auto_ban_leavers"]:
            try:
                await context.bot.ban_chat_member(chat.id, user.id)
                await context.bot.send_message(
                    chat.id,
                    f"{mention(user.id, user.first_name)} gruptan ayrildi. Otomatik banlandı.",
                    parse_mode="HTML",
                )
                return
            except Exception:
                pass
        else:
            await mark_left(user.id, chat.id)

        row = await get_welcome_row(chat.id)
        if row["enabled"] and row["goodbye_msg"]:
            text = row["goodbye_msg"].format(
                name=html.escape(user.first_name),
                chat=html.escape(chat.title or ""),
                count="?", id=user.id,
            )
            try:
                await context.bot.send_message(chat.id, text, parse_mode="HTML")
            except Exception:
                pass


# ─── Captcha ─────────────────────────────────────────────────────────────────

async def _send_captcha(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user, timeout: int):
    a = random.randint(1, 15)
    b = random.randint(1, 15)
    answer = a + b
    wrong1 = answer + random.choice([-2, -1, 1, 2])
    wrong2 = answer + random.choice([-3, 3, 4, -4])

    buttons = [answer, wrong1, wrong2]
    random.shuffle(buttons)

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(str(x), callback_data=f"cap_{user.id}_{x}")
        for x in buttons
    ]])

    try:
        # Restrict user
        await context.bot.restrict_chat_member(chat_id, user.id, MUTE_PERMS)
        msg = await context.bot.send_message(
            chat_id,
            f"{mention(user.id, user.first_name)} — bot degil misin? Cevapla!\n\n"
            f"<b>{a} + {b} = ?</b>\n\n"
            f"<i>{timeout} saniye icinde cevapla, yoksa atilirsin.</i>",
            parse_mode="HTML",
            reply_markup=kb,
        )
        await set_captcha(user.id, chat_id, answer, int(time.time()) + timeout, msg.message_id)

        context.job_queue.run_once(
            _captcha_expire, timeout,
            data={"user_id": user.id, "chat_id": chat_id},
            name=f"cap_{user.id}_{chat_id}",
        )
    except Exception:
        pass


async def _captcha_expire(context: ContextTypes.DEFAULT_TYPE):
    data    = context.job.data
    user_id = data["user_id"]
    chat_id = data["chat_id"]

    cap = await get_captcha(user_id, chat_id)
    if not cap:
        return
    await clear_captcha(user_id, chat_id)
    try:
        await context.bot.kick_chat_member(chat_id, user_id)
        await context.bot.send_message(
            chat_id, f"Captcha cevaplanmadi. Kullanici atildi."
        )
        try:
            await context.bot.delete_message(chat_id, cap["msg_id"])
        except Exception:
            pass
    except Exception:
        pass


async def captcha_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    data = q.data  # cap_{user_id}_{answer}
    parts = data.split("_")
    if len(parts) != 3:
        return

    target_uid = int(parts[1])
    chosen     = int(parts[2])
    clicker    = update.effective_user.id
    chat_id    = update.effective_chat.id

    if clicker != target_uid:
        return await q.answer("Bu sana ait degil!", show_alert=True)

    cap = await get_captcha(target_uid, chat_id)
    if not cap:
        return await q.answer("Captcha suresi doldu.", show_alert=True)

    if int(time.time()) > cap["expires"]:
        await clear_captcha(target_uid, chat_id)
        return await q.answer("Sure doldu!", show_alert=True)

    await clear_captcha(target_uid, chat_id)

    if chosen == cap["answer"]:
        try:
            await context.bot.restrict_chat_member(chat_id, target_uid, FULL_PERMS)
            await q.edit_message_text(
                f"{mention(target_uid, update.effective_user.first_name)} dogrulandi! Hos geldin.",
                parse_mode="HTML",
            )
        except Exception:
            pass
    else:
        try:
            await q.edit_message_text("Yanlis cevap! Atiliyorsun...")
            await context.bot.ban_chat_member(chat_id, target_uid)
            await context.bot.unban_chat_member(chat_id, target_uid)
        except Exception:
            pass


def register_welcome_handlers(app):
    from telegram.ext import filters
    for cmd, handler in [
        ("setwelcome", setwelcome_cmd), ("setgoodbye", setgoodbye_cmd),
        ("welcome", welcome_preview_cmd), ("autoban", autoban_cmd),
        ("captcha", captcha_cmd),
    ]:
        app.add_handler(CommandHandler(cmd, handler))
        app.add_handler(MessageHandler(filters.TEXT & dot_filter(cmd), handler))

    app.add_handler(ChatMemberHandler(on_chat_member, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(CallbackQueryHandler(captcha_answer, pattern=r"^cap_"))
