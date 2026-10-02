"""Tests du stockage des fiches de personnage."""

import json
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from jjkbot import config
from jjkbot.content.stats import DEFAULT_STATS
from jjkbot.storage.profiles import (
    Profile,
    delete_profile,
    get_profile,
    normalize_stats,
    parse_timestamp,
    profile_key,
    save_profile,
)


class ProfileMigrationTests(unittest.TestCase):
    def test_ancien_format_migre(self):
        profile = Profile.from_dict(
            {
                "name": "Zuruï",
                "race": "Fléau",
                "characterClass": "Spécial",
                "camp": "Chaotique mauvais",
                "quote": "Tricheur, menteur",
                "traits": ["Rusé"],
                "flaws": ["Impitoyable"],
                "stats": {"force": 12, "resistance": 4},
                "statPoints": 3,
                "experience": 40,
                "unlockedSkills": ["strength_1"],
                "imageUrl": "https://exemple.test/perso.png",
            }
        )

        self.assertEqual(profile.grade, "Spécial")
        self.assertEqual(profile.alignment, "Chaotique mauvais")
        self.assertEqual(profile.age, "Non renseigné")
        self.assertEqual(profile.role, "Rôle non défini")
        self.assertEqual(profile.stats["force"], 12)
        self.assertEqual(profile.stats["vitesse"], 0)
        self.assertEqual(profile.stat_points, 3)
        self.assertEqual(profile.experience, 40)
        self.assertEqual(profile.unlocked_skills, ["strength_1"])

    def test_champs_absents_prennent_les_valeurs_par_defaut(self):
        profile = Profile.from_dict({})

        self.assertEqual(profile.name, "Personnage sans nom")
        self.assertEqual(profile.stats, DEFAULT_STATS)
        self.assertEqual(profile.traits, [])
        self.assertEqual(profile.stat_points, 0)

    def test_statistiques_inconnues_ignorees(self):
        profile = Profile.from_dict({"stats": {"force": 5, "sagesse": 99, "resistance": "x"}})

        self.assertEqual(profile.stats["force"], 5)
        self.assertNotIn("sagesse", profile.stats)
        self.assertEqual(profile.stats["resistance"], 0)

    def test_valeurs_negatives_ramenees_a_zero(self):
        profile = Profile.from_dict({"stats": {"force": -4}, "statPoints": -10, "experience": -3})

        self.assertEqual(profile.stats["force"], 0)
        self.assertEqual(profile.stat_points, 0)
        self.assertEqual(profile.experience, 0)

    def test_anciennes_statistiques_sans_nouvelles_cles_sont_reinitialisees(self):
        profile = Profile.from_dict({"stats": {"force": 8}})

        # « force » existe dans le nouveau modèle : les autres reviennent à 0.
        self.assertEqual(profile.stats, {**DEFAULT_STATS, "force": 8})

    def test_aller_retour_json_stable(self):
        original = Profile.from_dict({"name": "Zuruï", "age": "1 an", "alignment": "Chaotique"})
        restored = Profile.from_dict(original.to_dict())

        self.assertEqual(restored.to_dict(), original.to_dict())

    def test_normalize_stats_sur_valeur_non_dict(self):
        self.assertEqual(normalize_stats(None), DEFAULT_STATS)

    def test_profile_key(self):
        self.assertEqual(profile_key(42, 7), "42:7")

    def test_parse_timestamp(self):
        self.assertIsNotNone(parse_timestamp("2026-10-02T12:00:00.000Z"))
        self.assertIsNone(parse_timestamp("pas une date"))
        self.assertIsNone(parse_timestamp(None))


class ProfileStorageTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.data_file = Path(self.directory.name) / "profiles.json"
        self.patch = unittest.mock.patch.object(config, "DATA_FILE", self.data_file)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.directory.cleanup()

    async def test_lecture_sans_fichier(self):
        self.assertIsNone(await get_profile(1, 2))

    async def test_sauvegarde_et_lecture_utf8(self):
        profile = Profile.from_dict({"name": "Zuruï", "quote": "Énergie occulte — 呪術"})
        await save_profile(1, 2, profile)

        raw = self.data_file.read_text(encoding="utf-8")
        self.assertIn("Zuruï", raw)
        self.assertIn("呪術", raw)
        self.assertEqual(json.loads(raw)["version"], 2)

        reloaded = await get_profile(1, 2)
        self.assertEqual(reloaded.name, "Zuruï")
        self.assertEqual(reloaded.quote, "Énergie occulte — 呪術")

    async def test_ecriture_atomique_sans_fichier_temporaire(self):
        await save_profile(1, 2, Profile.from_dict({"name": "Test"}))

        self.assertTrue(self.data_file.exists())
        self.assertFalse(self.data_file.with_suffix(".json.tmp").exists())

    async def test_les_profils_sont_isoles_par_serveur(self):
        await save_profile(1, 2, Profile.from_dict({"name": "Serveur 1"}))
        await save_profile(9, 2, Profile.from_dict({"name": "Serveur 9"}))

        self.assertEqual((await get_profile(1, 2)).name, "Serveur 1")
        self.assertEqual((await get_profile(9, 2)).name, "Serveur 9")

    async def test_suppression(self):
        await save_profile(1, 2, Profile.from_dict({"name": "Test"}))
        await delete_profile(1, 2)

        self.assertIsNone(await get_profile(1, 2))

    async def test_ancien_fichier_est_migre_a_la_lecture(self):
        self.data_file.write_text(
            json.dumps(
                {
                    "profiles": {
                        "1:2": {
                            "name": "Ancien",
                            "characterClass": "Grade 4",
                            "camp": "Neutre",
                            "stats": {"force": 6},
                        }
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        profile = await get_profile(1, 2)

        self.assertEqual(profile.grade, "Grade 4")
        self.assertEqual(profile.alignment, "Neutre")
        self.assertEqual(profile.stats["force"], 6)

    async def test_json_invalide_leve_une_erreur_claire(self):
        self.data_file.write_text("{cassé", encoding="utf-8")

        with self.assertRaises(RuntimeError):
            await get_profile(1, 2)

    async def test_structure_inattendue_reinitialisee(self):
        self.data_file.write_text(json.dumps(["pas un objet"]), encoding="utf-8")

        self.assertIsNone(await get_profile(1, 2))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
