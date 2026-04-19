import html, random, math, re, time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Poll
from telegram.ext import ContextTypes, MessageHandler, filters
from database import (get_all_chats, set_afk, get_afk, clear_afk, bump_stats, top_users,
                      get_all_users)
from utils import require_admin, mention, dcmd, fmt_ago, get_args
from config import OWNER_ID


# ── Broadcast ─────────────────────────────────────────────────────────────────

async def broadcast_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.effective_message.reply_text("❌ Sadece bot sahibi."); return
    msg = update.effective_message
    _a = get_args(update, ctx)
    text = " ".join(_a) if _a else (
        msg.reply_to_message.text if msg.reply_to_message else "")
    if not text:
        await msg.reply_text("Kullanım: /broadcast <metin>"); return
    chats = await get_all_chats()
    ok = fail = 0
    for ch in chats:
        try:
            await ctx.bot.send_message(ch["chat_id"], text)
            ok += 1
        except Exception:
            fail += 1
    await msg.reply_text(f"📣 Gönderildi: {ok} ✅ | Başarısız: {fail} ❌")


# ── AFK ───────────────────────────────────────────────────────────────────────

async def afk_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    reason = " ".join(get_args(update, ctx))
    await set_afk(user.id, reason)
    text = f"😴 {html.escape(user.first_name)} AFK moduna geçti."
    if reason: text += f"\nSebep: {reason}"
    await update.effective_message.reply_text(text, parse_mode="HTML")

async def _check_afk(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not msg.from_user: return

    uid = msg.from_user.id
    afk = await get_afk(uid)
    if afk:
        await clear_afk(uid)
        elapsed = fmt_ago(afk["since"])
        m = await msg.reply_text(
            f"👋 {html.escape(msg.from_user.first_name)} AFK'dan döndü! ({elapsed} önce gitti)",
            parse_mode="HTML")
        from utils import later
        later(10, m.delete())
        return

    if msg.reply_to_message and msg.reply_to_message.from_user:
        target = msg.reply_to_message.from_user
        ta = await get_afk(target.id)
        if ta:
            elapsed = fmt_ago(ta["since"])
            text = f"💤 {html.escape(target.first_name)} şu an AFK ({elapsed} önce)"
            if ta["reason"]: text += f"\nSebep: {ta['reason']}"
            m = await msg.reply_text(text, parse_mode="HTML")
            from utils import later
            later(10, m.delete())


# ── Stats ─────────────────────────────────────────────────────────────────────

async def _track_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    c = update.effective_chat
    if u and c and c.type != "private":
        await bump_stats(u.id, c.id)

async def top_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    rows = await top_users(update.effective_chat.id, 10)
    if not rows:
        await update.effective_message.reply_text("Henüz istatistik yok."); return
    lines = []
    medals = ["🥇","🥈","🥉"]
    for i, row in enumerate(rows):
        medal = medals[i] if i < 3 else f"{i+1}."
        try:
            u = await ctx.bot.get_chat(row["user_id"])
            name = u.first_name
        except Exception:
            name = str(row["user_id"])
        lines.append(f"{medal} {html.escape(name)} — {row['messages']} mesaj")
    await update.effective_message.reply_text(
        "📊 <b>En aktif üyeler:</b>\n" + "\n".join(lines), parse_mode="HTML")


# ── Fun commands ──────────────────────────────────────────────────────────────

async def dice_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_dice()

async def flip_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "🪙 " + random.choice(["Yazı!", "Tura!"]))

_RPS = {"tas":"🪨","kaya":"🪨","stone":"🪨","rock":"🪨",
        "kagit":"📄","kağıt":"📄","paper":"📄",
        "makas":"✂️","scissors":"✂️"}
_RPS_WIN = [("tas","makas"),("kagit","tas"),("makas","kagit"),
            ("kaya","makas"),("kağıt","kaya"),("scissors","rock"),
            ("rock","scissors"),("paper","rock"),("scissors","paper")]

async def rps_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = get_args(update, ctx)
    choices = list(_RPS.keys())
    bot_choice = random.choice(["tas","kagit","makas"])
    if not args:
        await update.effective_message.reply_text(
            f"Kullanım: /rps <taş|kağıt|makas>\nBenim seçimim: {_RPS[bot_choice]}"); return
    user_choice = args[0].lower().replace("ğ","ğ")
    if user_choice not in _RPS:
        await update.effective_message.reply_text("taş, kağıt veya makas gir!"); return
    ue = _RPS[user_choice]
    be = _RPS[bot_choice]
    if user_choice == bot_choice:
        result = "🤝 Berabere!"
    elif (user_choice, bot_choice) in _RPS_WIN:
        result = "🎉 Sen kazandın!"
    else:
        result = "🤖 Ben kazandım!"
    await update.effective_message.reply_text(f"Sen: {ue} | Ben: {be}\n{result}")

async def calc_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = get_args(update, ctx)
    if not args:
        await update.effective_message.reply_text("Kullanım: /calc <işlem>"); return
    expr = " ".join(args)
    safe = re.sub(r"[^0-9+\-*/().% ]", "", expr)
    try:
        result = eval(safe, {"__builtins__": {}})
        await update.effective_message.reply_text(f"🧮 {expr} = {result}")
    except Exception:
        await update.effective_message.reply_text("❌ Geçersiz işlem.")

