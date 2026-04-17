"""
Info + Help (Rose-style inline menu) + Start panel
"""
import html

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from telegram.constants import ChatMemberStatus

from utils import resolve_user, is_admin, mention, dot_filter, fmt_ago
from database import (
    get_rules, set_rules, get_top_users,
    register_chat, get_warnings,
)
from config import OWNER_ID


# ═══ HELP CATEGORIES ════════════════════════════════════════════════════════

_HELP = {
    "admin": (
        "🔨 <b>Moderasyon</b>\n\n"
        "<b>Ban/Kick:</b>\n"
        "• .ban @user [sebep]\n"
        "• .dban — mesaj sil + banla\n"
        "• .sban — sessiz banla\n"
        "• .unban @user\n"
        "• .kick @user / .dkick\n\n"
        "<b>Susturma:</b>\n"
        "• .mute @user [1h/30m/1d] [sebep]\n"
        "• .dmute — mesaj sil + sustur\n"
        "• .unmute @user\n\n"
        "<b>Diger:</b>\n"
        "• .del — mesaj sil\n"
        "• .promote / .demote\n"
        "• .pin / .unpin / .unpinall\n"
        "• .approve / .unapprove"
    ),
    "warn": (
        "⚠️ <b>Uyari Sistemi</b>\n\n"
        "• .warn @user [sebep] — uyard\n"
        "• .dwarn — mesaj sil + uyard\n"
        "• .unwarn @user — 1 uyari kaldir\n"
        "• .resetwarns @user — sifirla\n"
        "• .warns @user — uyarilari goster\n"
        "• .warnmode ban|kick|mute — uyari eylemi\n"
        "• .warnlimit 3 — uyari limiti"
    ),
    "filter": (
        "🔍 <b>Filtreler</b>\n\n"
        "<b>Kelime:</b>\n"
        "• .filter <kelime> — ekle\n"
        "• .unfilter <kelime> — kaldir\n"
        "• .filters — listele\n\n"
        "<b>Tur filtreleri (ac/kapat):</b>\n"
        "• .linkfilter\n"
        "• .stickerfilter\n"
        "• .mediafilter\n"
        "• .botfilter"
    ),
    "welcome": (
        "👋 <b>Karsilama</b>\n\n"
        "• .setwelcome <metin> — karsilama mesaji\n"
        "• .setgoodbye <metin> — veda mesaji\n"
        "• .welcome — onizle\n"
        "• .autoban on|off — ayrilanlari banla\n"
        "• .captcha on|off — captcha dogrulama\n\n"
        "<b>Degiskenler:</b>\n"
        "  {name} {chat} {count} {id}"
    ),
    "notes": (
        "📝 <b>Notlar</b>\n\n"
        "• .save <isim> <icerik> — kaydet\n"
        "• .save <isim> — reply ile kaydet (medya destekli)\n"
        "• .get <isim> — getir\n"
        "• .notes — tum notlar\n"
        "• .clear <isim> — sil\n"
        "• #notismi — hizli cagir"
    ),
    "mod": (
        "🛡️ <b>Grup Yonetimi</b>\n\n"
        "• .purge 10 — son 10 mesaj sil\n"
        "• .purge (reply) — o mesajdan sil\n"
        "• .lock / .unlock — kilitle/ac\n"
        "• .slowmode <sn> — yavas mod\n"
        "• .antiflood on|off|<limit>\n"
        "• .settings — ayarlar paneli"
    ),
    "fun": (
        "🎮 <b>Eglence</b>\n\n"
        "• .dice / .roll — zar at\n"
        "• .flip / .coin — para at\n"
        "• .rps — tas-kagit-makas\n"
        "• .calc <ifade> — hesap\n"
        "• .weather <sehir> — hava\n"
        "• .poll <soru> <s1> <s2> — anket\n"
        "• .quote — alinti\n"
        "• .afk [sebep] — afk modu\n"
        "• .giveaway <sure> <kazanan> <odul>\n"
        "• .report — admin bilgilendir"
    ),
    "dl": (
        "📥 <b>Indirme</b>\n\n"
        "• .play <sarki adi>\n"
        "• .play <youtube/spotify/soundcloud linki>\n"
        "• .video <url> — video indir\n"
        "• .dl <url> — otomatik\n\n"
        "Desteklenen:\n"
        "YouTube • TikTok • Instagram\n"
        "Twitter/X • SoundCloud • Spotify\n\n"
        "Ayrica: Link yapistirinca otomatik butonlar cikar"
    ),
    "tr": (
        "🌐 <b>Ceviri</b>\n\n"
        "• .tr — reply mesaji Turkceye cevir\n"
        "• .tr en — Ingilizceye cevir\n"
        "• .tr de Merhaba — Almancaya cevir\n"
        "• .langs — dil listesi\n\n"
        "50+ dil destekleniyor\n"
        "Ornekler: tr en de fr es ar ru ja zh ko it pt"
    ),
    "owner": (
        "👑 <b>Sahip Komutlari</b>\n\n"
        "• .broadcast <metin> — tum gruplara yayin\n"
        "• .pbroadcast <metin> — yayin + sabitle\n"
        "• .bc <metin> — kisayol\n\n"
        f"<i>Sahip ID: {OWNER_ID}</i>"
    ),
}

