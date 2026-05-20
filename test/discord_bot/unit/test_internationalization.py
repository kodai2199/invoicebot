from discord_bot import internationalization as i18n


class FakeTranslator:
    def __init__(self, singular_prefix: str = "tr"):
        self.singular_prefix = singular_prefix

    def gettext(self, text: str) -> str:
        return f"{self.singular_prefix}:{text}"

    def ngettext(self, singular: str, plural: str, n: int) -> str:
        return singular if n == 1 else plural


def test_set_user_locale_exact_match(monkeypatch):
    monkeypatch.setattr(i18n, "TRANSLATIONS", {"it-IT": FakeTranslator()})

    i18n.set_user_locale("it-IT")

    assert i18n._current_locale.get() == "it-IT"


def test_set_user_locale_falls_back_to_base_lang_dash(monkeypatch):
    monkeypatch.setattr(i18n, "TRANSLATIONS", {"it": FakeTranslator()})

    i18n.set_user_locale("it-CH")

    assert i18n._current_locale.get() == "it"


def test_set_user_locale_falls_back_to_base_lang_underscore(monkeypatch):
    monkeypatch.setattr(i18n, "TRANSLATIONS", {"it": FakeTranslator()})

    i18n.set_user_locale("it_IT")

    assert i18n._current_locale.get() == "it"


def test_set_user_locale_falls_back_to_en(monkeypatch):
    monkeypatch.setattr(i18n, "TRANSLATIONS", {})

    result = i18n.set_user_locale("zz-ZZ")

    assert i18n._current_locale.get() == "en"
    assert result == "en"


def test_translate_with_selected_locale(monkeypatch):
    monkeypatch.setattr(
        i18n,
        "TRANSLATIONS",
        {"it": FakeTranslator("it"), "en-US": FakeTranslator("en")},
    )
    i18n._current_locale.set("it")

    assert i18n._("hello") == "it:hello"


def test_translate_with_missing_locale_uses_raw_text(monkeypatch):
    monkeypatch.setattr(i18n, "TRANSLATIONS", {})
    i18n._current_locale.set("missing")

    assert i18n._("hello") == "hello"


def test_ngettext_with_translator(monkeypatch):
    monkeypatch.setattr(
        i18n,
        "TRANSLATIONS",
        {"en": FakeTranslator(), "en-US": FakeTranslator()},
    )
    i18n._current_locale.set("en")

    assert i18n.ngettext("invoice", "invoices", 1) == "invoice"
    assert i18n.ngettext("invoice", "invoices", 2) == "invoices"


def test_ngettext_without_translator(monkeypatch):
    monkeypatch.setattr(i18n, "TRANSLATIONS", {})
    i18n._current_locale.set("en")

    assert i18n.ngettext("invoice", "invoices", 1) == "invoice"
    assert i18n.ngettext("invoice", "invoices", 3) == "invoices"
