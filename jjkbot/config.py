"""Configuration du bot, lue depuis le fichier `.env`."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT_DIR / ".env"

# Le .env est chargé sans écraser les variables déjà présentes dans
# l’environnement : sur un hébergeur, ce sont ces dernières qui gagnent.
load_dotenv(ENV_FILE)

# Variables sans lesquelles le bot ne peut pas démarrer.
REQUIRED: tuple[str, ...] = ("DISCORD_TOKEN",)


class ConfigError(RuntimeError):
    """Erreur de configuration : une variable obligatoire est absente."""


def missing_required() -> list[str]:
    """Variables obligatoires absentes de l’environnement (et du .env)."""
    return [name for name in REQUIRED if not os.getenv(name, "").strip()]


def check_required() -> None:
    """Vérifie la configuration au démarrage et explique quoi faire si besoin."""
    missing = missing_required()
    if not missing:
        return

    state = "trouvé" if ENV_FILE.exists() else "absent"
    raise ConfigError(
        "Configuration incomplète — variable(s) obligatoire(s) manquante(s) : "
        f"{', '.join(missing)}. "
        f"Fichier .env attendu : {ENV_FILE} ({state}). "
        "Renseigne ces variables dans le panneau de l’hébergeur "
        "(onglet « Startup » > « Environment Variables »), ou crée le fichier .env "
        "à la racine du projet via le gestionnaire de fichiers (voir .env.example)."
    )


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigError(
            f"La variable d’environnement {name} est manquante. "
            "Renseigne-la dans le panneau de l’hébergeur ou dans le fichier .env."
        )
    return value


def _optional(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None


def _optional_int(name: str) -> int | None:
    value = _optional(name)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError as error:
        raise ConfigError(f"La variable d’environnement {name} doit être un identifiant numérique.") from error


def token() -> str:
    """Token du bot (lecture paresseuse : l’absence est signalée au démarrage)."""
    return _required("DISCORD_TOKEN")


def client_id() -> int:
    """Identifiant de l’application Discord."""
    value = _optional_int("CLIENT_ID")
    return value if value is not None else int(_required("CLIENT_ID"))


GUILD_ID: int | None = _optional_int("GUILD_ID")

BANNER_URL: str | None = _optional("BANNER_URL")
HELP_GIF_URL: str | None = _optional("HELP_GIF_URL")
STAFF_ROLE_ID: int | None = _optional_int("STAFF_ROLE_ID")

# Palette active : « violet » (défaut) ou « noblesse ».
THEME: str = (os.getenv("THEME", "").strip().lower() or "violet")

# Dossier des données du bot : fiches (`profiles.json`) et images de personnage.
#
# Par défaut c’est `data/` à côté du code — le dossier qu’un `git clone`
# régénère vide. Sur un hébergeur qui **remplace** le dossier à chaque
# déploiement (clone Git), cela efface les fiches à chaque mise à jour : il faut
# alors pointer `DATA_DIR` vers un stockage persistant hors du dépôt, par ex.
# `DATA_DIR=/data/jjkbot`.
DATA_DIR: Path = Path(_optional("DATA_DIR") or (ROOT_DIR / "data")).expanduser()
DATA_FILE: Path = DATA_DIR / "profiles.json"
IMAGES_DIR: Path = DATA_DIR / "images"
# Réglages par serveur (salon des demandes d’XP) et demandes d’XP en attente.
# Ils vivent dans DATA_DIR et non dans `config/` : ce dernier est écrasé à
# chaque déploiement (clone Git), ce qui perdrait le salon configuré et
# rendrait non cliquables les demandes déjà envoyées.
SETTINGS_FILE: Path = DATA_DIR / "settings.json"
XP_REQUESTS_FILE: Path = DATA_DIR / "xp_requests.json"
EMOJIS_FILE: Path = ROOT_DIR / "config" / "emojis.json"
# Correspondance trait → modificateur de chance de Black Flash, éditable par le
# staff (voir `jjkbot.content.blackflash`). Des valeurs par défaut prennent le
# relais si le fichier est absent ou invalide.
BLACKFLASH_FILE: Path = ROOT_DIR / "config" / "blackflash.json"
ASSETS_DIR: Path = ROOT_DIR / "assets"

# Image de bannière servie LOCALEMENT (attachment://) : elle vit dans le dépôt
# et n’expire jamais, contrairement aux URL de CDN Discord, qui sont signées
# et valables seulement quelques heures. `BANNER_URL` reste possible en repli
# si ce fichier est absent (voir theme.banner_embed).
BANNER_PATH: Path = ASSETS_DIR / "banniere_jjk.png"

# Images du Black Flash servies LOCALEMENT (attachment://) : même raison que la
# bannière, les URL du CDN Discord expirent en quelques heures. Les variables
# `BLACKFLASH_*_URL` ne servent que de repli si le fichier est absent
# (voir theme.blackflash_image).
BLACKFLASH_OK_PATH: Path = ASSETS_DIR / "blackflash_ok.png"
BLACKFLASH_KO_PATH: Path = ASSETS_DIR / "blackflash_ko.png"
BLACKFLASH_OK_URL: str | None = _optional("BLACKFLASH_OK_URL")
BLACKFLASH_KO_URL: str | None = _optional("BLACKFLASH_KO_URL")

# Images de la Renaissance en Esprit Vengeur, mêmes règles que le Black Flash :
# le fichier local est joint via `attachment://`, l’URL ne sert que de repli.
RENAISSANCE_OK_PATH: Path = ASSETS_DIR / "renaissance_ok.png"
RENAISSANCE_KO_PATH: Path = ASSETS_DIR / "renaissance_ko.png"
RENAISSANCE_OK_URL: str | None = _optional("RENAISSANCE_OK_URL")
RENAISSANCE_KO_URL: str | None = _optional("RENAISSANCE_KO_URL")
