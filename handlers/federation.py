"""
Federation sistemi - Rose bot tarzı çoklu grup birleştirme.
Bir federasyona bağlı tüm gruplarda geçerli fban sistemi.
"""

import html
import uuid
import aiosqlite
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler
from telegram.constants import ChatType

from database import (
    create_federation, get_federation, get_user_federation, get_chat_federation,
    join_federation, leave_federation,
    fban_user, unfban_user, get_fban, get_fban_list,
    get_fed_chats, get_fed_admins,
    fpromote, fdemote, is_fed_admin,
)
from utils import resolve_user, require_admin, mention, dcmd, get_args
from config import DB_PATH


# ── Helpers ────────────────────────────────────────────────────────────────────

def _new_fed_id() -> str:
    return str(uuid.uuid4())[:8]


async def _get_feds_where_admin(user_id: int) -> list[dict]:
    """Return all federations where user_id appears in fed_admins."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT f.fed_id, f.name, f.owner_id"
            " FROM federations f"
            " JOIN fed_admins fa ON fa.fed_id = f.fed_id"
            " WHERE fa.user_id=?",
            (user_id,)
        ) as c:
            return [
                {"fed_id": r[0], "name": r[1], "owner_id": r[2]}
                for r in await c.fetchall()
            ]


async def _fed_owner_check(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    Ensure caller owns a federation.
    Returns (fed, msg) on success, (None, None) on failure (reply already sent).
    """
    msg = update.effective_message
    user = update.effective_user
    fed = await get_user_federation(user.id)
    if not fed:
        await msg.reply_text(
            "❌ Sahip olduğunuz bir federasyon bulunamadı.",
            parse_mode="HTML")
        return None, None
    return fed, msg


