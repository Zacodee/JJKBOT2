"""Règles du Black Flash : probabilités, empilement, traits et buffs narratifs.

Le Black Flash est le coup rarissime de l’univers de Jujutsu Kaisen :

- **5 %** de chance de base ;
- **+5 %** à chaque succès, jusqu’à un plafond de **100 %** ;
- retour à la **base effective** dès qu’un essai échoue.

La base effective vaut 5 % par défaut, mais certains traits de la fiche la
relèvent (« Béni de l’étincelle » = 20 %, « Adepte du Black Flash » = 10 %), et
« Fièvre » ajoute +5 %. Un échec ramène donc à *cette* base, pas à 5 % : sans
cela, un simple raté effacerait le bonus du trait.

Le coup réussi donne un **buff de statistiques** : **+30 % de Force** sur le
coup porté (effet instantané, décrit dans l’embed), puis **+10 % à toutes les
statistiques attribuables** (Réserve d’EO exceptée) pendant **3 tours**. Ce buff
vit dans la fiche et s’affiche dans `/profil voir` tant qu’il reste des tours.
Un Black Flash rend en outre **75 EO**, annoncé dans l’embed du coup (gain
narratif : la fiche n’est pas modifiée).

S’y ajoute le **Record Man du Rayon Noir** : quatre succès consécutifs donnent
un titre **personnel** — chaque joueur le décroche pour lui-même, définitivement,
sans le prendre à personne — et une augmentation permanente de chance
(`RECORD_BONUS`, `MORTAL_RECORD_BONUS` en Combat Mortel). La série en cours et le
record personnel vivent tous deux dans la fiche (`blackflashStreak`,
`blackflashRecord`).
"""

from __future__ import annotations

import json
import logging
import random
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from jjkbot import config
from jjkbot.content.stats import SPENDABLE_STATS

logger = logging.getLogger(__name__)

# Probabilité de départ, en pourcentage.
BASE_CHANCE = 5
# Gain apporté par chaque succès, en pourcentage.
CHANCE_STEP = 5
# Plafond d’empilement, en pourcentage.
MAX_CHANCE = 100

# --- Record Man du Rayon Noir --------------------------------------------
#
# Quatre Rayons Noirs **consécutifs** (dans un même combat, donc sans échec et
# sans `/jjk blackflash-reset`) décrochent le titre de « recordman du Rayon
# Noir ». Le titre est **personnel** : chaque joueur le décroche pour lui-même et
# le garde — il n’y a pas un détenteur unique, et personne ne peut le lui
# reprendre. Il donne une augmentation **permanente** de chance, qui passe du
# double lors d’un **Combat Mortel**.
#
# Le bonus est traité comme un plancher (voir `effective_base`) : il survit donc
# à un échec comme à une fin de combat.
RECORD_STREAK = 4
RECORD_BONUS = 10
MORTAL_RECORD_BONUS = 20

# --- Buff de statistiques -------------------------------------------------
#
# Un Black Flash réussi ne fait pas que relever la chance de le refaire : il
# embrase le personnage. Le coup porté gagne **+30 % de Force** — effet
# instantané, purement narratif, qui ne vit que dans l’embed du coup — puis
# **toutes les statistiques attribuables** (Force, Résistance, Vitesse,
# Manipulation occulte, Sortie d’EO) gagnent **+10 %** pendant **3 tours**. La
# Réserve d’EO, figée à la création (`StatDefinition.fixed`), en est exclue.
#
# Le buff vit dans la fiche (`blackflashBuffTurns`) et s’applique à l’affichage
# des statistiques : `/profil voir` montre donc les valeurs buffées tant qu’il
# reste des tours. Le staff peut le fixer ou le retirer avec `/blackflash buff`
# (voir `cogs.blackflash`), puisque le bot ne suit pas les tours de combat.
STRIKE_FORCE_PERCENT = 30
BUFF_STAT_PERCENT = 10
BUFF_TURNS = 3
# Borne du compteur, pour une correction manuelle du staff.
MAX_BUFF_TURNS = 99

# Energie rendue au personnage par un Black Flash réussi. C’est un gain
# **narratif**, écrit dans l’embed du coup pour le joueur : il ne touche pas la
# fiche (ni la Réserve d’EO, qui reste une statistique figée) et n’apparaît donc
# pas dans `/profil voir`.
EO_RESTORE = 75

# Textes narratifs des deux issues (adaptés des écrans de référence).
SUCCESS_TEXT = (
    "Ton coup touche avec succès l’adversaire mais quelque chose de surréaliste arrive, "
    "à l’impact c’est comme si tu avais tordu la réalité autour de toi pendant une fraction "
    "de seconde, et c’est normal car tu viens tout juste de réaliser un Rayon noir ! "
    "Boostant tes capacités pendant un temps limité."
)
FAIL_TEXT = (
    "Ton coup touche avec succès l’adversaire mais rien ne se passe, c’est comme si tu "
    "donnais un coup tout à fait banal, tu n’obtiens donc aucune récompense, malheureusement."
)

