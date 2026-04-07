"""
Info commands: .info .id .rules .setrules .stats .report .start .help
"""
import html
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from telegram.constants import ChatMemberStatus

from utils import resolve_user, is_admin, mention_html
from database import get_rules, set_rules

import re as re_mod


def _dot_filter(cmd: str):
    return filters.Regex(rf"^[./!]{re_mod.escape(cmd)}(\s|$)")


# ─── START / HELP ─────────────────────────────────────────────────────────────

HELP_TEXT = """
<b>KOMUT LISTESI</b>

<b>Moderasyon:</b>
• .ban [kullanici] [sebep] — Banla
• .unban [kullanici] — Bani kaldir
• .kick [kullanici] [sebep] — At
• .mute [kullanici] [sure] [sebep] — Sustur (ornek: .mute @user 1h)
• .unmute [kullanici] — Susu kaldir
• .warn [kullanici] [sebep] — Uyard (3 uyaridansonra otomatik ban)
• .unwarn [kullanici] — 1 uyari kaldir
• .resetwarns [kullanici] — Tum uyarilari sifirla
• .warns [kullanici] — Uyari durumunu goster
• .purge [sayi] — Son N mesaji sil
• .del — Reply atilan mesaji sil
• .lock — Grubu kilitle (sadece adminler yazabilir)
• .unlock — Grubu ac

<b>Karsilama:</b>
• .setwelcome [metin] — Karsilama mesaji ayarla
• .setgoodbye [metin] — Veda mesaji ayarla
• .welcome — Karsilama mesajini onizle
• .autoban on/off — Gruptan ayrilanlari otomatik banla

<b>Filtreler:</b>
• .filter [kelime] — Kelime filtresi ekle
• .unfilter [kelime] — Filtre kaldir
• .filters — Aktif filtreleri listele

<b>Admin:</b>
• .promote [kullanici] — Admin yap
• .demote [kullanici] — Adminligi al
• .pin — Reply atilan mesaji sabitle
• .unpin — Sabit mesaji kaldir

<b>Ceviri:</b>
• .tr [dil] — Reply atilan mesaji cevir
• .tr en [metin] — Metni Ingilizceye cevir
• Dil kodlari: tr, en, de, fr, es, ar, ru, ja, zh...

<b>Bilgi:</b>
• .info [kullanici] — Kullanici bilgisi
• .id — Chat/kullanici ID'sini goster
• .rules — Kuralları goster
• .setrules [metin] — Kuralları ayarla
• .stats — Bot istatistikleri
• .report — Admini bilgilendir

<b>Degiskenler (karsilama/veda):</b>
  {name} — kullanici adi
  {chat} — grup adi
  {count} — uye sayisi
"""


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "Merhaba! Ben Rose'dan daha guclu bir grup yonetici botuyum.\n"
        "Komutlari gormek icin .help yaz.",
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(HELP_TEXT, parse_mode="HTML")


# ─── INFO ─────────────────────────────────────────────────────────────────────

async def info_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat

    uid, name, _ = await resolve_user(update, context)
    if not uid:
        uid = update.effective_user.id
        name = update.effective_user.first_name

    try:
        member = await chat.get_member(uid)
        user = member.user

        status_map = {
            ChatMemberStatus.OWNER: "Kurucu",
            ChatMemberStatus.ADMINISTRATOR: "Admin",
            ChatMemberStatus.MEMBER: "Uye",
            ChatMemberStatus.RESTRICTED: "Kisitli",
            ChatMemberStatus.LEFT: "Ayrilmis",
            ChatMemberStatus.BANNED: "Banlı",
        }
        status = status_map.get(member.status, member.status)

        username_line = f"\nKullanici adi: @{user.username}" if user.username else ""
        lang_line = f"\nDil: {user.language_code}" if user.language_code else ""
        bot_line = "\nBot: Evet" if user.is_bot else ""

        text = (
            f"<b>Kullanici Bilgisi</b>\n"
            f"Ad: {html.escape(user.first_name)}"
            f"{(' ' + html.escape(user.last_name)) if user.last_name else ''}"
            f"{username_line}\n"
            f"ID: <code>{user.id}</code>\n"
            f"Durum: {status}"
            f"{lang_line}"
            f"{bot_line}"
        )
        await msg.reply_text(text, parse_mode="HTML")
    except Exception as e:
        await msg.reply_text(f"Bilgi alinamadi: {e}")


