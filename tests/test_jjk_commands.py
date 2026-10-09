"""Tests des commandes du cog `/jjk`.

Deux sujets :

- `/jjk eo` (Réserve d’EO) — « Réserve d’EO » est la seule statistique **figée**
  de la fiche : aucun point ne s’y dépense (`/profil attribuer-stat` la refuse),
  c’est donc cette commande, et elle seule, qui la pose après validation de la
  fiche RP du joueur ;
- `/jjk blackflash-chance` (diagnostic du staff) et la surface de `/jjk
  blackflash`, dont l’option `mortel` est réservée aux recordmen du Rayon Noir.
"""

import tempfile
import unittest
import unittest.mock
from pathlib import Path
from types import SimpleNamespace

from jjkbot import config
from jjkbot.cogs.jjk import JjkCog, build_help_embed, set_reserve_eo
from jjkbot.content.stats import RESERVE_EO
from jjkbot.storage.profiles import Profile, get_profile, save_profile


class FakePlayer:
    """Membre Discord factice : seuls l’identité et la mention sont lues."""

    def __init__(self, user_id: int = 42, name: str = "Izouk"):
        self.id = user_id
        self.display_name = name

    @property
    def mention(self) -> str:
        return f"<@{self.id}>"


class FakeResponse:
    def __init__(self):
        self.sent = None

    async def send_message(self, **kwargs):
        self.sent = kwargs


class FakeInteraction:
    def __init__(self, *, admin: bool = True):
        self.guild_id = 1
        self.guild = None
        self.response = FakeResponse()
        self.permissions = SimpleNamespace(administrator=admin, moderate_members=False)


class ReserveEOTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.patch = unittest.mock.patch.object(
            config, "DATA_FILE", Path(self.directory.name) / "profiles.json"
        )
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.directory.cleanup()

    async def make_profile(self, **stats):
        await save_profile(1, 42, Profile.from_dict({"name": "Izouk", "stats": stats or None}))

    def sent_embed(self, interaction):
        return interaction.response.sent["embed"]

    async def test_administrateur_fixe_la_reserve(self):
        await self.make_profile()

        interaction = FakeInteraction()
        await set_reserve_eo(interaction, FakePlayer(), 400)

        self.assertEqual((await get_profile(1, 42)).stats[RESERVE_EO.id], 400)
        self.assertIn("400", self.sent_embed(interaction).description)
        self.assertTrue(interaction.response.sent["ephemeral"])

    async def test_relance_corrige_la_valeur(self):
        await self.make_profile(**{RESERVE_EO.id: 250})

        interaction = FakeInteraction()
        await set_reserve_eo(interaction, FakePlayer(), 100)

        self.assertEqual((await get_profile(1, 42)).stats[RESERVE_EO.id], 100)
        # Le montant précédent est rappelé : le staff voit la correction.
        self.assertIn("avant : 250", self.sent_embed(interaction).description)

    async def test_sans_fiche_la_commande_refuse(self):
        interaction = FakeInteraction()
        await set_reserve_eo(interaction, FakePlayer(99), 400)

        self.assertIn("n’a pas encore de fiche", self.sent_embed(interaction).description)

    async def test_non_administrateur_refuse(self):
        await self.make_profile()

        interaction = FakeInteraction(admin=False)
        await set_reserve_eo(interaction, FakePlayer(), 400)

        self.assertEqual((await get_profile(1, 42)).stats[RESERVE_EO.id], 0)
        self.assertIn("administrateurs", self.sent_embed(interaction).description)

    async def test_reserve_ne_touche_pas_les_autres_statistiques(self):
        await self.make_profile(force=12, **{RESERVE_EO.id: 5})

        await set_reserve_eo(FakeInteraction(), FakePlayer(), 300)

        stats = (await get_profile(1, 42)).stats
        self.assertEqual(stats["force"], 12)
        self.assertEqual(stats[RESERVE_EO.id], 300)


class BlackflashChanceDiagnosticTests(unittest.IsolatedAsyncioTestCase):
    """`/jjk blackflash-chance` doit annoncer aussi le bonus du recordman.

    Le bonus du record n’est pas l’exception du staff : sans ce rappel, le staff
    verrait un plancher effectif plus haut que celle qu’il vient de poser, et
    croirait à une valeur oubliée.
    """

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.patches = [
            unittest.mock.patch.object(config, "DATA_FILE", root / "profiles.json"),
        ]
        for patch in self.patches:
            patch.start()

    def tearDown(self):
        for patch in reversed(self.patches):
            patch.stop()
        self.directory.cleanup()

    async def _run(self, interaction):
        # `self` n’est pas lu par la commande : un espace de noms suffit.
        await JjkCog.blackflash_chance.callback(
            SimpleNamespace(), interaction, FakePlayer(), base=10, bonus=0
        )

    async def test_le_recordman_voit_son_bonus_dans_le_diagnostic(self):
        # Le titre est personnel : il se lit sur la fiche du joueur.
        await save_profile(
            1, 42, Profile.from_dict({"name": "Izouk", "blackflashRecord": 4})
        )
        interaction = FakeInteraction()

        await self._run(interaction)

        description = interaction.response.sent["embed"].description
        self.assertIn("recordman du Rayon Noir (+10)", description)
        self.assertIn("effectif **20%**", description)

    async def test_sans_record_aucune_ligne_recordman(self):
        await save_profile(1, 42, Profile.from_dict({"name": "Izouk"}))
        interaction = FakeInteraction()

        await self._run(interaction)

        description = interaction.response.sent["embed"].description
        self.assertNotIn("recordman", description)
        self.assertIn("effectif **10%**", description)


class CommandSurfaceTests(unittest.TestCase):
    """La commande doit rester invisible des non-administrateurs."""

    def test_eo_est_reservee_aux_administrateurs(self):
        command = JjkCog.eo

        self.assertEqual(command.name, "eo")
        self.assertTrue(command.default_permissions.administrator)

    def test_blackflash_a_une_option_combat_mortel(self):
        names = {parameter.name for parameter in JjkCog.blackflash.parameters}

        self.assertIn("mortel", names)

    def test_le_guide_annonce_le_record_man(self):
        self.assertIn("Record Man du Rayon Noir", build_help_embed().description)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
