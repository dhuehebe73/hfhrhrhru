import html
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler
from telegram.error import BadRequest
from utils import dcmd

_HELP_CATEGORIES = {
    "admin": {
        "title": "👮 Admin Komutları",
        "text": (
            "/ban — Yasakla\n/dban — Sil + Yasakla\n/sban — Sessiz yasakla\n"
            "/unban — Yasak kaldır\n/kick — At\n/dkick — Sil + At\n"
            "/mute — Sustur\n/dmute — Sil + Sustur\n/unmute — Susturmayı kaldır\n"
            "/warn — Uyar\n/dwarn — Sil + Uyar\n/unwarn — Uyarı sil\n"
            "/warns — Uyarıları göster\n/resetwarns — Uyarıları sıfırla\n"
            "/promote — Admin yap\n/demote — Admin'den indir\n"
            "/approve — Filtrelerden muaf tut\n/unapprove — Muafiyeti kaldır\n"
            "/pin — Mesajı sabitle\n/unpin — Sabitlemeyi kaldır\n/del — Mesajı sil"
        ),
    },
    "moderation": {
        "title": "🛡 Moderasyon",
        "text": (
            "/purge — Mesajları temizle (yanıttan itibaren)\n"
            "/lock — Grubu kilitle\n/unlock — Kilidi aç\n"
            "/slowmode <sn> — Yavaş mod\n"
            "/antiflood on|off [limit] — Anti-flood ayarı\n"
            "/warnlimit <n> — Uyarı limiti\n/warnmode ban|kick|mute — Uyarı aksiyonu"
        ),
    },
    "filters": {
        "title": "🔍 Filtreler",
        "text": (
            "/filter <kelime> — Kelime filtresi ekle\n"
            "/unfilter <kelime> — Kelime filtresi kaldır\n"
            "/filters — Filtreleri listele\n"
            "\nAyarlar panelinden: link/sticker/medya/bot filtresi açılabilir."
        ),
    },
    "welcome": {
        "title": "👋 Karşılama",
        "text": (
            "/setwelcome <metin> — Karşılama mesajı ayarla\n"
            "/setgoodbye <metin> — Veda mesajı ayarla\n"
            "/welcome on|off — Karşılamayı aç/kapat\n"
            "/captcha on|off — Captcha doğrulaması\n"
            "/autoban on|off — Çıkan üyeyi otomatik yasakla\n"
            "\nDeğişkenler: {name} {first} {last} {username} {chat}"
        ),
    },
    "notes": {
        "title": "📝 Notlar",
        "text": (
            "/save <isim> <içerik> — Not kaydet\n"
            "/get <isim> veya #isim — Notu getir\n"
            "/notes — Notları listele\n"
            "/clear <isim> — Notu sil"
        ),
    },
    "translate": {
        "title": "🌐 Çeviri",
        "text": (
            "/tr [dil] <metin> — Çevir (varsayılan: Türkçe)\n"
            "/langs — Desteklenen diller\n"
            "\nÖrnek: /tr en Merhaba → Hello\n/tr de Günaydın"
        ),
    },
    "downloader": {
        "title": "🎵 İndirici",
        "text": (
            "/play <url> — Ses/video seçeneği sun\n"
            "/video <url> — Video indir\n"
            "/dl <url> — Otomatik indir\n"
            "\nDesteklenen: YouTube, TikTok, Instagram, Twitter, SoundCloud vb."
        ),
    },
    "giveaway": {
        "title": "🎉 Çekiliş",
        "text": (
            "/giveaway <süre> [kazanan] <ödül> — Çekiliş başlat\n"
            "/gend — Çekilişi bitir\n/greroll — Kazananı yeniden seç\n"
            "\nÖrnek: /giveaway 1h 2 Nitro Boost"
        ),
    },
    "extras": {
        "title": "🎲 Eğlence & Diğer",
        "text": (
            "/dice — Zar at\n/flip — Yazı-tura\n/rps <taş|kağıt|makas> — Eşleş\n"
            "/calc <işlem> — Hesap makinesi\n/ping — Bot gecikmesi\n"
            "/id — Kullanıcı/grup ID\n/info — Kullanıcı bilgisi\n"
            "/afk [sebep] — AFK modu\n/top — En aktif üyeler\n"
            "/rules — Kuralları göster\n/setrules <metin> — Kural ayarla\n"
            "/report — Mesajı adminlere şikayet et\n"
            "/broadcast <metin> — Tüm gruplara duyuru (sadece sahip)"
        ),
    },
    "settings": {
        "title": "⚙️ Ayarlar",
        "text": (
            "/settings — Grup ayarları paneli\n"
            "\nPanel üzerinden tek tıkla açıp kapatabilirsiniz:\n"
            "• Anti-Flood • Link Filtresi • Sticker Filtresi\n"
            "• Medya Filtresi • Bot Filtresi • Çıkan = Ban"
        ),
    },
}

