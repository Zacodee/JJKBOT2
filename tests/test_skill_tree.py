"""Tests de l’arbre de compétences."""

import unittest

from jjkbot.content.skill_tree import (
    BRANCHES,
    SKILL_TREE,
    can_unlock_skill,
    get_missing_prerequisites,
    get_skill,
    get_skills_for_branch,
)
from jjkbot.content.stats import DEFAULT_STATS
from jjkbot.storage.profiles import Profile


class SkillTreeIntegrityTests(unittest.TestCase):
    def test_identifiants_uniques(self):
        identifiers = [skill.id for skill in SKILL_TREE]

        self.assertEqual(len(identifiers), len(set(identifiers)))

    def test_tous_les_prerequis_existent(self):
        for skill in SKILL_TREE:
            for prerequisite in skill.prerequisites:
                self.assertIsNotNone(get_skill(prerequisite), f"prérequis inconnu : {prerequisite}")

    def test_aucun_cycle_direct(self):
        for skill in SKILL_TREE:
            self.assertNotIn(skill.id, skill.prerequisites)

    def test_categories_et_libelles(self):
        self.assertEqual(len(BRANCHES), 6)
        self.assertEqual(BRANCHES[0], "Énergie occulte")
        for branch in BRANCHES:
            self.assertTrue(get_skills_for_branch(branch))

    def test_couts_positifs_et_libelles_courts(self):
        for skill in SKILL_TREE:
            self.assertGreaterEqual(skill.cost, 0)
            self.assertLessEqual(len(skill.label), 100)


class SkillUnlockTests(unittest.TestCase):
    def make_profile(self, experience=0, unlocked=()):
        profile = Profile()
        profile.stats = dict(DEFAULT_STATS)
        profile.experience = experience
        profile.unlocked_skills = list(unlocked)
        return profile

    def test_competence_sans_prerequis_achetable_avec_assez_dxp(self):
        profile = self.make_profile(experience=0)

        self.assertTrue(can_unlock_skill(profile, get_skill("manipulation_occult_1")))

    def test_xp_insuffisante(self):
        profile = self.make_profile(experience=5)

        self.assertFalse(can_unlock_skill(profile, get_skill("manipulation_occult_2")))

    def test_prerequis_manquant(self):
        profile = self.make_profile(experience=500)

        self.assertFalse(can_unlock_skill(profile, get_skill("manipulation_occult_2")))
        self.assertEqual(
            [skill.id for skill in get_missing_prerequisites("manipulation_occult_2", [])],
            ["manipulation_occult_1"],
        )

    def test_debloquable_une_fois_le_prerequis_obtenu(self):
        profile = self.make_profile(experience=500, unlocked=("manipulation_occult_1",))

        self.assertTrue(can_unlock_skill(profile, get_skill("manipulation_occult_2")))

    def test_competence_deja_debloquee_non_rachetable(self):
        profile = self.make_profile(experience=500, unlocked=("manipulation_occult_1",))

        self.assertFalse(can_unlock_skill(profile, get_skill("manipulation_occult_1")))

    def test_competence_inexistante(self):
        profile = self.make_profile(experience=500)

        self.assertFalse(can_unlock_skill(profile, None))
        self.assertEqual(get_missing_prerequisites("inconnue", []), [])
        self.assertIsNone(get_skill("inconnue"))

    def test_prerequis_multiples(self):
        # « Renforcement IV » exige Renforcement III et Manipulation occulte II.
        profile = self.make_profile(experience=500, unlocked=("reinforcement_3",))

        self.assertEqual(
            [skill.id for skill in get_missing_prerequisites("reinforcement_4", profile.unlocked_skills)],
            ["manipulation_occult_2"],
        )

    def test_tout_larbre_est_franchissable_avec_suffisamment_dxp(self):
        profile = self.make_profile(experience=10000)
        for _ in range(len(SKILL_TREE)):
            for skill in SKILL_TREE:
                if can_unlock_skill(profile, skill):
                    profile.unlocked_skills.append(skill.id)
                    break

        self.assertEqual(len(profile.unlocked_skills), len(SKILL_TREE))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
