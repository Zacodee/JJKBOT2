"""Tests des commandes staff `/blackflash` : forcer la chance, gérer le titre.

Ces deux commandes n’existent que pour **tester** l’évènement Record Man du
Rayon Noir : sans elles, enchaîner 4 Black Flash sur un tirage à 5 % ne peut pas
être vérifié à la main. Elles écrivent dans la fiche du joueur, avec les mêmes
champs que le jeu normal.
"""

import tempfile
import unittest
import unittest.mock
from pathlib import Path
from types import SimpleNamespace

from jjkbot import config
from jjkbot.cogs.blackflash import (
    BlackflashCog,
    set_blackflash_buff,
    set_blackflash_chance,
    set_blackflash_record,
)
from jjkbot.content import blackflash as rules
from jjkbot.storage.profiles import Profile, get_profile, save_profile
from jjkbot.views import blackflash as blackflash_views


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
    def __init__(self, *, staff: bool = True):
        self.guild_id = 1
        self.guild = None
        # L’auteur n’est pas un `discord.Member` : seul `permissions` décide du
        # passage, comme pour un membre sans rôle staff configuré.
        self.user = SimpleNamespace(id=1, roles=[])
        self.response = FakeResponse()
        self.permissions = SimpleNamespace(
            administrator=staff, moderate_members=staff
        )


class BlackflashChanceCommandTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.patch = unittest.mock.patch.object(
            config, "DATA_FILE", Path(self.directory.name) / "profiles.json"
        )
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.directory.cleanup()

    async def make_profile(self, **data):
        await save_profile(1, 42, Profile.from_dict({"name": "Izouk", **data}))

    def sent(self, interaction):
        return interaction.response.sent["embed"].description

    async def test_force_la_chance_du_prochain_tirage(self):
        await self.make_profile()

        interaction = FakeInteraction()
        await set_blackflash_chance(interaction, FakePlayer(), 100)

        profile = await get_profile(1, 42)
        self.assertEqual(profile.blackflash_chance, rules.MAX_CHANCE)
        self.assertIn("`5%` → `100%`", self.sent(interaction))
        self.assertTrue(interaction.response.sent["ephemeral"])

    async def test_valeur_bruite_ramenee_dans_les_bornes(self):
        await self.make_profile(blackflashChance=90)

        await set_blackflash_chance(FakeInteraction(), FakePlayer(), 40)

        self.assertEqual((await get_profile(1, 42)).blackflash_chance, 40)

    async def test_retirer_rend_la_base_effective(self):
        # Traits, exception du staff et titre de recordman compris.
        await self.make_profile(
            blackflashChance=100,
            traits=["Fièvre"],
            blackflashRecord=rules.RECORD_STREAK,
        )

        interaction = FakeInteraction()
        await set_blackflash_chance(interaction, FakePlayer(), retirer=True)

        expected = rules.BASE_CHANCE + 5 + rules.RECORD_BONUS
        self.assertEqual((await get_profile(1, 42)).blackflash_chance, expected)
        self.assertIn(f"`100%` → `{expected}%`", self.sent(interaction))

    async def test_sans_valeur_ni_retrait_la_commande_refuse(self):
        await self.make_profile()

        interaction = FakeInteraction()
        await set_blackflash_chance(interaction, FakePlayer())

        self.assertEqual((await get_profile(1, 42)).blackflash_chance, rules.BASE_CHANCE)
        self.assertIn("Précise une **valeur**", self.sent(interaction))

    async def test_sans_fiche_la_commande_refuse(self):
        interaction = FakeInteraction()
        await set_blackflash_chance(interaction, FakePlayer(99), 100)

        self.assertIn("n’a pas encore de fiche", self.sent(interaction))

    async def test_non_staff_refuse(self):
        await self.make_profile()

        interaction = FakeInteraction(staff=False)
        await set_blackflash_chance(interaction, FakePlayer(), 100)

        self.assertEqual((await get_profile(1, 42)).blackflash_chance, rules.BASE_CHANCE)
        self.assertIn("staff", self.sent(interaction))


class BlackflashRecordCommandTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.patch = unittest.mock.patch.object(
            config, "DATA_FILE", Path(self.directory.name) / "profiles.json"
        )
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.directory.cleanup()

    def sent(self, interaction):
        return interaction.response.sent["embed"].description

    async def test_affiche_le_record_et_le_titre(self):
        await save_profile(
            1,
            42,
            Profile.from_dict(
                {"name": "Izouk", "blackflashStreak": 2, "blackflashRecord": 5}
            ),
        )

        interaction = FakeInteraction()
        await set_blackflash_record(interaction, FakePlayer())

        description = self.sent(interaction)
        self.assertIn("recordman du Rayon Noir", description)
        self.assertIn("`5` Black Flash consécutifs", description)
        self.assertIn(f"+{rules.RECORD_BONUS} %", description)

    async def test_affiche_quand_le_titre_nest_pas_encore_acquis(self):
        await save_profile(1, 42, Profile.from_dict({"name": "Izouk", "blackflashRecord": 3}))

        interaction = FakeInteraction()
        await set_blackflash_record(interaction, FakePlayer())

        self.assertIn("pas encore recordman", self.sent(interaction))

    async def test_retirer_le_titre_et_la_serie(self):
        await save_profile(
            1,
            42,
            Profile.from_dict(
                {"name": "Izouk", "blackflashStreak": 4, "blackflashRecord": 6}
            ),
        )

        interaction = FakeInteraction()
        await set_blackflash_record(interaction, FakePlayer(), retirer=True)

        profile = await get_profile(1, 42)
        self.assertEqual(profile.blackflash_record, 0)
        self.assertEqual(profile.blackflash_streak, 0)
        self.assertIn("`6` → `0`", self.sent(interaction))

    async def test_non_staff_refuse(self):
        await save_profile(1, 42, Profile.from_dict({"name": "Izouk", "blackflashRecord": 6}))

        interaction = FakeInteraction(staff=False)
        await set_blackflash_record(interaction, FakePlayer(), retirer=True)

        self.assertEqual((await get_profile(1, 42)).blackflash_record, 6)


