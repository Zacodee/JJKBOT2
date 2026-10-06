"""Tests de la fonctionnalité Black Flash : règles, fiche, embed et envoi."""

from __future__ import annotations

import json
import tempfile
import unittest
import unittest.mock
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace

import discord

from jjkbot import config, theme
from jjkbot.content import blackflash as rules
from jjkbot.emojis import DEFAULT_CATALOG, DISPLAY_ORDER, load_catalog
from jjkbot.storage.profiles import Profile
from jjkbot.views import blackflash as blackflash_views

# Clés du catalogue utilisées par l’embed de résultat.
BLACKFLASH_KEYS = ("blackflash", "blackflash_rate", "blackflash_tentative", "blackflash_chance")


class FakeEmoji:
    """Emoji de serveur factice, rendu comme Discord le ferait."""

    def __init__(self, name: str, emoji_id: int, animated: bool = False):
        self.name = name
        self.id = emoji_id
        self.animated = animated

    def __str__(self) -> str:
        return f"<{'a' if self.animated else ''}:{self.name}:{self.id}>"


class FakeGuild:
    """Serveur factice portant les emojis du Black Flash."""

    id = 4242
    emojis = [
        FakeEmoji("jjk_blackflash", 901),
        FakeEmoji("jjk_blackflash_tentative", 902),
        FakeEmoji("jjk_blackflash_chance", 903),
    ]


class BlackflashRulesTests(unittest.TestCase):
    def test_tirage_reussi_quand_le_des_tombe_dans_la_chance(self):
        self.assertTrue(rules.roll(5, randint=lambda low, high: 5))
        self.assertTrue(rules.roll(100, randint=lambda low, high: 100))

    def test_tirage_rate_au_dessus_de_la_chance(self):
        self.assertFalse(rules.roll(5, randint=lambda low, high: 6))
        self.assertFalse(rules.roll(0, randint=lambda low, high: 1))

    def test_succes_augmente_la_chance_de_cinq(self):
        self.assertEqual(rules.next_chance(5, True), 10)
        self.assertEqual(rules.next_chance(45, True), 50)

    def test_succes_plafonne_a_cent(self):
        self.assertEqual(rules.next_chance(100, True), 100)
        self.assertEqual(rules.next_chance(98, True), 100)

    def test_echec_retombe_a_la_base(self):
        self.assertEqual(rules.next_chance(45, False), rules.BASE_CHANCE)
        self.assertEqual(rules.next_chance(100, False), rules.BASE_CHANCE)

    def test_normalize_ramene_dans_les_bornes(self):
        self.assertEqual(rules.normalize(150), 100)
        self.assertEqual(rules.normalize(-3), 0)
        self.assertEqual(rules.normalize("8"), 8)
        self.assertEqual(rules.normalize(None), rules.BASE_CHANCE)


class BlackflashCatalogTests(unittest.TestCase):
    def test_cles_presentes_dans_le_catalogue_et_laffichage(self):
        for key in BLACKFLASH_KEYS:
            with self.subTest(key=key):
                self.assertIn(key, DEFAULT_CATALOG)
                self.assertIn(key, DISPLAY_ORDER)

    def test_noms_des_emojis_a_creer_sur_le_serveur(self):
        self.assertEqual(DEFAULT_CATALOG["blackflash"].name, "jjk_blackflash")
        self.assertEqual(DEFAULT_CATALOG["blackflash_rate"].name, "jjk_blackflash_rate")
        self.assertEqual(DEFAULT_CATALOG["blackflash_tentative"].name, "jjk_blackflash_tentative")
        self.assertEqual(DEFAULT_CATALOG["blackflash_chance"].name, "jjk_blackflash_chance")

    def test_config_emojis_json_liste_les_memes_cles(self):
        # /jjk emojis lit ce fichier : chaque clé doit y être éditable.
        catalog = load_catalog(config.EMOJIS_FILE)
        for key in BLACKFLASH_KEYS:
            with self.subTest(key=key):
                self.assertEqual(catalog[key].name, DEFAULT_CATALOG[key].name)
                self.assertEqual(catalog[key].fallback, DEFAULT_CATALOG[key].fallback)


