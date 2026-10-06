"""Règles de la Renaissance en Esprit Vengeur : seuils, tirage et textes.

Certains défunts refusent de disparaître : à la **mort définitive** d’un
personnage, un dé de 100 décide si son âme renaît en **Esprit Vengeur**. Le
seuil de réussite dépend des circonstances de la mort :

- **5 ou moins** : condition de base ;
- **10 ou moins** : le personnage nourrissait du ressentiment envers la
  personne responsable de sa mort ;
- **15 ou moins** : cette personne était son **rival**.

Ce n’est pas une résurrection : le personnage revient sous une forme maudite,
sa personnalité altérée par les émotions de sa mort. La renaissance se joue en
RP et ses capacités sont redéfinies avec le staff.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

# Bornes du dé de 100.
MIN_ROLL = 1
MAX_ROLL = 100


@dataclass(frozen=True)
class Situation:
    """Circonstance de la mort, qui relève le seuil de réussite."""

    id: str
    label: str
    threshold: int


SITUATIONS: tuple[Situation, ...] = (
    Situation("base", "Mort sans circonstance particulière", 5),
    Situation("ressentiment", "Ressentiment envers le responsable de sa mort", 10),
    Situation("rival", "Le responsable de sa mort était son rival", 15),
)
SITUATIONS_BY_ID: dict[str, Situation] = {situation.id: situation for situation in SITUATIONS}
DEFAULT_SITUATION = "base"

# Textes narratifs des deux issues.
SUCCESS_TEXT = (
    "Ton personnage devait disparaître… et pourtant son âme refuse de céder. "
    "Une haine trop profonde, un ressentiment impossible à apaiser ou un "
    "attachement trop puissant le retiennent à ce monde : la mort n’aura pas "
    "le dernier mot. Il renaît sous la forme d’un **Esprit Vengeur**, à jamais "
    "marqué par les émotions qui l’habitaient à l’instant de sa mort."
)
FAIL_TEXT = (
    "Malgré tout ce qui le retenait encore, l’âme de ton personnage finit par "
    "se dissiper : la mort reste la fin de son existence, et aucune renaissance "
    "n’aura lieu."
)


def get_situation(situation) -> Situation:
    """Situation connue, ou la condition de base si l’identifiant est inconnu."""
    return SITUATIONS_BY_ID.get(situation, SITUATIONS_BY_ID[DEFAULT_SITUATION])


def threshold(situation=DEFAULT_SITUATION) -> int:
    """Seuil de réussite de la situation, en pourcentage."""
    return get_situation(situation).threshold


def roll(*, randint=random.randint) -> int:
    """Tirage d’un dé de 1 à 100.

    `randint` est injectable pour rendre les tests déterministes.
    """
    return randint(MIN_ROLL, MAX_ROLL)


def success(die: int, situation=DEFAULT_SITUATION) -> bool:
    """Réussite si le dé est **inférieur ou égal** au seuil de la situation."""
    try:
        value = int(die)
    except (TypeError, ValueError):
        return False
    return value <= threshold(situation)
