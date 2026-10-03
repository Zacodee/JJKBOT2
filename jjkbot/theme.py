"""Palettes et mise en forme des embeds.

Tout le rendu visuel du bot passe par ce module : titres, lignes groupées,
séparateurs, citations et bannière. Changer de palette revient à changer
`THEME` dans `.env` (« violet » ou « noblesse »).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import discord

from jjkbot import config
from jjkbot.emojis import emojis

logger = logging.getLogger(__name__)

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


def fallback(key: str) -> str:
    """Emoji unicode de secours d’une clé, insérable dans un bloc de code.

    À l’intérieur d’un ``` les emojis custom du serveur ne sont PAS rendus
    (ils s’affichent en texte brut `<:nom:id>`) : on y met donc toujours le
    repli unicode, qui reste lisible en monospace.
    """
    return emojis.fallback(key)


# --- Mise en forme -----------------------------------------------------------


def title(key: str, label: str, guild=None, suffix: str | None = None) -> str:
    """Ligne de titre en Markdown : `## 📛 Profil : @joueur`.

    Discord ne rend AUCUN Markdown dans le champ `title` d’un embed (les
    `__`, `**` ou `##` s’afficheraient tels quels) : le vrai titre stylé est
    donc cette ligne `##` à placer en tête de la **description**, où les
    titres, le gras et les emojis custom sont rendus.
    """
    return heading(f"{label}{suffix or ''}", 2, guild, key)


def entry(
    key: str,
    label: str,
    value,
    guild=None,
) -> str:
    """Une ligne d’information compacte : `🪪 **Identité :** `Zuruï``.

    Le libellé est en **gras** et la valeur entre accents graves (`code`) :
    c’est ce contraste de graisse et de police qui donne à une fiche sa
    hiérarchie visuelle, sans alourdir la mise en page.
    """
    return f"{emoji(key, guild)} **{label} :** {value_code(value)}"


def field_label(key: str, text: str, guild=None) -> str:
    """Libellé de champ en petit titre souligné : `### 🪪 __Identité__`.

    Discord n’a pas de taille « moyenne » : `###` est le plus petit titre et
    fait légèrement ressortir le libellé au-dessus du texte courant, et le
    soulignement le sépare visuellement du reste. Comme tout titre, ça ne
    fonctionne que dans la **description** d’un embed.
    """
    return f"### {emoji(key, guild)} __{text}__"


def value_code(value) -> str:
    """Valeur d’un champ entre accents graves (`code`), propre pour le Markdown."""
    text = str(value).strip() if value is not None and str(value).strip() else "Non renseigné"
    # Une apostrophe inversée saisie par un joueur casserait la mise en forme.
    # (hors expression de f-string : les antislashs y sont interdits avant 3.12)
    clean = text.replace("`", "\u2019")
    return f"`{clean}`"


def row(*specs, guild=None) -> str:
    """Plusieurs champs de fiche sur une MÊME ligne, séparés par « • ».

    Version compacte de `group` : deux champs par ligne au lieu d’un libellé
    + une valeur sur chacune, ce qui allège nettement la première page d’une
    fiche. Chaque spécification est un tuple `(clé_emoji, libellé, valeur)`.
    """
    return "  •  ".join(entry(spec[0], spec[1], spec[2], guild=guild) for spec in specs)


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


def heading(text: str, level: int = 2, guild=None, key: str | None = None) -> str:
    """Titre Markdown (`##`, `###`).

    Attention : les titres ne sont rendus par Discord que dans la
    **description** d’un embed, jamais dans les noms ni les valeurs de champ.
    """
    glyph = f"{emoji(key, guild)} " if key else ""
    return f"{'#' * max(1, min(3, level))} {glyph}{text}"


def code_block(lines, language: str = "") -> str:
    """Bloc de code Markdown (triple accent grave), idéal pour un tableau aligné.

    À l’intérieur, ni le gras, ni l’italique, ni les emojis custom ne sont
    rendus : réserve-le aux données brutes (chiffres, barres, colonnes).
    """
    body = "\n".join(str(line) for line in lines)
    return f"```{language}\n{body}\n```"


def mono_table(rows) -> str:
    """Tableau de colonnes alignées, rendu dans un bloc de code.

    Chaque ligne est une séquence de cellules ; les colonnes sont calées sur
    la cellule la plus large. En monospace, les barres et les chiffres
    s’alignent parfaitement, comme un tableau dessiné à la main.
    """
    rows = [tuple(str(cell) for cell in row) for row in rows]
    if not rows:
        return ""
    width = [max(len(row[column]) for row in rows) for column in range(len(rows[0]))]
    lines = [
        "  ".join(cell.ljust(width[column]) for column, cell in enumerate(row)).rstrip()
        for row in rows
    ]
    return code_block(lines)


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


# --- Bannière ----------------------------------------------------------------


def banner_file() -> discord.File | None:
    """Copie fraîche de l’image de bannière locale.

    Un `discord.File` ne peut être envoyé qu’une seule fois : on en ouvre un
    nouveau à chaque envoi. Renvoie None si l’image locale est absente.
    """
    path = Path(config.BANNER_PATH)
    if not path.is_file() or path.stat().st_size <= 0:
        return None
    try:
        return discord.File(path, filename=path.name)
    except OSError as error:  # pragma: no cover - dépend du disque
        logger.warning("Image de bannière illisible (%s) : %s", path, error)
        return None


def banner_embed(files: list[discord.File] | None = None) -> discord.Embed | None:
    """Embed de bannière : image locale en priorité, `BANNER_URL` en repli.

    L’image locale (`assets/banniere_jjk.png`) est jointe au message via
    `attachment://` : contrairement aux URL de CDN Discord, qui sont signées
    et expirent en quelques heures, elle n’a pas de date de péremption. Elle
    est donc prioritaire sur `BANNER_URL`.

    Sans image locale, `BANNER_URL` s’il est configuré s’affiche tel quel.
    Et si la bannière vient du fichier local mais qu’aucune liste `files`
    n’est fournie, l’image ne pourrait pas être jointe au message : on
    renvoie None plutôt que l’embed d’une image qui ne s’afficherait pas
    (et on n’ouvre jamais le fichier pour rien).
    """
    path = Path(config.BANNER_PATH)
    if path.is_file() and path.stat().st_size > 0:
        if files is None:
            return None
        file = banner_file()
        if file is None:  # pragma: no cover - le fichier vient d’être vérifié
            return None
        files.append(file)
        return discord.Embed(color=color(SECTION_NEUTRE)).set_image(
            url=f"attachment://{file.filename}"
        )

    if config.BANNER_URL:
        return discord.Embed(color=color(SECTION_NEUTRE)).set_image(url=config.BANNER_URL)
    return None


def with_banner(
    content_embed: discord.Embed,
    files: list[discord.File] | None = None,
) -> list[discord.Embed]:
    """Embeds d’une réponse : bannière, contenu, bannière (début et fin).

    La bannière encadre le message comme dans le visuel d’origine. Passer
    `files` permet de joindre l’image locale au message ; sans elle, seule
    une bannière par `BANNER_URL` (sans fichier) peut s’afficher.
    """
    banner = banner_embed(files)
    if banner is None:
        return [content_embed]
    return [banner, content_embed, banner]


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
