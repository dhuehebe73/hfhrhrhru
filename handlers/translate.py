from telegram import Update
from telegram.ext import ContextTypes, MessageHandler
from deep_translator import GoogleTranslator
from utils import dcmd, get_args

# ISO code → deep_translator full name (required by deep_translator 1.x)
_LANG = {
    "tr":"turkish","en":"english","de":"german","fr":"french","es":"spanish",
    "it":"italian","pt":"portuguese","ru":"russian","ar":"arabic",
    "zh":"chinese (simplified)","ja":"japanese","ko":"korean",
    "nl":"dutch","pl":"polish","sv":"swedish","no":"norwegian","da":"danish",
    "fi":"finnish","cs":"czech","sk":"slovak","ro":"romanian","hu":"hungarian",
    "bg":"bulgarian","uk":"ukrainian","el":"greek","he":"hebrew","fa":"persian",
    "hi":"hindi","bn":"bengali","ur":"urdu","vi":"vietnamese","th":"thai",
    "id":"indonesian","ms":"malay","tl":"tagalog","af":"afrikaans",
    "sq":"albanian","hy":"armenian","az":"azerbaijani","eu":"basque",
    "be":"belarusian","ca":"catalan","hr":"croatian","et":"estonian",
    "gl":"galician","ka":"georgian","is":"icelandic","ga":"irish",
    "lv":"latvian","lt":"lithuanian","mk":"macedonian","mt":"maltese",
    "sr":"serbian","sl":"slovenian","sw":"swahili","cy":"welsh","eo":"esperanto",
}

_CODE_BY_NAME = {v: k for k, v in _LANG.items()}


def _resolve(token: str) -> str | None:
    t = token.lower().strip()
    if t in _LANG: return t
    if t in _CODE_BY_NAME: return _CODE_BY_NAME[t]
    return None


async def tr_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg  = update.effective_message
    args = get_args(update, ctx)

    # Default to user's preferred language (stored in DB), fallback to "en"
    uid = update.effective_user.id if update.effective_user else 0
    try:
        from database import get_user_lang
        default_lang = await get_user_lang(uid)
    except Exception:
        default_lang = "en"

    target = default_lang
    text_to_translate = None

    if args:
        resolved = _resolve(args[0])
        if resolved:
            target = resolved
            rest   = " ".join(args[1:])
        else:
            rest   = " ".join(args)
        if rest:
            text_to_translate = rest

    if not text_to_translate and msg.reply_to_message:
        text_to_translate = (msg.reply_to_message.text or
                             msg.reply_to_message.caption or "")

    if not text_to_translate:
        await msg.reply_text(
            "Usage: /tr [lang] <text>  or  reply to a message\n"
            "Examples:\n"
            "  /tr en Merhaba     →  Hello\n"
            "  /tr tr Hello       →  Merhaba\n"
            "  /tr de Good morning\n\n"
            "Use /langs for the full language list."
        )
        return

    # Pass full language name (e.g. "english") — deep_translator requirement
    lang_name = _LANG.get(target, target)
    try:
        result = GoogleTranslator(source="auto", target=lang_name).translate(text_to_translate)
        flag   = _flag(target)
        await msg.reply_text(f"{flag} <b>{target.upper()}</b>: {result}", parse_mode="HTML")
    except Exception as e:
        await msg.reply_text(f"Translation error: {e}")


def _flag(lang: str) -> str:
    return {
        "tr":"🇹🇷","en":"🇬🇧","de":"🇩🇪","fr":"🇫🇷","es":"🇪🇸","it":"🇮🇹",
        "pt":"🇵🇹","ru":"🇷🇺","ar":"🇸🇦","zh":"🇨🇳","ja":"🇯🇵","ko":"🇰🇷",
        "nl":"🇳🇱","pl":"🇵🇱","uk":"🇺🇦","el":"🇬🇷","he":"🇮🇱","fa":"🇮🇷",
        "hi":"🇮🇳","vi":"🇻🇳","th":"🇹🇭","id":"🇮🇩",
    }.get(lang, "🌐")


async def langs_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    pairs = ", ".join(sorted(_LANG.keys()))
    await update.effective_message.reply_text(f"🌐 Supported language codes:\n{pairs}")


def register(app):
    app.add_handler(MessageHandler(dcmd("tr"),        tr_cmd),    group=10)
    app.add_handler(MessageHandler(dcmd("translate"), tr_cmd),    group=10)
    app.add_handler(MessageHandler(dcmd("langs"),     langs_cmd), group=10)
