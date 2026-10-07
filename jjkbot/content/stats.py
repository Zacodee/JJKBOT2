"""Définition des statistiques d’un personnage."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StatDefinition:
    """Une statistique du personnage.

    `emoji` est la clé du catalogue d’emojis (voir `config/emojis.json`).

    `fixed` marque une statistique **non attribuable** : elle est définie à la
    création du personnage et ne bouge plus — un staff peut seul la modifier.
    On ne peut donc y dépenser aucun point ; elle n’entre ni dans le total
    réparti ni dans les barres de progression, et la page Statistiques
    l’affiche dans son propre bloc, sous un filet et cadenassée.
    """

    id: str
    label: str
    emoji: str
    fixed: bool = False


# Identifiant de la statistique fixée à la création du personnage.
RESERVE_EO_ID = "reserveEO"

STAT_DEFINITIONS: tuple[StatDefinition, ...] = (
    StatDefinition(id="force", label="Force", emoji="force"),
    StatDefinition(id="resistance", label="Résistance", emoji="resistance"),
    StatDefinition(id="vitesse", label="Vitesse", emoji="vitesse"),
    StatDefinition(id="manipulationEO", label="Manipulation occulte", emoji="manipulation_eo"),
    StatDefinition(id="sortieEO", label="Sortie d'EO", emoji="sortie_eo"),
    # En dernière position et marquée `fixed` : la page Statistiques la range
    # dans son propre bloc, après les statistiques que les points font vivre.
    StatDefinition(id=RESERVE_EO_ID, label="Réserve d'EO", emoji="reserve_eo", fixed=True),
)

DEFAULT_STATS: dict[str, int] = {stat.id: 0 for stat in STAT_DEFINITIONS}

STATS_BY_ID: dict[str, StatDefinition] = {stat.id: stat for stat in STAT_DEFINITIONS}

# La Réserve d’EO est la seule statistique `fixed` : aucun point ne s’y dépense,
# c’est le staff qui la fixe à la validation de la fiche RP (voir `/jjk eo`).
RESERVE_EO: StatDefinition = STATS_BY_ID[RESERVE_EO_ID]

# Borne haute de la Réserve d’EO posée par le staff, alignée sur les autres
# commandes de statistiques.
MAX_RESERVE_EO = 100000

# Statistiques attribuables : seules elles acceptent des points de statistique.
SPENDABLE_STATS: tuple[StatDefinition, ...] = tuple(
    stat for stat in STAT_DEFINITIONS if not stat.fixed
)

# Statistiques gelées à la création (affichage distinct, aucun point possible).
FIXED_STATS: tuple[StatDefinition, ...] = tuple(stat for stat in STAT_DEFINITIONS if stat.fixed)


def get_stat(stat_id: str) -> StatDefinition | None:
    """Renvoie la statistique correspondante, ou None si elle n’existe pas."""
    return STATS_BY_ID.get(stat_id)
