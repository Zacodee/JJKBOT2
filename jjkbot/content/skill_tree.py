"""Arbre de compétences et règles de déblocage.

Portage fidèle de l’ancien `src/data/skill-tree.js`.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Skill:
    """Un palier de compétence de l’arbre."""

    id: str
    label: str
    branch: str
    cost: int
    prerequisites: tuple[str, ...] = field(default=())


ENERGY = "Énergie occulte"
PHYSICAL = "Stats physiques"
TECHNIQUE = "Sort"
RCT = "Sort d’inversion (RCT)"
BARRIER = "Techniques de barrière"
DOMAIN = "Domaines"

SKILL_TREE: tuple[Skill, ...] = (
    # Énergie occulte et renforcement
    Skill("manipulation_occult_1", "Manipulation occulte I", ENERGY, 0),
    Skill("manipulation_occult_2", "Manipulation occulte II", ENERGY, 20, ("manipulation_occult_1",)),
    Skill("manipulation_occult_3", "Manipulation occulte III", ENERGY, 35, ("manipulation_occult_2",)),
    Skill("manipulation_occult_4", "Manipulation occulte IV", ENERGY, 50, ("manipulation_occult_3",)),
    Skill("manipulation_occult_5", "Manipulation occulte V", ENERGY, 100, ("manipulation_occult_4",)),
    Skill("reinforcement_1", "Renforcement I", ENERGY, 10, ("manipulation_occult_1",)),
    Skill("reinforcement_2", "Renforcement II", ENERGY, 20, ("reinforcement_1",)),
    Skill("reinforcement_3", "Renforcement III", ENERGY, 40, ("reinforcement_2",)),
    Skill("reinforcement_4", "Renforcement IV", ENERGY, 50, ("reinforcement_3", "manipulation_occult_2")),
    Skill("reinforcement_5", "Renforcement V", ENERGY, 50, ("reinforcement_4", "manipulation_occult_3")),
    # Statistiques physiques
    Skill("strength_1", "Force I", PHYSICAL, 0),
    Skill("strength_2", "Force II", PHYSICAL, 35, ("strength_1",)),
    Skill("strength_3", "Force III", PHYSICAL, 35, ("strength_2",)),
    Skill("strength_4", "Force IV", PHYSICAL, 100, ("strength_3",)),
    Skill("speed_1", "Vitesse I", PHYSICAL, 0),
    Skill("speed_2", "Vitesse II", PHYSICAL, 35, ("speed_1",)),
    Skill("speed_3", "Vitesse III", PHYSICAL, 35, ("speed_2",)),
    Skill("speed_4", "Vitesse IV", PHYSICAL, 100, ("speed_3",)),
    Skill("resistance_1", "Résistance I", PHYSICAL, 0),
    Skill("resistance_2", "Résistance II", PHYSICAL, 35, ("resistance_1",)),
    Skill("resistance_3", "Résistance III", PHYSICAL, 35, ("resistance_2",)),
    Skill("resistance_4", "Résistance IV", PHYSICAL, 100, ("resistance_3",)),
    Skill("heavenly_restriction", "Restriction céleste", PHYSICAL, 0),
    # Sorts et extensions
    Skill("basic_extension_1", "Extension de sort basique I", TECHNIQUE, 20),
    Skill("basic_extension_2", "Extension de sort basique II", TECHNIQUE, 20, ("basic_extension_1",)),
    Skill("basic_extension_3", "Extension de sort basique III", TECHNIQUE, 20, ("basic_extension_2",)),
    Skill(
        "basic_extension_4",
        "Extension de sort basique IV",
        TECHNIQUE,
        25,
        ("basic_extension_3", "manipulation_occult_2"),
    ),
    Skill("basic_extension_5", "Extension de sort basique V", TECHNIQUE, 30, ("basic_extension_4",)),
    Skill("expert_extension_1", "Extension de sort experte I", TECHNIQUE, 35, ("basic_extension_5",)),
    Skill("expert_extension_2", "Extension de sort experte II", TECHNIQUE, 35, ("expert_extension_1",)),
    Skill("expert_extension_3", "Extension de sort experte III", TECHNIQUE, 35, ("expert_extension_2",)),
    Skill(
        "maximum_technique",
        "Sort maximum",
        TECHNIQUE,
        75,
        ("expert_extension_3", "manipulation_occult_5"),
    ),
    # Sort d’inversion (RCT)
    Skill("rct_1", "Sort d’inversion I", RCT, 45),
    Skill("rct_2", "Sort d’inversion II", RCT, 55, ("rct_1",)),
    Skill("rct_3", "Sort d’inversion III", RCT, 70, ("rct_2",)),
    Skill("rct_4", "Sort d’inversion IV", RCT, 70, ("rct_3",)),
    Skill("rct_5", "Sort d’inversion absolue", RCT, 100, ("rct_4",)),
    Skill("reverse_extension", "Extension de sort inversée", RCT, 50, ("rct_3",)),
    # Barrières
    Skill("barrier_1", "Barrière I — Rideaux", BARRIER, 10),
    Skill("barrier_2", "Barrière II", BARRIER, 20, ("barrier_1",)),
    Skill("barrier_3", "Barrière III", BARRIER, 35, ("barrier_2", "manipulation_occult_3")),
    Skill("barrier_4", "Barrière IV", BARRIER, 60, ("barrier_3",)),
    Skill("barrier_5", "Barrière V", BARRIER, 80, ("barrier_4",)),
    # Domaines
    Skill("simple_domain_1", "Territoire simple I", DOMAIN, 20, ("barrier_3",)),
    Skill("simple_domain_2", "Territoire simple II", DOMAIN, 20, ("simple_domain_1",)),
    Skill("simple_domain_3", "Territoire simple III", DOMAIN, 50, ("simple_domain_2",)),
    Skill("anti_domain", "Mesures anti-domaines", DOMAIN, 0, ("simple_domain_2",)),
    Skill("petal_rain", "Pluie de pétales épris", DOMAIN, 50, ("anti_domain",)),
    Skill("void_basket", "Arcane — Panier du vide", DOMAIN, 50, ("anti_domain",)),
    Skill("domain_extension_1", "Extension du territoire I", DOMAIN, 75, ("barrier_3",)),
    Skill(
        "domain_extension_2",
        "Extension du territoire II",
        DOMAIN,
        100,
        ("domain_extension_1", "barrier_4"),
    ),
    Skill(
        "domain_extension_3",
        "Extension du territoire III",
        DOMAIN,
        50,
        ("domain_extension_2", "barrier_5"),
    ),
    Skill("territory_prolongation", "Prolongement du territoire", DOMAIN, 100, ("barrier_4",)),
    Skill("open_domain", "Territoire ouvert", DOMAIN, 150, ("barrier_5", "manipulation_occult_5")),
)

SKILLS_BY_ID: dict[str, Skill] = {skill.id: skill for skill in SKILL_TREE}

# Catégories, dans l’ordre d’apparition dans l’arbre.
BRANCHES: tuple[str, ...] = tuple(dict.fromkeys(skill.branch for skill in SKILL_TREE))


def get_skill(skill_id: str) -> Skill | None:
    """Renvoie la compétence correspondante, ou None si elle n’existe pas."""
    return SKILLS_BY_ID.get(skill_id)


def get_skills_for_branch(branch: str) -> list[Skill]:
    """Renvoie les paliers d’une catégorie, dans l’ordre de l’arbre."""
    return [skill for skill in SKILL_TREE if skill.branch == branch]


def get_missing_prerequisites(skill_id: str, unlocked_skills=()) -> list[Skill]:
    """Renvoie les prérequis non débloqués d’une compétence."""
    skill = get_skill(skill_id)
    if skill is None:
        return []

    unlocked = set(unlocked_skills)
    missing: list[Skill] = []
    for prerequisite_id in skill.prerequisites:
        prerequisite = get_skill(prerequisite_id)
        if prerequisite is not None and prerequisite.id not in unlocked:
            missing.append(prerequisite)
    return missing


def can_unlock_skill(profile, skill: Skill | None) -> bool:
    """Indique si un profil peut acheter une compétence immédiatement."""
    if skill is None:
        return False

    unlocked = profile.unlocked_skills
    if skill.id in unlocked:
        return False

    return profile.experience >= skill.cost and not get_missing_prerequisites(skill.id, unlocked)