# Buffs rappelés dans le bloc de code de l’embed de succès.
BUFFS_TEXT = (
    f"+{STRIKE_FORCE_PERCENT}% de Force sur le coup, puis "
    f"+{BUFF_STAT_PERCENT}% à toutes les stats (Réserve d’EO exceptée) "
    f"pendant {BUFF_TURNS} tours"
)
NO_BUFF_TEXT = "Rien."


def buffed_value(value, turns: int, percent: int = BUFF_STAT_PERCENT) -> int:
    """Valeur d’une statistique sous l’effet du buff du Rayon Noir.

    Le pourcentage est arrondi **au supérieur** (10 % de 5 vaut 1, pas 0) : un
    petit bonus ne doit jamais disparaître par troncature.
    """
    if turns <= 0 or percent <= 0:
        return int(value or 0)
    base = int(value or 0)
    bonus = (base * percent + 99) // 100
    return base + bonus


def apply_stat_buff(stats, turns: int) -> dict[str, int]:
    """Statistiques affichées : buff appliqué aux seules statistiques attribuables.

    La Réserve d’EO n’est pas dans `SPENDABLE_STATS` : elle reste donc intacte.
    """
    result = dict(stats or {})
    if turns <= 0:
        return result
    for stat in SPENDABLE_STATS:
        result[stat.id] = buffed_value(result.get(stat.id, 0), turns)
    return result


# --- Traits et évènements -------------------------------------------------
#
# Certains traits de la fiche (texte libre) augmentent naturellement les chances
# de Black Flash. La correspondance vit dans `config/blackflash.json`, éditable
# sans toucher au code, avec les valeurs par défaut ci-dessous si le fichier est
# absent ou invalide — comme le catalogue d’emojis.
#
# Deux familles d’effets :
#   • `base`  : plancher imposé au joueur (« Béni de l’étincelle » = 20) ;
#   • `bonus` : points ajoutés à la base (« Fièvre » = +5).
# Un effet `exclusive` ignore tout le reste : « Béni de l’étincelle » ne se
# cumule donc jamais avec « Fièvre », tandis qu’« Adepte du Black Flash » (base)
# s’additionne bien avec « Fièvre » (bonus).


@dataclass(frozen=True)
class TraitEffect:
    """Effet d’un trait ou d’un évènement sur les chances de Black Flash."""

    base: int = 0
    bonus: int = 0
    exclusive: bool = False
    label: str = ""


def normalize_label(text: str) -> str:
    """Clé de reconnaissance d’un trait : casse, accents et espaces neutralisés.

    Les traits sont du texte libre : sans cette normalisation, « Fièvre »,
    « FIEVRE » ou «  fièvre  » seraient vus comme trois traits différents.
    """
    decomposed = unicodedata.normalize("NFKD", str(text))
    without_accents = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    # Les apostrophes typographiques et accents graves deviennent l’apostrophe
    # droite, pour que « Béni de l’étincelle » et « Béni de l’etincelle » se
    # rejoignent.
    folded = without_accents.replace("’", "'").replace("`", "'")
    return " ".join(folded.casefold().split())


# Effets canoniques (une seule instance réutilisée par tous leurs alias).
_FIEVRE = TraitEffect(bonus=5, label="Fièvre")
_BENI = TraitEffect(base=20, exclusive=True, label="Béni de l’étincelle")
_ADEPTE = TraitEffect(base=10, label="Adepte du Black Flash")

# Les clés sont déjà normalisées. Les « alias » couvrent les variantes que la
# normalisation ne peut pas deviner : mots collés, apostrophe remplacée par un
# espace, abréviations. Pour toute autre écriture, ajoute un alias dans
# `config/blackflash.json`.
DEFAULT_TRAIT_EFFECTS: dict[str, TraitEffect] = {
    "fievre": _FIEVRE,
    "beni de l'etincelle": _BENI,
    "beni etincelle": _BENI,
    "beni de l etincelle": _BENI,
    "adepte du black flash": _ADEPTE,
    "adepte du blackflash": _ADEPTE,
    "adepte black flash": _ADEPTE,
    "adepte bf": _ADEPTE,
    # « Rayon noir » est le nom français du Black Flash : c’est l’écriture
    # qu’un joueur francophone emploie naturellement sur sa fiche.
    "adepte du rayon noir": _ADEPTE,
    "adepte rayon noir": _ADEPTE,
    "adepte du rayon noire": _ADEPTE,
    "adepte rayon noire": _ADEPTE,
}


