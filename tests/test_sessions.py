"""Tests des attentes de session (création de fiche, réinitialisation)."""

import time
import unittest

from jjkbot import sessions


class PendingProfileTests(unittest.TestCase):
    def setUp(self):
        sessions.clear_all()

    def tearDown(self):
        sessions.clear_all()

    def test_creation_puis_lecture(self):
        sessions.remember_profile(1, 2, "create", {"name": "Zuruï"})

        pending = sessions.get_pending_profile(1, 2)
        self.assertEqual(pending.mode, "create")
        self.assertEqual(pending.identity["name"], "Zuruï")

    def test_les_joueurs_sont_isoles(self):
        sessions.remember_profile(1, 2, "create", {"name": "A"})
        sessions.remember_profile(1, 3, "create", {"name": "B"})

        self.assertEqual(sessions.get_pending_profile(1, 3).identity["name"], "B")
        self.assertEqual(sessions.get_pending_profile(1, 2).identity["name"], "A")

    def test_expiration(self):
        pending = sessions.remember_profile(1, 2, "edit", {"name": "A"})
        pending.expires_at = time.monotonic() - 1

        self.assertIsNone(sessions.get_pending_profile(1, 2))

    def test_sweep_purge_les_attentes_expirees(self):
        pending = sessions.remember_profile(1, 2, "create", {"name": "A"})
        pending.expires_at = time.monotonic() - 1
        sessions.remember_profile(1, 3, "create", {"name": "B"})

        sessions.sweep()

        self.assertIsNone(sessions.get_pending_profile(1, 2))
        self.assertIsNotNone(sessions.get_pending_profile(1, 3))

    def test_clear(self):
        sessions.remember_profile(1, 2, "create", {"name": "A"})
        sessions.clear_pending_profile(1, 2)

        self.assertIsNone(sessions.get_pending_profile(1, 2))

    def test_nouvelle_creation_remplace_la_precedente(self):
        sessions.remember_profile(1, 2, "create", {"name": "A"})
        sessions.remember_profile(1, 2, "edit", {"name": "B"})

        self.assertEqual(sessions.get_pending_profile(1, 2).mode, "edit")


class PendingResetTests(unittest.TestCase):
    def setUp(self):
        sessions.clear_all()

    def tearDown(self):
        sessions.clear_all()

    def test_reset_puis_lecture(self):
        sessions.remember_reset(1, 2, 99, "stats")

        pending = sessions.get_pending_reset(1, 2)
        self.assertEqual(pending.target_user_id, 99)
        self.assertEqual(pending.reset_type, "stats")

    def test_expiration(self):
        pending = sessions.remember_reset(1, 2, 99, "profil")
        pending.expires_at = time.monotonic() - 1

        self.assertIsNone(sessions.get_pending_reset(1, 2))

    def test_sweep_purge_les_resets_expires(self):
        pending = sessions.remember_reset(1, 2, 99, "profil")
        pending.expires_at = time.monotonic() - 1

        sessions.sweep()

        self.assertIsNone(sessions.get_pending_reset(1, 2))

    def test_libelles_de_reset(self):
        self.assertEqual(set(sessions.RESET_LABELS), set(sessions.RESET_TYPES))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
