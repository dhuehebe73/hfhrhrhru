"""
Translation — .tr [lang] reply or inline
Default: Turkish. 50+ languages.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from utils import dot_filter

try:
    from deep_translator import GoogleTranslator
    TRANSLATE_OK = True
except ImportError:
    TRANSLATE_OK = False

# ─── Language map ─────────────────────────────────────────────────────────────
_LANG = {
    # Turkish
    "tr": "tr", "turkce": "tr", "turkish": "tr",
    # English
    "en": "en", "english": "en", "ingilizce": "en",
    # German
    "de": "de", "german": "de", "almanca": "de",
    # French
    "fr": "fr", "french": "fr", "fransizca": "fr",
    # Spanish
    "es": "es", "spanish": "es", "ispanyolca": "es",
    # Italian
    "it": "it", "italian": "it", "italyanca": "it",
    # Portuguese
    "pt": "pt", "portuguese": "pt", "portekizce": "pt",
    # Russian
    "ru": "ru", "russian": "ru", "rusca": "ru",
    # Arabic
    "ar": "ar", "arabic": "ar", "arapca": "ar",
    # Japanese
    "ja": "ja", "jp": "ja", "japanese": "ja", "japonca": "ja",
    # Chinese
    "zh": "zh-CN", "cn": "zh-CN", "chinese": "zh-CN", "cince": "zh-CN",
    "zh-cn": "zh-CN", "zh-tw": "zh-TW",
    # Korean
    "ko": "ko", "korean": "ko", "korece": "ko",
    # Persian
    "fa": "fa", "persian": "fa", "farsca": "fa",
    # Ukrainian
    "uk": "uk", "ukrainian": "uk", "ukraynaca": "uk",
    # Polish
    "pl": "pl", "polish": "pl", "polonyaca": "pl",
    # Dutch
    "nl": "nl", "dutch": "nl", "hollandaca": "nl",
    # Swedish
    "sv": "sv", "swedish": "sv", "isvecce": "sv",
    # Norwegian
    "no": "no", "norwegian": "no", "norvecce": "no",
    # Finnish
    "fi": "fi", "finnish": "fi", "fince": "fi",
    # Danish
    "da": "da", "danish": "da", "danimarkaca": "da",
    # Greek
    "el": "el", "greek": "el", "rumca": "el",
    # Hebrew
    "he": "he", "hebrew": "he", "ibranice": "he",
    # Hindi
    "hi": "hi", "hindi": "hi", "hintce": "hi",
    # Indonesian
    "id": "id", "indonesian": "id",
    # Malay
    "ms": "ms", "malay": "ms",
    # Thai
    "th": "th", "thai": "th", "tayca": "th",
    # Vietnamese
    "vi": "vi", "vietnamese": "vi", "vietnamca": "vi",
    # Romanian
    "ro": "ro", "romanian": "ro", "rumence": "ro",
    # Hungarian
    "hu": "hu", "hungarian": "hu", "macarca": "hu",
    # Czech
    "cs": "cs", "czech": "cs", "cekce": "cs",
    # Bulgarian
    "bg": "bg", "bulgarian": "bg", "bulgarca": "bg",
    # Serbian
    "sr": "sr", "serbian": "sr", "sirpca": "sr",
    # Croatian
    "hr": "hr", "croatian": "hr", "hirvatca": "hr",
    # Slovak
    "sk": "sk", "slovak": "sk",
    # Lithuanian
    "lt": "lt", "lithuanian": "lt", "litvanca": "lt",
    # Latvian
    "lv": "lv", "latvian": "lv",
    # Estonian
    "et": "et", "estonian": "et",
    # Azerbaijani
    "az": "az", "azerbaijani": "az", "azerbaycanca": "az",
    # Georgian
    "ka": "ka", "georgian": "ka", "gurcuce": "ka",
    # Armenian
    "hy": "hy", "armenian": "hy", "ermenice": "hy",
    # Kazakh
    "kk": "kk", "kazakh": "kk", "kazakca": "kk",
    # Uzbek
    "uz": "uz", "uzbek": "uz", "ozbekce": "uz",
    # Catalan
    "ca": "ca", "catalan": "ca",
    # Afrikaans
    "af": "af", "afrikaans": "af",
    # Albanian
    "sq": "sq", "albanian": "sq",
    # Belarusian
    "be": "be", "belarusian": "be",
    # Bengali
    "bn": "bn", "bengali": "bn", "bengalce": "bn",
    # Swahili
    "sw": "sw", "swahili": "sw",
    # Urdu
    "ur": "ur", "urdu": "ur",
    # Tagalog
    "tl": "tl", "tagalog": "tl", "filipince": "tl",
    # Icelandic
    "is": "is", "icelandic": "is", "izlandaca": "is",
}

_VALID = set(_LANG.values())

LANGS_TEXT = (
    "<b>🌐 Desteklenen Diller</b>\n\n"
    "<b>Avrupa:</b> tr en de fr es it pt ru pl nl sv no fi da el ro hu cs bg sr hr sk lt lv et\n\n"
    "<b>Asya:</b> ar ja zh ko fa hi th vi id ms tl ur bn\n\n"
    "<b>Diger:</b> uk az ka hy kk uz be sw af sq ca\n\n"
    "Kullanim: <code>.tr en</code> (Ingilizce)\n"
    "Kullanim: <code>.tr de Merhaba</code> (Almancaya cevir)\n"
    "Varsayilan: Turkce (<code>.tr</code>)"
)


def _resolve(s: str) -> str | None:
    s = s.lower().strip()
    if s in _LANG:
        return _LANG[s]
    if s in _VALID:
        return s
    return None


async def translate_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message

    if not TRANSLATE_OK:
        return await msg.reply_text(
            "deep-translator yuklu degil.\nKur: <code>pip install deep-translator</code>",
            parse_mode="HTML",
        )

    args   = list(context.args or [])
    target = "tr"   # default Turkish

    # Detect language from first arg
    if args:
        candidate = _resolve(args[0])
        if candidate:
            target = candidate
            args.pop(0)

    # Get text: remaining args OR replied message
    if args:
        text_to_tr = " ".join(args)
    elif msg.reply_to_message:
        r = msg.reply_to_message
        text_to_tr = r.text or r.caption or ""
    else:
        return await msg.reply_text(
            "Kullanim:\n"
            "• Mesaja reply at: <code>.tr [dil]</code>\n"
            "• Inline: <code>.tr [dil] [metin]</code>\n\n"
            "Dil listesi: /langs",
            parse_mode="HTML",
        )

    text_to_tr = text_to_tr.strip()
    if not text_to_tr:
        return await msg.reply_text("Cevrilecek metin yok.")

    try:
        translator = GoogleTranslator(source="auto", target=target)
        result     = translator.translate(text_to_tr)

        # Show flag/language name
        _FLAG = {
            "tr": "🇹🇷", "en": "🇬🇧", "de": "🇩🇪", "fr": "🇫🇷",
            "es": "🇪🇸", "it": "🇮🇹", "ru": "🇷🇺", "ar": "🇸🇦",
            "ja": "🇯🇵", "zh-CN": "🇨🇳", "ko": "🇰🇷", "pt": "🇵🇹",
            "nl": "🇳🇱", "pl": "🇵🇱", "uk": "🇺🇦", "fa": "🇮🇷",
            "hi": "🇮🇳", "az": "🇦🇿",
        }
        flag = _FLAG.get(target, "🌐")

        await msg.reply_text(
            f"{flag} <b>Ceviri ({target.upper()}):</b>\n\n{result}",
            parse_mode="HTML",
        )
    except Exception as e:
        await msg.reply_text(
            f"Ceviri basarisiz: {e}\n\n"
            "Not: Dil kodu dogru mu? Ornek: tr, en, de, fr, es"
        )


async def langs_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(LANGS_TEXT, parse_mode="HTML")


def register_translate_handlers(app):
    for cmd in ("tr", "translate", "cevir", "cevirici"):
        app.add_handler(CommandHandler(cmd, translate_cmd))
        app.add_handler(MessageHandler(filters.TEXT & dot_filter(cmd), translate_cmd))
    app.add_handler(CommandHandler("langs", langs_cmd))
    app.add_handler(MessageHandler(filters.TEXT & dot_filter("langs"), langs_cmd))
