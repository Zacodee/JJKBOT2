"""Définition des statistiques d’un personnage."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StatDefinition:
    """Une statistique du personnage.

    `emoji` est la clé du catalogue d’emojis (voir `config/emojis.json`).
    """

    id: str
    label: str
    emoji: str


STAT_DEFINITIONS: tuple[StatDefinition, ...] = (
    StatDefinition(id="force", label="Force", emoji="force"),
    StatDefinition(id="resistance", label="Résistance", emoji="resistance"),
    StatDefinition(id="vitesse", label="Vitesse", emoji="vitesse"),
    StatDefinition(id="reserveEO", label="Réserve d'EO", emoji="reserve_eo"),
    StatDefinition(id="sortieEO", label="Sortie d'EO", emoji="sortie_eo"),
)

DEFAULT_STATS: dict[str, int] = {stat.id: 0 for stat in STAT_DEFINITIONS}

STATS_BY_ID: dict[str, StatDefinition] = {stat.id: stat for stat in STAT_DEFINITIONS}


def get_stat(stat_id: str) -> StatDefinition | None:
    """Renvoie la statistique correspondante, ou None si elle n’existe pas."""
    return STATS_BY_ID.get(stat_id)
