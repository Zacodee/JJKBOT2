"""Palettes et mise en forme des embeds.

Tout le rendu visuel du bot passe par ce module : titres, lignes groupées,
séparateurs, citations et bannière. Changer de palette revient à changer
`THEME` dans `.env` (« violet » ou « noblesse »).
"""

from __future__ import annotations

from dataclasses import dataclass

import discord

from jjkbot import config
from jjkbot.emojis import emojis

# Sections possibles d’un embed.
SECTION_PROFIL = "profil"
SECTION_STATS = "stats"
SECTION_COMPETENCES = "competences"
SECTION_PANIER = "panier"
SECTION_AIDE = "aide"
SECTION_SUCCES = "succes"
SECTION_ERREUR = "erreur"
SECTION_ALERTE = "alerte"
SECTION_NEUTRE = "neutre"


@dataclass(frozen=True)
class Palette:
    """Jeu de couleurs d’un thème."""

    label: str
    colors: dict[str, int]

    def color(self, section: str) -> int:
        return self.colors.get(section, self.colors[SECTION_NEUTRE])


PALETTES: dict[str, Palette] = {
    # Thème « violet », inspiré des embeds de référence.
    "violet": Palette(
        label="Violet",
        colors={
            SECTION_PROFIL: 0x8B5CF6,
            SECTION_STATS: 0x5865F2,
            SECTION_COMPETENCES: 0x22A06B,
            SECTION_PANIER: 0xC9A227,
            SECTION_AIDE: 0x8B5CF6,
            SECTION_SUCCES: 0x22A06B,
            SECTION_ERREUR: 0xE74C3C,
            SECTION_ALERTE: 0xE0A458,
            SECTION_NEUTRE: 0x4B0D14,
        },
    ),
    # Thème « noblesse » : l’identité visuelle d’origine du bot.
    "noblesse": Palette(
        label="Noblesse Jujogo",
        colors={
            SECTION_PROFIL: 0x9A0A16,
            SECTION_STATS: 0x9A0A16,
            SECTION_COMPETENCES: 0x9A0A16,
            SECTION_PANIER: 0x9A0A16,
            SECTION_AIDE: 0x9A0A16,
            SECTION_SUCCES: 0x8A6B2F,
            SECTION_ERREUR: 0x9A0A16,
            SECTION_ALERTE: 0xC9B458,
            SECTION_NEUTRE: 0x4B0D14,
        },
    ),
}

PAGE_FOOTERS = ("Page 1 / 3", "Page 2 / 3", "Page 3 / 3")


def palette() -> Palette:
    """Renvoie la palette active."""
    return PALETTES.get(config.THEME, PALETTES["violet"])


def color(section: str = SECTION_NEUTRE) -> int:
    """Couleur d’une section dans la palette active."""
    return palette().color(section)


def emoji(key: str, guild=None) -> str:
    """Emoji du serveur correspondant à une clé, sinon repli unicode."""
    return emojis.get(key, guild)


def partial_emoji(key: str, guild=None) -> discord.PartialEmoji | None:
    """Emoji utilisable par les boutons et les menus déroulants."""
    return emojis.as_partial(key, guild)


# --- Mise en forme -----------------------------------------------------------


def title(key: str, label: str, guild=None, suffix: str | None = None) -> str:
    """Titre d’embed : `📛 — __Profil__ : @joueur`."""
    heading = f"{emoji(key, guild)} — __{label}__"
    return f"{heading} {suffix}".strip() if suffix else heading


def entry(
    key: str,
    label: str,
    value,
    guild=None,
    style: str = "arrow",
    last: bool = False,
) -> str:
    """Une ligne d’information, dans le style de la fiche de référence.

    Le libellé est en **gras** et la valeur en `code` : c’est ce contraste de
    graisse et de police qui donne à la fiche sa hiérarchie visuelle.

    - `style="arrow"` : `│ · 🪪 **[Identité]** → `["Zuruï"]``
    - `style="colon"` : `╰ · ⏳ **Âge** : `[1 an]``
    """
    prefix = "╰ ·" if last else "│ ·"
    text = str(value).strip() if value is not None and str(value).strip() else "Non renseigné"
    glyph = emoji(key, guild)
    # Une apostrophe inversée saisie par un joueur casserait la mise en forme.
    clean = text.replace("`", "\u2019")

    if style == "colon":
        return f"{prefix} {glyph} **{label}** : `[{clean}]`"
    return f'{prefix} {glyph} **[{label}]** → `["{clean}"]`'