def _clamp(value, default: int = 0) -> int:
    """Entier borné à [0, MAX_CHANCE], `default` si la valeur n’est pas un nombre."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return max(0, min(MAX_CHANCE, int(value)))


def load_trait_effects(path=None) -> dict[str, TraitEffect]:
    """Charge `config/blackflash.json`, complété par les effets par défaut.

    Chaque clé (et ses `aliases`) est normalisée : le fichier peut donc écrire
    les traits avec leurs accents et majuscules, comme sur la fiche.
    """
    effects = dict(DEFAULT_TRAIT_EFFECTS)
    source = Path(path) if path is not None else Path(config.BLACKFLASH_FILE)

    try:
        with open(source, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except FileNotFoundError:
        logger.warning(
            "config/blackflash.json est introuvable : seuls les traits par défaut "
            "sont reconnus."
        )
        return effects
    except (json.JSONDecodeError, OSError) as error:
        logger.error(
            "config/blackflash.json illisible (%s) : traits par défaut conservés.", error
        )
        return effects

    if not isinstance(raw, dict):
        logger.error("config/blackflash.json doit contenir un objet JSON.")
        return effects

    for key, value in raw.items():
        if not isinstance(value, dict):
            continue
        base = _clamp(value.get("base"))
        bonus = _clamp(value.get("bonus"))
        if base == 0 and bonus == 0:
            continue
        raw_label = value.get("label")
        label = raw_label.strip() if isinstance(raw_label, str) and raw_label.strip() else str(key)
        effect = TraitEffect(
            base=base,
            bonus=bonus,
            exclusive=bool(value.get("exclusive")),
            label=label,
        )
        aliases = value.get("aliases")
        names = [key, *(aliases if isinstance(aliases, list) else [])]
        for name in names:
            effects[normalize_label(name)] = effect
    return effects


# Table en mémoire, rechargée seulement si le chemin change (comme les fiches).
_effects_cache: dict[Path, dict[str, TraitEffect]] = {}


def trait_effects() -> dict[str, TraitEffect]:
    """Table des effets chargée depuis le disque, mise en cache par chemin."""
    path = Path(config.BLACKFLASH_FILE)
    if path not in _effects_cache:
        _effects_cache[path] = load_trait_effects(path)
    return _effects_cache[path]


def trait_modifiers(traits) -> tuple[int, int]:
    """Renvoie `(plancher, bonus)` apportés par les traits reconnus d’une fiche.

    Un trait « exclusif » (« Béni de l’étincelle ») ignore tous les autres :
    c’est le seul cas où un bonus additif comme « Fièvre » ne s’applique pas.
    """
    effects = trait_effects()
    recognized = [
        effects[key]
        for key in (normalize_label(trait) for trait in traits or ())
        if key in effects
    ]
    if not recognized:
        return 0, 0

    exclusive = [effect for effect in recognized if effect.exclusive]
    if exclusive:
        return max(effect.base for effect in exclusive), 0

    base = max((effect.base for effect in recognized), default=0)
    bonus = sum(effect.bonus for effect in recognized)
    return base, bonus


def record_bonus(mortal: bool = False) -> int:
    """Chance permanente du recordman : `RECORD_BONUS`, doublée en Combat Mortel.

    Réservé aux joueurs qui ont décroché le titre (record personnel au moins
    égal à `RECORD_STREAK`) : les autres ne reçoivent rien.
    """
    return MORTAL_RECORD_BONUS if mortal else RECORD_BONUS


def effective_base(traits, base_override=None, bonus_override=0, record_bonus=0) -> int:
    """Base de chance d’une fiche : traits compris, exception du staff incluse.

    C’est la chance à laquelle un échec (ou `/jjk blackflash-reset`) ramène le
    joueur. Le plafond `MAX_CHANCE` s’applique ici aussi.

    `record_bonus` est l’augmentation permanente du **recordman du Rayon Noir**
    (+10, +20 en Combat Mortel) : la passer ici en fait un plancher, si bien
    qu’un raté ne la retire pas — c’est ce que veut dire « définitivement ».
    """
    trait_base, trait_bonus = trait_modifiers(traits)
    base = max(BASE_CHANCE, trait_base, _clamp(base_override))
    bonus = trait_bonus + _clamp(bonus_override) + _clamp(record_bonus)
    return min(MAX_CHANCE, base + bonus)


# --- Tirage ---------------------------------------------------------------


def normalize(chance) -> int:
    """Chance ramenée à un entier compris entre 0 et `MAX_CHANCE`."""
    try:
        value = int(chance)
    except (TypeError, ValueError):
        return BASE_CHANCE
    return max(0, min(MAX_CHANCE, value))


def roll(chance: int, *, randint=random.randint) -> bool:
    """Tirage d’une tentative : réussie si le dé (1-100) tombe dans la chance.

    `randint` est injectable pour rendre les tests déterministes.
    """
    return randint(1, 100) <= normalize(chance)


def next_chance(chance: int, success: bool, base: int = BASE_CHANCE) -> int:
    """Chance suivante : +5 % par succès (plafond 100 %), retour à `base` à l’échec.

    `base` est la base effective du joueur (traits compris) : sans elle, un échec
    effacerait le plancher d’un trait comme « Béni de l’étincelle ».
    """
    if success:
        return min(MAX_CHANCE, normalize(chance) + CHANCE_STEP)
    return normalize(base)
