import html
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler
from telegram.error import BadRequest
from utils import dcmd
from config import OWNER_ID
from database import register_user, get_user_lang, set_user_lang

# ── Locale strings ────────────────────────────────────────────────────────────

_STR = {
    "en": {
        "start_pm": (
            "👋 Hello, <b>{name}</b>!\n\n"
            "I'm an advanced Telegram group management bot.\n"
            "Press <b>Help</b> to explore all features."
        ),
        "start_group": "👋 Hello {name}! Use /help for commands.",
        "btn_help":    "📖 Help",
        "btn_settings":"⚙️ Settings",
        "btn_add":     "➕ Add to Group",
        "btn_support": "💬 Support",
        "btn_lang":    "🌐 Language",
        "btn_owner":   "👑 Owner Panel",
        "btn_back":    "◀️ Back",
        "btn_home":    "🏠 Home",
        "help_hdr":    "📚 <b>Help</b> — Select a category:",
        "lang_hdr":    "🌐 Choose your language:",
    },
    "tr": {
        "start_pm": (
            "👋 Merhaba, <b>{name}</b>!\n\n"
            "Gelişmiş bir Telegram grup yönetim botuyum.\n"
            "Tüm özellikleri keşfetmek için <b>Yardım</b>'a bas."
        ),
        "start_group": "👋 Merhaba {name}! Komutlar için /help yaz.",
        "btn_help":    "📖 Yardım",
        "btn_settings":"⚙️ Ayarlar",
        "btn_add":     "➕ Gruba Ekle",
        "btn_support": "💬 Destek",
        "btn_lang":    "🌐 Dil",
        "btn_owner":   "👑 Sahip Paneli",
        "btn_back":    "◀️ Geri",
        "btn_home":    "🏠 Ana Menü",
        "help_hdr":    "📚 <b>Yardım</b> — Bir kategori seç:",
        "lang_hdr":    "🌐 Dilinizi seçin:",
    },
    "de": {
        "start_pm": (
            "👋 Hallo, <b>{name}</b>!\n\n"
            "Ich bin ein fortgeschrittener Telegram-Gruppen-Verwaltungsbot.\n"
            "Drücke <b>Hilfe</b>, um alle Funktionen zu erkunden."
        ),
        "start_group": "👋 Hallo {name}! /help für Befehle.",
        "btn_help":    "📖 Hilfe",
        "btn_settings":"⚙️ Einstellungen",
        "btn_add":     "➕ Zur Gruppe",
        "btn_support": "💬 Support",
        "btn_lang":    "🌐 Sprache",
        "btn_owner":   "👑 Besitzer",
        "btn_back":    "◀️ Zurück",
        "btn_home":    "🏠 Start",
        "help_hdr":    "📚 <b>Hilfe</b> — Kategorie wählen:",
        "lang_hdr":    "🌐 Sprache wählen:",
    },
    "fr": {
        "start_pm": (
            "👋 Bonjour, <b>{name}</b>!\n\n"
            "Je suis un bot avancé de gestion de groupes Telegram.\n"
            "Appuie sur <b>Aide</b> pour explorer toutes les fonctionnalités."
        ),
        "start_group": "👋 Bonjour {name}! /help pour les commandes.",
        "btn_help":    "📖 Aide",
        "btn_settings":"⚙️ Paramètres",
        "btn_add":     "➕ Ajouter",
        "btn_support": "💬 Support",
        "btn_lang":    "🌐 Langue",
        "btn_owner":   "👑 Propriétaire",
        "btn_back":    "◀️ Retour",
        "btn_home":    "🏠 Accueil",
        "help_hdr":    "📚 <b>Aide</b> — Choisir une catégorie:",
        "lang_hdr":    "🌐 Choisissez votre langue:",
    },
    "es": {
        "start_pm": (
            "👋 ¡Hola, <b>{name}</b>!\n\n"
            "Soy un bot avanzado de gestión de grupos de Telegram.\n"
            "Presiona <b>Ayuda</b> para explorar todas las funciones."
        ),
        "start_group": "👋 ¡Hola {name}! /help para comandos.",
        "btn_help":    "📖 Ayuda",
        "btn_settings":"⚙️ Configuración",
        "btn_add":     "➕ Añadir",
        "btn_support": "💬 Soporte",
        "btn_lang":    "🌐 Idioma",
        "btn_owner":   "👑 Propietario",
        "btn_back":    "◀️ Volver",
        "btn_home":    "🏠 Inicio",
        "help_hdr":    "📚 <b>Ayuda</b> — Selecciona una categoría:",
        "lang_hdr":    "🌐 Elige tu idioma:",
    },
    "ru": {
        "start_pm": (
            "👋 Привет, <b>{name}</b>!\n\n"
            "Я продвинутый бот для управления группами Telegram.\n"
            "Нажми <b>Помощь</b>, чтобы изучить все функции."
        ),
        "start_group": "👋 Привет {name}! /help для команд.",
        "btn_help":    "📖 Помощь",
        "btn_settings":"⚙️ Настройки",
        "btn_add":     "➕ Добавить",
        "btn_support": "💬 Поддержка",
        "btn_lang":    "🌐 Язык",
        "btn_owner":   "👑 Владелец",
        "btn_back":    "◀️ Назад",
        "btn_home":    "🏠 Главная",
        "help_hdr":    "📚 <b>Помощь</b> — Выбери категорию:",
        "lang_hdr":    "🌐 Выберите ваш язык:",
    },
}

