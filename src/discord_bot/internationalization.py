import contextvars
import gettext
import os
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parent

_current_locale: contextvars.ContextVar[str] = contextvars.ContextVar(
    "current_locale", default="en"
)
TRANSLATIONS = {}
LOCALES_DIR = MODULE_DIR / "locales"

if os.path.exists(LOCALES_DIR):
    for locale in os.listdir(LOCALES_DIR):
        # Translation domains are named 'discord_bot' (e.g.,
        # locales/es/LC_MESSAGES/discord_bot.mo)
        try:
            TRANSLATIONS[locale] = gettext.translation(
                domain="discord_bot",
                localedir=LOCALES_DIR,
                languages=[locale],
                fallback=True,
            )
        except Exception:
            pass


def set_user_locale(locale: str) -> None:
    """Call this to lock in the language.

    Normalizes locales. If 'it-IT' doesn't exist, checks for 'it'.
    Falls back to 'en-US' if nothing matches.
    """
    # 1. Direct exact match (e.g., if you have an explicit 'it-IT' folder)
    if locale in TRANSLATIONS:
        _current_locale.set(locale)
        return

    # 2. Base language fallback (e.g., convert 'it-IT' or 'it-CH' to 'it')
    base_lang = locale.split("-")[0]
    if base_lang in TRANSLATIONS:
        _current_locale.set(base_lang)
        return

    base_lang = locale.split("_")[0]
    if base_lang in TRANSLATIONS:
        _current_locale.set(base_lang)
        return

    # 3. Ultimate global fallback
    _current_locale.set("en")
    return "en"


def _(text: str) -> str:
    """The universal singular translator function."""
    locale = _current_locale.get()
    # Fetch translation object, fallback to raw text if missing
    translator = TRANSLATIONS.get(locale, TRANSLATIONS.get("en-US"))
    if translator:
        return translator.gettext(text)
    return text


def ngettext(singular: str, plural: str, n: int) -> str:
    """The universal plural translator function."""
    locale = _current_locale.get()
    translator = TRANSLATIONS.get(locale, TRANSLATIONS.get("en-US"))
    if translator:
        return translator.ngettext(singular, plural, n)
    return singular if n == 1 else plural
