"""Tests du nuancier de couleurs et de l’analyse d’un code hexadécimal."""

import unittest

from jjkbot.content import colors


class ParseHexTests(unittest.TestCase):
    def test_formes_acceptees(self):
        for text in ("#8B5CF6", "8b5cf6", "0x8B5CF6", "  #8b5cf6  "):
            self.assertEqual(colors.parse_hex(text), 0x8B5CF6, text)

    def test_forme_courte_doublee(self):
        # `#abc` équivaut à `#aabbcc`, comme en CSS.
        self.assertEqual(colors.parse_hex("#abc"), 0xAABBCC)

    def test_invalides(self):
        for text in ("", "#12", "zzzzzz", "#GGGGGG", None, "0x", "#1234567"):
            self.assertIsNone(colors.parse_hex(text), repr(text))


class ResolveTests(unittest.TestCase):
    def test_nom_du_nuancier(self):
        self.assertEqual(colors.resolve("Rubis"), colors.NAMED_COLORS["Rubis"])

    def test_insensible_casse_accents_et_separateurs(self):
        self.assertEqual(colors.resolve("rubis"), colors.NAMED_COLORS["Rubis"])
        self.assertEqual(colors.resolve("AIGUE-MARINE"), colors.NAMED_COLORS["Aigue-marine"])
        self.assertEqual(colors.resolve("aigue marine"), colors.NAMED_COLORS["Aigue-marine"])
        self.assertEqual(colors.resolve("émeraude"), colors.NAMED_COLORS["Émeraude"])

    def test_hex_reconnu(self):
        self.assertEqual(colors.resolve("#8B5CF6"), 0x8B5CF6)
        self.assertEqual(colors.resolve("#000000"), 0)

    def test_inconnu(self):
        self.assertIsNone(colors.resolve("zorglub"))
        self.assertIsNone(colors.resolve(""))

    def test_nuancier_varié_et_sans_doublon(self):
        self.assertGreaterEqual(len(colors.NAMED_COLORS), 20)
        self.assertEqual(len(set(colors.NAMED_COLORS.values())), len(colors.NAMED_COLORS))

    def test_hex_label(self):
        self.assertEqual(colors.hex_label(0x8B5CF6), "#8B5CF6")
        self.assertEqual(colors.hex_label(0), "#000000")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
