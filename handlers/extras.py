"""
Extras: broadcast, fun commands, AFK, weather, calculator, poll, dice, report
"""
import html, random, math, re, time
from datetime import datetime

from telegram import Update, Poll, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters

from utils import (
    require_admin, is_owner, mention, dot_filter,
    resolve_user, is_admin,
)
from database import (
    set_afk, get_afk, clear_afk,
    get_all_chats, register_chat,
)
from config import OWNER_ID


# ═══ BROADCAST ═══════════════════════════════════════════════════════════════

async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not await is_owner(update):
        return await msg.reply_text("Sadece bot sahibi kullanabilir.")

    text = ""
    if msg.reply_to_message:
        text = msg.reply_to_message.text or msg.reply_to_message.caption or ""
    elif context.args:
        text = " ".join(context.args)

    if not text:
        return await msg.reply_text(
            "Kullanim:\n"
            "  .broadcast <metin>\n"
            "  Bir mesaja reply at + .broadcast"
        )

    chats = await get_all_chats()
    if not chats:
        return await msg.reply_text("Hicbir grup/kanal kayitli degil.")

    sent = 0
    failed = 0
    status = await msg.reply_text(f"Yayinlaniyor... ({len(chats)} grup/kanal)")

    for chat in chats:
        try:
            await context.bot.send_message(
                chat["chat_id"], text, parse_mode="HTML"
            )
            sent += 1
        except Exception:
            failed += 1

    await status.edit_text(
        f"Yayin tamamlandi!\n✓ Gonderildi: {sent}\n✗ Basarisiz: {failed}"
    )


