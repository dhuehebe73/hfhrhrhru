"""
Info commands: info id stats chatinfo admins members rules setrules help
Different help for admin vs user.
"""
import html
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from telegram.constants import ChatMemberStatus

from utils import resolve_user, is_admin, mention, dot_filter, fmt_ago
from database import (
    get_rules, set_rules, get_top_users,
    register_chat, get_warnings,
)
from config import OWNER_ID

# ─── HELP ─────────────────────────────────────────────────────────────────────

USER_HELP = """
<b>Kullanici Komutlari</b>

• .help — Bu mesaj
• .rules — Grup kurallari
• .id — Chat/kullanici ID'si
• .info — Kullanici bilgisi
• .warns — Uyari durumu
• .report — Admini bilgilendir
• .afk [sebep] — AFK modu
• .tr [dil] — Mesaj cevir
• .play [sarki] — Sarki indir
• .video [url] — Video indir
• .calc [ifade] — Hesap makinesi
• .weather [sehir] — Hava durumu
• .dice — Zar at
• .flip — Para at
• .poll — Anket olustur
• .giveaway — Aktif cekilise katil
"""

ADMIN_HELP = """
<b>Admin Komutlari</b>

<b>Yasaklama:</b>
• .ban @user [sebep] — Banla
• .dban — Mesaj sil + banla
• .sban — Sessiz banla
• .unban @user — Bani kaldir
• .kick @user — At
• .dkick — Mesaj sil + at

<b>Susturma:</b>
• .mute @user [1h] [sebep] — Sustur
• .dmute — Mesaj sil + sustur
• .unmute @user — Sus kaldir

<b>Uyari:</b>
• .warn @user [sebep] — Uyard
• .dwarn — Mesaj sil + uyar
• .unwarn @user — Uyari kaldir
• .resetwarns @user — Sifirla
• .warns @user — Uyari goster
• .warnmode ban/kick/mute — Uyari modu
• .warnlimit 3 — Uyari limiti

<b>Mesaj:</b>
• .del — Mesaj sil
• .purge 10 / reply+.purge — Toplu sil
• .pin / .unpin / .unpinall — Sabitle

<b>Grup:</b>
• .lock / .unlock — Grupla/ac
• .slowmode [sn] — Yavas mod
• .antiflood on/off/[limit] — Flood koruması
• .promote @user — Admin yap
• .demote @user — Admin al
• .approve @user — Onayla
• .unapprove @user — Onay kaldir

<b>Filtreler:</b>
• .filter [kelime] — Kelime filtrele
• .unfilter [kelime] — Kaldir
• .filters — Listele
• .linkfilter — Link filtresini aç/kapat
• .stickerfilter — Sticker filtresi
• .mediafilter — Medya filtresi

<b>Karsilama:</b>
• .setwelcome [metin] — Karsilama mesaji
• .setgoodbye [metin] — Veda mesaji
• .welcome — Onizle
• .autoban on/off — Ayrilanları banla
• .captcha on/off — Captcha sistemi

<b>Notlar:</b>
• .save [isim] [icerik] — Not kaydet
• .get [isim] — Not getir
• .notes — Tum notlar
• .clear [isim] — Not sil
• #notismi — Not cagir

<b>Diger:</b>
• .setrules [metin] — Kural belirle
• .giveaway [sure] [kazanan] [odul] — Cekilis
• .gend — Cekilisi bitir
• .greroll — Yeni kazanan sec
"""

OWNER_HELP = """
<b>Sahip Komutlari</b>

• .broadcast [metin] — Tum gruplara yayin
• .pbroadcast [metin] — Yayin + sabitle
• .bc [metin] — .broadcast kisayolu
"""


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    # Register this chat
    await register_chat(chat.id, chat.type, chat.title or "")

    if chat.type == "private":
        await update.effective_message.reply_text(
            f"Merhaba {html.escape(user.first_name)}!\n\n"
            "Ben kapsamli bir grup yonetim botuyum.\n"
            "Grubuna ekle ve admin yap.\n\n"
            "/help — Komutlari gor",
            parse_mode="HTML",
        )
    else:
        await update.effective_message.reply_text(
            f"Merhaba! Komutlar icin /help yaz.", parse_mode="HTML"
        )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin = await is_admin(update, context)
    owner = update.effective_user.id == OWNER_ID

    if owner:
        text = USER_HELP + ADMIN_HELP + OWNER_HELP
    elif admin:
        text = USER_HELP + ADMIN_HELP
    else:
        text = USER_HELP

    await update.effective_message.reply_text(text, parse_mode="HTML")


