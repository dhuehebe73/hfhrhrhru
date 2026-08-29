"""
Anti-spam ve anti-raid koruması.

Flood tracker: bellekte {chat_id: {user_id: [timestamps]}}
Raid tracker:  bellekte {chat_id: [join_timestamps]}
Raid modu:     bellekte {chat_id: expires_ts}
Flood aksiyon: bellekte {chat_id: action_str}  (kalıcı değil)
"""

import time
from collections import defaultdict
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
from database import get_settings, set_setting, is_approved
from utils import require_admin, is_admin, MUTE_PERMS, dcmd, get_args, mention, later


# ── In-memory state ───────────────────────────────────────────────────────────

# {chat_id: {user_id: [timestamps]}}
_flood: dict[int, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))

# {chat_id: [join_timestamps]}
_raid_joins: dict[int, list[float]] = defaultdict(list)

# {chat_id: expires_ts}  — eksik ya da 0 ise raid modu kapalı
_raid_mode: dict[int, float] = {}

# {chat_id: action_str}  — "warn" | "mute" | "kick" | "ban"
_flood_action: dict[int, str] = {}

_FLOOD_WINDOW  = 5.0    # saniye
_RAID_WINDOW   = 30.0   # saniye
_RAID_DURATION = 300.0  # 5 dakika


# ── Yardımcı fonksiyonlar ─────────────────────────────────────────────────────

def _raid_active(chat_id: int) -> bool:
    """Raid modunun şu an aktif olup olmadığını kontrol eder."""
    expires = _raid_mode.get(chat_id, 0)
    if expires and time.time() < expires:
        return True
    # Süresi dolmuşsa temizle
    if chat_id in _raid_mode:
        del _raid_mode[chat_id]
    return False


async def _apply_flood_action(ctx: ContextTypes.DEFAULT_TYPE,
                               chat, uid: int, name: str,
                               action: str, now: float):
    """Flood cezasını uygular ve gruba bildirim gönderir."""
    try:
        if action == "mute":
            await ctx.bot.restrict_chat_member(
                chat.id, uid, MUTE_PERMS,
                until_date=int(now) + 300)
            text = f"⚠️ {mention(uid, name)} flood yaptı, 5 dakika susturuldu."
        elif action == "kick":
            await ctx.bot.ban_chat_member(chat.id, uid)
            await ctx.bot.unban_chat_member(chat.id, uid)
            text = f"⚠️ {mention(uid, name)} flood yaptı ve gruptan atıldı."
        elif action == "ban":
            await ctx.bot.ban_chat_member(chat.id, uid)
            text = f"⚠️ {mention(uid, name)} flood yaptı ve banlandı."
        else:  # warn
            text = (f"⚠️ {mention(uid, name)} çok hızlı mesaj gönderiyor! "
                    f"Lütfen yavaşla.")

        m = await ctx.bot.send_message(chat.id, text, parse_mode="HTML")
        later(10, m.delete())
    except Exception:
        pass


# ── Herkese açık API (welcome.py tarafından çağrılır) ─────────────────────────

async def check_raid(ctx: ContextTypes.DEFAULT_TYPE,
                     chat_id: int, user_id: int, chat) -> bool:
    """
    welcome.py'nin _on_member_update fonksiyonundan yeni üye katıldığında çağrılır.

    Raid koruması aktifse ve raid tetiklendiyse/devam ediyorsa kullanıcıyı
    susturur veya banlar.  True döndürürse çağıran taraf karşılama mesajını
    atlayabilir.
    """
    s = await get_settings(chat_id)
    if not s.get("anti_raid", False):
        return False

    now = time.time()

    # Raid modu zaten aktifse yeni katılanı direkt cezalandır
    if _raid_active(chat_id):
        action = s.get("anti_raid_action", "mute")
        try:
            if action == "ban":
                await ctx.bot.ban_chat_member(chat_id, user_id)
            else:
                await ctx.bot.restrict_chat_member(chat_id, user_id, MUTE_PERMS)
        except Exception:
            pass
        return True

    # Katılım zamanını kaydet ve eski kayıtları temizle
    joins = _raid_joins[chat_id]
    joins.append(now)
    _raid_joins[chat_id] = [t for t in joins if now - t < _RAID_WINDOW]

    limit = s.get("anti_raid_limit", 10)
    if len(_raid_joins[chat_id]) >= limit:
        # Raid modunu aktifleştir
        _raid_mode[chat_id] = now + _RAID_DURATION
        _raid_joins[chat_id] = []

        action = s.get("anti_raid_action", "mute")
        # Bu kullanıcıyı da cezalandır
        try:
            if action == "ban":
                await ctx.bot.ban_chat_member(chat_id, user_id)
            else:
                await ctx.bot.restrict_chat_member(chat_id, user_id, MUTE_PERMS)
        except Exception:
            pass

        # Admin uyarısı gönder
        try:
            await ctx.bot.send_message(
                chat_id,
                f"⚠️ <b>RAID TESPİT EDİLDİ!</b> {limit} kişi katıldı.\n"
                f"Yeni üyeler otomatik susturuldu. "
                f"Raid modu <b>5 dakika</b> sürecek.",
                parse_mode="HTML",
            )
        except Exception:
            pass

        # 5 dakika sonra raid modunun sona erdiğini bildir
        later(_RAID_DURATION, _raid_expire_notice(ctx, chat_id))
        return True

    return False


