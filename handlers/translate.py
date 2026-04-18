from telegram import Update
from telegram.ext import ContextTypes, MessageHandler
from deep_translator import GoogleTranslator
from utils import dcmd

_LANG = {
    "tr":"turkish","en":"english","de":"german","fr":"french","es":"spanish",
    "it":"italian","pt":"portuguese","ru":"russian","ar":"arabic","zh":"chinese(simplified)",
    "ja":"japanese","ko":"korean","nl":"dutch","pl":"polish","sv":"swedish",
    "no":"norwegian","da":"danish","fi":"finnish","cs":"czech","sk":"slovak",
    "ro":"romanian","hu":"hungarian","bg":"bulgarian","uk":"ukrainian","el":"greek",
    "he":"hebrew","fa":"persian","hi":"hindi","bn":"bengali","ur":"urdu",
    "vi":"vietnamese","th":"thai","id":"indonesian","ms":"malay","tl":"tagalog",
    "af":"afrikaans","sq":"albanian","hy":"armenian","az":"azerbaijani","eu":"basque",
    "be":"belarusian","ca":"catalan","hr":"croatian","et":"estonian","gl":"galician",
    "ka":"georgian","is":"icelandic","ga":"irish","lv":"latvian","lt":"lithuanian",
    "mk":"macedonian","mt":"maltese","sr":"serbian","sl":"slovenian","sw":"swahili",
    "cy":"welsh","eo":"esperanto","la":"latin",
}

_LANG_NAMES = {v: k for k, v in _LANG.items()}


def _resolve_lang(token: str) -> str | None:
    t = token.lower().strip()
    if t in _LANG: return t
    if t in _LANG_NAMES: return _LANG_NAMES[t]
    return None


async def tr_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    args = ctx.args or []

    target = "tr"
    text_to_translate = None

    if args:
        resolved = _resolve_lang(args[0])
        if resolved:
            target = resolved
            extra = " ".join(args[1:])
        else:
            extra = " ".join(args)

        if extra:
            text_to_translate = extra

    if not text_to_translate and msg.reply_to_message:
        text_to_translate = msg.reply_to_message.text or msg.reply_to_message.caption

    if not text_to_translate:
        await msg.reply_text(
            "Kullanım: /tr [dil] <metin> veya bir mesajı yanıtla\n"
            "Örnek: /tr en Merhaba\n"
            "Diller: " + ", ".join(sorted(_LANG.keys()))); return

    try:
        result = GoogleTranslator(source="auto", target=target).translate(text_to_translate)
        flag = _lang_flag(target)
        await msg.reply_text(f"{flag} <b>{target.upper()}</b>: {result}", parse_mode="HTML")
    except Exception as e:
        await msg.reply_text(f"Çeviri hatası: {e}")


def _lang_flag(lang: str) -> str:
    flags = {
        "tr":"🇹🇷","en":"🇬🇧","de":"🇩🇪","fr":"🇫🇷","es":"🇪🇸","it":"🇮🇹",
        "pt":"🇵🇹","ru":"🇷🇺","ar":"🇸🇦","zh":"🇨🇳","ja":"🇯🇵","ko":"🇰🇷",
        "nl":"🇳🇱","pl":"🇵🇱","uk":"🇺🇦","el":"🇬🇷","he":"🇮🇱","fa":"🇮🇷",
        "hi":"🇮🇳","vi":"🇻🇳","th":"🇹🇭","id":"🇮🇩",
    }
    return flags.get(lang, "🌐")


async def langs_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    pairs = ", ".join(f"{k}({v[:3]})" for k, v in sorted(_LANG.items()))
    await update.effective_message.reply_text(f"🌐 Desteklenen diller:\n{pairs}")


def register(app):
    app.add_handler(MessageHandler(dcmd("tr"), tr_cmd), group=10)
    app.add_handler(MessageHandler(dcmd("translate"), tr_cmd), group=10)
    app.add_handler(MessageHandler(dcmd("langs"), langs_cmd), group=10)