_HELP_MAIN_KB = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("🔨 Moderasyon",  callback_data="helpcat_admin"),
        InlineKeyboardButton("⚠️ Uyarilar",   callback_data="helpcat_warn"),
    ],
    [
        InlineKeyboardButton("🔍 Filtreler",  callback_data="helpcat_filter"),
        InlineKeyboardButton("👋 Karsilama",  callback_data="helpcat_welcome"),
    ],
    [
        InlineKeyboardButton("📝 Notlar",     callback_data="helpcat_notes"),
        InlineKeyboardButton("🛡️ Yonetim",    callback_data="helpcat_mod"),
    ],
    [
        InlineKeyboardButton("🎮 Eglence",    callback_data="helpcat_fun"),
        InlineKeyboardButton("📥 Indirme",    callback_data="helpcat_dl"),
    ],
    [
        InlineKeyboardButton("🌐 Ceviri",     callback_data="helpcat_tr"),
        InlineKeyboardButton("👑 Sahip",      callback_data="helpcat_owner"),
    ],
])

def _back_kb():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ Geri", callback_data="helpmain")
    ]])


# ═══ START ═══════════════════════════════════════════════════════════════════

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    await register_chat(chat.id, chat.type, chat.title or "")

    if chat.type == "private":
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📖 Komutlar",  callback_data="helpmain"),
                InlineKeyboardButton("ℹ️ Hakkinda", callback_data="helpcat_owner"),
            ],
            [
                InlineKeyboardButton("📥 Indirme",  callback_data="helpcat_dl"),
                InlineKeyboardButton("🌐 Ceviri",   callback_data="helpcat_tr"),
            ],
        ])
        await update.effective_message.reply_text(
            f"👋 Merhaba <b>{html.escape(user.first_name)}</b>!\n\n"
            "Ben kapsamli bir Telegram grup yonetim botuyum.\n\n"
            "🔹 Beni grubuna ekle ve <b>admin</b> yap\n"
            "🔹 <code>/help</code> ile tum komutlari gor\n"
            "🔹 <code>/settings</code> ile ayarlari yonet\n\n"
            "Rose'dan daha iyiyim! 😎",
            parse_mode="HTML",
            reply_markup=kb,
        )
    else:
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📖 Komutlar",     callback_data="helpmain"),
                InlineKeyboardButton("⚙️ Ayarlar",       url=f"https://t.me/{(await context.bot.get_me()).username}?start=settings"),
            ],
            [
                InlineKeyboardButton("📊 Istatistikler", callback_data="infostats"),
                InlineKeyboardButton("📋 Kurallar",      callback_data="inforules"),
            ],
        ])
        await update.effective_message.reply_text(
            f"✅ Merhaba! Komutlar icin /help yaz.\n"
            f"Ayarlar icin /settings yaz.",
            reply_markup=kb,
        )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "📚 <b>Komut Kategorileri</b>\n\nBir kategori sec:",
        parse_mode="HTML",
        reply_markup=_HELP_MAIN_KB,
    )


