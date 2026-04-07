"""
Translation: .tr [lang] (reply to a message)
Default target language: Turkish (tr)
Supports: .tr en, .tr de, .tr fr, .tr ar, etc.
Also: .translate [lang] [text] for inline translation
"""
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters

import re as re_mod

try:
    from deep_translator import GoogleTranslator
    TRANSLATE_AVAILABLE = True
except ImportError:
    TRANSLATE_AVAILABLE = False


LANG_ALIASES = {
    "tr": "tr",
    "turkce": "tr",
    "turkish": "tr",
    "en": "en",
    "english": "en",
    "ingilizce": "en",
    "de": "de",
    "german": "de",
    "almanca": "de",
    "fr": "fr",
    "french": "fr",
    "fransizca": "fr",
    "es": "es",
    "spanish": "es",
    "ispanyolca": "es",
    "ar": "ar",
    "arabic": "ar",
    "arapca": "ar",
    "ru": "ru",
    "russian": "ru",
    "rusca": "ru",
    "it": "it",
    "italian": "it",
    "italyanca": "it",
    "pt": "pt",
    "portuguese": "pt",
    "portekizce": "pt",
    "nl": "nl",
    "dutch": "nl",
    "jp": "ja",
    "ja": "ja",
    "japanese": "ja",
    "japonca": "ja",
    "zh": "zh-CN",
    "chinese": "zh-CN",
    "cince": "zh-CN",
    "ko": "ko",
    "korean": "ko",
    "korece": "ko",
    "fa": "fa",
    "persian": "fa",
    "farsca": "fa",
    "uk": "uk",
    "ukrainian": "uk",
    "ukraynaca": "uk",
}


def _dot_filter(cmd: str):
    return filters.Regex(rf"^[./!]{re_mod.escape(cmd)}(\s|$)")


def _resolve_lang(arg: str) -> str:
    return LANG_ALIASES.get(arg.lower(), arg.lower())


async def translate_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message

    if not TRANSLATE_AVAILABLE:
        await msg.reply_text(
            "Ceviri modulu yuklu degil. `pip install deep-translator` calistir.",
            parse_mode="Markdown",
        )
        return

    args = context.args or []
    target_lang = "tr"

    # Determine target language
    if args and not msg.reply_to_message:
        # .tr lang some text to translate
        candidate = _resolve_lang(args[0])
        target_lang = candidate
        text_to_translate = " ".join(args[1:])
    elif args and msg.reply_to_message:
        # .tr lang (replying to a message)
        target_lang = _resolve_lang(args[0])
        text_to_translate = None
    else:
        text_to_translate = None

    # Get text from reply if not inline
    if text_to_translate is None:
        if msg.reply_to_message:
            source_msg = msg.reply_to_message
            text_to_translate = (
                source_msg.text or source_msg.caption or ""
            )
        else:
            await msg.reply_text(
                "Nasil kullanilir:\n"
                "• Bir mesaja reply at: .tr [dil]\n"
                "• Inline: .tr [dil] [metin]\n"
                "• Varsayilan dil: Turkce\n\n"
                "Ornek: .tr en Merhaba dunya"
            )
            return

    if not text_to_translate.strip():
        await msg.reply_text("Cevrilecek metin bulunamadi.")
        return

    try:
        translator = GoogleTranslator(source="auto", target=target_lang)
        translated = translator.translate(text_to_translate)
        await msg.reply_text(
            f"<b>Ceviri ({target_lang.upper()}):</b>\n{translated}",
            parse_mode="HTML",
        )
    except Exception as e:
        await msg.reply_text(f"Ceviri basarisiz: {e}")


def register_translate_handlers(app):
    for cmd in ("tr", "translate", "cevir"):
        app.add_handler(CommandHandler(cmd, translate_cmd))
        app.add_handler(
            MessageHandler(filters.TEXT & _dot_filter(cmd), translate_cmd)
        )
