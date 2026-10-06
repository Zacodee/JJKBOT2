"""Nuancier de couleurs d’embed et analyse d’un code hexadécimal.

Un joueur peut teinter sa fiche soit par un nom du nuancier (menu déroulant
dans `/profil couleur`), soit par un code hexadécimal libre (`#RRGGBB`,
`RRGGBB`, `0xRRGGBB` ou la forme courte `#RGB`). La couleur est stockée telle
quelle sur la fiche ; en son absence, le thème du bot décide.
"""

from __future__ import annotations

import re
import unicodedata

# Nuancier proposé dans le menu déroulant de `/profil couleur`. Les valeurs sont
# des couleurs assez saturées pour rester lisibles sur le fond sombre d’un
# embed Discord ; les noms sont le libellé affiché au joueur.
NAMED_COLORS: dict[str, int] = {
    "Rubis": 0xE0115F,
    "Azur": 0x007FFF,
    "Émeraude": 0x50C878,
    "Saphir": 0x0F52BA,
    "Améthyste": 0x9966CC,
    "Or": 0xD4AF37,
    "Turquoise": 0x40E0D0,
    "Corail": 0xFF7F50,
    "Prune": 0x8E4585,
    "Ardoise": 0x708090,
    "Sakura": 0xFFB7C5,
    "Menthe": 0x98FF98,
    "Indigo": 0x4B0082,
    "Cuivre": 0xB87333,
    "Olive": 0x808000,
    "Bordeaux": 0x7B1E26,
    "Ciel": 0x87CEEB,
    "Citron": 0xF7E233,
    "Lavande": 0xB57EDC,
    "Aigue-marine": 0x7FFFD4,
    "Framboise": 0xE30B5C,
    "Ivoire": 0xFFFFF0,
    "Charbon": 0x36454F,
    "Jade": 0x00A86B,
}

_HEX_LONG = re.compile(r"^[0-9a-f]{6}$")
_HEX_SHORT = re.compile(r"^[0-9a-f]{3}$")


def _normalize(text: str) -> str:
    """Clé de recherche d’un nom : sans accents, sans casse, tirets unifiés."""
    decomposed = unicodedata.normalize("NFKD", text.strip().casefold())
    stripped = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(stripped.replace("-", " ").replace("_", " ").split())


# Table nom normalisé → couleur, construite une fois pour les recherches.
_NORMALIZED: dict[str, int] = {_normalize(name): value for name, value in NAMED_COLORS.items()}


def parse_hex(text: str) -> int | None:
    """Convertit un code hexadécimal en entier, ou None s’il est invalide.

    Accepte `#RRGGBB`, `RRGGBB`, `0xRRGGBB` et la forme courte `#RGB` (chaque
    chiffre est alors doublé, comme le veut la notation CSS `#abc`).
    """
    if not isinstance(text, str):
        return None
    candidate = text.strip().lower()
    if candidate.startswith("#"):
        candidate = candidate[1:]
    elif candidate.startswith("0x"):
        candidate = candidate[2:]
    if _HEX_LONG.match(candidate):
        return int(candidate, 16)
    if _HEX_SHORT.match(candidate):
        return int("".join(char * 2 for char in candidate), 16)
    return None


def resolve(text: str) -> int | None:
    """Couleur d’un nom du nuancier ou d’un code hexadécimal, sinon None."""
    if not isinstance(text, str) or not text.strip():
        return None

    color = parse_hex(text)
    if color is not None:
        return color

    return _NORMALIZED.get(_normalize(text))


def hex_label(color: int) -> str:
    """Code hexadécimal lisible (`#RRGGBB`) d’une couleur entière."""
    return f"#{color & 0xFFFFFF:06X}"
