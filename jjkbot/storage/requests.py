"""Demandes d’XP, persistées pour survivre aux redémarrages.

Une demande vit dans `DATA_DIR/xp_requests.json`. C’est la pièce qui rend les
boutons « Approuver / Décliner » durables : la vue interactive ne conserve
aucune donnée en mémoire, elle relit la demande sur le disque au moment du
clic — même une heure plus tard, même après un redéploiement qui a redémarré le
bot. Sans ce fichier, une vue `timeout=None` resterait cliquable mais ne
saurait plus à qui ni combien d’XP créditer.

Format :

    {"version": 1, "requests": {"<id>": {...}}}
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from jjkbot import config
from jjkbot.storage.profiles import now_iso

logger = logging.getLogger(__name__)

REQUESTS_VERSION = 1

# États d’une demande.
STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_DECLINED = "declined"

STATUS_LABELS = {
    STATUS_PENDING: "En attente",
    STATUS_APPROVED: "Approuvée",
    STATUS_DECLINED: "Déclinée",
}

_write_lock = asyncio.Lock()
_cache: dict[str, Any] | None = None
_cache_path: Path | None = None


def _requests_path() -> Path:
    return Path(config.XP_REQUESTS_FILE)


def _as_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return int(value)


def _as_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _optional_int(value: Any) -> int | None:
    return _as_int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


@dataclass
class XPRequest:
    """Une demande d’XP déposée par un joueur."""

    id: str
    guild_id: int
    user_id: int
    user_name: str = ""
    interaction_type: str = ""
    amount: int = 0
    description: str = ""
    channel_link: str = ""
    status: str = STATUS_PENDING
    message_id: int | None = None
    channel_id: int | None = None
    created_at: str = field(default_factory=now_iso)
    decided_by: int | None = None
    decided_by_name: str = ""
    decided_at: str | None = None

    @property
    def pending(self) -> bool:
        return self.status == STATUS_PENDING

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> XPRequest:
        return cls(
            id=_as_text(data.get("id")),
            guild_id=_as_int(data.get("guildId")),
            user_id=_as_int(data.get("userId")),
            user_name=_as_text(data.get("userName")),
            interaction_type=_as_text(data.get("interactionType")),
            amount=max(0, _as_int(data.get("amount"))),
            description=_as_text(data.get("description")),
            channel_link=_as_text(data.get("channelLink")),
            status=_as_text(data.get("status")) or STATUS_PENDING,
            message_id=_optional_int(data.get("messageId")),
            channel_id=_optional_int(data.get("channelId")),
            created_at=_as_text(data.get("createdAt")) or now_iso(),
            decided_by=_optional_int(data.get("decidedBy")),
            decided_by_name=_as_text(data.get("decidedByName")),
            decided_at=data.get("decidedAt") if isinstance(data.get("decidedAt"), str) else None,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "guildId": self.guild_id,
            "userId": self.user_id,
            "userName": self.user_name,
            "interactionType": self.interaction_type,
            "amount": self.amount,
            "description": self.description,
            "channelLink": self.channel_link,
            "status": self.status,
            "messageId": self.message_id,
            "channelId": self.channel_id,
            "createdAt": self.created_at,
            "decidedBy": self.decided_by,
            "decidedByName": self.decided_by_name,
            "decidedAt": self.decided_at,
        }


def _read_sync() -> dict[str, Any]:
    path = _requests_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        return {"version": REQUESTS_VERSION, "requests": {}}

    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as error:
        logger.error("Le fichier de demandes %s est illisible (%s) : demandes réinitialisées.", path, error)
        return {"version": REQUESTS_VERSION, "requests": {}}

    if not isinstance(data, dict) or not isinstance(data.get("requests"), dict):
        logger.error("Le fichier de demandes %s n’a pas la structure attendue : demandes réinitialisées.", path)
        return {"version": REQUESTS_VERSION, "requests": {}}

    data.setdefault("version", REQUESTS_VERSION)
    return data


def _write_sync(data: dict[str, Any]) -> None:
    path = _requests_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data["version"] = REQUESTS_VERSION
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temporary, path)


async def _load_locked() -> dict[str, Any]:
    """Charge la base en mémoire — doit être appelée sous `_write_lock`."""
    global _cache, _cache_path
    path = _requests_path()
    if _cache is None or _cache_path != path:
        _cache = await asyncio.to_thread(_read_sync)
        _cache_path = path
    return _cache


async def _mutate(mutator: Callable[[dict[str, Any]], None]) -> None:
    """Applique une modification sous verrou, puis réécrit le fichier."""
    async with _write_lock:
        data = await _load_locked()
        mutator(data)
        await asyncio.to_thread(_write_sync, data)


async def _read() -> dict[str, Any]:
    async with _write_lock:
        return await _load_locked()


def _new_id(existing: dict[str, Any]) -> str:
    """Identifiant court, unique dans la base."""
    while True:
        candidate = secrets.token_hex(4)
        if candidate not in existing:
            return candidate


async def create_request(
    guild_id: int | str,
    user_id: int | str,
    *,
    user_name: str,
    interaction_type: str,
    amount: int,
    description: str,
    channel_link: str,
) -> XPRequest:
    """Enregistre une nouvelle demande en attente et la renvoie."""
    created: XPRequest | None = None

    def mutator(data: dict[str, Any]) -> None:
        nonlocal created
        requests = data["requests"]
        request = XPRequest(
            id=_new_id(requests),
            guild_id=int(guild_id),
            user_id=int(user_id),
            user_name=user_name,
            interaction_type=interaction_type,
            amount=max(0, int(amount)),
            description=description,
            channel_link=channel_link,
        )
        requests[request.id] = request.to_dict()
        created = request

    await _mutate(mutator)
    assert created is not None  # mutator l’a toujours renseigné
    return created


async def get_request(request_id: str) -> XPRequest | None:
    data = await _read()
    raw = data["requests"].get(request_id)
    return XPRequest.from_dict(raw) if isinstance(raw, dict) else None


async def get_request_by_message(message_id: int) -> XPRequest | None:
    """Retrouve une demande à partir de l’identifiant de son message staff.

    Les boutons n’encodent pas la demande dans leur `custom_id` : ils sont
    génériques (`xp:approuver`, `xp:decliner`) pour qu’une seule vue persistante
    enregistrée au démarrage serve tous les messages. C’est donc le message
    cliqué qui identifie la demande.
    """
    data = await _read()
    wanted = int(message_id)
    for raw in data["requests"].values():
        if isinstance(raw, dict) and _optional_int(raw.get("messageId")) == wanted:
            return XPRequest.from_dict(raw)
    return None


async def attach_message(request_id: str, channel_id: int, message_id: int) -> XPRequest | None:
    """Associe une demande au message staff qui la porte."""
    updated: XPRequest | None = None

    def mutator(data: dict[str, Any]) -> None:
        nonlocal updated
        raw = data["requests"].get(request_id)
        if not isinstance(raw, dict):
            return
        raw["channelId"] = int(channel_id)
        raw["messageId"] = int(message_id)
        updated = XPRequest.from_dict(raw)

    await _mutate(mutator)
    return updated


async def decide(
    request_id: str,
    status: str,
    *,
    staff_id: int | str,
    staff_name: str,
) -> tuple[XPRequest | None, bool]:
    """Tranche une demande, une seule fois.

    Renvoie `(demande, appliqué)`. `demande` est None si l’identifiant est
    inconnu ; `appliqué` vaut False quand la demande avait déjà été tranchée —
    l’appelant peut alors prévenir « déjà traitée » au lieu de créditer l’XP une
    seconde fois. Vérification et écriture partagent le même verrou : deux
    membres du staff qui cliquent simultanément ne créditent l’XP qu’une fois.
    """
    if status not in (STATUS_APPROVED, STATUS_DECLINED):
        raise ValueError(f"Statut de décision invalide : {status!r}")

    result: XPRequest | None = None
    applied = False

    def mutator(data: dict[str, Any]) -> None:
        nonlocal result, applied
        raw = data["requests"].get(request_id)
        if not isinstance(raw, dict):
            return
        request = XPRequest.from_dict(raw)
        if request.pending:
            request.status = status
            request.decided_by = int(staff_id)
            request.decided_by_name = staff_name
            request.decided_at = now_iso()
            raw.update(request.to_dict())
            applied = True
        result = request

    await _mutate(mutator)
    return result, applied


async def list_pending(guild_id: int | str | None = None) -> list[XPRequest]:
    """Demandes encore en attente, éventuellement limitées à un serveur."""
    data = await _read()
    requests = [XPRequest.from_dict(raw) for raw in data["requests"].values() if isinstance(raw, dict)]
    if guild_id is not None:
        requests = [request for request in requests if request.guild_id == int(guild_id)]
    return [request for request in requests if request.pending]