async def help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    data = q.data
    await q.answer()

    if data == "helpmain":
        await q.edit_message_text(
            "📚 <b>Komut Kategorileri</b>\n\nBir kategori sec:",
            parse_mode="HTML",
            reply_markup=_HELP_MAIN_KB,
        )
        return

    if data.startswith("helpcat_"):
        cat = data[8:]
        if cat == "owner" and update.effective_user.id != OWNER_ID:
            await q.answer("Bu bolum sadece bot sahibine ozel!", show_alert=True)
            return
        text = _HELP.get(cat, "Bulunamadi.")
        await q.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=_back_kb(),
        )
        return

    if data == "infostats":
        chat = update.effective_chat
        try:
            count = await context.bot.get_chat_member_count(chat.id)
        except Exception:
            count = "?"
        top  = await get_top_users(chat.id, 5)
        lines = [f"📊 <b>{html.escape(chat.title or 'Grup')}</b>", f"Uye: {count}"]
        if top:
            lines.append("\n<b>En aktif:</b>")
            for i, u in enumerate(top, 1):
                try:
                    m = await chat.get_member(u["user_id"])
                    name = m.user.first_name
                except Exception:
                    name = str(u["user_id"])
                lines.append(f"  {i}. {html.escape(name)}: {u['messages']}")
        await q.edit_message_text(
            "\n".join(lines), parse_mode="HTML", reply_markup=_back_kb()
        )
        return

    if data == "inforules":
        chat  = update.effective_chat
        rules = await get_rules(chat.id)
        text  = f"📋 <b>Kurallar</b>\n\n{rules}" if rules else "Henuz kural belirlenmemis."
        await q.edit_message_text(text, parse_mode="HTML", reply_markup=_back_kb())
        return


# ═══ INFO / ID / RULES / ADMINS / MEMBERS / STATS / CHATINFO ════════════════

async def info_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg  = update.effective_message
    chat = update.effective_chat

    uid, name, _ = await resolve_user(update, context)
    if not uid:
        uid  = update.effective_user.id
        name = update.effective_user.first_name

    try:
        member = await chat.get_member(uid)
        user   = member.user
        _S = {
            ChatMemberStatus.OWNER:         "👑 Kurucu",
            ChatMemberStatus.ADMINISTRATOR: "⭐ Admin",
            ChatMemberStatus.MEMBER:        "👤 Uye",
            ChatMemberStatus.RESTRICTED:    "🔇 Kisitli",
            ChatMemberStatus.LEFT:          "🚪 Ayrilmis",
            ChatMemberStatus.BANNED:        "🔨 Banlı",
        }
        status = _S.get(member.status, member.status)
        warn_count, _ = await get_warnings(uid, chat.id)

        lines = [
            f"<b>👤 Kullanici Bilgisi</b>",
            f"Ad: {html.escape(user.first_name)}"
            + (f" {html.escape(user.last_name)}" if user.last_name else ""),
        ]
        if user.username:
            lines.append(f"@{user.username}")
        lines += [
            f"ID: <code>{user.id}</code>",
            f"Durum: {status}",
            f"Uyari: {warn_count}",
        ]
        if uid == OWNER_ID:
            lines.append("🔑 Bot Sahibi")
        await msg.reply_text("\n".join(lines), parse_mode="HTML")
    except Exception as e:
        await msg.reply_text(f"Bilgi alinamadi: {e}")


async def id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg  = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    lines = [
        "<b>🆔 ID Bilgisi</b>",
        f"Sen: <code>{user.id}</code>",
        f"Chat: <code>{chat.id}</code>",
    ]
    if msg.reply_to_message and msg.reply_to_message.from_user:
        r = msg.reply_to_message.from_user
        lines.append(f"Reply: <code>{r.id}</code>")
    await msg.reply_text("\n".join(lines), parse_mode="HTML")


async def rules_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rules = await get_rules(update.effective_chat.id)
    if not rules:
        return await update.effective_message.reply_text(
            "Henuz kural belirlenmemis. Admin: .setrules [metin]"
        )
    await update.effective_message.reply_text(
        f"📋 <b>{html.escape(update.effective_chat.title or 'Kurallar')}:</b>\n\n{rules}",
        parse_mode="HTML",
    )


