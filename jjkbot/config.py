"""Configuration du bot, lue depuis le fichier `.env`."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent

load_dotenv(ROOT_DIR / ".env")


class ConfigError(RuntimeError):
    """Erreur de configuration : une variable obligatoire est absente."""


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigError(
            f"La variable d’environnement {name} est manquante. "
            "Copie `.env.example` vers `.env` puis renseigne-la."
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

DATA_FILE: Path = ROOT_DIR / "data" / "profiles.json"
IMAGES_DIR: Path = ROOT_DIR / "data" / "images"
EMOJIS_FILE: Path = ROOT_DIR / "config" / "emojis.json"
ASSETS_DIR: Path = ROOT_DIR / "assets"
