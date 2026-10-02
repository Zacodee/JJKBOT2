"""Tests de la couche de présentation."""

import unittest

import discord

from jjkbot import config, theme


class _FakeAvatar:
    url = "https://exemple.test/avatar.png"


class _FakeUser:
    """Remplaçant minimal d’un utilisateur Discord pour les tests."""

    display_name = "Izouk"
    display_avatar = _FakeAvatar()


class ThemeRenderingTests(unittest.TestCase):
    def test_title_contient_le_libelle_et_le_repli_unicode(self):
        rendered = theme.title("profil", "Profil", None, suffix=": @izouk")

        self.assertTrue(rendered.startswith("📛"))
        self.assertIn("__Profil__", rendered)
        self.assertTrue(rendered.endswith(": @izouk"))

    def test_group_alterne_les_prefixes(self):
        blob = theme.group(
            ("identite", "Identité", "Zuruï"),
            ("age", "Âge", "1 an", "colon"),
        )
        lines = blob.splitlines()

        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith("│ ·"))
        self.assertTrue(lines[1].startswith("╰ ·"))
        self.assertIn('[Identité] → ["Zuruï"]', lines[0])
        self.assertIn("Âge : [1 an]", lines[1])

    def test_entry_remplace_les_valeurs_vides(self):
        self.assertIn('[Race] → ["Non renseigné"]', theme.entry("race", "Race", ""))

    def test_entry_unique_peut_porter_le_coude(self):
        self.assertTrue(theme.entry("race", "Race", "Fléau", last=True).startswith("╰ ·"))
        self.assertTrue(theme.entry("race", "Race", "Fléau").startswith("│ ·"))

    def test_blocks_separe_par_une_ligne_vide(self):
        blob = theme.blocks("a", None, "b")

        self.assertEqual(blob, "a\n\nb")

    def test_quote_block_avec_et_sans_citation(self):
        self.assertIn("Aucune citation", theme.quote_block(""))
        self.assertIn("Tricheur, menteur", theme.quote_block("Tricheur, menteur"))

    def test_quote_block_tronque_les_citations_longues(self):
        self.assertTrue(theme.quote_block("x" * 500).endswith("❞"))

    def test_truncate(self):
        self.assertEqual(theme.truncate("abcdef", 4), "abc…")
        self.assertEqual(theme.truncate("", 4), "")

    def test_progress_bar(self):
        bar = theme.progress_bar(3, 6, 10)

        self.assertEqual(len(bar), 10)
        self.assertIn("▰", bar)
        self.assertIn("▱", bar)
        self.assertEqual(theme.progress_bar(5, 0, 4), "▱▱▱▱")

    def test_bullet_list(self):
        self.assertEqual(theme.bullet_list(["a", "b"]), "• a\n• b")
        self.assertIn("Aucun renseignement", theme.bullet_list([]))

    def test_notice_embed_utilise_la_couleur_de_section(self):
        embed = theme.notice_embed(theme.SECTION_SUCCES, "succes", "Bien joué")

        self.assertIsInstance(embed, discord.Embed)
        self.assertEqual(embed.colour.value, theme.color(theme.SECTION_SUCCES))
        self.assertIn("Bien joué", embed.description)


class ThemePaletteTests(unittest.TestCase):
    def setUp(self):
        self.original = config.THEME

    def tearDown(self):
        config.THEME = self.original

    def test_theme_violet_par_defaut(self):
        config.THEME = "violet"

        self.assertEqual(theme.color(theme.SECTION_PROFIL), 0x8B5CF6)
        self.assertEqual(theme.palette().label, "Violet")

    def test_theme_noblesse(self):
        config.THEME = "noblesse"

        self.assertEqual(theme.color(theme.SECTION_PROFIL), 0x9A0A16)
        self.assertEqual(theme.color(theme.SECTION_ALERTE), 0xC9B458)

    def test_theme_inconnu_retombe_sur_le_violet(self):
        config.THEME = "turquoise"

        self.assertEqual(theme.color(theme.SECTION_PROFIL), 0x8B5CF6)

    def test_section_inconnue_utilise_la_couleur_neutre(self):
        config.THEME = "violet"

        self.assertEqual(theme.color("section-fantome"), theme.color(theme.SECTION_NEUTRE))


class ThemeBannerTests(unittest.TestCase):
    def setUp(self):
        self.original = config.BANNER_URL

    def tearDown(self):
        config.BANNER_URL = self.original

    def test_sans_banniere_un_seul_embed(self):
        config.BANNER_URL = None
        embed = theme.content_embed(theme.SECTION_PROFIL, "Titre")

        self.assertEqual(theme.with_banner(embed), [embed])
        self.assertIsNone(theme.banner_embed())

    def test_avec_banniere_deux_embeds(self):
        config.BANNER_URL = "https://exemple.test/banniere.png"
        embed = theme.content_embed(theme.SECTION_PROFIL, "Titre")
        embeds = theme.with_banner(embed)

        self.assertEqual(len(embeds), 2)
        self.assertEqual(embeds[0].image.url, "https://exemple.test/banniere.png")
        self.assertIs(embeds[1], embed)

    def test_content_embed_avec_auteur(self):
        embed = theme.content_embed(
            theme.SECTION_STATS,
            "Titre",
            description="Détail",
            footer="✦ pied",
            author=_FakeUser(),
        )

        self.assertEqual(embed.description, "Détail")
        self.assertEqual(embed.footer.text, "✦ pied")
        self.assertEqual(embed.author.name, "Izouk")
        self.assertEqual(embed.author.icon_url, "https://exemple.test/avatar.png")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