def group(*specs, guild=None) -> str:
    """Assemble un bloc de lignes : la dernière porte `╰`, les autres `│`.

    Chaque spécification est un tuple `(clé_emoji, libellé, valeur)` ou
    `(clé_emoji, libellé, valeur, style)`.
    """
    lines: list[str] = []
    for index, spec in enumerate(specs):
        key, label, value = spec[0], spec[1], spec[2]
        style = spec[3] if len(spec) > 3 else "arrow"
        lines.append(entry(key, label, value, guild=guild, style=style, last=index == len(specs) - 1))
    return "\n".join(lines)


def blocks(*chunks) -> str:
    """Assemble plusieurs blocs ou lignes en les séparant par une ligne vide."""
    return "\n\n".join(chunk for chunk in chunks if chunk)


def quote_block(quote: str, guild=None) -> str:
    """Citation mise en avant, sur une seule ligne : `❯ **Citation** ❝ … ❞`."""
    text = str(quote).strip() if quote and str(quote).strip() else "Aucune citation renseignée."
    return f"{emoji('citation', guild)} **Citation** ❝ *{truncate(text, 300)}* ❞"


def highlight(key: str, text: str, guild=None) -> str:
    """Ligne mise en avant, utile pour les totaux et les compteurs."""
    return f"▌ {emoji(key, guild)} {text}"


def section(key: str, text: str, guild=None) -> str:
    """Sous-titre de section à l’intérieur d’une description."""
    return f"{emoji(key, guild)} **{text}**"


def divider() -> str:
    """Séparateur discret entre deux blocs."""
    return "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"


def progress_bar(value: int, total: int, length: int = 10) -> str:
    """Barre de progression textuelle."""
    if total <= 0:
        return "▱" * length
    filled = max(0, min(length, round(length * value / total)))
    return "▰" * filled + "▱" * (length - filled)


def truncate(value: str, max_length: int) -> str:
    """Raccourcit un texte trop long."""
    if not value:
        return ""
    return value if len(value) <= max_length else f"{value[: max_length - 1]}…"


def bullet_list(entries: list[str], prefix: str = "•") -> str:
    """Liste à puces, ou rappel qu’aucune donnée n’est renseignée."""
    if not entries:
        return "*Aucun renseignement pour le moment.*"
    return "\n".join(f"{prefix} {entry_}" for entry_ in entries)


# --- Embeds ------------------------------------------------------------------


def banner_embed() -> discord.Embed | None:
    """Bannière décorative affichée en haut des réponses, si configurée."""
    if not config.BANNER_URL:
        return None
    return discord.Embed(color=color(SECTION_NEUTRE)).set_image(url=config.BANNER_URL)


def with_banner(content_embed: discord.Embed) -> list[discord.Embed]:
    """Liste d’embeds d’une réponse : bannière puis contenu."""
    banner = banner_embed()
    return [banner, content_embed] if banner is not None else [content_embed]


def notice_embed(
    section_name: str,
    key: str,
    message: str,
    guild=None,
    footer: str | None = None,
) -> discord.Embed:
    """Petit embed de confirmation, d’erreur ou d’alerte."""
    embed = discord.Embed(colour=color(section_name), description=f"{emoji(key, guild)} {message}")
    if footer:
        embed.set_footer(text=footer)
    return embed


def content_embed(
    section_name: str,
    title_text: str,
    description: str | None = None,
    footer: str | None = None,
    author: discord.abc.User | None = None,
) -> discord.Embed:
    """Embed de contenu prêt à l’emploi, à la couleur de la section."""
    embed = discord.Embed(colour=color(section_name), title=title_text)
    if description:
        embed.description = description
    if footer:
        embed.set_footer(text=footer)
    if author is not None:
        embed.set_author(name=author.display_name, icon_url=author.display_avatar.url)
    return embed
