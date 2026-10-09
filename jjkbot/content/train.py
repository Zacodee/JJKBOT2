"""Règles de `/train` : entraînement hebdomadaire et son gain d’XP.

Chaque joueur peut s’entraîner **une fois par semaine** et gagne **500 XP**.
La semaine est calculée en **7 jours glissants** depuis le dernier `/train` :
un joueur qui s’entraîne un mardi peut recommencer le mardi suivant, pas avant.

Le rendez-vous vit sur la fiche (`trainLastAt`) — le staff peut le remettre à
zéro avec `/train-reset` pour rendre une séance à un joueur (rattrapage, test,
correction d’une date).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

# Gain d’un entraînement.
TRAIN_XP = 500
# Délai entre deux entraînements : une semaine glissante.
WEEK = timedelta(days=7)


def now() -> datetime:
    """Instant présent, en UTC et conscient du fuseau."""
    return datetime.now(timezone.utc)


def parse_iso(value) -> datetime | None:
    """Convertit une date ISO stockée en `datetime` conscient, ou None.

    Les dates écrites par `storage.profiles.now_iso` sont déjà en UTC ; une
    date sans fuseau (import ancien) est considérée comme UTC pour ne jamais
    comparer naïf et conscient.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment


def next_available(last_at, current: datetime | None = None) -> datetime | None:
    """Date du prochain `/train` possible, ou None si le joueur n’en a jamais fait."""
    last = parse_iso(last_at)
    if last is None:
        return None
    return last + WEEK


def is_available(last_at, current: datetime | None = None) -> bool:
    """Vrai si le joueur peut s’entraîner maintenant."""
    moment = current or now()
    ready = next_available(last_at, moment)
    return ready is None or moment >= ready


def remaining(last_at, current: datetime | None = None) -> timedelta:
    """Temps restant avant le prochain `/train` (zéro s’il est disponible)."""
    moment = current or now()
    ready = next_available(last_at, moment)
    if ready is None or moment >= ready:
        return timedelta(0)
    return ready - moment


def format_delay(delta: timedelta) -> str:
    """Durée lisible en français : « 3 j 04 h 12 min »."""
    total = max(0, int(delta.total_seconds()))
    days, rest = divmod(total, 86400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60
    parts: list[str] = []
    if days:
        parts.append(f"{days} j")
    if hours or days:
        parts.append(f"{hours:02d} h")
    parts.append(f"{minutes:02d} min")
    return " ".join(parts)
