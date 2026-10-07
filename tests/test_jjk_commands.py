"""Tests de la commande administrateur `/jjk eo` (Réserve d’EO).

« Réserve d’EO » est la seule statistique **figée** de la fiche : aucun point ne
s’y dépense (`/profil attribuer-stat` la refuse). C’est donc cette commande, et
elle seule, qui la pose — après validation de la fiche RP du joueur.
"""

import tempfile
import unittest
import unittest.mock
from pathlib import Path
from types import SimpleNamespace

from jjkbot import config
from jjkbot.cogs.jjk import JjkCog, set_reserve_eo
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


class CommandSurfaceTests(unittest.TestCase):
    """La commande doit rester invisible des non-administrateurs."""

    def test_eo_est_reservee_aux_administrateurs(self):
        command = JjkCog.eo

        self.assertEqual(command.name, "eo")
        self.assertTrue(command.default_permissions.administrator)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