_MAIN_KB = [
    [InlineKeyboardButton("👮 Admin",      callback_data="help|admin"),
     InlineKeyboardButton("🛡 Moderasyon", callback_data="help|moderation")],
    [InlineKeyboardButton("🔍 Filtreler",  callback_data="help|filters"),
     InlineKeyboardButton("👋 Karşılama",  callback_data="help|welcome")],
    [InlineKeyboardButton("📝 Notlar",     callback_data="help|notes"),
     InlineKeyboardButton("🌐 Çeviri",     callback_data="help|translate")],
    [InlineKeyboardButton("🎵 İndirici",   callback_data="help|downloader"),
     InlineKeyboardButton("🎉 Çekiliş",    callback_data="help|giveaway")],
    [InlineKeyboardButton("🎲 Eğlence",    callback_data="help|extras"),
     InlineKeyboardButton("⚙️ Ayarlar",    callback_data="help|settings")],
]


def _main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(_MAIN_KB)


def _category_kb(cat: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("◀️ Geri", callback_data="help|main")
    ]])


async def start_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if chat.type != "private":
        await update.effective_message.reply_text(
            f"👋 Merhaba {html.escape(user.first_name)}! Ben bir grup yönetim botuyum.\n"
            "Komutlar için /help yaz.")
        return
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📖 Yardım", callback_data="help|main"),
         InlineKeyboardButton("⚙️ Ayarlar", callback_data="help|settings")],
        [InlineKeyboardButton("➕ Gruba Ekle", url="https://t.me/+8342801633")],
    ])
    await update.effective_message.reply_text(
        f"👋 Merhaba, <b>{html.escape(user.first_name)}</b>!\n\n"
        "Ben gelişmiş bir Telegram grup yönetim botuyum.\n"
        "Tüm komutlarımı görmek için <b>Yardım</b>'a tıkla.",
        parse_mode="HTML", reply_markup=kb)


async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "📚 <b>Yardım Menüsü</b>\n\nBir kategori seç:",
        parse_mode="HTML", reply_markup=_main_menu_kb())


async def help_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if not data.startswith("help|"): return
    cat = data.split("|", 1)[1]
    try:
        if cat == "main":
            await query.edit_message_text(
                "📚 <b>Yardım Menüsü</b>\n\nBir kategori seç:",
                parse_mode="HTML", reply_markup=_main_menu_kb())
            return
        if cat not in _HELP_CATEGORIES: return
        info = _HELP_CATEGORIES[cat]
        # html.escape prevents <metin> <url> etc. from being parsed as HTML tags
        body = html.escape(info["text"])
        await query.edit_message_text(
            f"<b>{html.escape(info['title'])}</b>\n\n{body}",
            parse_mode="HTML", reply_markup=_category_kb(cat))
    except BadRequest as e:
        if "not modified" not in str(e).lower():
            raise


def register(app):
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help",  help_cmd))
    app.add_handler(MessageHandler(dcmd("start"), start_cmd), group=10)
    app.add_handler(MessageHandler(dcmd("help"),  help_cmd),  group=10)
    app.add_handler(CallbackQueryHandler(help_callback, pattern=r"^help\|"), group=10)
