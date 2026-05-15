"""
Bağlantı sistemi — PM'den grup yönetimi (Rose tarzı /connect).

Kullanıcı bir gruba /connect ile bağlandıktan sonra PM'den gönderdiği
/ban, /mute vb. komutlar o grup üzerinde çalışır.

Dışa aktarılan fonksiyon:
    get_connected_chat(update, ctx) → chat_id | None
"""

from telegram import Update
from telegram.ext import ContextTypes, MessageHandler
from database import get_connection, set_connection, clear_connection
from utils import is_admin, dcmd, get_args, mention


# ── Public utility (imported by admin/moderation handlers) ────────────────────

async def get_connected_chat(update: Update,
                              ctx: ContextTypes.DEFAULT_TYPE) -> int | None:
    """
    Eğer kullanıcı PM'den yazıyorsa ve aktif bir bağlantısı varsa,
    bağlı olduğu chat_id'yi döndürür. Aksi hâlde None.
    """
    if update.effective_chat.type != "private":
        return None
    conn = await get_connection(update.effective_user.id)
    if not conn:
        return None
    return conn["chat_id"]


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _check_user_is_admin_in_chat(ctx: ContextTypes.DEFAULT_TYPE,
                                        user_id: int,
                                        chat_id: int) -> bool:
    """Verilen chat'te kullanıcının admin olup olmadığını kontrol eder."""
    from config import OWNER_ID
    if user_id == OWNER_ID:
        return True
    try:
        from telegram.constants import ChatMemberStatus
        member = await ctx.bot.get_chat_member(chat_id, user_id)
        return member.status in (ChatMemberStatus.ADMINISTRATOR,
                                  ChatMemberStatus.OWNER)
    except Exception:
        return False


# ── Commands ──────────────────────────────────────────────────────────────────

async def connect_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    /connect <chat_id>
    Belirtilen gruba bağlanır. Kullanıcı o grubun admini olmak zorundadır.
    Hem PM'den hem gruptan çalışır.
    """
    msg  = update.effective_message
    user = update.effective_user
    args = get_args(update, ctx)

    if not args:
        await msg.reply_text(
            "❓ <b>Kullanım:</b> <code>/connect &lt;chat_id&gt;</code>\n\n"
            "Örnek: <code>/connect -1001234567890</code>",
            parse_mode="HTML",
        )
        return

    raw = args[0]
    if not raw.lstrip("-").isdigit():
        await msg.reply_text("❌ Geçersiz chat_id. Negatif bir tam sayı olmalıdır.")
        return

    chat_id = int(raw)

    # Verify the bot is in that chat and fetch its title
    try:
        chat_obj = await ctx.bot.get_chat(chat_id)
    except Exception:
        await msg.reply_text(
            "❌ Bu gruba erişilemiyor. Botu gruba eklediğinizden emin olun.",
        )
        return

    if chat_obj.type not in ("group", "supergroup"):
        await msg.reply_text("❌ Yalnızca gruplara ve süper gruplara bağlanabilirsiniz.")
        return

    # Verify the user is admin in that chat
    if not await _check_user_is_admin_in_chat(ctx, user.id, chat_id):
        await msg.reply_text(
            f"❌ <b>{chat_obj.title}</b> grubunda admin değilsiniz.",
            parse_mode="HTML",
        )
        return

    await set_connection(user.id, chat_id, chat_obj.title or str(chat_id))
    await msg.reply_text(
        f"🔗 <b>{chat_obj.title}</b> grubuna bağlandınız!\n\n"
        f"Artık PM'den gönderdiğiniz yönetim komutları "
        f"(<code>/ban</code>, <code>/mute</code> vb.) bu grupta çalışacak.\n\n"
        f"Bağlantıyı kesmek için: <code>/disconnect</code>",
        parse_mode="HTML",
    )


async def disconnect_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    /disconnect
    Mevcut bağlantıyı keser.
    """
    msg  = update.effective_message
    user = update.effective_user

    conn = await get_connection(user.id)
    if not conn:
        await msg.reply_text("ℹ️ Aktif bir bağlantınız yok.")
        return

    title = conn.get("chat_title", str(conn["chat_id"]))
    await clear_connection(user.id)
    await msg.reply_text(
        f"🔌 <b>{title}</b> grubundan bağlantı kesildi.",
        parse_mode="HTML",
    )


async def connection_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    /connection  veya  /connected
    Mevcut bağlantı bilgisini gösterir.
    """
    msg  = update.effective_message
    user = update.effective_user

    conn = await get_connection(user.id)
    if not conn:
        await msg.reply_text(
            "ℹ️ Şu anda herhangi bir gruba bağlı değilsiniz.\n\n"
            "Bağlanmak için: <code>/connect &lt;chat_id&gt;</code>",
            parse_mode="HTML",
        )
        return

    chat_id    = conn["chat_id"]
    chat_title = conn.get("chat_title", str(chat_id))

    # Try to verify the connection is still valid
    still_admin = await _check_user_is_admin_in_chat(ctx, user.id, chat_id)
    status_line = (
        "✅ Admin yetkiniz geçerli" if still_admin
        else "⚠️ Bu grupta artık admin değilsiniz"
    )

    await msg.reply_text(
        f"🔗 <b>Aktif Bağlantı</b>\n\n"
        f"Grup: <b>{chat_title}</b>\n"
        f"Chat ID: <code>{chat_id}</code>\n"
        f"Durum: {status_line}\n\n"
        f"Bağlantıyı kesmek için: <code>/disconnect</code>",
        parse_mode="HTML",
    )


# ── Register ──────────────────────────────────────────────────────────────────

def register(app):
    for cmd, handler in [
        ("connect",     connect_cmd),
        ("disconnect",  disconnect_cmd),
        ("connection",  connection_cmd),
        ("connected",   connection_cmd),
    ]:
        app.add_handler(MessageHandler(dcmd(cmd), handler), group=10)