async def _raid_expire_notice(ctx: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Raid modu otomatik sona erdiğinde gruba bildirim gönderir."""
    # _raid_active çağrısı süresi dolmuşsa _raid_mode'u temizler
    if not _raid_active(chat_id):
        try:
            await ctx.bot.send_message(
                chat_id,
                "✅ <b>Raid modu sona erdi.</b> Normal üye kabulü devam ediyor.",
                parse_mode="HTML",
            )
        except Exception:
            pass


# ── Flood mesaj handler'ı ─────────────────────────────────────────────────────

async def _flood_check(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Grup mesajlarını izler; flood tespitinde aksiyon uygular (group=6)."""
    msg = update.effective_message
    if not msg or not msg.from_user:
        return
    chat = update.effective_chat
    if not chat or chat.type == "private":
        return

    uid = msg.from_user.id

    # Onaylı kullanıcılar ve adminler muaf
    if await is_approved(uid, chat.id):
        return
    if await is_admin(update, ctx):
        return

    s = await get_settings(chat.id)
    if not s.get("anti_flood", True):
        return

    limit = int(s.get("flood_limit", 5))
    now   = time.time()

    # Zaman damgalarını güncelle
    msgs = _flood[chat.id][uid]
    msgs.append(now)
    _flood[chat.id][uid] = [t for t in msgs if now - t < _FLOOD_WINDOW]

    if len(_flood[chat.id][uid]) >= limit:
        # Sayacı sıfırla
        _flood[chat.id][uid] = []
        # Aksiyon: bellekte varsa kullan, yoksa db warn_action'a bak, son çare "mute"
        action = _flood_action.get(chat.id) or s.get("warn_action", "mute")
        await _apply_flood_action(ctx, chat, uid, msg.from_user.first_name, action, now)


# ── Komutlar ──────────────────────────────────────────────────────────────────

async def antiflood_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    /antiflood on|off [limit]
    Flood korumasını açar/kapatır ve isteğe bağlı limit belirler.
    """
    if not await require_admin(update, ctx):
        return
    args = get_args(update, ctx)
    cid  = update.effective_chat.id
    s    = await get_settings(cid)

    if not args:
        state  = "açık ✅" if s.get("anti_flood", True) else "kapalı ❌"
        limit  = s.get("flood_limit", 5)
        action = _flood_action.get(cid) or s.get("warn_action", "mute")
        await update.effective_message.reply_text(
            f"🌊 <b>Anti-Flood Durumu</b>\n\n"
            f"Durum: {state}\n"
            f"Limit: <b>{limit}</b> mesaj / 5 saniye\n"
            f"Aksiyon: <code>{action}</code>\n\n"
            f"Değiştirmek için: <code>/antiflood on|off [limit]</code>",
            parse_mode="HTML",
        )
        return

    sub = args[0].lower()
    if sub in ("on", "ac", "aç", "1", "true"):
        await set_setting(cid, "anti_flood", 1)
        reply = "✅ Anti-flood koruması <b>açıldı</b>."
        if len(args) > 1 and args[1].isdigit() and int(args[1]) > 0:
            new_limit = int(args[1])
            await set_setting(cid, "flood_limit", new_limit)
            reply += f" Limit: <b>{new_limit}</b> mesaj / 5sn"
        await update.effective_message.reply_text(reply, parse_mode="HTML")
    elif sub in ("off", "kapat", "0", "false"):
        await set_setting(cid, "anti_flood", 0)
        await update.effective_message.reply_text("❌ Anti-flood koruması <b>kapatıldı</b>.",
                                                   parse_mode="HTML")
    elif sub.isdigit() and int(sub) > 0:
        await set_setting(cid, "flood_limit", int(sub))
        await update.effective_message.reply_text(
            f"✅ Flood limiti güncellendi: <b>{sub}</b> mesaj / 5sn",
            parse_mode="HTML",
        )
    else:
        await update.effective_message.reply_text(
            "❓ Kullanım: <code>/antiflood on|off [limit]</code>",
            parse_mode="HTML",
        )


async def antiraid_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    /antiraid on|off
    Raid korumasını açar/kapatır.
    """
    if not await require_admin(update, ctx):
        return
    args = get_args(update, ctx)
    cid  = update.effective_chat.id
    s    = await get_settings(cid)

    if not args:
        state  = "açık ✅" if s.get("anti_raid", False) else "kapalı ❌"
        limit  = s.get("anti_raid_limit", 10)
        action = s.get("anti_raid_action", "mute")
        active = "🔴 Aktif" if _raid_active(cid) else "🟢 Pasif"
        await update.effective_message.reply_text(
            f"🛡 <b>Anti-Raid Durumu</b>\n\n"
            f"Koruma: {state}\n"
            f"Limit: <b>{limit}</b> kişi / 30 saniye\n"
            f"Aksiyon: <code>{action}</code>\n"
            f"Raid modu şu an: {active}\n\n"
            f"Değiştirmek için: <code>/antiraid on|off</code>",
            parse_mode="HTML",
        )
        return

    sub = args[0].lower()
    if sub in ("on", "ac", "aç", "1", "true"):
        await set_setting(cid, "anti_raid", 1)
        await update.effective_message.reply_text(
            "✅ Anti-raid koruması <b>açıldı</b>.", parse_mode="HTML")
    elif sub in ("off", "kapat", "0", "false"):
        await set_setting(cid, "anti_raid", 0)
        await update.effective_message.reply_text(
            "❌ Anti-raid koruması <b>kapatıldı</b>.", parse_mode="HTML")
    else:
        await update.effective_message.reply_text(
            "❓ Kullanım: <code>/antiraid on|off</code>", parse_mode="HTML")


async def raidmode_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    /raidmode
    Raid modunu manuel olarak 5 dakika aktif eder.
    """
    if not await require_admin(update, ctx):
        return
    cid = update.effective_chat.id

    if _raid_active(cid):
        remaining = int(_raid_mode[cid] - time.time())
        await update.effective_message.reply_text(
            f"⚠️ Raid modu zaten aktif! Kalan süre: <b>{remaining} saniye</b>",
            parse_mode="HTML",
        )
        return

    _raid_mode[cid] = time.time() + _RAID_DURATION
    await update.effective_message.reply_text(
        "🚨 <b>Raid modu manuel olarak aktif edildi!</b>\n"
        "Yeni katılan üyeler <b>5 dakika</b> boyunca kısıtlanacak.",
        parse_mode="HTML",
    )
    later(_RAID_DURATION, _raid_expire_notice(ctx, cid))


async def floodmode_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    /floodmode warn|mute|kick|ban
    Flood ceza aksiyonunu ayarlar (oturum boyunca geçerli).
    """
    if not await require_admin(update, ctx):
        return
    args  = get_args(update, ctx)
    cid   = update.effective_chat.id
    valid = ("warn", "mute", "kick", "ban")

    if not args or args[0].lower() not in valid:
        s       = await get_settings(cid)
        current = _flood_action.get(cid) or s.get("warn_action", "mute")
        await update.effective_message.reply_text(
            f"ℹ️ Mevcut flood aksiyonu: <code>{current}</code>\n\n"
            f"Değiştirmek için: <code>/floodmode warn|mute|kick|ban</code>",
            parse_mode="HTML",
        )
        return

    action = args[0].lower()
    _flood_action[cid] = action
    labels = {
        "warn": "uyarı ⚠️",
        "mute": "susturma 🔇",
        "kick": "atma 👢",
        "ban":  "banlama 🚫",
    }
    await update.effective_message.reply_text(
        f"✅ Flood aksiyonu güncellendi: <b>{labels[action]}</b>",
        parse_mode="HTML",
    )


# ── Kayıt ─────────────────────────────────────────────────────────────────────

def register(app):
    # Flood handler: tüm grup mesajları, grup önceliği 6
    app.add_handler(
        MessageHandler(filters.ChatType.GROUPS & filters.ALL, _flood_check),
        group=6,
    )
    # Komutlar
    for cmd, handler in [
        ("antiflood", antiflood_cmd),
        ("antiraid",  antiraid_cmd),
        ("raidmode",  raidmode_cmd),
        ("floodmode", floodmode_cmd),
    ]:
        app.add_handler(MessageHandler(dcmd(cmd), handler), group=10)
