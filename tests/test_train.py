"""Tests de `/train` : fenêtre hebdomadaire, gain d’XP et remise à zéro (staff)."""

import tempfile
import unittest
import unittest.mock
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from jjkbot import config
from jjkbot.cogs.train import TrainCog
from jjkbot.content import train as rules
from jjkbot.storage.profiles import Profile, get_profile, save_profile
from jjkbot.views import train as train_views


class FakePlayer:
    def __init__(self, user_id: int = 42, name: str = "Izouk"):
        self.id = user_id
        self.display_name = name

    @property
    def mention(self) -> str:
        return f"<@{self.id}>"


class FakeResponse:
    def __init__(self):
        self.sent = None
        self.deferred = False

    async def send_message(self, **kwargs):
        self.sent = kwargs

    async def defer(self, **kwargs):
        self.deferred = True

    def is_done(self):
        return self.deferred


class FakeFollowup:
    def __init__(self):
        self.sent = None

    async def send(self, **kwargs):
        self.sent = kwargs


class FakeInteraction:
    def __init__(self, *, staff: bool = True, user_id: int = 42):
        self.guild_id = 1
        self.guild = None
        self.user = SimpleNamespace(id=user_id, roles=[])
        self.response = FakeResponse()
        self.followup = FakeFollowup()
        self.permissions = SimpleNamespace(administrator=staff, moderate_members=staff)


class TrainRulesTests(unittest.TestCase):
    def test_gain_de_500_xp(self):
        self.assertEqual(rules.TRAIN_XP, 500)

    def test_disponible_sans_historique(self):
        self.assertTrue(rules.is_available(None))

    def test_indisponible_dans_les_sept_jours(self):
        last = rules.now() - timedelta(days=2)

        self.assertFalse(rules.is_available(last.isoformat()))
        self.assertGreater(rules.remaining(last.isoformat()), timedelta(days=4, hours=23))

    def test_disponible_apres_sept_jours(self):
        last = rules.now() - timedelta(days=8)

        self.assertTrue(rules.is_available(last.isoformat()))
        self.assertEqual(rules.remaining(last.isoformat()), timedelta(0))

    def test_prochain_rendez_vous_a_sept_jours(self):
        last = datetime(2026, 1, 1, tzinfo=timezone.utc)

        ready = rules.next_available(last.isoformat())

        self.assertEqual(ready, datetime(2026, 1, 8, tzinfo=timezone.utc))

    def test_date_invalide_ne_bloque_pas(self):
        self.assertTrue(rules.is_available("pas-une-date"))

    def test_format_delai_lisible(self):
        self.assertEqual(rules.format_delay(timedelta(days=3, hours=4, minutes=12)), "3 j 04 h 12 min")
        self.assertEqual(rules.format_delay(timedelta(minutes=5)), "05 min")


class TrainSendTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.image = root / "train.png"
        self.image.write_bytes(b"\x89PNG")
        self.patches = [
            unittest.mock.patch.object(config, "DATA_FILE", root / "profiles.json"),
            unittest.mock.patch.object(config, "TRAIN_PATH", self.image),
            unittest.mock.patch.object(config, "TRAIN_URL", None),
            unittest.mock.patch.object(config, "BANNER_URL", None),
            unittest.mock.patch.object(config, "BANNER_PATH", root / "absente.png"),
        ]
        for patch in self.patches:
            patch.start()

    async def asyncTearDown(self):
        for patch in reversed(self.patches):
            patch.stop()
        for file in (getattr(self, "_files", None) or []):
            file.close()
        self.directory.cleanup()

    async def test_premier_entrainement_donne_500_xp(self):
        await save_profile(1, 42, Profile.from_dict({"name": "Izouk"}))
        interaction = FakeInteraction()

        await train_views.send_train(interaction)

        self._files = interaction.followup.sent.get("files") or []
        profile = await get_profile(1, 42)
        self.assertEqual(profile.experience, rules.TRAIN_XP)
        self.assertIsNotNone(profile.train_last_at)
        embeds = interaction.followup.sent["embeds"]
        # Sans bannière (patched absente), le message ne porte que l’embed de train.
        content = embeds[-1]
        self.assertIn(f"+{rules.TRAIN_XP} XP", content.description)
        self.assertEqual(content.image.url, "attachment://train.png")

    async def test_deuxieme_entrainement_bloque(self):
        await save_profile(
            1, 42, Profile.from_dict({"name": "Izouk", "experience": 100})
        )
        interaction = FakeInteraction()
        await train_views.send_train(interaction)  # premier : passe
        self._files = interaction.followup.sent.get("files") or []

        second = FakeInteraction()
        await train_views.send_train(second)

        self.assertEqual((await get_profile(1, 42)).experience, 100 + rules.TRAIN_XP)
        self.assertIn("déjà entraîné", second.response.sent["embed"].description)
        self.assertTrue(second.response.sent["ephemeral"])

    async def test_sans_fiche_la_commande_refuse(self):
        interaction = FakeInteraction()

        await train_views.send_train(interaction)

        self.assertIn("pas encore de fiche", interaction.response.sent["embed"].description)


class TrainResetTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.patch = unittest.mock.patch.object(
            config, "DATA_FILE", Path(self.directory.name) / "profiles.json"
        )
        self.patch.start()

    async def asyncTearDown(self):
        self.patch.stop()
        self.directory.cleanup()

    async def test_reset_rend_la_seance(self):
        await save_profile(
            1,
            42,
            Profile.from_dict({"name": "Izouk", "trainLastAt": rules.now().isoformat()}),
        )
        interaction = FakeInteraction()

        await train_views.send_train_reset(interaction, FakePlayer())

        self.assertIsNone((await get_profile(1, 42)).train_last_at)
        self.assertIn("réinitialisé", interaction.response.sent["embed"].description)

    async def test_reset_refuse_aux_non_staff(self):
        await save_profile(
            1,
            42,
            Profile.from_dict({"name": "Izouk", "trainLastAt": rules.now().isoformat()}),
        )
        interaction = FakeInteraction(staff=False)

        await train_views.send_train_reset(interaction, FakePlayer())

        self.assertIsNotNone((await get_profile(1, 42)).train_last_at)
        self.assertIn("staff", interaction.response.sent["embed"].description)


class TrainCommandSurfaceTests(unittest.TestCase):
    def test_commandes_declarees(self):
        self.assertEqual(TrainCog.train.name, "train")
        self.assertEqual(TrainCog.train_reset.name, "train-reset")

    def test_reset_reserve_au_staff(self):
        self.assertTrue(TrainCog.train_reset.default_permissions.moderate_members)
        self.assertFalse(TrainCog.train_reset.default_permissions.administrator)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
