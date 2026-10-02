"""Lecture et écriture des fiches de personnage.

Le fichier `data/profiles.json` conserve l’enveloppe écrite par l’ancienne
version Node (`{"profiles": {"guildId:userId": {...}}}`) : les profils existants
sont donc lus tels quels puis migrés à la volée vers le nouveau modèle.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jjkbot import config
from jjkbot.content.stats import DEFAULT_STATS

logger = logging.getLogger(__name__)

# Version du modèle de fiche. La version 1 correspond à l’ancien format Node.
PROFILE_VERSION = 2
DATABASE_VERSION = 2

DEFAULT_DATABASE: dict[str, Any] = {"version": DATABASE_VERSION, "profiles": {}}

_write_lock = asyncio.Lock()


def now_iso() -> str:
    """Horodatage ISO 8601 en UTC, comme `new Date().toISOString()`."""
    return datetime.now(timezone.utc).isoformat()


def parse_timestamp(value: Any) -> datetime | None:
    """Convertit un horodatage stocké en `datetime` utilisable par les embeds."""
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def profile_key(guild_id: int | str, user_id: int | str) -> str:
    """Clé d’un profil dans le fichier de données."""
    return f"{guild_id}:{user_id}"


def _as_text(value: Any, fallback: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    return fallback


def _as_text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(entry).strip() for entry in value if str(entry).strip()]


def _as_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return max(0, int(value))


def normalize_stats(stats: Any) -> dict[str, int]:
    """Ne garde que les statistiques connues, en entiers positifs."""
    if not isinstance(stats, dict):
        return dict(DEFAULT_STATS)

    normalized = dict(DEFAULT_STATS)
    for key, value in stats.items():
        if key in DEFAULT_STATS and isinstance(value, (int, float)) and not isinstance(value, bool):
            normalized[key] = max(0, int(value))
    return normalized


@dataclass
class Profile:
    """Fiche de personnage d’un joueur."""

    name: str = "Personnage sans nom"
    age: str = "Non renseigné"
    race: str = "Race inconnue"
    grade: str = "Grade non défini"
    alignment: str = "Alignement inconnu"
    role: str = "Rôle non défini"
    quote: str = ""
    traits: list[str] = field(default_factory=list)
    flaws: list[str] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_STATS))
    stat_points: int = 0
    experience: int = 0
    unlocked_skills: list[str] = field(default_factory=list)
    image_name: str | None = None
    image_url: str | None = None
    image_file: str | None = None
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Profile:
        """Construit une fiche depuis le JSON, en migrant l’ancien format."""
        legacy_stats = data.get("stats") or {}
        has_current_stats = any(key in legacy_stats for key in DEFAULT_STATS)

        return cls(
            name=_as_text(data.get("name"), "Personnage sans nom"),
            age=_as_text(data.get("age"), "Non renseigné"),
            race=_as_text(data.get("race"), "Race inconnue"),
            # v1 : « characterClass » ; v2 : « grade ».
            grade=_as_text(data.get("grade") or data.get("characterClass"), "Grade non défini"),
            # v1 : « camp » ; v2 : « alignment ».
            alignment=_as_text(data.get("alignment") or data.get("camp"), "Alignement inconnu"),
            role=_as_text(data.get("role"), "Rôle non défini"),
            quote=data.get("quote") if isinstance(data.get("quote"), str) else "",
            traits=_as_text_list(data.get("traits")),
            flaws=_as_text_list(data.get("flaws")),
            stats=normalize_stats(legacy_stats) if has_current_stats else dict(DEFAULT_STATS),
            stat_points=_as_int(data.get("statPoints")),
            experience=_as_int(data.get("experience")),
            unlocked_skills=[str(skill) for skill in data.get("unlockedSkills") or []]
            if isinstance(data.get("unlockedSkills"), list)
            else [],
            image_name=data.get("imageName") if isinstance(data.get("imageName"), str) else None,
            image_url=data.get("imageUrl") if isinstance(data.get("imageUrl"), str) else None,
            image_file=data.get("imageFile") if isinstance(data.get("imageFile"), str) else None,
            created_at=_as_text(data.get("createdAt"), now_iso()),
            updated_at=_as_text(data.get("updatedAt"), now_iso()),
        )

    def to_dict(self) -> dict[str, Any]:
        """Représentation JSON, avec les clés d’origine conservées."""
        return {
            "name": self.name,
            "age": self.age,
            "race": self.race,
            "grade": self.grade,
            "alignment": self.alignment,
            "role": self.role,
            "quote": self.quote,
            "traits": list(self.traits),
            "flaws": list(self.flaws),
            "stats": dict(self.stats),
            "statPoints": self.stat_points,
            "experience": self.experience,
            "unlockedSkills": list(self.unlocked_skills),
            "imageName": self.image_name,
            "imageUrl": self.image_url,
            "imageFile": self.image_file,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }

    def touch(self) -> None:
        """Met à jour la date de dernière modification."""
        self.updated_at = now_iso()


def _database_path() -> Path:
    return Path(config.DATA_FILE)


def _read_database_sync() -> dict[str, Any]:
    path = _database_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        return {"version": DATABASE_VERSION, "profiles": {}}

    try:
        with path.open("r", encoding="utf-8") as handle:
            database = json.load(handle)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"Le fichier {path} contient du JSON invalide. "
            "Corrige-le ou renomme-le pour repartir d’une base vide."
        ) from error

    if not isinstance(database, dict) or not isinstance(database.get("profiles"), dict):
        logger.warning("%s n’a pas la structure attendue, il est réinitialisé.", path)
        return {"version": DATABASE_VERSION, "profiles": {}}

    database.setdefault("version", DATABASE_VERSION)
    return database


def _write_database_sync(database: dict[str, Any]) -> None:
    path = _database_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    database["version"] = DATABASE_VERSION
    # Écriture atomique : fichier temporaire puis remplacement.
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(database, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temporary, path)


async def _read_database() -> dict[str, Any]:
    async with _write_lock:
        return await asyncio.to_thread(_read_database_sync)


async def _mutate_database(mutator) -> None:
    """Sérialise les lectures/écritures pour éviter les écritures concurrentes."""
    async with _write_lock:
        database = await asyncio.to_thread(_read_database_sync)
        mutator(database)
        await asyncio.to_thread(_write_database_sync, database)


async def get_profile(guild_id: int | str, user_id: int | str) -> Profile | None:
    """Renvoie la fiche d’un joueur, ou None s’il n’en a pas."""
    database = await _read_database()
    raw = database["profiles"].get(profile_key(guild_id, user_id))
    if not isinstance(raw, dict):
        return None
    return Profile.from_dict(raw)


async def save_profile(guild_id: int | str, user_id: int | str, profile: Profile) -> Profile:
    """Enregistre une fiche et renvoie la version normalisée."""
    payload = profile.to_dict()
    payload["version"] = PROFILE_VERSION

    def mutator(database: dict[str, Any]) -> None:
        database["profiles"][profile_key(guild_id, user_id)] = payload

    await _mutate_database(mutator)
    return Profile.from_dict(payload)


async def delete_profile(guild_id: int | str, user_id: int | str) -> None:
    """Supprime définitivement la fiche d’un joueur."""

    def mutator(database: dict[str, Any]) -> None:
        database["profiles"].pop(profile_key(guild_id, user_id), None)

    await _mutate_database(mutator)
