"""Tests de la garde de configuration (variables obligatoires)."""

import os
import unittest
from unittest import mock

from jjkbot import config


class CheckRequiredTests(unittest.TestCase):
    def test_variable_presente_ne_leve_pas(self) -> None:
        with mock.patch.dict(os.environ, {"DISCORD_TOKEN": "abc"}, clear=False):
            config.check_required()  # ne doit rien lever

    def test_variable_absente_liste_le_nom(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(config.missing_required(), ["DISCORD_TOKEN"])
            with self.assertRaises(config.ConfigError) as caught:
                config.check_required()

        message = str(caught.exception)
        self.assertIn("DISCORD_TOKEN", message)
        self.assertIn(str(config.ENV_FILE), message)

    def test_valeur_blanche_compte_comme_absente(self) -> None:
        with mock.patch.dict(os.environ, {"DISCORD_TOKEN": "   "}, clear=True):
            self.assertEqual(config.missing_required(), ["DISCORD_TOKEN"])

    def test_token_est_lu_paresseusement(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(config.ConfigError):
                config.token()

        with mock.patch.dict(os.environ, {"DISCORD_TOKEN": "xyz"}, clear=True):
            self.assertEqual(config.token(), "xyz")


if __name__ == "__main__":
    unittest.main()