def _s(lang: str, key: str) -> str:
    return (_STR.get(lang) or _STR["en"]).get(key) or _STR["en"].get(key, key)


# ── Help categories (EN + TR; other langs fall back to EN) ────────────────────

_CATS = {
    "admin": {
        "en": ("👮 Admin Commands",
               "/ban [user] — Ban\n/dban — Delete & Ban\n/sban — Silent ban\n"
               "/unban [user] — Unban\n/kick [user] — Kick\n/dkick — Delete & Kick\n"
               "/mute [user] [time] — Mute\n/dmute — Delete & Mute\n/unmute — Unmute\n"
               "/warn [user] — Warn\n/dwarn — Delete & Warn\n/unwarn — Remove warn\n"
               "/warns [user] — Show warnings\n/resetwarns [user] — Reset warnings\n"
               "/promote [user] — Make admin\n/demote [user] — Remove admin\n"
               "/approve [user] — Exempt from filters\n/unapprove — Remove exemption\n"
               "/pin — Pin message (reply)\n/unpin — Unpin\n/del — Delete message"),
        "tr": ("👮 Admin Komutları",
               "/ban [kullanıcı] — Yasakla\n/dban — Sil+Yasakla\n/sban — Sessiz yasakla\n"
               "/unban — Yasak kaldır\n/kick — At\n/dkick — Sil+At\n"
               "/mute [süre] — Sustur\n/dmute — Sil+Sustur\n/unmute — Susturma kaldır\n"
               "/warn — Uyar\n/dwarn — Sil+Uyar\n/unwarn — Uyarı sil\n"
               "/warns — Uyarıları göster\n/resetwarns — Uyarıları sıfırla\n"
               "/promote — Admin yap\n/demote — Admin'den indir\n"
               "/approve — Filtrelerden muaf\n/unapprove — Muafiyeti kaldır\n"
               "/pin — Sabitle\n/unpin — Sabitleme kaldır\n/del — Mesajı sil"),
    },
    "moderation": {
        "en": ("🛡 Moderation",
               "/purge — Delete messages from reply to now\n"
               "/lock — Lock group (no one can write)\n/unlock — Unlock group\n"
               "/slowmode [sec] — Slow mode (0 = off)\n"
               "/antiflood on|off [limit] — Flood protection\n"
               "/warnlimit [n] — Set warning limit\n/warnmode ban|kick|mute — Warn action"),
        "tr": ("🛡 Moderasyon",
               "/purge — Yanıttan itibaren mesajları sil\n"
               "/lock — Grubu kilitle\n/unlock — Kilidi aç\n"
               "/slowmode [sn] — Yavaş mod (0=kapat)\n"
               "/antiflood on|off [limit] — Flood koruması\n"
               "/warnlimit [n] — Uyarı limiti\n/warnmode ban|kick|mute — Uyarı aksiyonu"),
    },
    "filters": {
        "en": ("🔍 Filters",
               "/filter [word] — Add word filter\n"
               "/unfilter [word] — Remove word filter\n"
               "/filters — List all active filters\n\n"
               "Toggle in /settings panel:\n"
               "Link filter • Sticker filter • Media filter • Bot filter"),
        "tr": ("🔍 Filtreler",
               "/filter [kelime] — Kelime filtresi ekle\n"
               "/unfilter [kelime] — Kelime filtresi kaldır\n"
               "/filters — Aktif filtreleri listele\n\n"
               "/settings panelinden:\n"
               "Link • Sticker • Medya • Bot filtresi"),
    },
    "welcome": {
        "en": ("👋 Welcome / Goodbye",
               "/setwelcome [text] — Set welcome message\n"
               "/setgoodbye [text] — Set goodbye message\n"
               "/welcome on|off — Toggle welcome messages\n"
               "/captcha on|off — Math verification for new members\n"
               "/autoban on|off — Auto-ban members who rejoin after leaving\n\n"
               "Variables: {name} {first} {last} {username} {chat}"),
        "tr": ("👋 Karşılama / Veda",
               "/setwelcome [metin] — Karşılama mesajı ayarla\n"
               "/setgoodbye [metin] — Veda mesajı ayarla\n"
               "/welcome on|off — Karşılamayı aç/kapat\n"
               "/captcha on|off — Yeni üye için matematik doğrulaması\n"
               "/autoban on|off — Çıkıp geri gelen üyeyi otomatik yasakla\n\n"
               "Değişkenler: {name} {first} {last} {username} {chat}"),
    },
    "notes": {
        "en": ("📝 Notes",
               "/save [name] [content] — Save note (or reply to message)\n"
               "/get [name] or #name — Retrieve note\n"
               "/notes — List all notes\n"
               "/clear [name] — Delete note"),
        "tr": ("📝 Notlar",
               "/save [isim] [içerik] — Not kaydet (ya da mesajı yanıtla)\n"
               "/get [isim] veya #isim — Notu getir\n"
               "/notes — Tüm notları listele\n"
               "/clear [isim] — Notu sil"),
    },
    "translate": {
        "en": ("🌐 Translate",
               "/tr [lang] [text] — Translate text\n"
               "/translate — Same as /tr\n"
               "/langs — List supported languages\n\n"
               "Examples:\n"
               "  /tr tr Hello       → Merhaba\n"
               "  /tr de Good morning → Guten Morgen\n"
               "  /tr en Bonjour     → Hello\n"
               "  Reply to a message + /tr en"),
        "tr": ("🌐 Çeviri",
               "/tr [dil] [metin] — Metni çevir\n"
               "/translate — /tr ile aynı\n"
               "/langs — Desteklenen diller\n\n"
               "Örnekler:\n"
               "  /tr en Merhaba  → Hello\n"
               "  /tr de Günaydın → Guten Morgen\n"
               "  Mesajı yanıtla + /tr en"),
    },
    "downloader": {
        "en": ("🎵 Downloader",
               "/play [name or URL] — Download audio or video\n"
               "/video [name or URL] — Download video\n"
               "/dl [name or URL] — Smart download\n\n"
               "Supports: YouTube, TikTok, Instagram, Twitter, SoundCloud…"),
        "tr": ("🎵 İndirici",
               "/play [isim veya URL] — Ses veya video seç\n"
               "/video [isim veya URL] — Video indir\n"
               "/dl [isim veya URL] — Otomatik indir\n\n"
               "Desteklenen: YouTube, TikTok, Instagram, Twitter, SoundCloud…"),
    },
    "giveaway": {
        "en": ("🎉 Giveaway",
               "/giveaway [duration] [winners] [prize] — Start giveaway\n"
               "/gend — End active giveaway\n"
               "/greroll — Re-roll winner\n\n"
               "Duration: 30m / 1h / 2d\n"
               "Example: /giveaway 1h 2 Nitro Boost"),
        "tr": ("🎉 Çekiliş",
               "/giveaway [süre] [kazanan] [ödül] — Çekiliş başlat\n"
               "/gend — Aktif çekilişi bitir\n"
               "/greroll — Kazananı yeniden seç\n\n"
               "Süre: 30m / 1h / 2g\n"
               "Örnek: /giveaway 1h 2 Nitro Boost"),
    },
    "extras": {
        "en": ("🎲 Fun & Extras",
               "/dice — Roll dice 🎲\n/flip — Coin flip 🪙\n"
               "/rps rock|paper|scissors — Play RPS\n"
               "/calc [expr] — Calculator 🧮\n/ping — Bot latency\n"
               "/id — User/group ID\n/info [user] — User info\n"
               "/afk [reason] — Set AFK status\n/top — Most active members\n"
               "/rules — Show rules\n/setrules [text] — Set rules\n"
               "/report — Report message to admins\n"
               "/broadcast [text] — Broadcast to all groups (owner only)"),
        "tr": ("🎲 Eğlence & Diğer",
               "/dice — Zar at 🎲\n/flip — Yazı-tura 🪙\n"
               "/rps taş|kağıt|makas — Taş kağıt makas\n"
               "/calc [işlem] — Hesap makinesi 🧮\n/ping — Gecikme\n"
               "/id — ID\n/info [kullanıcı] — Kullanıcı bilgisi\n"
               "/afk [sebep] — AFK modu\n/top — En aktif üyeler\n"
               "/rules — Kurallar\n/setrules [metin] — Kural ayarla\n"
               "/report — Adminlere şikayet et\n"
               "/broadcast [metin] — Tüm gruplara yayın (sadece sahip)"),
    },
    "settings": {
        "en": ("⚙️ Settings",
               "/settings — Open group settings panel\n\n"
               "Toggle with one click:\n"
               "• Anti-Flood  • Link Filter  • Sticker Filter\n"
               "• Media Filter  • Bot Filter  • Auto-ban on leave\n\n"
               "/slowmode [sec]  •  /warnlimit [n]  •  /warnmode ban|kick|mute"),
        "tr": ("⚙️ Ayarlar",
               "/settings — Grup ayarları paneli\n\n"
               "Tek tıkla aç/kapat:\n"
               "• Anti-Flood  • Link  • Sticker  • Medya  • Bot  • Çıkan=Ban\n\n"
               "/slowmode [sn]  •  /warnlimit [n]  •  /warnmode ban|kick|mute"),
    },
}