async def _require_fed_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    Ensure the caller is the owner OR a fed admin of the current chat's federation.
    Returns (fed, msg) on success, (None, None) on failure.
    """
    msg = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    # Find federation: prefer chat's federation, fall back to user's own federation
    fed = None
    if chat and chat.type != ChatType.PRIVATE:
        fed = await get_chat_federation(chat.id)
    if not fed:
        # Allow owner/admin to act from DM using their own federation
        fed = await get_user_federation(user.id)

    if not fed:
        await msg.reply_text(
            "❌ Bu sohbet herhangi bir federasyona bağlı değil.",
            parse_mode="HTML")
        return None, None

    fed_id = fed["fed_id"]
    if user.id != fed["owner_id"] and not await is_fed_admin(fed_id, user.id):
        await msg.reply_text(
            "❌ Bu işlemi yapmak için federasyon yöneticisi olmalısınız.",
            parse_mode="HTML")
        return None, None

    return fed, msg


# ── /newfed ────────────────────────────────────────────────────────────────────

async def newfed_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if chat.type != ChatType.PRIVATE:
        await msg.reply_text(
            "❌ Federasyon yalnızca özel sohbette oluşturulabilir.",
            parse_mode="HTML")
        return

    args = get_args(update, ctx)
    if not args:
        await msg.reply_text(
            "❌ Kullanım: <code>/newfed &lt;federasyon adı&gt;</code>",
            parse_mode="HTML")
        return

    name = " ".join(args).strip()
    if len(name) > 64:
        await msg.reply_text(
            "❌ Federasyon adı en fazla 64 karakter olabilir.",
            parse_mode="HTML")
        return

    existing = await get_user_federation(user.id)
    if existing:
        await msg.reply_text(
            f"❌ Zaten <b>{html.escape(existing['name'])}</b> adlı bir federasyonunuz var.\n"
            f"Önce <code>/delfed</code> komutuyla silin.",
            parse_mode="HTML")
        return

    fed_id = _new_fed_id()
    await create_federation(fed_id, name, user.id)

    await msg.reply_text(
        f"🌐 <b>Federasyon oluşturuldu!</b>\n\n"
        f"📛 <b>Ad:</b> {html.escape(name)}\n"
        f"🆔 <b>Fed ID:</b> <code>{fed_id}</code>\n\n"
        f"Grubunuzu bağlamak için gruba gidip:\n"
        f"<code>/joinfed {fed_id}</code>\n"
        f"komutunu kullanın.",
        parse_mode="HTML")


# ── /delfed ────────────────────────────────────────────────────────────────────

async def delfed_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat

    if chat.type != ChatType.PRIVATE:
        await msg.reply_text(
            "❌ Bu komut yalnızca özel sohbette kullanılabilir.",
            parse_mode="HTML")
        return

    fed, _ = await _fed_owner_check(update, ctx)
    if not fed:
        return

    fed_id = fed["fed_id"]

    # Remove all chats from federation first
    chats = await get_fed_chats(fed_id)
    for cid in chats:
        try:
            await leave_federation(cid)
        except Exception:
            pass

    # Delete federation record, admins and bans
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM federations WHERE fed_id=?", (fed_id,))
        await db.execute("DELETE FROM fed_admins WHERE fed_id=?", (fed_id,))
        await db.execute("DELETE FROM fed_bans WHERE fed_id=?", (fed_id,))
        await db.commit()

    await msg.reply_text(
        f"🗑 <b>{html.escape(fed['name'])}</b> federasyonu silindi.\n"
        f"📤 {len(chats)} gruptan ayrıldı.",
        parse_mode="HTML")


# ── /joinfed ──────────────────────────────────────────────────────────────────

async def joinfed_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat

    if chat.type == ChatType.PRIVATE:
        await msg.reply_text(
            "❌ Bu komut yalnızca gruplarda kullanılabilir.",
            parse_mode="HTML")
        return

    if not await require_admin(update, ctx):
        return

    args = get_args(update, ctx)
    if not args:
        await msg.reply_text(
            "❌ Kullanım: <code>/joinfed &lt;fed_id&gt;</code>",
            parse_mode="HTML")
        return

    fed_id = args[0].strip()
    fed = await get_federation(fed_id)
    if not fed:
        await msg.reply_text(
            f"❌ <code>{html.escape(fed_id)}</code> ID'li federasyon bulunamadı.",
            parse_mode="HTML")
        return

    current = await get_chat_federation(chat.id)
    if current:
        await msg.reply_text(
            f"❌ Bu grup zaten <b>{html.escape(current['name'])}</b> federasyonuna bağlı.\n"
            f"Önce <code>/leavefed</code> komutuyla ayrılın.",
            parse_mode="HTML")
        return

    await join_federation(fed_id, chat.id)
    await msg.reply_text(
        f"✅ Bu grup <b>{html.escape(fed['name'])}</b> federasyonuna katıldı!\n"
        f"🆔 Fed ID: <code>{fed_id}</code>",
        parse_mode="HTML")


# ── /leavefed ─────────────────────────────────────────────────────────────────

async def leavefed_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat

    if chat.type == ChatType.PRIVATE:
        await msg.reply_text(
            "❌ Bu komut yalnızca gruplarda kullanılabilir.",
            parse_mode="HTML")
        return

    if not await require_admin(update, ctx):
        return

    current = await get_chat_federation(chat.id)
    if not current:
        await msg.reply_text(
            "❌ Bu grup herhangi bir federasyona bağlı değil.",
            parse_mode="HTML")
        return

    await leave_federation(chat.id)
    await msg.reply_text(
        f"✅ Bu grup <b>{html.escape(current['name'])}</b> federasyonundan ayrıldı.",
        parse_mode="HTML")


# ── /fpromote ─────────────────────────────────────────────────────────────────

async def fpromote_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    user = update.effective_user

    fed, _ = await _fed_owner_check(update, ctx)
    if not fed:
        return

    target_id, target_name, _ = await resolve_user(update, ctx)
    if not target_id:
        await msg.reply_text(
            "❌ Kullanıcı belirtin: mesajı yanıtlayın veya @kullanıcı / ID yazın.",
            parse_mode="HTML")
        return

    if target_id == user.id:
        await msg.reply_text("❌ Kendinizi yönetici yapamazsınız.", parse_mode="HTML")
        return

    if target_id == fed["owner_id"]:
        await msg.reply_text(
            "❌ Federasyon sahibi zaten en yüksek yetkiye sahip.",
            parse_mode="HTML")
        return

    if await is_fed_admin(fed["fed_id"], target_id):
        await msg.reply_text(
            f"ℹ️ {mention(target_id, target_name)} zaten federasyon yöneticisi.",
            parse_mode="HTML")
        return

    await fpromote(fed["fed_id"], target_id)
    await msg.reply_text(
        f"✅ {mention(target_id, target_name)} <b>{html.escape(fed['name'])}</b> "
        f"federasyonuna yönetici olarak eklendi.",
        parse_mode="HTML")


# ── /fdemote ──────────────────────────────────────────────────────────────────

async def fdemote_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message

    fed, _ = await _fed_owner_check(update, ctx)
    if not fed:
        return

    target_id, target_name, _ = await resolve_user(update, ctx)
    if not target_id:
        await msg.reply_text(
            "❌ Kullanıcı belirtin: mesajı yanıtlayın veya @kullanıcı / ID yazın.",
            parse_mode="HTML")
        return

    if not await is_fed_admin(fed["fed_id"], target_id):
        await msg.reply_text(
            f"ℹ️ {mention(target_id, target_name)} federasyon yöneticisi değil.",
            parse_mode="HTML")
        return

    await fdemote(fed["fed_id"], target_id)
    await msg.reply_text(
        f"✅ {mention(target_id, target_name)} <b>{html.escape(fed['name'])}</b> "
        f"federasyonundan yöneticilikten alındı.",
        parse_mode="HTML")


# ── /fban ─────────────────────────────────────────────────────────────────────

async def fban_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    user = update.effective_user

    fed, _ = await _require_fed_admin(update, ctx)
    if not fed:
        return

    target_id, target_name, reason = await resolve_user(update, ctx)
    if not target_id:
        await msg.reply_text(
            "❌ Kullanıcı belirtin: mesajı yanıtlayın veya @kullanıcı / ID yazın.",
            parse_mode="HTML")
        return

    if target_id == user.id:
        await msg.reply_text("❌ Kendinizi fban edemezsiniz.", parse_mode="HTML")
        return

    if target_id == fed["owner_id"]:
        await msg.reply_text("❌ Federasyon sahibi fban edilemez.", parse_mode="HTML")
        return

    try:
        me = await ctx.bot.get_me()
        if target_id == me.id:
            await msg.reply_text("❌ Beni fban edemezsiniz.", parse_mode="HTML")
            return
    except Exception:
        pass

    fed_id = fed["fed_id"]

    existing = await get_fban(fed_id, target_id)
    if existing:
        old_reason = html.escape(existing.get("reason") or "(yok)")
        await msg.reply_text(
            f"ℹ️ {mention(target_id, target_name)} zaten bu federasyonda banlı.\n"
            f"📝 Mevcut sebep: {old_reason}",
            parse_mode="HTML")
        return

    await fban_user(fed_id, target_id, reason or "", user.id)

    fed_chats = await get_fed_chats(fed_id)
    banned_count = 0
    failed_count = 0

    progress_msg = await msg.reply_text(
        f"⏳ <b>{html.escape(fed['name'])}</b> federasyonundaki "
        f"{len(fed_chats)} gruptan banlanıyor...",
        parse_mode="HTML")

    for cid in fed_chats:
        try:
            await ctx.bot.ban_chat_member(cid, target_id)
            banned_count += 1
        except Exception:
            failed_count += 1

    reason_text = f"\n📝 <b>Sebep:</b> {html.escape(reason)}" if reason else ""
    result_text = (
        f"🔨 <b>Federasyon Banı</b>\n\n"
        f"👤 <b>Kullanıcı:</b> {mention(target_id, target_name)}\n"
        f"🌐 <b>Federasyon:</b> {html.escape(fed['name'])}"
        f"{reason_text}\n\n"
        f"✅ {banned_count} gruptan banlandı."
        + (f"\n⚠️ {failed_count} grupta başarısız oldu." if failed_count else "")
    )

    try:
        await progress_msg.edit_text(result_text, parse_mode="HTML")
    except Exception:
        await msg.reply_text(result_text, parse_mode="HTML")


# ── /unfban ───────────────────────────────────────────────────────────────────

async def unfban_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message

    fed, _ = await _require_fed_admin(update, ctx)
    if not fed:
        return

    target_id, target_name, _ = await resolve_user(update, ctx)
    if not target_id:
        await msg.reply_text(
            "❌ Kullanıcı belirtin: mesajı yanıtlayın veya @kullanıcı / ID yazın.",
            parse_mode="HTML")
        return

    fed_id = fed["fed_id"]

    existing = await get_fban(fed_id, target_id)
    if not existing:
        await msg.reply_text(
            f"ℹ️ {mention(target_id, target_name)} bu federasyonda banlı değil.",
            parse_mode="HTML")
        return

    await unfban_user(fed_id, target_id)

    fed_chats = await get_fed_chats(fed_id)
    unbanned_count = 0
    failed_count = 0

    progress_msg = await msg.reply_text(
        f"⏳ <b>{html.escape(fed['name'])}</b> federasyonundaki "
        f"{len(fed_chats)} gruptan ban kaldırılıyor...",
        parse_mode="HTML")

    for cid in fed_chats:
        try:
            await ctx.bot.unban_chat_member(cid, target_id, only_if_banned=True)
            unbanned_count += 1
        except Exception:
            failed_count += 1

    result_text = (
        f"✅ <b>Federasyon Banı Kaldırıldı</b>\n\n"
        f"👤 <b>Kullanıcı:</b> {mention(target_id, target_name)}\n"
        f"🌐 <b>Federasyon:</b> {html.escape(fed['name'])}\n\n"
        f"✅ {unbanned_count} gruptan ban kaldırıldı."
        + (f"\n⚠️ {failed_count} grupta başarısız oldu." if failed_count else "")
    )

    try:
        await progress_msg.edit_text(result_text, parse_mode="HTML")
    except Exception:
        await msg.reply_text(result_text, parse_mode="HTML")


# ── /fedinfo ──────────────────────────────────────────────────────────────────

async def fedinfo_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    args = get_args(update, ctx)

    fed = None
    if args:
        fed = await get_federation(args[0].strip())
        if not fed:
            await msg.reply_text(
                f"❌ <code>{html.escape(args[0])}</code> ID'li federasyon bulunamadı.",
                parse_mode="HTML")
            return
    elif chat.type != ChatType.PRIVATE:
        fed = await get_chat_federation(chat.id)
        if not fed:
            await msg.reply_text(
                "❌ Bu grup herhangi bir federasyona bağlı değil.",
                parse_mode="HTML")
            return
    else:
        # In DM: try owned federation first, then fed admin membership
        fed = await get_user_federation(update.effective_user.id)
        if not fed:
            admin_feds = await _get_feds_where_admin(update.effective_user.id)
            if admin_feds:
                fed = admin_feds[0]
        if not fed:
            await msg.reply_text(
                "❌ Federasyon bulunamadı. Bir fed_id belirtin:\n"
                "<code>/fedinfo &lt;fed_id&gt;</code>",
                parse_mode="HTML")
            return

    fed_id = fed["fed_id"]
    chats = await get_fed_chats(fed_id)
    admins = await get_fed_admins(fed_id)
    bans = await get_fban_list(fed_id)

    try:
        owner_chat = await ctx.bot.get_chat(fed["owner_id"])
        owner_name = owner_chat.first_name or str(fed["owner_id"])
    except Exception:
        owner_name = str(fed["owner_id"])

    await msg.reply_text(
        f"🌐 <b>Federasyon Bilgisi</b>\n\n"
        f"📛 <b>Ad:</b> {html.escape(fed['name'])}\n"
        f"🆔 <b>Fed ID:</b> <code>{fed_id}</code>\n"
        f"👑 <b>Sahip:</b> {mention(fed['owner_id'], owner_name)}\n"
        f"👥 <b>Grup sayısı:</b> {len(chats)}\n"
        f"🛡 <b>Yönetici sayısı:</b> {len(admins)}\n"
        f"🔨 <b>Banlı kullanıcı:</b> {len(bans)}",
        parse_mode="HTML")


# ── /chatfed ──────────────────────────────────────────────────────────────────

async def chatfed_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat

    if chat.type == ChatType.PRIVATE:
        await msg.reply_text(
            "❌ Bu komut yalnızca gruplarda kullanılabilir.",
            parse_mode="HTML")
        return

    fed = await get_chat_federation(chat.id)
    if not fed:
        await msg.reply_text(
            "ℹ️ Bu grup herhangi bir federasyona bağlı değil.",
            parse_mode="HTML")
        return

    fed_id = fed["fed_id"]
    chats = await get_fed_chats(fed_id)
    bans = await get_fban_list(fed_id)

    try:
        owner_chat = await ctx.bot.get_chat(fed["owner_id"])
        owner_name = owner_chat.first_name or str(fed["owner_id"])
    except Exception:
        owner_name = str(fed["owner_id"])

    await msg.reply_text(
        f"🌐 Bu grup <b>{html.escape(fed['name'])}</b> federasyonuna bağlı.\n\n"
        f"🆔 <b>Fed ID:</b> <code>{fed_id}</code>\n"
        f"👑 <b>Sahip:</b> {mention(fed['owner_id'], owner_name)}\n"
        f"👥 <b>Federasyondaki grup sayısı:</b> {len(chats)}\n"
        f"🔨 <b>Banlı kullanıcı:</b> {len(bans)}",
        parse_mode="HTML")


# ── /fbanlist ─────────────────────────────────────────────────────────────────

async def fbanlist_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat

    fed = None
    if chat.type != ChatType.PRIVATE:
        fed = await get_chat_federation(chat.id)
    if not fed:
        fed = await get_user_federation(update.effective_user.id)

    if not fed:
        await msg.reply_text(
            "❌ Bu sohbet herhangi bir federasyona bağlı değil.",
            parse_mode="HTML")
        return

    fed_id = fed["fed_id"]
    bans = await get_fban_list(fed_id)

    if not bans:
        await msg.reply_text(
            f"✅ <b>{html.escape(fed['name'])}</b> federasyonunda banlı kullanıcı yok.",
            parse_mode="HTML")
        return

    lines = [f"🔨 <b>{html.escape(fed['name'])} — Fban Listesi</b> ({len(bans)} kullanıcı)\n"]
    for entry in bans[:50]:
        uid = entry["user_id"]
        reason = html.escape(entry.get("reason") or "(sebep yok)")
        lines.append(f"• <code>{uid}</code> — {reason}")

    if len(bans) > 50:
        lines.append(f"\n<i>...ve {len(bans) - 50} kullanıcı daha.</i>")

    await msg.reply_text("\n".join(lines), parse_mode="HTML")


# ── /myfeds ───────────────────────────────────────────────────────────────────

async def myfeds_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if chat.type != ChatType.PRIVATE:
        await msg.reply_text(
            "❌ Bu komut yalnızca özel sohbette kullanılabilir.",
            parse_mode="HTML")
        return

    lines = []

    # Federations owned by user
    owned = await get_user_federation(user.id)
    if owned:
        fed_id = owned["fed_id"]
        chats = await get_fed_chats(fed_id)
        bans = await get_fban_list(fed_id)
        lines.append(
            f"👑 <b>{html.escape(owned['name'])}</b> <i>(Sahip)</i>\n"
            f"   🆔 <code>{fed_id}</code>\n"
            f"   👥 {len(chats)} grup · 🔨 {len(bans)} ban")

    # Federations where user is an admin
    admin_feds = await _get_feds_where_admin(user.id)
    for fed in admin_feds:
        fed_id = fed["fed_id"]
        chats = await get_fed_chats(fed_id)
        bans = await get_fban_list(fed_id)
        lines.append(
            f"🛡 <b>{html.escape(fed['name'])}</b> <i>(Yönetici)</i>\n"
            f"   🆔 <code>{fed_id}</code>\n"
            f"   👥 {len(chats)} grup · 🔨 {len(bans)} ban")

    if not lines:
        await msg.reply_text(
            "ℹ️ Sahip olduğunuz veya yöneticisi olduğunuz bir federasyon bulunamadı.",
            parse_mode="HTML")
        return

    await msg.reply_text(
        "🌐 <b>Federasyonlarınız</b>\n\n" + "\n\n".join(lines),
        parse_mode="HTML")


# ── Auto-ban new members that are fbanned ─────────────────────────────────────

async def check_fban(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    Called when a new member joins a group.
    If they are fbanned in the group's federation, auto-ban them.
    Exported for use in welcome.py's _on_member_update.
    """
    result = update.chat_member
    if not result:
        return

    chat = result.chat
    old = result.old_chat_member
    new = result.new_chat_member
    user = new.user
    if not user:
        return

    from telegram.constants import ChatMemberStatus as CMS
    joined = (old.status in (CMS.LEFT, CMS.BANNED) and
              new.status in (CMS.MEMBER, CMS.RESTRICTED))
    if not joined:
        return

    fed = await get_chat_federation(chat.id)
    if not fed:
        return

    fban_info = await get_fban(fed["fed_id"], user.id)
    if not fban_info:
        return

    reason = fban_info.get("reason") or "(federasyon banı)"
    try:
        await ctx.bot.ban_chat_member(chat.id, user.id)
        await ctx.bot.send_message(
            chat.id,
            f"🔨 {mention(user.id, user.first_name)} bu federasyonda banlı olduğu için "
            f"otomatik olarak gruptan çıkarıldı.\n"
            f"📝 Sebep: {html.escape(reason)}",
            parse_mode="HTML")
    except Exception:
        pass


# ── Register ──────────────────────────────────────────────────────────────────

def register(app):
    from telegram.ext import ChatMemberHandler

    # Auto-fban check fires before welcome handler (group=4 < group=5)
    app.add_handler(
        ChatMemberHandler(check_fban, ChatMemberHandler.CHAT_MEMBER),
        group=4)

    for cmd, handler in [
        ("newfed",   newfed_cmd),
        ("delfed",   delfed_cmd),
        ("joinfed",  joinfed_cmd),
        ("leavefed", leavefed_cmd),
        ("fpromote", fpromote_cmd),
        ("fdemote",  fdemote_cmd),
        ("fban",     fban_cmd),
        ("unfban",   unfban_cmd),
        ("fedinfo",  fedinfo_cmd),
        ("chatfed",  chatfed_cmd),
        ("fbanlist", fbanlist_cmd),
        ("myfeds",   myfeds_cmd),
    ]:
        app.add_handler(MessageHandler(dcmd(cmd), handler), group=10)