async def pbroadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pin message in all chats."""
    msg = update.effective_message
    if not await is_owner(update):
        return await msg.reply_text("Sadece bot sahibi kullanabilir.")

    text = " ".join(context.args) if context.args else ""
    if not text:
        return await msg.reply_text(".pbroadcast <metin>")

    chats = await get_all_chats()
    sent = 0
    for chat in chats:
        try:
            sent_msg = await context.bot.send_message(
                chat["chat_id"], text, parse_mode="HTML"
            )
            await context.bot.pin_chat_message(chat["chat_id"], sent_msg.message_id)
            sent += 1
        except Exception:
            pass

    await msg.reply_text(f"Sabitlendi: {sent} grup/kanal")


# ═══ AFK ══════════════════════════════════════════════════════════════════════

async def afk_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user   = update.effective_user
    reason = " ".join(context.args) if context.args else ""
    await set_afk(user.id, reason)
    r = f": {html.escape(reason)}" if reason else ""
    await update.effective_message.reply_text(
        f"{mention(user.id, user.first_name)} AFK moduna gecti{r}.",
        parse_mode="HTML",
    )


async def back_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    afk  = await get_afk(user.id)
    if not afk:
        return
    from utils import fmt_ago
    ago = fmt_ago(afk["since"])
    await clear_afk(user.id)
    await update.effective_message.reply_text(
        f"{mention(user.id, user.first_name)} geri dondu! ({ago} yoktu)",
        parse_mode="HTML",
    )


async def check_afk_mention(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not msg.text:
        return

    user = update.effective_user
    if not user:
        return

    # Auto-back when AFK user sends a message
    afk = await get_afk(user.id)
    if afk:
        from utils import fmt_ago
        ago = fmt_ago(afk["since"])
        await clear_afk(user.id)
        try:
            await msg.reply_text(
                f"{mention(user.id, user.first_name)} AFK modundan cikti! ({ago} yoktu)",
                parse_mode="HTML",
            )
        except Exception:
            pass

    # Check if replied user is AFK
    if msg.reply_to_message and msg.reply_to_message.from_user:
        target = msg.reply_to_message.from_user
        t_afk  = await get_afk(target.id)
        if t_afk:
            from utils import fmt_ago
            ago    = fmt_ago(t_afk["since"])
            reason = t_afk["reason"]
            r_text = f" ({html.escape(reason)})" if reason else ""
            try:
                await msg.reply_text(
                    f"{mention(target.id, target.first_name)} simdi AFK{r_text}. ({ago} once)",
                    parse_mode="HTML",
                )
            except Exception:
                pass


# ═══ FUN ══════════════════════════════════════════════════════════════════════

async def dice_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_dice()


async def flip_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = random.choice(["Yazı (heads) 🪙", "Tura (tails) 🪙"])
    await update.effective_message.reply_text(result)


async def rps_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choices = ["✊ Tas", "✋ Kagit", "✌️ Makas"]
    await update.effective_message.reply_text(f"Botun secimi: {random.choice(choices)}")


async def calc_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    expr = " ".join(context.args) if context.args else ""
    if not expr:
        return await update.effective_message.reply_text("Kullanim: .calc 2+2*3")

    # Safe eval - only allow math
    safe_expr = re.sub(r"[^0-9+\-*/%.()\s^sqrtpielog]", "", expr.lower())
    safe_expr = safe_expr.replace("^", "**")
    try:
        result = eval(safe_expr, {"__builtins__": {}}, {
            "sqrt": math.sqrt, "pi": math.pi, "e": math.e,
            "sin": math.sin, "cos": math.cos, "tan": math.tan,
            "log": math.log, "abs": abs, "round": round,
        })
        await update.effective_message.reply_text(
            f"<code>{expr} = {result}</code>", parse_mode="HTML"
        )
    except Exception:
        await update.effective_message.reply_text("Gecersiz ifade.")


async def weather_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = " ".join(context.args) if context.args else ""
    if not city:
        return await update.effective_message.reply_text("Kullanim: .weather Istanbul")
    try:
        import requests
        r = requests.get(
            f"https://wttr.in/{city.replace(' ', '+')}?format=4",
            timeout=5,
            headers={"User-Agent": "TelegramBot"},
        )
        if r.status_code == 200 and r.text.strip():
            await update.effective_message.reply_text(f"🌤 {r.text.strip()}")
        else:
            await update.effective_message.reply_text("Hava durumu alinamadi.")
    except Exception as e:
        await update.effective_message.reply_text(f"Hata: {e}")


async def poll_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    args = context.args
    if not args or len(args) < 3:
        return await msg.reply_text(
            "Kullanim: .poll <soru> <secenek1> <secenek2> [secenek3...]\n"
            'Ornek: .poll "Favori rengin?" Mavi Yesil Kirmizi'
        )

    # Parse quoted question or first word
    text = " ".join(args)
    if text.startswith('"'):
        end = text.find('"', 1)
        if end != -1:
            question = text[1:end]
            options  = text[end+1:].strip().split()
        else:
            parts    = args
            question = parts[0]
            options  = parts[1:]
    else:
        question = args[0]
        options  = args[1:]

    if len(options) < 2:
        return await msg.reply_text("En az 2 secenek gerekli.")
    if len(options) > 10:
        return await msg.reply_text("En fazla 10 secenek olabilir.")

    await context.bot.send_poll(
        update.effective_chat.id,
        question=question[:300],
        options=[o[:100] for o in options[:10]],
        is_anonymous=True,
    )


async def quote_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if msg.reply_to_message:
        r    = msg.reply_to_message
        text = r.text or r.caption or ""
        name = r.from_user.first_name if r.from_user else "Bilinmeyen"
        if text:
            await msg.reply_text(
                f"❝ {html.escape(text)} ❞\n\n— {html.escape(name)}",
                parse_mode="HTML",
            )
        else:
            await msg.reply_text("Alcintılanacak metin yok.")
    else:
        quotes = [
            "Hayat bir bisiklet surmek gibidir. Dengeni korumak icin hareket etmelisin. — Einstein",
            "Basari, hevesle aranan bir seyin sonucudur. — Edison",
            "Eger dugme dikmesini bilmiyorsan, tahta oturma. — Ataturk",
        ]
        await msg.reply_text(f"💬 {random.choice(quotes)}")


async def report_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg.reply_to_message:
        return await msg.reply_text("Kimi sikayet ediyorsun? Mesajina reply at.")

    reported = msg.reply_to_message.from_user
    reporter = update.effective_user
    reason   = " ".join(context.args) if context.args else "Sebep belirtilmedi"
    chat     = update.effective_chat

    try:
        admins = await chat.get_administrators()
        admin_pings = " ".join(
            f"@{a.user.username}" if a.user.username else ""
            for a in admins if not a.user.is_bot and a.user.username
        )
    except Exception:
        admin_pings = ""

    await msg.reply_text(
        f"⚠️ <b>Sikayet</b>\n\n"
        f"Sikayet eden: {mention(reporter.id, reporter.first_name)}\n"
        f"Sikayet edilen: {mention(reported.id, reported.first_name)}\n"
        f"Sebep: {html.escape(reason)}\n\n"
        f"{admin_pings}",
        parse_mode="HTML",
    )


# ═══ REGISTER ════════════════════════════════════════════════════════════════

def register_extras_handlers(app):
    cmds = [
        ("broadcast", broadcast_cmd), ("bc", broadcast_cmd),
        ("pbroadcast", pbroadcast_cmd),
        ("afk", afk_cmd), ("back", back_cmd),
        ("dice", dice_cmd), ("roll", dice_cmd),
        ("flip", flip_cmd), ("coin", flip_cmd),
        ("rps", rps_cmd),
        ("calc", calc_cmd), ("hesapla", calc_cmd),
        ("weather", weather_cmd), ("hava", weather_cmd),
        ("poll", poll_cmd), ("anket", poll_cmd),
        ("quote", quote_cmd), ("alinti", quote_cmd),
        ("report", report_cmd), ("sikayet", report_cmd),
    ]
    for cmd, handler in cmds:
        app.add_handler(CommandHandler(cmd, handler))
        app.add_handler(MessageHandler(filters.TEXT & dot_filter(cmd), handler))

    # AFK check on every message
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, check_afk_mention),
        group=20,
    )