_CAT_LABELS = {
    "admin":      {"en": "👮 Admin",      "tr": "👮 Admin"},
    "moderation": {"en": "🛡 Moderation", "tr": "🛡 Moderasyon"},
    "filters":    {"en": "🔍 Filters",    "tr": "🔍 Filtreler"},
    "welcome":    {"en": "👋 Welcome",    "tr": "👋 Karşılama"},
    "notes":      {"en": "📝 Notes",      "tr": "📝 Notlar"},
    "translate":  {"en": "🌐 Translate",  "tr": "🌐 Çeviri"},
    "downloader": {"en": "🎵 Downloader", "tr": "🎵 İndirici"},
    "giveaway":   {"en": "🎉 Giveaway",   "tr": "🎉 Çekiliş"},
    "extras":     {"en": "🎲 Fun",        "tr": "🎲 Eğlence"},
    "settings":   {"en": "⚙️ Settings",   "tr": "⚙️ Ayarlar"},
}

_LANG_DISPLAY = [
    ("en", "🇬🇧", "English"),
    ("tr", "🇹🇷", "Türkçe"),
    ("de", "🇩🇪", "Deutsch"),
    ("fr", "🇫🇷", "Français"),
    ("es", "🇪🇸", "Español"),
    ("ru", "🇷🇺", "Русский"),
]
_VALID_LANGS = {c for c, _, _ in _LANG_DISPLAY}


