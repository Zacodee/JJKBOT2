"""Catalogue d’emojis : emojis du serveur en priorité, repli unicode sinon.

Chaque clé (par exemple `profil` ou `force`) est associée au nom d’un emoji
custom et à un emoji unicode de secours. La correspondance est décrite dans
`config/emojis.json` : tu peux renommer ou ajouter des emojis sans toucher au
code, et un emoji manquant ne casse jamais un embed.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass

import discord

from jjkbot import config

logger = logging.getLogger(__name__)

# Délai minimal entre deux récupérations REST pour un même serveur.
REST_FETCH_COOLDOWN = 300.0


@dataclass(frozen=True)
class EmojiSpec:
    """Nom d’emoji custom attendu sur le serveur et repli unicode."""

    name: str
    fallback: str


DEFAULT_CATALOG: dict[str, EmojiSpec] = {
    "profil": EmojiSpec("jjk_profil", "📛"),
    "identite": EmojiSpec("jjk_identite", "🪪"),
    "age": EmojiSpec("jjk_age", "⏳"),
    "race": EmojiSpec("jjk_race", "🧬"),
    "grade": EmojiSpec("jjk_grade", "🎖️"),
    "role": EmojiSpec("jjk_role", "🎭"),
    "citation": EmojiSpec("jjk_citation", "❯"),
    "image": EmojiSpec("jjk_image", "🖼️"),
    "stats": EmojiSpec("jjk_stats", "📊"),
    "force": EmojiSpec("jjk_force", "⚔️"),
    "resistance": EmojiSpec("jjk_resistance", "🛡️"),
    "vitesse": EmojiSpec("jjk_vitesse", "💨"),
    "manipulation_eo": EmojiSpec("jjk_eo_manipulation", "🪄"),
    "reserve_eo": EmojiSpec("jjk_eo_reserve", "🔮"),
    "sortie_eo": EmojiSpec("jjk_eo_sortie", "🌀"),
    # Sous-statistiques (voir `content.stats`) : elles découlent d’une
    # statistique principale et ne s’achètent pas.
    "perception": EmojiSpec("jjk_perception", "👁️"),
    "projectile": EmojiSpec("jjk_projectile", "🎯"),
    "perception_occulte": EmojiSpec("jjk_perception_occulte", "🔍"),
    "points": EmojiSpec("jjk_points", "💠"),
    "competences": EmojiSpec("jjk_competences", "🌳"),
    "xp": EmojiSpec("jjk_xp", "⭐"),
    "train": EmojiSpec("jjk_train", "💪"),
    "debloque": EmojiSpec("jjk_debloque", "✅"),
    "disponible": EmojiSpec("jjk_disponible", "🔓"),
    "verrouille": EmojiSpec("jjk_verrouille", "🔒"),
    "panier": EmojiSpec("jjk_panier", "🛒"),
    "valider": EmojiSpec("jjk_valider", "✔️"),
    "annuler": EmojiSpec("jjk_annuler", "✖️"),
    "continuer": EmojiSpec("jjk_continuer", "➡️"),
    "succes": EmojiSpec("jjk_succes", "✅"),
    "erreur": EmojiSpec("jjk_erreur", "❌"),
    "alerte": EmojiSpec("jjk_alerte", "⚠️"),
    "aide": EmojiSpec("jjk_aide", "⛩️"),
    "fleche": EmojiSpec("jjk_fleche", "❯"),
    "categorie": EmojiSpec("jjk_categorie", "📂"),
    "progression": EmojiSpec("jjk_progression", "📈"),
    "page_profil": EmojiSpec("jjk_page_profil", "📜"),
    "page_stats": EmojiSpec("jjk_page_stats", "📊"),
    "page_traits": EmojiSpec("jjk_page_traits", "🧬"),
    "blackflash": EmojiSpec("jjk_blackflash", "🎭"),
    "blackflash_rate": EmojiSpec("jjk_blackflash_rate", "⚔️"),
    "blackflash_tentative": EmojiSpec("jjk_blackflash_tentative", "🌙"),
    "blackflash_chance": EmojiSpec("jjk_blackflash_chance", "🎲"),
    "renaissance": EmojiSpec("jjk_renaissance", "👻"),
    "renaissance_rate": EmojiSpec("jjk_renaissance_rate", "💀"),
    "renaissance_tentative": EmojiSpec("jjk_renaissance_tentative", "🕯️"),
    "renaissance_chance": EmojiSpec("jjk_renaissance_chance", "🎲"),
    "demande_xp": EmojiSpec("jjk_demande_xp", "📨"),
    "attente": EmojiSpec("jjk_attente", "🕒"),
}

# Clés affichées dans `/jjk emojis`, dans un ordre lisible.
DISPLAY_ORDER: tuple[str, ...] = tuple(DEFAULT_CATALOG)


def load_catalog(path=None) -> dict[str, EmojiSpec]:
    """Charge `config/emojis.json`, en complétant avec les valeurs par défaut."""
    catalog = dict(DEFAULT_CATALOG)
    emojis_path = path or config.EMOJIS_FILE

    try:
        with open(emojis_path, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except FileNotFoundError:
        logger.warning("config/emojis.json est introuvable, les emojis unicode sont utilisés.")
        return catalog
    except json.JSONDecodeError as error:
        logger.error("config/emojis.json est invalide (%s), les emojis unicode sont utilisés.", error)
        return catalog

    if not isinstance(raw, dict):
        logger.error("config/emojis.json doit contenir un objet JSON.")
        return catalog

    for key, value in raw.items():
        if isinstance(value, str) and value.strip():
            catalog[key] = EmojiSpec(value.strip(), catalog.get(key, EmojiSpec(key, "❔")).fallback)
        elif isinstance(value, dict):
            previous = catalog.get(key, EmojiSpec(key, "❔"))
            name = value.get("name")
            fallback = value.get("fallback")
            catalog[key] = EmojiSpec(
                name.strip() if isinstance(name, str) and name.strip() else previous.name,
                fallback if isinstance(fallback, str) and fallback else previous.fallback,
            )
    return catalog


class EmojiResolver:
    """Résout les clés du catalogue vers un emoji du serveur ou un repli unicode."""

    def __init__(self, catalog: dict[str, EmojiSpec]):
        self._catalog = catalog
        self._by_guild: dict[int, dict[str, discord.Emoji]] = {}
        self._by_name: dict[str, discord.Emoji] = {}
        self._last_rest_fetch: dict[int, float] = {}

    @property
    def catalog(self) -> dict[str, EmojiSpec]:
        return self._catalog

    def refresh(self, guilds) -> None:
        """Réindexe les emojis des serveurs connus."""
        self._by_guild = {}
        self._by_name = {}
        for guild in guilds or ():
            index: dict[str, discord.Emoji] = {}
            for emoji in getattr(guild, "emojis", ()) or ():
                index[emoji.name] = emoji
                self._by_name.setdefault(emoji.name, emoji)
            self._by_guild[guild.id] = index
        logger.debug("Catalogue d’emojis indexé : %d serveur(s).", len(self._by_guild))

    def _guild_index(self, guild) -> dict[str, discord.Emoji]:
        if guild is None:
            return {}
        index = self._by_guild.get(getattr(guild, "id", None))
        return index if index is not None else {}

    def _find(self, spec: EmojiSpec, guild) -> discord.Emoji | None:
        index = self._guild_index(guild)
        if spec.name in index:
            return index[spec.name]
        # L’index peut être en retard (emoji ajouté pendant la session) : on
        # relit directement la collection du serveur passé au rendu.
        if guild is not None:
            for emoji in getattr(guild, "emojis", ()) or ():
                if getattr(emoji, "name", None) == spec.name:
                    return emoji
        # L’emoji peut vivre sur un autre serveur du bot : il reste utilisable.
        return self._by_name.get(spec.name)

    def index_count(self) -> int:
        """Nombre d’emojis custom indexés (diagnostic)."""
        return len(self._by_name)

    def fallback(self, key: str) -> str:
        """Emoji unicode de secours d’une clé.

        À l’intérieur d’un bloc de code Markdown, les emojis custom du
        serveur ne sont pas rendus : on y insère donc ce repli unicode.
        """
        spec = self._catalog.get(key)
        return spec.fallback if spec else "❔"

    async def ensure_loaded(self, guild) -> None:
        """Complète l’index via l’API REST si le cache du serveur est vide.

        Filet de sécurité : si l’intent « emojis » n’était pas actif au
        démarrage (ancien déploiement) ou si le cache passerelle est vide,
        `guild.emojis` ne contient rien et tous les emojis retombent sur leur
        repli unicode. L’endpoint REST `GET /guilds/{id}/emojis` fonctionne
        lui même sans cet intent : on s’en sert pour réparer à chaud.
        """
        if guild is None or not hasattr(guild, "fetch_emojis"):
            return
        if list(getattr(guild, "emojis", ()) or ()):
            # Cache passerelle peuplé : `_find` le lit en direct, rien à faire.
            return

        guild_id = getattr(guild, "id", None)
        last = self._last_rest_fetch.get(guild_id, float("-inf"))
        if time.monotonic() - last < REST_FETCH_COOLDOWN:
            return
        self._last_rest_fetch[guild_id] = time.monotonic()

        try:
            fetched = await guild.fetch_emojis()
        except discord.HTTPException as error:
            logger.warning(
                "Impossible de récupérer les emojis du serveur %s via l’API REST : %s",
                guild_id,
                error,
            )
            return

        index: dict[str, discord.Emoji] = {}
        for emoji in fetched:
            index[emoji.name] = emoji
            self._by_name.setdefault(emoji.name, emoji)
        if guild_id in self._by_guild:
            self._by_guild[guild_id].update(index)
        else:
            self._by_guild[guild_id] = index
        logger.info(
            "Emojis récupérés via l’API REST pour le serveur %s : %d trouvé(s).",
            guild_id,
            len(index),
        )

    def get(self, key: str, guild=None) -> str:
        """Renvoie l’emoji prêt à être inséré dans un texte."""
        spec = self._catalog.get(key)
        if spec is None:
            return "❔"
        custom = self._find(spec, guild)
        return str(custom) if custom is not None else spec.fallback

    def as_partial(self, key: str, guild=None) -> discord.PartialEmoji | None:
        """Renvoie un PartialEmoji utilisable par les boutons et les menus."""
        spec = self._catalog.get(key)
        candidate = self._find(spec, guild) if spec else None
        if candidate is not None:
            return discord.PartialEmoji(name=candidate.name, id=candidate.id, animated=candidate.animated)
        if spec is None or not spec.fallback:
            return None
        try:
            return discord.PartialEmoji.from_str(spec.fallback)
        except Exception:  # pragma: no cover - repli défensif
            return None

    def status(self, guild) -> list[tuple[str, EmojiSpec, discord.Emoji | None]]:
        """État du catalogue pour un serveur, utilisé par `/jjk emojis`."""
        rows = []
        for key in DISPLAY_ORDER:
            spec = self._catalog[key]
            rows.append((key, spec, self._find(spec, guild)))
        return rows

    def missing_keys(self, guild) -> list[str]:
        """Clés dont l’emoji custom n’a pas été trouvé sur le serveur."""
        return [key for key, _spec, found in self.status(guild) if found is None]


# Instance partagée par tout le bot.
emojis = EmojiResolver(load_catalog())


def refresh_emojis(guilds) -> None:
    """Rafraîchit le catalogue global."""
    emojis.refresh(guilds)


async def ensure_loaded(guild) -> None:
    """Répare l’index d’un serveur via l’API REST si son cache est vide."""
    await emojis.ensure_loaded(guild)
