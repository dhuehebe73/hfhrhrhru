"""
Translation: .tr [lang] (reply) | .tr [lang] [text]
Default: Turkish. Supports 50+ languages.
"""
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from utils import dot_filter

try:
    from deep_translator import GoogleTranslator, single_detection
    TRANSLATE_OK = True
except ImportError:
    TRANSLATE_OK = False

_ALIASES = {
    "tr": "tr", "turkce": "tr", "turkish": "tr",
    "en": "en", "english": "en", "ingilizce": "en",
    "de": "de", "german": "de", "almanca": "de",
    "fr": "fr", "french": "fr", "fransizca": "fr",
    "es": "es", "spanish": "es", "ispanyolca": "es",
    "it": "it", "italian": "it", "italyanca": "it",
    "pt": "pt", "portuguese": "pt", "portekizce": "pt",
    "ru": "ru", "russian": "ru", "rusca": "ru",
    "ar": "ar", "arabic": "ar", "arapca": "ar",
    "ja": "ja", "jp": "ja", "japanese": "ja", "japonca": "ja",
    "zh": "zh-CN", "cn": "zh-CN", "chinese": "zh-CN", "cince": "zh-CN",
    "ko": "ko", "korean": "ko", "korece": "ko",
    "fa": "fa", "persian": "fa", "farsca": "fa",
    "uk": "uk", "ukrainian": "uk", "ukraynaca": "uk",
    "pl": "pl", "polish": "pl", "polonyaca": "pl",
    "nl": "nl", "dutch": "nl", "hollandaca": "nl",
    "sv": "sv", "swedish": "sv", "isvecce": "sv",
    "no": "no", "norwegian": "no", "norvecce": "no",
    "fi": "fi", "finnish": "fi", "fince": "fi",
    "da": "da", "danish": "da", "danimarkaca": "da",
    "el": "el", "greek": "el", "rumca": "el",
    "he": "he", "hebrew": "he", "ibranice": "he",
    "hi": "hi", "hindi": "hi",
    "id": "id", "indonesian": "id", "endonezce": "id",
    "ms": "ms", "malay": "ms", "malezce": "ms",
    "th": "th", "thai": "th", "tayca": "th",
    "vi": "vi", "vietnamese": "vi", "vietnamca": "vi",
    "ro": "ro", "romanian": "ro", "rumence": "ro",
    "hu": "hu", "hungarian": "hu", "macarca": "hu",
    "cs": "cs", "czech": "cs", "cekce": "cs",
    "bg": "bg", "bulgarian": "bg", "bulgarca": "bg",
    "sr": "sr", "serbian": "sr", "sirpca": "sr",
    "hr": "hr", "croatian": "hr", "hirvatca": "hr",
    "sk": "sk", "slovak": "sk", "slovakca": "sk",
    "lt": "lt", "lithuanian": "lt", "litvanca": "lt",
    "lv": "lv", "latvian": "lv", "letonca": "lv",
    "et": "et", "estonian": "et", "estonca": "et",
    "az": "az", "azerbaijani": "az", "azerbaycanca": "az",
    "ka": "ka", "georgian": "ka", "gurcuce": "ka",
    "hy": "hy", "armenian": "hy", "ermenice": "hy",
    "kk": "kk", "kazakh": "kk", "kazakca": "kk",
    "uz": "uz", "uzbek": "uz", "ozbekce": "uz",
}


def _resolve_lang(s: str) -> str:
    return _ALIASES.get(s.lower(), s.lower())


async def translate_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message

    if not TRANSLATE_OK:
        return await msg.reply_text(
            "Ceviri modulu eksik. Calistir:\n`pip install deep-translator`",
            parse_mode="Markdown",
        )

    args = context.args or []
    target = "tr"
    text_to_tr = None

    if args:
        candidate = _resolve_lang(args[0])
        if candidate in GoogleTranslator().get_supported_languages(as_dict=True).values() \
                or candidate in _ALIASES.values():
            target = candidate
            args = args[1:]
        else:
            # First arg might be text, not a lang
            pass

    if args:
        text_to_tr = " ".join(args)
    elif msg.reply_to_message:
        r = msg.reply_to_message
        text_to_tr = r.text or r.caption or ""

    if not text_to_tr:
        return await msg.reply_text(
            "Nasil kullanilir:\n"
            "• Bir mesaja reply at: .tr [dil]\n"
            "• Inline: .tr [dil] [metin]\n\n"
            "Dil ornekleri: tr en de fr es ar ru ja zh ko\n"
            "Varsayilan: Turkce"
        )

    try:
        translator = GoogleTranslator(source="auto", target=target)
        result = translator.translate(text_to_tr.strip())

        # Try to detect source language
        try:
            src = GoogleTranslator(source="auto", target="en").translate(
                text_to_tr[:30]
            )
            detected = ""
        except Exception:
            detected = ""

        await msg.reply_text(
            f"🌐 <b>Ceviri ({target.upper()}):</b>\n{result}",
            parse_mode="HTML",
        )
    except Exception as e:
        await msg.reply_text(f"Ceviri basarisiz: {e}")


async def langs_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    common = [
        "tr - Turkce", "en - Ingilizce", "de - Almanca",
        "fr - Fransizca", "es - Ispanyolca", "ar - Arapca",
        "ru - Rusca", "ja - Japonca", "zh - Cince",
        "ko - Korece", "it - Italyanca", "pt - Portekizce",
        "fa - Farsca", "uk - Ukraynaca", "hi - Hintce",
    ]
    await update.effective_message.reply_text(
        "<b>Desteklenen Diller (ornek):</b>\n" + "\n".join(f"  {l}" for l in common) +
        "\n\n50+ dil destekleniyor. ISO kodu kullan.",
        parse_mode="HTML",
    )


def register_translate_handlers(app):
    for cmd in ("tr", "translate", "cevir"):
        app.add_handler(CommandHandler(cmd, translate_cmd))
        app.add_handler(MessageHandler(filters.TEXT & dot_filter(cmd), translate_cmd))
    app.add_handler(CommandHandler("langs", langs_cmd))
    app.add_handler(MessageHandler(filters.TEXT & dot_filter("langs"), langs_cmd))