# ── Keyboard builders ─────────────────────────────────────────────────────────

def _start_kb(lang: str, bot_username: str, is_owner: bool) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(_s(lang, "btn_help"),     callback_data="help|main"),
         InlineKeyboardButton(_s(lang, "btn_settings"), callback_data="start|settings")],
        [InlineKeyboardButton(_s(lang, "btn_add"),
                              url=f"https://t.me/{bot_username}?startgroup=start"),
         InlineKeyboardButton(_s(lang, "btn_support"),  url="https://t.me/baron_hesaplar")],
        [InlineKeyboardButton(_s(lang, "btn_lang"),     callback_data="help|lang")],
    ]
    if is_owner:
        rows.append([InlineKeyboardButton(_s(lang, "btn_owner"), callback_data="owner|panel")])
    return InlineKeyboardMarkup(rows)


def _main_kb(lang: str) -> InlineKeyboardMarkup:
    keys = list(_CAT_LABELS.keys())
    rows = []
    for i in range(0, len(keys), 2):
        row = []
        for k in keys[i:i+2]:
            lbl = _CAT_LABELS[k].get(lang) or _CAT_LABELS[k]["en"]
            row.append(InlineKeyboardButton(lbl, callback_data=f"help|{k}"))
        rows.append(row)
    return InlineKeyboardMarkup(rows)


def _cat_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(_s(lang, "btn_back"), callback_data="help|main"),
        InlineKeyboardButton(_s(lang, "btn_home"), callback_data="start|home"),
    ]])


def _lang_kb() -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(_LANG_DISPLAY), 3):
        rows.append([
            InlineKeyboardButton(f"{flag} {name}", callback_data=f"set_lang|{code}")
            for code, flag, name in _LANG_DISPLAY[i:i+3]
        ])
    rows.append([InlineKeyboardButton("◀️ Back / Geri", callback_data="start|home")])
    return InlineKeyboardMarkup(rows)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _lang(uid: int) -> str:
    try:
        return await get_user_lang(uid)
    except Exception:
        return "en"


def _start_text(lang: str, user) -> str:
    return _s(lang, "start_pm").replace("{name}", html.escape(user.first_name or "?"))