async def id_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if msg.reply_to_message and msg.reply_to_message.from_user:
        u = msg.reply_to_message.from_user
        await msg.reply_text(
            f"👤 {html.escape(u.full_name)}\n🆔 ID: <code>{u.id}</code>", parse_mode="HTML")
    else:
        u = update.effective_user
        c = update.effective_chat
        await msg.reply_text(
            f"👤 Sen: <code>{u.id}</code>\n💬 Grup: <code>{c.id}</code>", parse_mode="HTML")

async def ping_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    start = time.time()
    m = await update.effective_message.reply_text("🏓 Pong!")
    delta = (time.time() - start) * 1000
    await m.edit_text(f"🏓 Pong! <b>{delta:.0f}ms</b>", parse_mode="HTML")

async def info_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    target = msg.reply_to_message.from_user if msg.reply_to_message else update.effective_user
    u = target
    text = (f"👤 <b>{html.escape(u.full_name)}</b>\n"
            f"🆔 <code>{u.id}</code>\n"
            f"📛 @{u.username or '(yok)'}\n"
            f"🤖 Bot: {'Evet' if u.is_bot else 'Hayır'}")
    await msg.reply_text(text, parse_mode="HTML")

async def report_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg.reply_to_message:
        await msg.reply_text("Şikayet etmek için bir mesajı yanıtla."); return
    reported = msg.reply_to_message.from_user
    reporter = update.effective_user
    admins = await update.effective_chat.get_administrators()
    for adm in admins:
        if adm.user.is_bot: continue
        try:
            await ctx.bot.send_message(adm.user.id,
                f"⚠️ Şikayet!\n"
                f"Şikayet eden: {mention(reporter.id, reporter.first_name)}\n"
                f"Şikayet edilen: {mention(reported.id, reported.first_name)}\n"
                f"Grup: {html.escape(update.effective_chat.title or '')}",
                parse_mode="HTML")
        except Exception: pass
    await msg.reply_text("✅ Adminler bilgilendirildi.")

async def rules_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from database import get_rules
    text = await get_rules(update.effective_chat.id)
    if not text:
        await update.effective_message.reply_text("Henüz kural eklenmemiş."); return
    await update.effective_message.reply_text(
        f"📜 <b>Kurallar:</b>\n{text}", parse_mode="HTML")

async def setrules_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, ctx): return
    from database import set_rules
    msg = update.effective_message
    _a = get_args(update, ctx)
    text = " ".join(_a) if _a else (
        msg.reply_to_message.text if msg.reply_to_message else "")
    if not text:
        await msg.reply_text("Kullanım: /setrules <kurallar>"); return
    await set_rules(update.effective_chat.id, text)
    await msg.reply_text("✅ Kurallar ayarlandı.")


async def users_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.effective_message.reply_text("❌ Owner only."); return
    users = await get_all_users()
    if not users:
        await update.effective_message.reply_text("No users yet."); return
    lines = []
    for u in users[:50]:
        name = html.escape(u["first_name"] or str(u["user_id"]))
        un   = f" @{u['username']}" if u["username"] else ""
        lines.append(f"• <code>{u['user_id']}</code> {name}{un}")
    text = f"👥 <b>Bot Users ({len(users)})</b>\n\n" + "\n".join(lines)
    if len(users) > 50:
        text += f"\n\n…and {len(users)-50} more."
    await update.effective_message.reply_text(text, parse_mode="HTML")

async def chats_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.effective_message.reply_text("❌ Owner only."); return
    chats = await get_all_chats()
    if not chats:
        await update.effective_message.reply_text("No chats registered yet."); return
    groups   = [c for c in chats if c["chat_type"] in ("group","supergroup")]
    channels = [c for c in chats if c["chat_type"] == "channel"]
    lines = [f"📊 <b>Registered Chats ({len(chats)})</b>",
             f"👥 Groups: {len(groups)} | 📢 Channels: {len(channels)}\n"]
    for c in chats[:40]:
        icon = "📢" if c["chat_type"] == "channel" else "👥"
        lines.append(f"{icon} <code>{c['chat_id']}</code> {html.escape(c['title'] or '')}")
    if len(chats) > 40:
        lines.append(f"\n…and {len(chats)-40} more.")
    await update.effective_message.reply_text("\n".join(lines), parse_mode="HTML")


def register(app):
    app.add_handler(MessageHandler(
        filters.ChatType.GROUPS & filters.TEXT & ~filters.COMMAND,
        _check_afk), group=20)
    app.add_handler(MessageHandler(
        filters.ChatType.GROUPS & filters.ALL & ~filters.COMMAND,
        _track_stats), group=20)

    for cmd, h in [
        ("broadcast", broadcast_cmd),
        ("users", users_cmd),
        ("chats", chats_cmd),
        ("afk", afk_cmd),
        ("top", top_cmd),
        ("dice", dice_cmd),
        ("flip", flip_cmd),
        ("rps", rps_cmd),
        ("calc", calc_cmd),
        ("id", id_cmd),
        ("ping", ping_cmd),
        ("info", info_cmd),
        ("report", report_cmd),
        ("rules", rules_cmd),
        ("setrules", setrules_cmd),
    ]:
        app.add_handler(MessageHandler(dcmd(cmd), h), group=10)
