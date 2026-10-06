"""Types d’interaction d’une demande d’XP.

Le joueur choisit dans le formulaire la nature de la scène qu’il déclare. Ces
types servent au staff à lire la demande d’un coup d’œil ; ils ne fixent aucun
barème — le montant demandé est libre, le staff juge (décision produit).

L’`id` est la valeur stockée (stable, sans accent) ; le `label` est ce que le
joueur lit dans le menu déroulant.
"""

from __future__ import annotations

from dataclasses import dataclass

# Bornes du montant demandé, alignées sur les autres commandes d’XP.
MIN_AMOUNT = 1
MAX_AMOUNT = 100000


@dataclass(frozen=True)
class InteractionType:
    """Nature d’une scène, telle que déclarée par le joueur."""

    id: str
    label: str


INTERACTION_TYPES: tuple[InteractionType, ...] = (
    InteractionType("interaction_personnelle", "Interaction personnelle"),
    InteractionType("interaction_serieuse", "Interaction sérieuse"),
    InteractionType("interaction_profonde", "Interaction profonde"),
    InteractionType("combat_personnel", "Combat personnel"),
    InteractionType("combat_serieux", "Combat sérieux"),
    InteractionType("combat_profond", "Combat profond"),
    InteractionType("mission", "Mission"),
)

INTERACTION_TYPES_BY_ID: dict[str, InteractionType] = {
    interaction.id: interaction for interaction in INTERACTION_TYPES
}

DEFAULT_INTERACTION = INTERACTION_TYPES[0].id


def get_interaction_type(interaction_id: str) -> InteractionType | None:
    """Type d’interaction correspondant, ou None si l’identifiant est inconnu."""
    return INTERACTION_TYPES_BY_ID.get(interaction_id)


def label_of(interaction_id: str) -> str:
    """Libellé lisible d’un type, avec repli sur l’identifiant brut."""
    interaction = INTERACTION_TYPES_BY_ID.get(interaction_id)
    return interaction.label if interaction is not None else interaction_id