# ─── INFO ─────────────────────────────────────────────────────────────────────

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

        _STATUS = {
            ChatMemberStatus.OWNER:         "👑 Kurucu",
            ChatMemberStatus.ADMINISTRATOR: "⭐ Admin",
            ChatMemberStatus.MEMBER:        "👤 Uye",
            ChatMemberStatus.RESTRICTED:    "🔇 Kisitli",
            ChatMemberStatus.LEFT:          "🚪 Ayrilmis",
            ChatMemberStatus.BANNED:        "🔨 Banlı",
        }
        status = _STATUS.get(member.status, member.status)

        warn_count, _ = await get_warnings(uid, chat.id)

        lines = [
            f"<b>Kullanici Bilgisi</b>",
            f"Ad: {html.escape(user.first_name)}"
            + (f" {html.escape(user.last_name)}" if user.last_name else ""),
        ]
        if user.username:
            lines.append(f"Kullanici adi: @{user.username}")
        lines += [
            f"ID: <code>{user.id}</code>",
            f"Durum: {status}",
            f"Uyarilar: {warn_count}",
        ]
        if user.language_code:
            lines.append(f"Dil: {user.language_code}")
        if user.is_bot:
            lines.append("Bot: Evet")

        await msg.reply_text("\n".join(lines), parse_mode="HTML")

    except Exception as e:
        await msg.reply_text(f"Bilgi alinamadi: {e}")


# ─── ID ───────────────────────────────────────────────────────────────────────

async def id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg  = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    lines = [
        f"<b>ID Bilgisi</b>",
        f"Kullanici ID: <code>{user.id}</code>",
        f"Chat ID: <code>{chat.id}</code>",
    ]
    if msg.reply_to_message and msg.reply_to_message.from_user:
        r = msg.reply_to_message.from_user
        lines.append(f"Cevaplanan kullanici: <code>{r.id}</code>")

    await msg.reply_text("\n".join(lines), parse_mode="HTML")


# ─── RULES ────────────────────────────────────────────────────────────────────

async def rules_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rules = await get_rules(update.effective_chat.id)
    if not rules:
        return await update.effective_message.reply_text("Henuz kural belirlenmemis.")
    await update.effective_message.reply_text(
        f"<b>📜 {html.escape(update.effective_chat.title or 'Kurallar')}:</b>\n\n{rules}",
        parse_mode="HTML",
    )


async def setrules_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return await update.effective_message.reply_text("Admin olmalisin.")
    if not context.args:
        return await update.effective_message.reply_text(".setrules [kural metni]")
    await set_rules(update.effective_chat.id, " ".join(context.args))
    await update.effective_message.reply_text("Kurallar ayarlandi!")


# ─── ADMINS ───────────────────────────────────────────────────────────────────

async def admins_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    try:
        members = await chat.get_administrators()
        lines = ["<b>Adminler:</b>"]
        for m in members:
            u    = m.user
            name = html.escape(u.first_name)
            tag  = f" (@{u.username})" if u.username else ""
            bot  = " 🤖" if u.is_bot else ""
            role = "👑" if m.status == ChatMemberStatus.OWNER else "⭐"
            lines.append(f"  {role} {mention(u.id, name)}{tag}{bot}")
        await update.effective_message.reply_text("\n".join(lines), parse_mode="HTML")
    except Exception as e:
        await update.effective_message.reply_text(f"Adminler alinamadi: {e}")


# ─── MEMBERS / STATS ──────────────────────────────────────────────────────────

async def members_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    try:
        count = await context.bot.get_chat_member_count(chat.id)
        await update.effective_message.reply_text(
            f"👥 <b>{html.escape(chat.title or 'Bu grup')}</b>\nUye sayisi: <b>{count}</b>",
            parse_mode="HTML",
        )
    except Exception as e:
        await update.effective_message.reply_text(f"Alinmadi: {e}")


async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    try:
        count = await context.bot.get_chat_member_count(chat.id)
    except Exception:
        count = "?"

    top = await get_top_users(chat.id, 5)
    me  = await context.bot.get_me()

    lines = [
        f"<b>📊 {html.escape(chat.title or 'Grup')} İstatistikleri</b>",
        f"Bot: @{me.username}",
        f"Uye Sayisi: {count}",
    ]
    if top:
        lines.append("\n<b>En Aktif Uyeler:</b>")
        for i, u in enumerate(top, 1):
            try:
                member = await chat.get_member(u["user_id"])
                name   = member.user.first_name
            except Exception:
                name = str(u["user_id"])
            lines.append(f"  {i}. {html.escape(name)}: {u['messages']} mesaj")

    await update.effective_message.reply_text("\n".join(lines), parse_mode="HTML")


# ─── CHATINFO ─────────────────────────────────────────────────────────────────

async def chatinfo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    try:
        count   = await context.bot.get_chat_member_count(chat.id)
        admins  = await chat.get_administrators()
        n_admins = len(admins)
    except Exception:
        count    = "?"
        n_admins = "?"

    invite = getattr(chat, "invite_link", None) or ""
    lines = [
        f"<b>Grup Bilgisi</b>",
        f"Ad: {html.escape(chat.title or '')}",
        f"ID: <code>{chat.id}</code>",
        f"Tür: {chat.type}",
        f"Uye: {count}",
        f"Admin: {n_admins}",
    ]
    if invite:
        lines.append(f"Davet: {invite}")
    if chat.description:
        lines.append(f"Aciklama: {html.escape(chat.description[:200])}")

    await update.effective_message.reply_text("\n".join(lines), parse_mode="HTML")


# ─── REGISTER ─────────────────────────────────────────────────────────────────

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