async def _show_start(query, lang: str, user, bot_username: str):
    is_owner = user.id == OWNER_ID
    try:
        await query.edit_message_text(
            _start_text(lang, user),
            parse_mode="HTML",
            reply_markup=_start_kb(lang, bot_username, is_owner))
    except BadRequest as e:
        if "not modified" not in str(e).lower():
            raise


# ── Commands ──────────────────────────────────────────────────────────────────

async def start_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if not user: return

    try:
        await register_user(user.id, user.username or "", user.first_name or "")
    except Exception:
        pass

    lang = await _lang(user.id)

    if chat.type != "private":
        await update.effective_message.reply_text(
            _s(lang, "start_group").replace("{name}", html.escape(user.first_name or "")))
        return

    bot_username = ctx.bot.username or ""
    is_owner = user.id == OWNER_ID
    await update.effective_message.reply_text(
        _start_text(lang, user),
        parse_mode="HTML",
        reply_markup=_start_kb(lang, bot_username, is_owner))


async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id if update.effective_user else 0
    lang = await _lang(uid)
    await update.effective_message.reply_text(
        _s(lang, "help_hdr"), parse_mode="HTML", reply_markup=_main_kb(lang))


# ── Callback handler ──────────────────────────────────────────────────────────

async def help_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid   = query.from_user.id
    lang  = await _lang(uid)
    data  = query.data

    try:
        # ── Home / start screen ────────────────────────────────────────────
        if data in ("start|home", "start|settings_back"):
            await _show_start(query, lang, query.from_user, ctx.bot.username or "")
            return

        # ── Settings page (from start menu — back goes to start, not help) ─
        if data == "start|settings":
            cat_data = _CATS["settings"].get(lang) or _CATS["settings"]["en"]
            title, body = cat_data
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton(_s(lang, "btn_home"), callback_data="start|home")
            ]])
            await query.edit_message_text(
                f"<b>{html.escape(title)}</b>\n\n{html.escape(body)}",
                parse_mode="HTML", reply_markup=kb)
            return

        # ── Main help menu ─────────────────────────────────────────────────
        if data == "help|main":
            await query.edit_message_text(
                _s(lang, "help_hdr"), parse_mode="HTML", reply_markup=_main_kb(lang))
            return

        # ── Language picker ────────────────────────────────────────────────
        if data == "help|lang":
            await query.edit_message_text(_s(lang, "lang_hdr"), reply_markup=_lang_kb())
            return

        # ── Set language ───────────────────────────────────────────────────
        if data.startswith("set_lang|"):
            new_lang = data.split("|", 1)[1]
            if new_lang not in _VALID_LANGS:
                return
            await set_user_lang(uid, new_lang)
            await _show_start(query, new_lang, query.from_user, ctx.bot.username or "")
            return

        # ── Owner panel ────────────────────────────────────────────────────
        if data == "owner|panel":
            if uid != OWNER_ID:
                await query.answer("❌ Not authorized.", show_alert=True)
                return
            texts = {
                "en": (
                    "👑 <b>Owner Panel</b>\n\n"
                    "Special commands (use in DM):\n\n"
                    "📊 /users — All users who started the bot\n"
                    "📋 /chats — All registered groups &amp; channels\n"
                    "📣 /broadcast [text] — Send to all groups"
                ),
                "tr": (
                    "👑 <b>Sahip Paneli</b>\n\n"
                    "Özel komutlar (DM'de kullan):\n\n"
                    "📊 /users — Botu başlatan tüm kullanıcılar\n"
                    "📋 /chats — Kayıtlı gruplar ve kanallar\n"
                    "📣 /broadcast [metin] — Tüm gruplara gönder"
                ),
            }
            text = texts.get(lang, texts["en"])
            await query.edit_message_text(
                text, parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(_s(lang, "btn_home"), callback_data="start|home")
                ]]))
            return

        # ── Help category ──────────────────────────────────────────────────
        if data.startswith("help|"):
            cat = data.split("|", 1)[1]
            if cat not in _CATS:
                return
            cat_data = _CATS[cat].get(lang) or _CATS[cat]["en"]
            title, body = cat_data
            await query.edit_message_text(
                f"<b>{html.escape(title)}</b>\n\n{html.escape(body)}",
                parse_mode="HTML", reply_markup=_cat_kb(lang))
            return

    except BadRequest as e:
        if "not modified" not in str(e).lower():
            raise


def register(app):
    app.add_handler(MessageHandler(dcmd("start"), start_cmd), group=10)
    app.add_handler(MessageHandler(dcmd("help"),  help_cmd),  group=10)
    app.add_handler(CallbackQueryHandler(
        help_callback,
        pattern=r"^(help|start|set_lang|owner)\|"), group=10)