class BlackflashProfileTests(unittest.TestCase):
    def test_chance_par_defaut_pour_une_ancienne_fiche(self):
        # Les fiches créées avant la fonctionnalité démarrent à la base.
        profile = Profile.from_dict({"name": "Zuruï"})

        self.assertEqual(profile.blackflash_chance, rules.BASE_CHANCE)
        self.assertEqual(profile.to_dict()["blackflashChance"], rules.BASE_CHANCE)

    def test_valeur_hors_bornes_ramenee_au_plafond(self):
        self.assertEqual(Profile.from_dict({"blackflashChance": 250}).blackflash_chance, 100)

    def test_valeur_invalide_retombe_a_la_base(self):
        self.assertEqual(
            Profile.from_dict({"blackflashChance": "beaucoup"}).blackflash_chance,
            rules.BASE_CHANCE,
        )

    def test_aller_retour_conserve_la_chance(self):
        profile = Profile.from_dict({"blackflashChance": 25})

        restored = Profile.from_dict(profile.to_dict())

        self.assertEqual(restored.blackflash_chance, 25)

    def test_ancienne_fiche_sans_exception_du_staff(self):
        profile = Profile.from_dict({"name": "Zuruï"})

        self.assertIsNone(profile.blackflash_base)
        self.assertEqual(profile.blackflash_bonus, 0)

    def test_aller_retour_conserve_lexception_du_staff(self):
        profile = Profile.from_dict({"blackflashBase": 15, "blackflashBonus": 5})

        restored = Profile.from_dict(profile.to_dict())

        self.assertEqual(restored.blackflash_base, 15)
        self.assertEqual(restored.blackflash_bonus, 5)


