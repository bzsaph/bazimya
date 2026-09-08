"""The translation layer.

Run with:  python3 -m unittest discover tests
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bazimya.support import lang  # noqa: E402


class LocaleDetectionTest(unittest.TestCase):
    def setUp(self):
        self._environ = dict(os.environ)

        for name in ("BAZIMYA_LANG", "LC_ALL", "LC_MESSAGES", "LANG"):
            os.environ.pop(name, None)

        lang.reset()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._environ)
        lang.reset()

    def test_defaults_to_english(self):
        self.assertEqual(lang.locale(), "en")

    def test_explicit_variable_wins(self):
        os.environ["BAZIMYA_LANG"] = "rw"
        os.environ["LANG"] = "en_US.UTF-8"

        self.assertEqual(lang.locale(), "rw")

    def test_reads_the_system_locale(self):
        os.environ["LANG"] = "rw_RW.UTF-8"

        self.assertEqual(lang.locale(), "rw")

    def test_iso_639_3_is_understood(self):
        os.environ["LANG"] = "kin_RW"

        self.assertEqual(lang.locale(), "rw")

    def test_an_unsupported_language_falls_back(self):
        os.environ["BAZIMYA_LANG"] = "fr"

        self.assertEqual(lang.locale(), "en")

    def test_set_locale_rejects_nonsense(self):
        self.assertEqual(lang.set_locale("klingon"), "en")


class TranslationTest(unittest.TestCase):
    def setUp(self):
        lang.set_locale("rw")

    def tearDown(self):
        lang.reset()

    def test_translates_a_known_sentence(self):
        self.assertEqual(lang.translate("Next:"), "Ibikurikira:")

    def test_leaves_an_unknown_sentence_alone(self):
        text = "Something nobody has translated yet."

        self.assertEqual(lang.translate(text), text)

    def test_keeps_surrounding_whitespace(self):
        self.assertEqual(lang.translate("  Next:"), "  Ibikurikira:")

    def test_fills_placeholders_after_translating(self):
        self.assertEqual(
            lang.translate("Scaffolded {} files.", 99), "Hakozwe dosiye 99."
        )

    def test_recovers_a_sentence_already_rendered(self):
        # Commands call .format() themselves, so the catalogue has to match
        # what actually reached the output layer.
        self.assertEqual(
            lang.translate("  Scaffolded 99 files."), "  Hakozwe dosiye 99."
        )

    def test_a_rendered_sentence_with_two_values(self):
        self.assertEqual(
            lang.translate("Seeder [Foo] was not found at /tmp/foo.py"),
            "Seeder [Foo] ntiyabonetse muri /tmp/foo.py",
        )

    def test_named_placeholders(self):
        self.assertEqual(
            lang.translate("The {field} field is required.", field="izina"),
            "Umwanya izina ugomba kuzuzwa.",
        )

    def test_english_is_left_exactly_as_written(self):
        lang.set_locale("en")

        self.assertEqual(lang.translate("Next:"), "Next:")
        self.assertEqual(
            lang.translate("Scaffolded {} files.", 4), "Scaffolded 4 files."
        )

    def test_empty_and_non_string_input_survives(self):
        self.assertEqual(lang.translate(""), "")
        self.assertEqual(lang.translate("   "), "   ")
        self.assertEqual(lang.translate(None), None)

    def test_a_broken_translation_does_not_raise(self):
        # A catalogue entry with the wrong placeholders must degrade to English
        # rather than blow up inside an error message.
        lang._catalogues["rw"] = dict(lang.catalogue("rw"))
        lang._catalogues["rw"]["Broken {} thing"] = "Bad {} {} entry"
        lang._patterns_cache.pop("rw", None)

        self.assertEqual(lang.translate("Broken {} thing", "one"), "Broken one thing")


class ValidationMessageTest(unittest.TestCase):
    def tearDown(self):
        lang.reset()

    def test_validator_errors_are_translated(self):
        from bazimya.validation import Validator

        lang.set_locale("rw")
        validator = Validator({"email": "nope"}, {"email": "required|email"})
        validator.passes()

        self.assertEqual(
            validator.errors["email"], ["email igomba kuba imeyili nyayo."]
        )

    def test_a_custom_message_is_never_touched(self):
        from bazimya.validation import Validator

        lang.set_locale("rw")
        validator = Validator(
            {"email": ""},
            {"email": "required"},
            {"email.required": "Andika imeyili yawe."},
        )
        validator.passes()

        self.assertEqual(validator.errors["email"], ["Andika imeyili yawe."])


class CatalogueTest(unittest.TestCase):
    def tearDown(self):
        lang.reset()

    def test_every_entry_is_a_string_pair(self):
        from bazimya.lang import rw

        for source, target in rw.MESSAGES.items():
            self.assertIsInstance(source, str)
            self.assertIsInstance(target, str)
            self.assertTrue(target.strip(), "empty translation for %r" % source)

    def test_placeholder_counts_line_up(self):
        """A translation may drop a placeholder but never invent one."""
        import re

        from bazimya.lang import rw

        placeholder = re.compile(r"\{[^{}]*\}")

        for source, target in rw.MESSAGES.items():
            extra = set(placeholder.findall(target)) - set(placeholder.findall(source))

            self.assertFalse(
                extra, "%r introduces %s which the English does not have" % (source, extra)
            )


if __name__ == "__main__":
    unittest.main()
