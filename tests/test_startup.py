"""Tests du démarrage : jalons de temps et synchronisation non bloquante.

`sync_commands` était attendu dans `setup_hook`, donc AVANT la connexion à la
passerelle Discord : un enregistrement des commandes lent retardait d’autant
l’apparition du bot en ligne. Ces tests verrouillent le comportement retenu —
tâche de fond en usage normal, attente conservée pour `--sync` — ainsi que la
présence des jalons de temps qui rendent un démarrage lent attribuable.
"""

from __future__ import annotations

import asyncio
import unittest
from unittest import mock

import main
from jjkbot.storage import profiles

LOGGER = "jjkbot"


class SetupHookStartupTests(unittest.IsolatedAsyncioTestCase):
    """Le démarrage ne doit plus dépendre de l’enregistrement des commandes."""

    def setUp(self) -> None:
        # Aucun de ces appels n’a besoin du réseau ni du disque : on mesure et
        # on vérifie l’enchaînement, pas les extensions elles-mêmes.
        self.patchers = [
            mock.patch.object(main.JJKBot, "load_extension", mock.AsyncMock()),
            mock.patch.object(profiles, "warmup", mock.AsyncMock()),
            mock.patch.object(main.JJKBot, "_log_database_state", mock.AsyncMock()),
        ]
        for patcher in self.patchers:
            patcher.start()
        self.addCleanup(self._stop_patchers)

    def _stop_patchers(self) -> None:
        for patcher in reversed(self.patchers):
            patcher.stop()

    async def test_la_synchronisation_part_en_tache_de_fond(self) -> None:
        bot = main.JJKBot()
        entered = asyncio.Event()
        release = asyncio.Event()

        async def blocked_sync(self):  # `self` : la substitution est posée sur la classe
            entered.set()
            await release.wait()

        with mock.patch.object(main.JJKBot, "sync_commands", blocked_sync):
            await bot.setup_hook()
            await asyncio.sleep(0)

            # `setup_hook` a rendu la main alors que la synchro est encore
            # bloquée : la connexion à Discord ne l’attend plus.
            self.assertTrue(entered.is_set())
            self.assertFalse(release.is_set())
            self.assertIsNotNone(bot._sync_task)

            release.set()
            await bot._sync_task

        await bot.close()

    async def test_le_mode_sync_attend_toujours_l_enregistrement(self) -> None:
        bot = main.JJKBot(sync_only=True)
        synced = asyncio.Event()

        async def immediate_sync(self):
            synced.set()

        with mock.patch.object(main.JJKBot, "sync_commands", immediate_sync):
            await bot.setup_hook()

        # `--sync` sert à enregistrer les commandes puis à quitter : l’attente
        # est indispensable, sinon le process sortirait avant l’enregistrement.
        self.assertTrue(synced.is_set())
        self.assertIsNone(bot._sync_task)
        await bot.close()

    async def test_la_tache_de_synchronisation_est_annulee_a_la_fermeture(self) -> None:
        bot = main.JJKBot()
        release = asyncio.Event()

        async def blocked_sync(self):
            await release.wait()

        with mock.patch.object(main.JJKBot, "sync_commands", blocked_sync):
            await bot.setup_hook()
            await asyncio.sleep(0)
            task = bot._sync_task
            await bot.close()

        with self.assertRaises(asyncio.CancelledError):
            await task

    async def test_les_jalons_de_demarrage_sont_journalises(self) -> None:
        bot = main.JJKBot(sync_only=True)

        async def immediate_sync(self):
            return None

        with mock.patch.object(main.JJKBot, "sync_commands", immediate_sync):
            with self.assertLogs(LOGGER, level="INFO") as captured:
                await bot.setup_hook()

        messages = "\n".join(captured.output)
        self.assertIn("extensions chargées", messages)
        self.assertIn("fiches prêtes", messages)
        await bot.close()


if __name__ == "__main__":
    unittest.main()