async def setrules_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return await update.effective_message.reply_text("Admin olmalisin.")
    if not context.args:
        return await update.effective_message.reply_text(".setrules [kural metni]")
    await set_rules(update.effective_chat.id, " ".join(context.args))
    await update.effective_message.reply_text("✅ Kurallar ayarlandi!")


async def admins_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    try:
        members = await chat.get_administrators()
        lines   = [f"<b>⭐ {html.escape(chat.title or '')} Adminleri</b>"]
        for m in members:
            u    = m.user
            icon = "👑" if m.status == ChatMemberStatus.OWNER else "⭐"
            tag  = f" (@{u.username})" if u.username else ""
            bot  = " 🤖" if u.is_bot else ""
            lines.append(f"  {icon} {mention(u.id, u.first_name)}{tag}{bot}")
        await update.effective_message.reply_text("\n".join(lines), parse_mode="HTML")
    except Exception as e:
        await update.effective_message.reply_text(f"Alinamadi: {e}")


async def members_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    try:
        count = await context.bot.get_chat_member_count(chat.id)
        await update.effective_message.reply_text(
            f"👥 <b>{html.escape(chat.title or 'Grup')}</b>\nUye sayisi: <b>{count}</b>",
            parse_mode="HTML",
        )
    except Exception as e:
        await update.effective_message.reply_text(f"Alinamadi: {e}")


async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    try:
        count = await context.bot.get_chat_member_count(chat.id)
    except Exception:
        count = "?"

    top  = await get_top_users(chat.id, 10)
    me   = await context.bot.get_me()
    lines = [
        f"📊 <b>{html.escape(chat.title or 'Grup')} Istatistikleri</b>",
        f"Bot: @{me.username}",
        f"Uye Sayisi: {count}",
    ]
    if top:
        lines.append("\n<b>En Aktif Uyeler:</b>")
        for i, u in enumerate(top, 1):
            try:
                m    = await chat.get_member(u["user_id"])
                name = m.user.first_name
            except Exception:
                name = str(u["user_id"])
            lines.append(f"  {i}. {html.escape(name)}: {u['messages']} mesaj")
    await update.effective_message.reply_text("\n".join(lines), parse_mode="HTML")


async def chatinfo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    try:
        count   = await context.bot.get_chat_member_count(chat.id)
        admins  = await chat.get_administrators()
        n_adm   = len(admins)
    except Exception:
        count = n_adm = "?"
    lines = [
        "<b>ℹ️ Grup Bilgisi</b>",
        f"Ad: {html.escape(chat.title or '')}",
        f"ID: <code>{chat.id}</code>",
        f"Tür: {chat.type}",
        f"Uye: {count}",
        f"Admin: {n_adm}",
    ]
    invite = getattr(chat, "invite_link", None)
    if invite:
        lines.append(f"Davet: {invite}")
    if getattr(chat, "description", None):
        lines.append(f"Aciklama: {html.escape(chat.description[:200])}")
    await update.effective_message.reply_text("\n".join(lines), parse_mode="HTML")


# ═══ REGISTER ════════════════════════════════════════════════════════════════

def register_info_handlers(app):
    app.add_handler(CommandHandler("start", start_cmd))

    for cmd, handler in [
        ("help", help_cmd), ("yardim", help_cmd),
        ("info", info_cmd), ("kullanici", info_cmd),
        ("id", id_cmd),
        ("rules", rules_cmd), ("kurallar", rules_cmd),
        ("setrules", setrules_cmd),
        ("admins", admins_cmd), ("adminler", admins_cmd),
        ("members", members_cmd), ("uyeler", members_cmd),
        ("stats", stats_cmd),
        ("chatinfo", chatinfo_cmd),
    ]:
        app.add_handler(CommandHandler(cmd, handler))
        app.add_handler(MessageHandler(filters.TEXT & dot_filter(cmd), handler))

    app.add_handler(CallbackQueryHandler(help_callback, pattern=r"^(helpmain|helpcat_|infostats|inforules)"))
