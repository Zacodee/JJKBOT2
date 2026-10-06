"""Tests de la Renaissance en Esprit Vengeur : règles, catalogue, embed, envoi."""

from __future__ import annotations

import tempfile
import unittest
import unittest.mock
from pathlib import Path
from types import SimpleNamespace

import discord

from jjkbot import config, theme
from jjkbot.content import renaissance as rules
from jjkbot.emojis import DEFAULT_CATALOG, DISPLAY_ORDER, load_catalog
from jjkbot.views import renaissance as renaissance_views

# Clés du catalogue utilisées par l’embed de résultat.
RENAISSANCE_KEYS = (
    "renaissance",
    "renaissance_rate",
    "renaissance_tentative",
    "renaissance_chance",
)


class FakeEmoji:
    """Emoji de serveur factice, rendu comme Discord le ferait."""

    def __init__(self, name: str, emoji_id: int, animated: bool = False):
        self.name = name
        self.id = emoji_id
        self.animated = animated

    def __str__(self) -> str:
        return f"<{'a' if self.animated else ''}:{self.name}:{self.id}>"


class FakeGuild:
    """Serveur factice portant les emojis de la Renaissance."""

    id = 4242
    emojis = [
        FakeEmoji("jjk_renaissance", 911),
        FakeEmoji("jjk_renaissance_tentative", 912),
        FakeEmoji("jjk_renaissance_chance", 913),
    ]


class RenaissanceRulesTests(unittest.TestCase):
    def test_seuils_par_situation(self):
        self.assertEqual(rules.threshold("base"), 5)
        self.assertEqual(rules.threshold("ressentiment"), 10)
        self.assertEqual(rules.threshold("rival"), 15)

    def test_situation_inconnue_retombe_sur_la_base(self):
        self.assertEqual(rules.threshold("inconnue"), rules.threshold("base"))
        self.assertEqual(rules.get_situation(None).id, "base")

    def test_tirage_dun_de_de_un_a_cent(self):
        seen = {}

        def fake_randint(low, high):
            seen["bornes"] = (low, high)
            return 37

        self.assertEqual(rules.roll(randint=fake_randint), 37)
        self.assertEqual(seen["bornes"], (1, 100))

    def test_reussite_si_le_de_est_inferieur_ou_egal_au_seuil(self):
        self.assertTrue(rules.success(1, "base"))
        self.assertTrue(rules.success(5, "base"))
        self.assertFalse(rules.success(6, "base"))

    def test_le_seuil_monte_avec_la_situation(self):
        self.assertFalse(rules.success(10, "base"))
        self.assertTrue(rules.success(10, "ressentiment"))
        self.assertFalse(rules.success(15, "ressentiment"))
        self.assertTrue(rules.success(15, "rival"))
        # Un tirage moyen ne réussit que dans le cas du rival.
        self.assertFalse(rules.success(12, "base"))
        self.assertFalse(rules.success(12, "ressentiment"))
        self.assertTrue(rules.success(12, "rival"))

    def test_de_invalide_ne_reussit_pas(self):
        self.assertFalse(rules.success("beaucoup", "base"))


class RenaissanceCatalogTests(unittest.TestCase):
    def test_cles_presentes_dans_le_catalogue_et_laffichage(self):
        for key in RENAISSANCE_KEYS:
            with self.subTest(key=key):
                self.assertIn(key, DEFAULT_CATALOG)
                self.assertIn(key, DISPLAY_ORDER)

    def test_noms_des_emojis_a_creer_sur_le_serveur(self):
        self.assertEqual(DEFAULT_CATALOG["renaissance"].name, "jjk_renaissance")
        self.assertEqual(DEFAULT_CATALOG["renaissance_rate"].name, "jjk_renaissance_rate")
        self.assertEqual(
            DEFAULT_CATALOG["renaissance_tentative"].name, "jjk_renaissance_tentative"
        )
        self.assertEqual(DEFAULT_CATALOG["renaissance_chance"].name, "jjk_renaissance_chance")

    def test_config_emojis_json_liste_les_memes_cles(self):
        catalog = load_catalog(config.EMOJIS_FILE)
        for key in RENAISSANCE_KEYS:
            with self.subTest(key=key):
                self.assertEqual(catalog[key].name, DEFAULT_CATALOG[key].name)
                self.assertEqual(catalog[key].fallback, DEFAULT_CATALOG[key].fallback)


