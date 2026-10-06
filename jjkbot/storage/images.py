"""Stockage local des images de personnage.

Les URL de pièces jointes Discord sont signées et expirent : on télécharge donc
l’image sur le disque, dans `data/images/`, et on l’envoie ensuite via
`attachment://` au moment d’afficher la fiche.
"""

from __future__ import annotations

import logging
from pathlib import Path

import discord

from jjkbot import config

logger = logging.getLogger(__name__)

# Type MIME accepté -> extension de fichier.
ALLOWED_TYPES: dict[str, str] = {
    "image/png": ".png",
    "image/gif": ".gif",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}

ALLOWED_EXTENSIONS: tuple[str, ...] = (".png", ".gif", ".jpg", ".jpeg", ".webp")
MAX_UPLOAD_SIZE = 8 * 1024 * 1024  # 8 Mo, la limite d’une pièce jointe Discord.


def images_dir() -> Path:
    directory = Path(config.IMAGES_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def extension_for(attachment: discord.Attachment) -> str | None:
    """Renvoie l’extension à utiliser, ou None si le fichier n’est pas accepté."""
    content_type = (attachment.content_type or "").split(";")[0].strip().lower()
    if content_type in ALLOWED_TYPES:
        return ALLOWED_TYPES[content_type]

    suffix = Path(attachment.filename).suffix.lower()
    if suffix in ALLOWED_EXTENSIONS:
        return ".jpg" if suffix == ".jpeg" else suffix
    return None


def find_image(guild_id: int | str, user_id: int | str) -> Path | None:
    """Renvoie le chemin de l’image locale d’un joueur, si elle existe.

    L’image suit le joueur : on cherche d’abord le nom indépendant du serveur
    (`userId.ext`), puis les anciens noms `guildId-userId.ext` — y compris ceux
    d’un **autre** serveur, pour qu’un déplacement du bot ne perde pas l’image.
    """
    directory = images_dir()
    for extension in ALLOWED_EXTENSIONS:
        candidate = directory / f"{user_id}{extension}"
        if candidate.exists() and candidate.stat().st_size > 0:
            return candidate
    for extension in ALLOWED_EXTENSIONS:
        candidate = directory / f"{guild_id}-{user_id}{extension}"
        if candidate.exists() and candidate.stat().st_size > 0:
            return candidate
    for candidate in sorted(directory.glob(f"*-{user_id}.*")):
        if candidate.is_file() and candidate.stat().st_size > 0:
            return candidate
    return None


def delete_image(guild_id: int | str, user_id: int | str) -> None:
    """Supprime toutes les images locales d’un joueur, quel que soit le serveur."""
    directory = images_dir()
    candidates = [directory / f"{user_id}{extension}" for extension in ALLOWED_EXTENSIONS]
    candidates += [
        directory / f"{guild_id}-{user_id}{extension}" for extension in ALLOWED_EXTENSIONS
    ]
    candidates += list(directory.glob(f"*-{user_id}.*"))

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.exists():
            try:
                candidate.unlink()
            except OSError as error:  # pragma: no cover - dépend du système de fichiers
                logger.warning("Impossible de supprimer %s : %s", candidate, error)


async def save_image(
    guild_id: int | str,
    user_id: int | str,
    attachment: discord.Attachment,
) -> tuple[str, Path]:
    """Télécharge une pièce jointe et renvoie (nom de fichier, chemin)."""
    extension = extension_for(attachment)
    if extension is None:
        raise ValueError("format non pris en charge")

    if attachment.size > MAX_UPLOAD_SIZE:
        raise ValueError("fichier trop volumineux")

    directory = images_dir()
    # On nettoie d’abord les anciennes images pour éviter les formats résiduels,
    # quel que soit le serveur sous lequel elles avaient été enregistrées.
    delete_image(guild_id, user_id)

    # Nom indépendant du serveur : l’image survit à un déplacement du bot.
    destination = directory / f"{user_id}{extension}"
    await attachment.save(destination)
    return destination.name, destination