# ─── ID ───────────────────────────────────────────────────────────────────────

async def id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    text = f"<b>ID Bilgisi</b>\nKullanici ID: <code>{user.id}</code>\nChat ID: <code>{chat.id}</code>"

    if msg.reply_to_message:
        reply_user = msg.reply_to_message.from_user
        text += f"\nCevaplanan kullanici ID: <code>{reply_user.id}</code>"

    await msg.reply_text(text, parse_mode="HTML")


# ─── RULES ────────────────────────────────────────────────────────────────────

async def rules_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    rules_text = await get_rules(update.effective_chat.id)

    if not rules_text:
        await msg.reply_text("Bu grupta henuz kural belirlenmemis.")
        return

    await msg.reply_text(
        f"<b>{html.escape(update.effective_chat.title or 'Grup')} Kurallari:</b>\n\n{rules_text}",
        parse_mode="HTML",
    )


async def setrules_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not await is_admin(update, context):
        await msg.reply_text("Bu komutu kullanmak icin admin olmalisin.")
        return

    if not context.args:
        await msg.reply_text("Kuralları gir: .setrules [kural metni]")
        return

    rules_text = " ".join(context.args)
    await set_rules(update.effective_chat.id, rules_text)
    await msg.reply_text("Kurallar ayarlandi!")


# ─── STATS ────────────────────────────────────────────────────────────────────

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat

    try:
        count = await context.bot.get_chat_member_count(chat.id)
    except Exception:
        count = "?"

    me = await context.bot.get_me()
    await msg.reply_text(
        f"<b>Bot Istatistikleri</b>\n"
        f"Bot: @{me.username}\n"
        f"Grup: {html.escape(chat.title or '')}\n"
        f"Uye sayisi: {count}",
        parse_mode="HTML",
    )


# ─── REPORT ───────────────────────────────────────────────────────────────────

async def report_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    reporter = update.effective_user

    if not msg.reply_to_message:
        await msg.reply_text("Kimi sikayet ediyorsun? Mesajina reply at.")
        return

    reported_user = msg.reply_to_message.from_user
    reason = " ".join(context.args) if context.args else "Sebep belirtilmedi"

    # Get admins
    try:
        admins = await chat.get_administrators()
        admin_mentions = " ".join(
            f"@{a.user.username}" if a.user.username else mention_html(a.user.id, a.user.first_name)
            for a in admins
            if not a.user.is_bot
        )
    except Exception:
        admin_mentions = "Adminler"

    await msg.reply_text(
        f"Sikayet bildirildi!\n\n"
        f"Sikayet eden: {mention_html(reporter.id, reporter.first_name)}\n"
        f"Sikayet edilen: {mention_html(reported_user.id, reported_user.first_name)}\n"
        f"Sebep: {html.escape(reason)}\n\n"
        f"Adminler: {admin_mentions}",
        parse_mode="HTML",
    )


def register_info_handlers(app):
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))

    for cmd, handler in [
        ("help", help_cmd),
        ("info", info_cmd),
        ("id", id_cmd),
        ("rules", rules_cmd),
        ("setrules", setrules_cmd),
        ("stats", stats_cmd),
        ("report", report_cmd),
    ]:
        app.add_handler(CommandHandler(cmd, handler))
        app.add_handler(
            MessageHandler(filters.TEXT & _dot_filter(cmd), handler)
        )
