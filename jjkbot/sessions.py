"""États d’attente des parcours multi-étapes.

Remplace les `Map` et `setTimeout(...)` de l’ancienne version Node : chaque
attente (seconde modale de création, confirmation de réinitialisation) est
horodatée et purgée automatiquement au bout de quinze minutes.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from jjkbot.storage.profiles import Profile

logger = logging.getLogger(__name__)

PENDING_TIMEOUT = 15 * 60  # 15 minutes, comme l’ancienne version.

# Types de réinitialisation acceptés (identiques à l’ancienne version).
RESET_TYPES = ("profil", "stats", "competences")

RESET_LABELS = {
    "profil": "le profil complet (fiche, stats, compétences et image)",
    "stats": "les statistiques et les points disponibles",
    "competences": "les compétences débloquées et l’XP",
}


def _key(guild_id, user_id) -> tuple[int, int]:
    return int(guild_id), int(user_id)


@dataclass
class PendingProfile:
    """Création ou modification de fiche en attente de la seconde modale."""

    guild_id: int
    user_id: int
    mode: str  # « create » ou « edit »
    identity: dict[str, str] = field(default_factory=dict)
    existing: Profile | None = None
    expires_at: float = field(default_factory=lambda: time.monotonic() + PENDING_TIMEOUT)

    @property
    def expired(self) -> bool:
        return time.monotonic() > self.expires_at

    def touch(self) -> None:
        self.expires_at = time.monotonic() + PENDING_TIMEOUT


@dataclass
class PendingReset:
    """Confirmation de réinitialisation en attente."""

    guild_id: int
    target_user_id: int
    reset_type: str
    expires_at: float = field(default_factory=lambda: time.monotonic() + PENDING_TIMEOUT)

    @property
    def expired(self) -> bool:
        return time.monotonic() > self.expires_at


_profiles: dict[tuple[int, int], PendingProfile] = {}
_resets: dict[tuple[int, int], PendingReset] = {}


def remember_profile(
    guild_id: int,
    user_id: int,
    mode: str,
    identity: dict[str, str],
    existing: Profile | None = None,
) -> PendingProfile:
    """Mémorise la première étape d’une création ou d’une modification."""
    pending = PendingProfile(
        guild_id=int(guild_id),
        user_id=int(user_id),
        mode=mode,
        identity=identity,
        existing=existing,
    )
    _profiles[_key(guild_id, user_id)] = pending
    return pending


def get_pending_profile(guild_id: int, user_id: int) -> PendingProfile | None:
    """Renvoie l’attente en cours, ou None si elle a expiré."""
    pending = _profiles.get(_key(guild_id, user_id))
    if pending is None:
        return None
    if pending.expired:
        _profiles.pop(_key(guild_id, user_id), None)
        return None
    return pending


def clear_pending_profile(guild_id: int, user_id: int) -> None:
    _profiles.pop(_key(guild_id, user_id), None)


def remember_reset(
    guild_id: int,
    user_id: int,
    target_user_id: int,
    reset_type: str,
) -> PendingReset:
    """Mémorise une demande de réinitialisation en attente de confirmation."""
    pending = PendingReset(
        guild_id=int(guild_id),
        target_user_id=int(target_user_id),
        reset_type=reset_type,
    )
    _resets[_key(guild_id, user_id)] = pending
    return pending


def get_pending_reset(guild_id: int, user_id: int) -> PendingReset | None:
    pending = _resets.get(_key(guild_id, user_id))
    if pending is None:
        return None
    if pending.expired:
        _resets.pop(_key(guild_id, user_id), None)
        return None
    return pending


def clear_pending_reset(guild_id: int, user_id: int) -> None:
    _resets.pop(_key(guild_id, user_id), None)


def sweep() -> None:
    """Purge les attentes expirées. Appelée périodiquement par le bot."""
    expired_profiles = [key for key, pending in _profiles.items() if pending.expired]
    for key in expired_profiles:
        _profiles.pop(key, None)

    expired_resets = [key for key, pending in _resets.items() if pending.expired]
    for key in expired_resets:
        _resets.pop(key, None)

    if expired_profiles or expired_resets:
        logger.debug(
            "Attentes purgées : %d création(s), %d réinitialisation(s).",
            len(expired_profiles),
            len(expired_resets),
        )


def clear_all() -> None:
    """Vide toutes les attentes (utilisé par les tests)."""
    _profiles.clear()
    _resets.clear()
