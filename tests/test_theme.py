"""Tests de la couche de présentation."""

import tempfile
import unittest
import unittest.mock
from pathlib import Path

import discord

from jjkbot import config, theme


class _FakeAvatar:
    url = "https://exemple.test/avatar.png"


class _FakeUser:
    """Remplaçant minimal d’un utilisateur Discord pour les tests."""

    display_name = "Izouk"
    display_avatar = _FakeAvatar()


class ThemeRenderingTests(unittest.TestCase):
    def test_title_est_une_ligne_de_titre_markdown(self):
        rendered = theme.title("profil", "Profil", None, suffix=" : @izouk")

        self.assertTrue(rendered.startswith("## 📛"))
        self.assertIn("Profil", rendered)
        self.assertTrue(rendered.endswith(": @izouk"))

    def test_row_affiche_une_paire_sur_deux_lignes_en_titre(self):
        rendered = theme.row(
            ("identite", "Identité", "Zuruï"),
            ("age", "Âge", "1 an"),
        )
        lines = rendered.splitlines()

        # Libellés en titre `###` (plus gros) avec un large espace entre les
        # deux champs, valeurs en `code` alignées dessous.
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith("### "))
        self.assertIn("__Identité__", lines[0])
        self.assertIn("__Âge__", lines[0])
        self.assertIn(theme.PAIR_GAP + "•" + theme.PAIR_GAP, lines[0])
        self.assertIn("`Zuruï`", lines[1])
        self.assertIn("`1 an`", lines[1])
        # L’espace est fait d’em-spaces, que le Markdown ne compresse pas.
        self.assertIn(theme.EM_SPACE, lines[0])
        self.assertNotIn("  •  ", lines[0])

    def test_field_label_est_un_titre_markdown_souligne(self):
        self.assertEqual(theme.field_label("race", "Race"), "### 🧬 __Race__")

    def test_entry_remplace_les_valeurs_vides(self):
        self.assertIn("**Race :** `Non renseigné`", theme.entry("race", "Race", ""))

    def test_entry_neutralise_les_apostrophes_inversees_de_la_valeur(self):
        rendered = theme.entry("race", "Race", "Fle`au")

        self.assertEqual(rendered.count("`"), 2)
        self.assertIn("Fle’au", rendered)

    def test_blocks_separe_par_une_ligne_vide(self):
        blob = theme.blocks("a", None, "b")

        self.assertEqual(blob, "a\n\nb")

    def test_heading_markdown(self):
        self.assertEqual(theme.heading("Titre", 2), "## Titre")
        self.assertEqual(theme.heading("Titre", 9), "### Titre")
        self.assertEqual(theme.heading("Titre", 0), "# Titre")

    def test_code_block_markdown(self):
        rendered = theme.code_block(["ligne 1", "ligne 2"])

        self.assertTrue(rendered.startswith("```"))
        self.assertTrue(rendered.endswith("```"))
        self.assertIn("ligne 1\nligne 2", rendered)

    def test_mono_table_aligne_les_colonnes(self):
        rendered = theme.mono_table(
            [("Force", "10", "▰▱▱▱▱▱▱▱▱▱"), ("Résistance", "8", "▰▱▱▱▱▱▱▱▱▱")]
        )

        self.assertTrue(rendered.startswith("```"))
        lines = rendered.strip("`").strip().splitlines()
        self.assertEqual(lines[0].index("10"), lines[1].index("8 "))
        self.assertEqual(lines[0].index("▰"), lines[1].index("▰"))

    def test_mono_table_vide(self):
        self.assertEqual(theme.mono_table([]), "")

    def test_fallback_renvoie_le_repli_unicode(self):
        self.assertEqual(theme.fallback("profil"), "📛")
        self.assertEqual(theme.fallback("cle_inconnue"), "❔")

    def test_quote_block_avec_et_sans_citation(self):
        self.assertIn("Aucune citation", theme.quote_block(""))
        self.assertIn("Tricheur, menteur", theme.quote_block("Tricheur, menteur"))

    def test_quote_block_tronque_les_citations_longues(self):
        self.assertTrue(theme.quote_block("x" * 500).endswith("❞"))

    def test_quote_block_tient_sur_une_seule_ligne(self):
        rendered = theme.quote_block("Je suis tuff")

        self.assertEqual(len(rendered.splitlines()), 1)
        self.assertIn("**Citation**", rendered)
        self.assertIn("❝ *Je suis tuff* ❞", rendered)

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

    @staticmethod
    def _missing_banner_path() -> Path:
        """Chemin d’image de bannière volontairement absent."""
        return Path(tempfile.gettempdir()) / "banniere_jjk_inexistante.png"

    def test_sans_banniere_un_seul_embed(self):
        config.BANNER_URL = None
        embed = theme.content_embed(theme.SECTION_PROFIL, "Titre")

        with unittest.mock.patch.object(config, "BANNER_PATH", self._missing_banner_path()):
            self.assertEqual(theme.with_banner(embed), [embed])
            self.assertIsNone(theme.banner_embed())

    def test_banniere_par_url_en_trois_embeds(self):
        config.BANNER_URL = "https://exemple.test/banniere.png"
        embed = theme.content_embed(theme.SECTION_PROFIL, "Titre")

        with unittest.mock.patch.object(config, "BANNER_PATH", self._missing_banner_path()):
            files: list[discord.File] = []
            embeds = theme.with_banner(embed, files)

        # Bannière en tête, contenu au milieu, même bannière en pied.
        self.assertEqual(len(embeds), 3)
        self.assertEqual(embeds[0].image.url, "https://exemple.test/banniere.png")
        self.assertIs(embeds[1], embed)
        self.assertEqual(embeds[2].image.url, embeds[0].image.url)
        self.assertEqual(files, [])

    def test_banniere_locale_jointe_au_message(self):
        config.BANNER_URL = None
        embed = theme.content_embed(theme.SECTION_PROFIL, "Titre")

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "banniere_jjk.png"
            path.write_bytes(b"image")
            with unittest.mock.patch.object(config, "BANNER_PATH", path):
                files: list[discord.File] = []
                embeds = theme.with_banner(embed, files)

            # Chaque bannière a SON attachment : un fichier partagé par deux
            # embeds laisserait l’un des deux sur l’image floutée de
            # remplacement (fermée avant de supprimer le dossier temporaire).
            self.assertEqual(len(embeds), 3)
            self.assertEqual(embeds[0].image.url, "attachment://banniere_jjk.png")
            self.assertEqual(embeds[2].image.url, "attachment://banniere_jjk_fin.png")
            self.assertEqual(len(files), 2)
            self.assertEqual(files[0].filename, "banniere_jjk.png")
            self.assertEqual(files[1].filename, "banniere_jjk_fin.png")
            for file_ in files:
                file_.close()

    def test_banniere_locale_sans_liste_de_fichiers_renvoie_none(self):
        # Sans `files`, l’image locale ne peut pas être jointe au message :
        # on préfère ne pas afficher de bannière qu’un lien cassé.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "banniere_jjk.png"
            path.write_bytes(b"image")
            with unittest.mock.patch.object(config, "BANNER_PATH", path):
                self.assertIsNone(theme.banner_embed())

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