class BlackflashBuffCommandTests(unittest.IsolatedAsyncioTestCase):
    """Le buff de stats du Black Flash : voir, fixer et retirer."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.patch = unittest.mock.patch.object(
            config, "DATA_FILE", Path(self.directory.name) / "profiles.json"
        )
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.directory.cleanup()

    def sent(self, interaction):
        return interaction.response.sent["embed"].description

    async def test_fixe_les_tours_restants(self):
        await save_profile(1, 42, Profile.from_dict({"name": "Izouk"}))

        interaction = FakeInteraction()
        await set_blackflash_buff(interaction, FakePlayer(), tours=2)

        self.assertEqual((await get_profile(1, 42)).blackflash_buff_turns, 2)
        self.assertIn("`0` → `2`", self.sent(interaction))

    async def test_retirer_eteint_le_buff(self):
        await save_profile(1, 42, Profile.from_dict({"name": "Izouk", "blackflashBuffTurns": 3}))

        interaction = FakeInteraction()
        await set_blackflash_buff(interaction, FakePlayer(), retirer=True)

        self.assertEqual((await get_profile(1, 42)).blackflash_buff_turns, 0)
        self.assertIn("`3` → `0`", self.sent(interaction))

    async def test_sans_valeur_affiche_letat(self):
        await save_profile(1, 42, Profile.from_dict({"name": "Izouk", "blackflashBuffTurns": 1}))

        interaction = FakeInteraction()
        await set_blackflash_buff(interaction, FakePlayer())

        self.assertIn("**1 tour(s)** restant(s)", self.sent(interaction))
        self.assertEqual((await get_profile(1, 42)).blackflash_buff_turns, 1)

    async def test_non_staff_refuse(self):
        await save_profile(1, 42, Profile.from_dict({"name": "Izouk", "blackflashBuffTurns": 3}))

        interaction = FakeInteraction(staff=False)
        await set_blackflash_buff(interaction, FakePlayer(), tours=0)

        self.assertEqual((await get_profile(1, 42)).blackflash_buff_turns, 3)


class BlackflashTestFlowTests(unittest.IsolatedAsyncioTestCase):
    """Le but affiché des commandes : pouvoir déclencher l’évènement à volonté."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        images = {}
        for name in ("blackflash_ok.png", "blackflash_ko.png", "record_rayon_noir.png"):
            path = self.root / name
            path.write_bytes(b"\x89PNG")
            images[name] = path
        self.patches = [
            unittest.mock.patch.object(config, "DATA_FILE", self.root / "profiles.json"),
            unittest.mock.patch.object(config, "BLACKFLASH_OK_PATH", images["blackflash_ok.png"]),
            unittest.mock.patch.object(config, "BLACKFLASH_KO_PATH", images["blackflash_ko.png"]),
            unittest.mock.patch.object(
                config, "BLACKFLASH_RECORD_PATH", images["record_rayon_noir.png"]
            ),
            unittest.mock.patch.object(config, "BLACKFLASH_RECORD_URL", None),
            unittest.mock.patch.object(config, "BANNER_URL", None),
            unittest.mock.patch.object(config, "BANNER_PATH", self.root / "banniere_absente.png"),
        ]
        for patch in self.patches:
            patch.start()

    def tearDown(self):
        for patch in reversed(self.patches):
            patch.stop()
        self.directory.cleanup()

    @staticmethod
    def _draw_interaction(user_id: int):
        return SimpleNamespace(
            guild_id=1,
            guild=None,
            user=SimpleNamespace(id=user_id),
            response=SimpleNamespace(
                is_done=lambda: False,
                defer=unittest.mock.AsyncMock(),
                send_message=unittest.mock.AsyncMock(),
            ),
            followup=SimpleNamespace(send=unittest.mock.AsyncMock()),
        )

    async def test_chance_forcee_declenche_le_titre_en_quatre_tentatives(self):
        await save_profile(1, 42, Profile.from_dict({"name": "Izouk"}))
        await set_blackflash_chance(FakeInteraction(), FakePlayer(), rules.MAX_CHANCE)

        draw = self._draw_interaction(42)
        for _ in range(rules.RECORD_STREAK):
            draw.followup.send.reset_mock()
            await blackflash_views.send_blackflash(draw)

        embeds = draw.followup.send.await_args.kwargs["embeds"]
        self.assertEqual(len(embeds), 2)
        self.assertIn("Record Man du Rayon Noir", embeds[1].description)
        for file in draw.followup.send.await_args.kwargs.get("files") or []:
            file.close()
        self.assertEqual((await get_profile(1, 42)).blackflash_record, rules.RECORD_STREAK)
        # Chaque réussite relance aussi le buff de statistiques.
        self.assertEqual((await get_profile(1, 42)).blackflash_buff_turns, rules.BUFF_TURNS)


class BlackflashCommandSurfaceTests(unittest.TestCase):
    """Commande réservée au staff : invisible des autres membres."""

    def test_groupe_et_sous_commandes(self):
        self.assertEqual(BlackflashCog.__cog_group_name__, "blackflash")
        names = sorted(command.name for command in BlackflashCog.__cog_app_commands__)

        self.assertEqual(names, ["buff", "chance", "record"])

    def test_reservees_au_staff(self):
        for command in (BlackflashCog.chance, BlackflashCog.record, BlackflashCog.buff):
            with self.subTest(command=command.name):
                self.assertTrue(command.default_permissions.moderate_members)
                self.assertFalse(command.default_permissions.administrator)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