class RenaissanceEmbedTests(unittest.TestCase):
    """Embed de résultat, avec des images locales factices."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.ok_path = root / "renaissance_ok.png"
        self.ko_path = root / "renaissance_ko.png"
        self.ok_path.write_bytes(b"\x89PNG")
        self.ko_path.write_bytes(b"\x89PNG")

        self.patches = [
            unittest.mock.patch.object(config, "RENAISSANCE_OK_PATH", self.ok_path),
            unittest.mock.patch.object(config, "RENAISSANCE_KO_PATH", self.ko_path),
            unittest.mock.patch.object(config, "RENAISSANCE_OK_URL", None),
            unittest.mock.patch.object(config, "RENAISSANCE_KO_URL", None),
        ]
        for patch in self.patches:
            patch.start()

    def tearDown(self):
        for patch in reversed(self.patches):
            patch.stop()
        self.directory.cleanup()

    def test_reussite_annonce_lesprit_vengeur(self):
        files: list = []
        embed = renaissance_views.build_renaissance_embed(True, 4, "base", None, files)

        self.assertIn("Renaissance en Esprit Vengeur", embed.title)
        self.assertNotIn("<:", embed.title)
        self.assertIn("Esprit Vengeur", embed.description)
        self.assertIn("**Réussit**", embed.description)
        self.assertIn("`4` ≤ seuil `5`", embed.description)
        self.assertIn("Mort sans circonstance particulière", embed.description)
        self.assertEqual(embed.colour.value, theme.color(theme.SECTION_RENAISSANCE))
        self.assertEqual(embed.footer.text, renaissance_views.FOOTER)
        self.assertEqual(embed.image.url, "attachment://renaissance_ok.png")
        self.assertEqual([file.filename for file in files], ["renaissance_ok.png"])
        for file in files:
            file.close()

    def test_echec_annonce_le_repos_de_lame(self):
        files: list = []
        embed = renaissance_views.build_renaissance_embed(False, 72, "base", None, files)

        self.assertIn("Pas de renaissance", embed.title)
        self.assertIn("se dissiper", embed.description)
        self.assertIn("**Échoué**", embed.description)
        self.assertIn("`72` > seuil `5`", embed.description)
        self.assertEqual(embed.colour.value, theme.color(theme.SECTION_NEUTRE))
        self.assertEqual(embed.image.url, "attachment://renaissance_ko.png")
        for file in files:
            file.close()

    def test_situation_affichee_dans_le_bloc(self):
        files: list = []
        embed = renaissance_views.build_renaissance_embed(True, 12, "rival", None, files)

        self.assertIn("Seuil de réussite : 15", embed.description)
        self.assertIn("son rival", embed.description)
        for file in files:
            file.close()

    def test_emojis_custom_du_serveur_dans_le_corps(self):
        files: list = []
        embed = renaissance_views.build_renaissance_embed(True, 3, "base", FakeGuild(), files)

        self.assertIn("<:jjk_renaissance_tentative:912> Tentative de renaissance", embed.description)
        self.assertIn("<:jjk_renaissance_chance:913> Dé", embed.description)
        for file in files:
            file.close()

    def test_titre_sans_emoji_custom(self):
        files: list = []
        embed = renaissance_views.build_renaissance_embed(True, 3, "base", FakeGuild(), files)

        self.assertTrue(embed.title.startswith(theme.fallback("renaissance")))
        for file in files:
            file.close()

    def test_image_locale_absente_retombe_sur_lurl_de_repli(self):
        missing = Path(tempfile.gettempdir()) / "renaissance_absente.png"
        with unittest.mock.patch.object(config, "RENAISSANCE_OK_PATH", missing):
            with unittest.mock.patch.object(
                config, "RENAISSANCE_OK_URL", "https://exemple.test/renaissance.png"
            ):
                files: list = []
                embed = renaissance_views.build_renaissance_embed(True, 3, "base", None, files)

        self.assertEqual(embed.image.url, "https://exemple.test/renaissance.png")
        self.assertEqual(files, [])


class FakeInteraction:
    """Interaction factice : réponse et follow-up enregistrés."""

    def __init__(self, guild_id: int = 4242, user_id: int = 7, guild=None):
        self.guild_id = guild_id
        self.user = SimpleNamespace(id=user_id)
        self.guild = guild
        self.response = SimpleNamespace(
            is_done=unittest.mock.Mock(return_value=False),
            defer=unittest.mock.AsyncMock(),
            send_message=unittest.mock.AsyncMock(),
        )
        self.followup = SimpleNamespace(send=unittest.mock.AsyncMock())


class RenaissanceSendTests(unittest.IsolatedAsyncioTestCase):
    """Déroulé complet de `/jjk renaissance`."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        ok_path = root / "renaissance_ok.png"
        ko_path = root / "renaissance_ko.png"
        ok_path.write_bytes(b"\x89PNG")
        ko_path.write_bytes(b"\x89PNG")

        self.patches = [
            unittest.mock.patch.object(config, "RENAISSANCE_OK_PATH", ok_path),
            unittest.mock.patch.object(config, "RENAISSANCE_KO_PATH", ko_path),
            unittest.mock.patch.object(config, "BANNER_URL", None),
            unittest.mock.patch.object(config, "BANNER_PATH", root / "banniere_absente.png"),
        ]
        for patch in self.patches:
            patch.start()

    def tearDown(self):
        for patch in reversed(self.patches):
            patch.stop()
        self.directory.cleanup()

    def _die(self, value: int):
        """Force le résultat du dé (nettoyage automatique du patch)."""
        patcher = unittest.mock.patch.object(renaissance_views.rules, "roll", return_value=value)
        patched = patcher.start()
        self.addCleanup(patcher.stop)
        return patched

    async def test_reussite_envoie_limage_de_succes(self):
        self._die(3)
        interaction = FakeInteraction()
        await renaissance_views.send_renaissance(interaction, "base")

        interaction.response.defer.assert_awaited_once()
        embeds = interaction.followup.send.await_args.kwargs["embeds"]
        files = interaction.followup.send.await_args.kwargs["files"]
        self.assertIn("attachment://renaissance_ok.png", [e.image.url for e in embeds if e.image])
        for file in files:
            file.close()

    async def test_echec_envoie_limage_dechec(self):
        self._die(90)
        interaction = FakeInteraction()
        await renaissance_views.send_renaissance(interaction, "base")

        embeds = interaction.followup.send.await_args.kwargs["embeds"]
        files = interaction.followup.send.await_args.kwargs["files"]
        self.assertIn("attachment://renaissance_ko.png", [e.image.url for e in embeds if e.image])
        self.assertNotIn(
            "attachment://renaissance_ok.png", [e.image.url for e in embeds if e.image]
        )
        for file in files:
            file.close()

    async def test_la_situation_change_le_verdict(self):
        # 12 échoue en base mais réussit face à un rival.
        self._die(12)
        interaction = FakeInteraction()
        await renaissance_views.send_renaissance(interaction, "rival")

        embeds = interaction.followup.send.await_args.kwargs["embeds"]
        files = interaction.followup.send.await_args.kwargs["files"]
        self.assertIn("attachment://renaissance_ok.png", [e.image.url for e in embeds if e.image])
        for file in files:
            file.close()

    async def test_image_refusee_le_renvoi_se_fait_sans_image(self):
        self._die(3)
        interaction = FakeInteraction()
        too_large = discord.HTTPException(
            SimpleNamespace(status=40005, reason="Request Entity Too Large"),
            {"code": 40005, "message": "Request entity too large"},
        )
        interaction.followup.send = unittest.mock.AsyncMock(side_effect=[too_large, None])

        with self.assertLogs("jjkbot.views.renaissance", level="WARNING"):
            await renaissance_views.send_renaissance(interaction, "base")

        self.assertEqual(interaction.followup.send.await_count, 2)
        retry = interaction.followup.send.await_args_list[1].kwargs["embeds"]
        self.assertEqual([embed.image.url for embed in retry if embed.image], [])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