class BlackflashEmbedTests(unittest.TestCase):
    """Embed de résultat, avec des images locales factices."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.ok_path = root / "blackflash_ok.png"
        self.ko_path = root / "blackflash_ko.png"
        self.ok_path.write_bytes(b"\x89PNG")
        self.ko_path.write_bytes(b"\x89PNG")

        self.patches = [
            unittest.mock.patch.object(config, "BLACKFLASH_OK_PATH", self.ok_path),
            unittest.mock.patch.object(config, "BLACKFLASH_KO_PATH", self.ko_path),
            unittest.mock.patch.object(config, "BLACKFLASH_OK_URL", None),
            unittest.mock.patch.object(config, "BLACKFLASH_KO_URL", None),
        ]
        for patch in self.patches:
            patch.start()

    def tearDown(self):
        for patch in reversed(self.patches):
            patch.stop()
        self.directory.cleanup()

    def test_succes_raconte_le_coup_et_ses_buffs(self):
        files: list = []
        embed = blackflash_views.build_blackflash_embed(True, 15, 20, None, files)

        self.assertIn("Black Flash", embed.title)
        self.assertNotIn("<:", embed.title)
        self.assertIn("Rayon noir", embed.description)
        self.assertIn(f"[ {rules.BUFFS_TEXT} ]", embed.description)
        self.assertIn("**Réussit**", embed.description)
        self.assertIn("`15%` → `20%`", embed.description)
        self.assertIn("**+400**", embed.description)
        self.assertIn("**+1000**", embed.description)
        self.assertEqual(embed.colour.value, theme.color(theme.SECTION_BLACKFLASH))
        self.assertEqual(embed.footer.text, blackflash_views.FOOTER)
        # L’image de succès est jointe au message (aucune URL qui expirerait).
        self.assertEqual(embed.image.url, "attachment://blackflash_ok.png")
        self.assertEqual([file.filename for file in files], ["blackflash_ok.png"])
        for file in files:
            file.close()

    def test_echec_sans_buff_et_gif_rate(self):
        files: list = []
        embed = blackflash_views.build_blackflash_embed(False, 15, 5, None, files)

        self.assertIn("Raté", embed.title)
        self.assertIn(f"[ {rules.NO_BUFF_TEXT} ]", embed.description)
        self.assertIn("**Échoué**", embed.description)
        self.assertIn("`15%` → `5%`", embed.description)
        self.assertNotIn(rules.BUFFS_TEXT, embed.description)
        self.assertEqual(embed.colour.value, theme.color(theme.SECTION_NEUTRE))
        self.assertEqual(embed.image.url, "attachment://blackflash_ko.png")
        self.assertEqual([file.filename for file in files], ["blackflash_ko.png"])
        for file in files:
            file.close()

    def test_emojis_custom_du_serveur_dans_le_corps(self):
        files: list = []
        embed = blackflash_views.build_blackflash_embed(True, 5, 10, FakeGuild(), files)

        self.assertIn("<:jjk_blackflash_tentative:902> Tentative de black flash", embed.description)
        self.assertIn("<:jjk_blackflash_chance:903> Chance actuelle", embed.description)
        for file in files:
            file.close()

    def test_titre_sans_emoji_custom(self):
        # Le champ `title` reste en repli unicode : un emoji custom peut y
        # s’afficher en texte brut selon le client Discord.
        files: list = []
        embed = blackflash_views.build_blackflash_embed(True, 5, 10, FakeGuild(), files)

        self.assertTrue(embed.title.startswith(theme.fallback("blackflash")))
        for file in files:
            file.close()

    def test_gif_local_absent_retombe_sur_lurl_de_repli(self):
        with unittest.mock.patch.object(config, "BLACKFLASH_OK_PATH", self._missing()):
            with unittest.mock.patch.object(config, "BLACKFLASH_OK_URL", "https://exemple.test/ok.gif"):
                files: list = []
                embed = blackflash_views.build_blackflash_embed(True, 5, 10, None, files)

        self.assertEqual(embed.image.url, "https://exemple.test/ok.gif")
        self.assertEqual(files, [])

    def test_gif_local_absent_sans_url_n_affiche_rien(self):
        with unittest.mock.patch.object(config, "BLACKFLASH_KO_PATH", self._missing()):
            files: list = []
            embed = blackflash_views.build_blackflash_embed(False, 5, 5, None, files)

        self.assertFalse(embed.image)  # proxy vide = aucune image
        self.assertEqual(files, [])

    @staticmethod
    def _missing() -> Path:
        return Path(tempfile.gettempdir()) / "blackflash_absent.png"


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


class BlackflashSendTests(unittest.IsolatedAsyncioTestCase):
    """Déroulé complet de `/jjk blackflash` et `/jjk blackflash-reset`."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        ok_path = root / "blackflash_ok.png"
        ko_path = root / "blackflash_ko.png"
        ok_path.write_bytes(b"\x89PNG")
        ko_path.write_bytes(b"\x89PNG")

        # Bannière et images isolées : le test ne dépend pas des assets du dépôt.
        self.patches = [
            unittest.mock.patch.object(config, "BLACKFLASH_OK_PATH", ok_path),
            unittest.mock.patch.object(config, "BLACKFLASH_KO_PATH", ko_path),
            unittest.mock.patch.object(config, "BANNER_URL", None),
            unittest.mock.patch.object(config, "BANNER_PATH", root / "banniere_absente.png"),
        ]
        for patch in self.patches:
            patch.start()

    def tearDown(self):
        for patch in reversed(self.patches):
            patch.stop()
        self.directory.cleanup()

    async def test_sans_fiche_une_erreur_est_affichee(self):
        interaction = FakeInteraction()
        with unittest.mock.patch.object(
            blackflash_views, "get_profile", unittest.mock.AsyncMock(return_value=None)
        ), unittest.mock.patch.object(
            blackflash_views, "save_profile", unittest.mock.AsyncMock()
        ) as save, unittest.mock.patch.object(
            blackflash_views, "notify_error", unittest.mock.AsyncMock()
        ) as error:
            await blackflash_views.send_blackflash(interaction)

        error.assert_awaited_once()
        self.assertIn("/profil creer", error.await_args.args[1])
        save.assert_not_awaited()
        interaction.response.send_message.assert_not_awaited()

    async def test_succes_porte_la_chance_au_plafond_et_joint_le_gif(self):
        # Chance à 100 % : le tirage est toujours réussi (test déterministe).
        profile = Profile.from_dict({"blackflashChance": 100})
        interaction = FakeInteraction()
        save = self._storage(profile)
        await blackflash_views.send_blackflash(interaction)

        self.assertEqual(save.await_args.args[2].blackflash_chance, 100)
        interaction.response.defer.assert_awaited_once()
        embeds = interaction.followup.send.await_args.kwargs["embeds"]
        files = interaction.followup.send.await_args.kwargs["files"]
        images = [embed.image.url for embed in embeds if embed.image]
        self.assertIn("attachment://blackflash_ok.png", images)
        for file in files:
            file.close()

    async def test_echec_remet_la_chance_a_la_base(self):
        # Aucun trait : l’échec ramène à la base 5 %. Le tirage est forcé, car
        # le plancher de base rend une chance stockée à 0 non déterministe.
        profile = Profile.from_dict({"blackflashChance": 45})
        interaction = FakeInteraction()
        save = self._storage(profile)
        with unittest.mock.patch.object(blackflash_views.rules, "roll", return_value=False):
            await blackflash_views.send_blackflash(interaction)

        self.assertEqual(save.await_args.args[2].blackflash_chance, rules.BASE_CHANCE)
        embeds = interaction.followup.send.await_args.kwargs["embeds"]
        files = interaction.followup.send.await_args.kwargs["files"]
        images = [embed.image.url for embed in embeds if embed.image]
        self.assertIn("attachment://blackflash_ko.png", images)
        for file in files:
            file.close()

    async def test_gif_refuse_le_renvoi_se_fait_sans_image(self):
        # Upload refusé (limite de poids) : la tentative reste comptée et le
        # résultat part quand même, sans image plutôt qu’en erreur.
        profile = Profile.from_dict({"blackflashChance": 100})
        interaction = FakeInteraction()
        too_large = discord.HTTPException(
            SimpleNamespace(status=40005, reason="Request Entity Too Large"),
            {"code": 40005, "message": "Request entity too large"},
        )
        interaction.followup.send = unittest.mock.AsyncMock(side_effect=[too_large, None])
        save = self._storage(profile)

        with self.assertLogs("jjkbot.views.blackflash", level="WARNING"):
            await blackflash_views.send_blackflash(interaction)

        self.assertEqual(interaction.followup.send.await_count, 2)
        self.assertEqual(save.await_args.args[2].blackflash_chance, 100)
        retry = interaction.followup.send.await_args_list[1].kwargs["embeds"]
        self.assertEqual([embed.image.url for embed in retry if embed.image], [])

    async def test_reset_remet_les_chances_a_la_base(self):
        profile = Profile.from_dict({"blackflashChance": 45})
        interaction = FakeInteraction()
        save = self._storage(profile)
        await blackflash_views.send_blackflash_reset(interaction)

        self.assertEqual(save.await_args.args[2].blackflash_chance, rules.BASE_CHANCE)
        embed = interaction.response.send_message.await_args.kwargs["embed"]
        self.assertIn("`45%` → `5%`", embed.description)

    async def test_reset_sans_fiche_une_erreur_est_affichee(self):
        interaction = FakeInteraction()
        with unittest.mock.patch.object(
            blackflash_views, "get_profile", unittest.mock.AsyncMock(return_value=None)
        ), unittest.mock.patch.object(
            blackflash_views, "notify_error", unittest.mock.AsyncMock()
        ) as error:
            await blackflash_views.send_blackflash_reset(interaction)

        error.assert_awaited_once()
        interaction.response.send_message.assert_not_awaited()

    def _storage(self, profile: Profile):
        """Fiche factice en lecture, écriture capturée (nettoyage automatique)."""
        save = unittest.mock.AsyncMock(return_value=profile)
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(
            unittest.mock.patch.object(
                blackflash_views, "get_profile", unittest.mock.AsyncMock(return_value=profile)
            )
        )
        stack.enter_context(unittest.mock.patch.object(blackflash_views, "save_profile", save))
        return save


