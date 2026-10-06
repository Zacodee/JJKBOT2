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
from jjkbot.content.blackflash import BASE_CHANCE, MAX_CHANCE
from jjkbot.content.stats import DEFAULT_STATS

logger = logging.getLogger(__name__)

# Version du modèle de fiche. La version 1 correspond à l’ancien format Node.
PROFILE_VERSION = 2
DATABASE_VERSION = 2

DEFAULT_DATABASE: dict[str, Any] = {"version": DATABASE_VERSION, "profiles": {}}

# Verrou commun aux lectures/écritures : sérialise les modifications.
_write_lock = asyncio.Lock()

# Cache mémoire de la base, rechargé uniquement quand le chemin change.
# Chaque commande évite ainsi une lecture disque et un parse JSON complets : les
# fiches sont servies depuis la RAM, puis réécrites sur le disque (écriture
# atomique) à chaque modification. Sur le disque lent d’un hébergeur, le gain est
# net, et il grandit avec le nombre de joueurs.
_cache: dict[str, Any] | None = None
_cache_path: Path | None = None


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
    """Clé d’un profil dans le fichier de données.

    La fiche est rattachée au **joueur**, jamais au serveur. Auparavant la clé
    était `guildId:userId` : déplacer le bot sur un autre serveur (ou changer
    d’identifiant de serveur de test) rendait alors toutes les fiches invisibles,
    ce qui obligeait les joueurs à recréer leur personnage. Les anciennes clés
    restent lisibles et sont migrées à l’écriture (voir `_legacy_user_id`).
    """
    return str(user_id)


def _legacy_user_id(key: str) -> str | None:
    """Joueur d’une ancienne clé `guildId:userId`, ou None si ce n’en est pas une."""
    guild, separator, user = key.partition(":")
    if not separator or not guild.isdigit() or not user.isdigit():
        return None
    return user


def _legacy_profiles(profiles: dict[str, Any], user_id: int | str) -> list[dict[str, Any]]:
    """Fiches rangées sous une ancienne clé `guildId:userId` pour ce joueur."""
    wanted = str(user_id)
    return [
        value
        for key, value in profiles.items()
        if _legacy_user_id(key) == wanted and isinstance(value, dict)
    ]


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


def _as_color(value: Any) -> int | None:
    """Couleur d’embed stockée (0x000000-0xFFFFFF), ou None si absente/invalide.

    None signifie « aucune préférence » : l’embed reprend alors la couleur du
    thème actif (voir `views.profil`). Un zéro n’est donc pas confondu avec un
    choix explicite… sauf s’il est bien présent, auquel cas le noir est un
    choix légitime — c’est pourquoi l’absence de clé, seule, vaut None.
    """
    if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return max(0, min(0xFFFFFF, int(value)))


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
    role: str = "Rôle non défini"
    quote: str = ""
    traits: list[str] = field(default_factory=list)
    flaws: list[str] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_STATS))
    stat_points: int = 0
    experience: int = 0
    # Chance actuelle de Black Flash, en pourcentage (5 % de base, 100 % max).
    blackflash_chance: int = BASE_CHANCE
    # Exception du staff : plancher imposé (`None` = seuls les traits comptent) et
    # bonus additif. Sert aux évènements ou à corriger une fiche sans attendre
    # que le joueur modifie ses traits (voir `blackflash.effective_base`).
    blackflash_base: int | None = None
    blackflash_bonus: int = 0
    # Couleur d’embed choisie par le joueur pour sa propre fiche (voir
    # `/profil couleur`). `None` = couleur du thème actif.
    embed_color: int | None = None
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
            # L’alignement (v1 : « camp », v2 : « alignment ») a été retiré du
            # bot : les anciennes clés restent donc simplement ignorées.
            role=_as_text(data.get("role"), "Rôle non défini"),
            quote=data.get("quote") if isinstance(data.get("quote"), str) else "",
            traits=_as_text_list(data.get("traits")),
            flaws=_as_text_list(data.get("flaws")),
            stats=normalize_stats(legacy_stats) if has_current_stats else dict(DEFAULT_STATS),
            stat_points=_as_int(data.get("statPoints")),
            experience=_as_int(data.get("experience")),
            blackflash_chance=min(MAX_CHANCE, _as_int(data.get("blackflashChance"), BASE_CHANCE)),
            blackflash_base=(
                None
                if data.get("blackflashBase") is None
                else min(MAX_CHANCE, _as_int(data.get("blackflashBase")))
            ),
            blackflash_bonus=min(MAX_CHANCE, _as_int(data.get("blackflashBonus"))),
            embed_color=_as_color(data.get("embedColor")),
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
            "role": self.role,
            "quote": self.quote,
            "traits": list(self.traits),
            "flaws": list(self.flaws),
            "stats": dict(self.stats),
            "statPoints": self.stat_points,
            "experience": self.experience,
            "blackflashChance": self.blackflash_chance,
            "blackflashBase": self.blackflash_base,
            "blackflashBonus": self.blackflash_bonus,
            "embedColor": self.embed_color,
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


