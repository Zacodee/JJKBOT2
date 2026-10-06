"""Réglages par serveur, conservés hors du dépôt.

Le salon des demandes d’XP est un réglage de serveur : il vit dans
`DATA_DIR/settings.json`, comme les fiches, et non dans `config/` — ce dernier
est écrasé à chaque déploiement (clone Git), ce qui réinitialiserait le réglage
à chaque mise à jour.

Format :

    {"version": 1, "guilds": {"<guildId>": {"xpChannel": <channelId>}}}
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

from jjkbot import config

logger = logging.getLogger(__name__)

SETTINGS_VERSION = 1

_write_lock = asyncio.Lock()
_cache: dict[str, Any] | None = None
_cache_path: Path | None = None


def _settings_path() -> Path:
    return Path(config.SETTINGS_FILE)


def _read_sync() -> dict[str, Any]:
    path = _settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        return {"version": SETTINGS_VERSION, "guilds": {}}

    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as error:
        logger.error("Le fichier de réglages %s est illisible (%s) : réglages réinitialisés.", path, error)
        return {"version": SETTINGS_VERSION, "guilds": {}}

    if not isinstance(data, dict) or not isinstance(data.get("guilds"), dict):
        logger.error("Le fichier de réglages %s n’a pas la structure attendue : réglages réinitialisés.", path)
        return {"version": SETTINGS_VERSION, "guilds": {}}

    data.setdefault("version", SETTINGS_VERSION)
    return data


def _write_sync(data: dict[str, Any]) -> None:
    path = _settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data["version"] = SETTINGS_VERSION
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temporary, path)


async def _load() -> dict[str, Any]:
    global _cache, _cache_path
    path = _settings_path()
    async with _write_lock:
        if _cache is None or _cache_path != path:
            _cache = await asyncio.to_thread(_read_sync)
            _cache_path = path
        return _cache


async def _mutate(mutator) -> None:
    global _cache, _cache_path
    path = _settings_path()
    async with _write_lock:
        if _cache is None or _cache_path != path:
            _cache = await asyncio.to_thread(_read_sync)
            _cache_path = path
        mutator(_cache)
        await asyncio.to_thread(_write_sync, _cache)


async def get_xp_channel(guild_id: int | str) -> int | None:
    """Salon des demandes d’XP d’un serveur, ou None s’il n’est pas défini."""
    data = await _load()
    entry = data["guilds"].get(str(guild_id))
    if not isinstance(entry, dict):
        return None
    value = entry.get("xpChannel")
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


async def set_xp_channel(guild_id: int | str, channel_id: int | str | None) -> None:
    """Fixe (ou retire) le salon des demandes d’XP d’un serveur."""

    def mutator(data: dict[str, Any]) -> None:
        guilds = data["guilds"]
        entry = guilds.setdefault(str(guild_id), {})
        if channel_id is None:
            entry.pop("xpChannel", None)
        else:
            entry["xpChannel"] = int(channel_id)

    await _mutate(mutator)