class BlackflashTraitTests(unittest.TestCase):
    """Reconnaissance des traits et calcul de la base effective."""

    def test_normalisation_casse_accents_et_espaces(self):
        self.assertEqual(rules.normalize_label("  Béni  de l’Étincelle "), "beni de l'etincelle")
        self.assertEqual(rules.normalize_label("FIEVRE"), "fievre")

    def test_trait_par_defaut_donne_un_bonus_additif(self):
        self.assertEqual(rules.trait_modifiers(["Fièvre"]), (0, 5))

    def test_trait_de_base_impose_le_plancher(self):
        self.assertEqual(rules.trait_modifiers(["Béni de l'étincelle"]), (20, 0))

    def test_base_et_bonus_se_cumulent(self):
        self.assertEqual(rules.trait_modifiers(["Adepte du Black Flash", "Fièvre"]), (10, 5))

    def test_trait_exclusif_ignore_les_autres(self):
        # « Béni de l’étincelle » + « Fièvre » : le bonus additif ne s’applique pas.
        self.assertEqual(rules.trait_modifiers(["Béni de l'étincelle", "Fièvre"]), (20, 0))

    def test_sans_trait_aucun_modificateur(self):
        self.assertEqual(rules.trait_modifiers([]), (0, 0))
        self.assertEqual(rules.trait_modifiers(["Trait inconnu"]), (0, 0))

    def test_base_effective_avec_et_sans_trait(self):
        self.assertEqual(rules.effective_base([]), rules.BASE_CHANCE)
        self.assertEqual(rules.effective_base(["Fièvre"]), 10)
        self.assertEqual(rules.effective_base(["Béni de l'étincelle"]), 20)
        self.assertEqual(rules.effective_base(["Adepte du Black Flash", "Fièvre"]), 15)

    def test_exception_du_staff_releve_la_base(self):
        self.assertEqual(rules.effective_base(["Fièvre"], base_override=30), 35)
        self.assertEqual(rules.effective_base([], base_override=40, bonus_override=10), 50)

    def test_base_effective_plafonnee_a_cent(self):
        self.assertEqual(
            rules.effective_base(["Béni de l'étincelle"], base_override=100, bonus_override=50),
            rules.MAX_CHANCE,
        )

    def test_succes_et_echec_utilisent_la_base_effective(self):
        self.assertEqual(rules.next_chance(20, True, 20), 25)
        self.assertEqual(rules.next_chance(45, False, 20), 20)

    def test_config_blackflash_json_liste_les_traits(self):
        # Le fichier éditable doit décrire les mêmes traits que les défauts.
        effects = rules.load_trait_effects(config.BLACKFLASH_FILE)
        self.assertEqual(effects["fievre"], rules.TraitEffect(bonus=5, label="Fièvre"))
        self.assertEqual(effects["beni de l'etincelle"].base, 20)
        self.assertTrue(effects["beni de l'etincelle"].exclusive)
        self.assertEqual(effects["adepte du black flash"].base, 10)

    def test_fichier_absent_retombe_sur_les_defauts(self):
        missing = Path(tempfile.gettempdir()) / "blackflash_absente.json"
        self.assertEqual(rules.load_trait_effects(missing), rules.DEFAULT_TRAIT_EFFECTS)

    def test_aliases_dun_fichier_personnalise(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "blackflash.json"
            path.write_text(
                json.dumps({"Onde noire": {"bonus": 7, "aliases": ["onde noire majeure"]}}),
                encoding="utf-8",
            )
            effects = rules.load_trait_effects(path)

        self.assertEqual(effects["onde noire"].bonus, 7)
        self.assertEqual(effects["onde noire majeure"].bonus, 7)

    def test_alias_decriture_du_fichier_reel(self):
        # Les variantes que la normalisation ne devine pas sont des alias.
        self.assertEqual(rules.effective_base(["Adepte du BlackFlash"]), 10)
        self.assertEqual(rules.effective_base(["Adepte BF"]), 10)
        self.assertEqual(rules.effective_base(["Béni de l etincelle"]), 20)
        self.assertEqual(rules.effective_base(["beni etincelle"]), 20)

    def test_adepte_du_rayon_noir_cumule_avec_fievre(self):
        # « Rayon noir » est le nom français du Black Flash : écrit tel quel sur
        # la fiche, il doit donner base 10 + 5 de Fièvre = 15.
        self.assertEqual(rules.trait_modifiers(["adepte du rayon noir"]), (10, 0))
        self.assertEqual(
            rules.trait_modifiers(["adepte du rayon noir", "Fièvre"]), (10, 5)
        )
        self.assertEqual(rules.effective_base(["adepte du rayon noir", "Fièvre"]), 15)
        self.assertEqual(rules.effective_base(["Adepte du Rayon Noir"]), 10)

    def test_faute_de_frappe_non_aliastee_reste_ignoree(self):
        self.assertEqual(rules.trait_modifiers(["Fievr"]), (0, 0))


class BlackflashTraitSendTests(unittest.IsolatedAsyncioTestCase):
    """Les traits s’appliquent au tirage et survivent à un échec."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        ok_path = root / "blackflash_ok.png"
        ko_path = root / "blackflash_ko.png"
        ok_path.write_bytes(b"\x89PNG")
        ko_path.write_bytes(b"\x89PNG")
        self.patches = [
            unittest.mock.patch.object(config, "BLACKFLASH_OK_PATH", ok_path),
            unittest.mock.patch.object(config, "BLACKFLASH_KO_PATH", ko_path),
            unittest.mock.patch.object(config, "BANNER_URL", None),
            unittest.mock.patch.object(config, "BANNER_PATH", root / "banniere_absente.png"),
        ]
        for patch in self.patches:
            patch.start()

    def tearDown(self):
        for patch in reversed(self.patches):
            patch.stop()
        self.directory.cleanup()

    def _storage(self, profile: Profile):
        save = unittest.mock.AsyncMock(return_value=profile)
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(
            unittest.mock.patch.object(
                blackflash_views, "get_profile", unittest.mock.AsyncMock(return_value=profile)
            )
        )
        stack.enter_context(unittest.mock.patch.object(blackflash_views, "save_profile", save))
        return save

    async def test_trait_de_base_survit_a_un_echec(self):
        profile = Profile.from_dict(
            {"blackflashChance": 5, "traits": ["Béni de l'étincelle"]}
        )
        interaction = FakeInteraction()
        save = self._storage(profile)
        with unittest.mock.patch.object(blackflash_views.rules, "roll", return_value=False):
            await blackflash_views.send_blackflash(interaction)

        # L’échec ramène à la base du trait (20 %), pas à 5 %.
        self.assertEqual(save.await_args.args[2].blackflash_chance, 20)
        embeds = interaction.followup.send.await_args.kwargs["embeds"]
        files = interaction.followup.send.await_args.kwargs["files"]
        self.assertTrue(any("`20%` → `20%`" in (embed.description or "") for embed in embeds))
        for file in files:
            file.close()

    async def test_base_et_bonus_cumules_au_tirage(self):
        profile = Profile.from_dict(
            {
                "blackflashChance": 0,
                "traits": ["Adepte du Black Flash", "Fièvre"],
            }
        )
        interaction = FakeInteraction()
        save = self._storage(profile)
        with unittest.mock.patch.object(blackflash_views.rules, "roll", return_value=False):
            await blackflash_views.send_blackflash(interaction)

        self.assertEqual(save.await_args.args[2].blackflash_chance, 15)
        for file in interaction.followup.send.await_args.kwargs["files"]:
            file.close()

    async def test_exception_du_staff_appliquee(self):
        profile = Profile.from_dict({"blackflashChance": 0, "blackflashBase": 30})
        interaction = FakeInteraction()
        save = self._storage(profile)
        with unittest.mock.patch.object(blackflash_views.rules, "roll", return_value=False):
            await blackflash_views.send_blackflash(interaction)

        self.assertEqual(save.await_args.args[2].blackflash_chance, 30)
        for file in interaction.followup.send.await_args.kwargs["files"]:
            file.close()

    async def test_reset_revient_a_la_base_effective(self):
        profile = Profile.from_dict(
            {"blackflashChance": 45, "traits": ["Béni de l'étincelle"]}
        )
        interaction = FakeInteraction()
        save = self._storage(profile)
        await blackflash_views.send_blackflash_reset(interaction)

        self.assertEqual(save.await_args.args[2].blackflash_chance, 20)
        embed = interaction.response.send_message.await_args.kwargs["embed"]
        self.assertIn("`45%` → `20%`", embed.description)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