def _quarantine(path: Path) -> Path | None:
    """Conserve une copie d’un fichier de fiches illisible avant de le remplacer.

    Sans cette copie, une base aux clés inattendues serait simplement écrasée à la
    prochaine sauvegarde : les fiches perdues seraient alors définitivement
    introuvables. Le fichier original n’est pas touché ici, on le laisse à côté.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = path.with_name(f"{path.name}.invalide-{stamp}")
    try:
        target.write_bytes(path.read_bytes())
    except OSError:  # pragma: no cover - dépend des droits du disque
        logger.exception("Copie de secours de %s impossible.", path)
        return None
    return target


def _read_database_sync() -> dict[str, Any]:
    path = _database_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        # Pas de fichier : soit un premier lancement, soit un déploiement qui a
        # remplacé le dossier. On repart vide SANS rien écrire, et on le signale
        # — une base vide silencieuse est invisible jusqu’aux premières plaintes.
        logger.warning(
            "Aucun fichier de fiches (%s) : base vide. Si le bot tournait déjà "
            "sur cet hébergeur, ses fiches ne sont pas dans ce dépôt : DATA_DIR "
            "doit pointer vers un stockage persistant.",
            path,
        )
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
        entries = database.get("profiles") if isinstance(database, dict) else None
        count = len(entries) if isinstance(entries, (dict, list)) else 0
        backup = _quarantine(path)
        logger.error(
            "%s n’a pas la structure attendue : base réinitialisée, mais une copie "
            "est conservée dans %s (%s entrée(s) récupérable(s)).",
            path,
            backup or "aucune",
            count,
        )
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


async def _load_database() -> dict[str, Any]:
    """Base en mémoire, chargée depuis le disque au premier accès seulement.

    Le verrou garantit que deux commandes simultanées ne déclenchent qu’une
    seule lecture, puis chaque accès renvoie la copie en RAM (sans disque).
    """
    global _cache, _cache_path
    path = _database_path()
    async with _write_lock:
        if _cache is None or _cache_path != path:
            # Seule lecture disque : dans un thread, pour ne pas bloquer la
            # boucle d’événements quand le disque du conteneur est lent.
            _cache = await asyncio.to_thread(_read_database_sync)
            _cache_path = path
        return _cache


async def _read_database() -> dict[str, Any]:
    return await _load_database()


async def warmup() -> None:
    """Charge les fiches en mémoire au démarrage (le disque n’est lu qu’une fois).

    Appelée par le bot au démarrage : la première commande n’attend alors ni la
    lecture ni le parse du fichier de données, dont le disque d’un hébergeur
    peut être lent au tout premier accès.
    """
    await _load_database()


async def database_state() -> tuple[Path, int]:
    """Chemin du fichier de fiches et nombre de fiches présentes.

    Rend visible au démarrage ce qui reste invisible autrement : une base vide
    après un déploiement qui a remplacé le dossier de données ne se signale
    que lorsque les joueurs se plaignent — sauf à le dire dès l’ouverture.
    """
    database = await _read_database()
    entries = database.get("profiles")
    if not isinstance(entries, dict):  # pragma: no cover - déjà filtré à la lecture
        entries = {}
    return _database_path(), sum(1 for value in entries.values() if isinstance(value, dict))


async def _mutate_database(mutator) -> None:
    """Met à jour la copie mémoire puis réécrit le fichier de façon atomique."""
    global _cache, _cache_path
    path = _database_path()
    async with _write_lock:
        if _cache is None or _cache_path != path:
            _cache = await asyncio.to_thread(_read_database_sync)
            _cache_path = path
        mutator(_cache)
        await asyncio.to_thread(_write_database_sync, _cache)


async def get_profile(guild_id: int | str, user_id: int | str) -> Profile | None:
    """Renvoie la fiche d’un joueur, ou None s’il n’en a pas.

    Si la fiche a été créée avant le changement de clé (ou sous un autre
    serveur), elle est retrouvée via son ancienne clé `guildId:userId` : un
    joueur ne perd donc jamais son personnage en déplaçant le bot.
    """
    database = await _read_database()
    profiles = database["profiles"]
    raw = profiles.get(profile_key(guild_id, user_id))
    if not isinstance(raw, dict):
        candidates = _legacy_profiles(profiles, user_id)
        if not candidates:
            return None
        # La plus récemment modifiée l’emporte : une fiche fantôme d’un ancien
        # serveur ne doit pas masquer la fiche active.
        raw = max(candidates, key=lambda data: str(data.get("updatedAt") or ""))
    return Profile.from_dict(raw)


async def save_profile(guild_id: int | str, user_id: int | str, profile: Profile) -> Profile:
    """Enregistre une fiche et renvoie la version normalisée."""
    payload = profile.to_dict()
    payload["version"] = PROFILE_VERSION

    def mutator(database: dict[str, Any]) -> None:
        profiles = database["profiles"]
        canonical = profile_key(guild_id, user_id)
        profiles[canonical] = payload
        # Purge les anciennes clés serveur du même joueur : sans cela, une
        # sauvegarde après un changement de serveur laisserait une copie fantôme
        # susceptible de refaire surface au prochain redémarrage.
        for key in list(profiles):
            if key != canonical and _legacy_user_id(key) == str(user_id):
                profiles.pop(key, None)

    await _mutate_database(mutator)
    return Profile.from_dict(payload)


async def replace_database(database: dict[str, Any]) -> int:
    """Remplace toute la base par celle d’une sauvegarde. Renvoie le nombre de fiches.

    Sert à `/jjk restaurer` : quand un déploiement a vidé `profiles.json`, une
    sauvegarde téléchargée auparavant peut être remise en place d’un coup. La
    base actuelle n’est jamais écrasée sans trace : elle est mise en quarantaine
    à côté (voir `_quarantine`) avant l’écriture.

    Lève `ValueError` si le contenu n’est pas une base de fiches exploitable.
    """
    if not isinstance(database, dict) or not isinstance(database.get("profiles"), dict):
        raise ValueError("Le fichier ne contient pas une base de fiches valide.")

    entries = {
        str(key): value
        for key, value in database["profiles"].items()
        if isinstance(value, dict)
    }
    if not entries:
        raise ValueError("Le fichier ne contient aucune fiche exploitable.")

    payload = {"version": DATABASE_VERSION, "profiles": entries}
    path = _database_path()
    if path.exists():
        _quarantine(path)

    global _cache, _cache_path
    async with _write_lock:
        _cache = payload
        _cache_path = path
        await asyncio.to_thread(_write_database_sync, payload)
    return len(entries)


async def delete_profile(guild_id: int | str, user_id: int | str) -> None:
    """Supprime définitivement la fiche d’un joueur."""

    def mutator(database: dict[str, Any]) -> None:
        profiles = database["profiles"]
        profiles.pop(profile_key(guild_id, user_id), None)
        # Supprime aussi les éventuelles copies d’anciennes clés serveur.
        for key in list(profiles):
            if _legacy_user_id(key) == str(user_id):
                profiles.pop(key, None)

    await _mutate_database(mutator)
