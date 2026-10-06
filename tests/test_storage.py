"""Tests du stockage des fiches de personnage."""

import json
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from jjkbot import config
from jjkbot.content.stats import DEFAULT_STATS
from jjkbot.storage import profiles as profiles_module
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
        original = Profile.from_dict({"name": "Zuruï", "age": "1 an"})
        restored = Profile.from_dict(original.to_dict())

        self.assertEqual(restored.to_dict(), original.to_dict())

    def test_ancien_champ_alignement_est_ignore(self):
        # L’alignement est retiré du bot : les clés v1 (« camp ») et v2
        # (« alignment ») ne sont plus lues à la lecture ni réécrites en
        # écriture — elles disparaissent donc des fiches au premier enregistrement.
        profile = Profile.from_dict(
            {"name": "Zuruï", "camp": "Neutre", "alignment": "Chaotique mauvais"}
        )

        self.assertFalse(hasattr(profile, "alignment"))
        self.assertNotIn("alignment", profile.to_dict())

    def test_normalize_stats_sur_valeur_non_dict(self):
        self.assertEqual(normalize_stats(None), DEFAULT_STATS)

    def test_profile_key(self):
        # La fiche est rattachée au joueur, pas au serveur : elle survit donc
        # à un déplacement du bot d’un serveur à un autre.
        self.assertEqual(profile_key(42, 7), "7")
        self.assertEqual(profile_key(99, 7), profile_key(42, 7))

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
        # Une base vide ne doit pas fabriquer de fichier : le jour où les fiches
        # reviendront (restauration), rien n’aura été écrit à leur place.
        self.assertFalse(self.data_file.exists())

    async def test_database_state_sans_fichier(self):
        path, count = await profiles_module.database_state()

        self.assertEqual(path, self.data_file)
        self.assertEqual(count, 0)

    async def test_database_state_compte_les_fiches(self):
        await save_profile(1, 2, Profile.from_dict({"name": "Zuruï"}))
        await save_profile(1, 3, Profile.from_dict({"name": "Izouk"}))

        path, count = await profiles_module.database_state()

        self.assertEqual(path, self.data_file)
        self.assertEqual(count, 2)

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

    async def test_une_fiche_suit_le_joueur_dun_serveur_a_lautre(self):
        await save_profile(1, 2, Profile.from_dict({"name": "Zuruï"}))

        # Le bot change de serveur : la fiche doit rester visible, sans
        # recréation de la part du joueur.
        moved = await get_profile(9, 2)
        self.assertIsNotNone(moved)
        self.assertEqual(moved.name, "Zuruï")
        self.assertEqual(moved.name, (await get_profile(1, 2)).name)

    async def test_ancienne_cle_serveur_retrouvee_et_migree(self):
        self.data_file.write_text(
            json.dumps(
                {
                    "profiles": {
                        "1:2": {
                            "name": "Ancien",
                            "updatedAt": "2026-01-01T00:00:00+00:00",
                        }
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        # Lue depuis un autre serveur que celui de création.
        profile = await get_profile(9, 2)
        self.assertIsNotNone(profile)
        self.assertEqual(profile.name, "Ancien")

        # Une sauvegarde bascule vers la clé joueur et purge l’ancienne.
        await save_profile(9, 2, profile)
        stored = json.loads(self.data_file.read_text(encoding="utf-8"))["profiles"]
        self.assertIn("2", stored)
        self.assertNotIn("1:2", stored)

    async def test_suppression(self):
        await save_profile(1, 2, Profile.from_dict({"name": "Test"}))
        await delete_profile(1, 2)

        self.assertIsNone(await get_profile(1, 2))

    async def test_restauration_remplace_toute_la_base(self):
        await save_profile(1, 2, Profile.from_dict({"name": "Ancien"}))

        count = await profiles_module.replace_database(
            {"profiles": {"3": {"name": "Nouveau"}, "4": {"name": "Autre"}}}
        )

        self.assertEqual(count, 2)
        self.assertIsNone(await get_profile(1, 2))
        self.assertEqual((await get_profile(1, 3)).name, "Nouveau")
        # La base restaurée est bien écrite sur le disque.
        self.assertIn('"Nouveau"', self.data_file.read_text(encoding="utf-8"))

    async def test_restauration_conserve_une_copie_de_lancienne_base(self):
        await save_profile(1, 2, Profile.from_dict({"name": "Ancien"}))

        await profiles_module.replace_database({"profiles": {"3": {"name": "Nouveau"}}})

        copies = sorted(self.data_file.parent.glob("profiles.json.invalide-*"))
        self.assertEqual(len(copies), 1)
        self.assertIn("Ancien", copies[0].read_text(encoding="utf-8"))

    async def test_restauration_refuse_une_structure_invalide(self):
        with self.assertRaises(ValueError):
            await profiles_module.replace_database({"pas": "une base"})
        with self.assertRaises(ValueError):
            await profiles_module.replace_database({"profiles": {}})

    async def test_les_lectures_ne_relisent_pas_le_disque(self):
        await save_profile(1, 2, Profile.from_dict({"name": "Zuruï"}))

        # Une fois chargée, la base vit en mémoire : plus aucune lecture disque.
        with unittest.mock.patch.object(profiles_module, "_read_database_sync") as reader:
            await get_profile(1, 2)
            await get_profile(1, 2)
            await get_profile(999, 2)

        reader.assert_not_called()

    async def test_ecriture_met_a_jour_memoire_et_disque(self):
        await save_profile(1, 2, Profile.from_dict({"name": "A"}))
        profile = await get_profile(1, 2)
        profile.name = "B"
        await save_profile(1, 2, profile)

        # Visible en mémoire tout de suite, et bien persistée sur le disque.
        self.assertEqual((await get_profile(1, 2)).name, "B")
        self.assertIn('"B"', self.data_file.read_text(encoding="utf-8"))

    async def test_ancien_fichier_est_migre_a_la_lecture(self):
        self.data_file.write_text(
            json.dumps(
                {
                    "profiles": {
                        "1:2": {
                            "name": "Ancien",
                            "characterClass": "Grade 4",
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
        self.assertEqual(profile.stats["force"], 6)

    async def test_json_invalide_leve_une_erreur_claire(self):
        self.data_file.write_text("{cassé", encoding="utf-8")

        with self.assertRaises(RuntimeError):
            await get_profile(1, 2)

    async def test_structure_inattendue_reinitialisee_sans_perdre_la_copie(self):
        original = json.dumps(["pas un objet"], ensure_ascii=False)
        self.data_file.write_text(original, encoding="utf-8")

        self.assertIsNone(await get_profile(1, 2))

        # La base repart vide, mais l’original est conservé à côté : une
        # structure inattendue ne doit jamais détruire les fiches sans trace.
        copies = sorted(self.data_file.parent.glob("profiles.json.invalide-*"))
        self.assertEqual(len(copies), 1)
        self.assertEqual(copies[0].read_text(encoding="utf-8"), original)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
