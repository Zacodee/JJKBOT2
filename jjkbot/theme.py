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
SECTION_BLACKFLASH = "blackflash"
SECTION_RENAISSANCE = "renaissance"
SECTION_DEMANDES = "demandes"

# Champ de nom vide : Discord impose un nom de champ non nul, mais un
# espace insécable ne prend pas de place — le libellé vit alors dans la
# valeur, où le Markdown est rendu.
BLANK_FIELD = "\u200b"


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
            SECTION_BLACKFLASH: 0x9A0A16,
            SECTION_RENAISSANCE: 0x6D28D9,
            SECTION_DEMANDES: 0x0EA5E9,
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
            SECTION_BLACKFLASH: 0x9A0A16,
            SECTION_RENAISSANCE: 0x9A0A16,
            SECTION_DEMANDES: 0x9A0A16,
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


def field_title(key: str, text: str, guild=None) -> str:
    """Titre de champ de la fiche : `🪪 **__Identité__**`.

    Les grands titres `###` ne sont rendus que dans la **description** d’un
    embed — Discord les interdit dans les valeurs de champ (discord-api-docs
    #7167) et n’y rend pas le Markdown dans les noms (#1089). Les valeurs de
    champ, elles, supportent tout le Markdown : c’est donc là que vit le
    libellé des colonnes. L’emoji reste **hors** du gras et du soulignement
    pour rester net, le libellé étant souligné pour signifier « colonne ».
    """
    return f"{emoji(key, guild)} **__{text}__**"


def _clean_value(value) -> str:
    """Texte d’une valeur, vide remplacé et accents graves neutralisés.

    Une apostrophe inversée saisie par un joueur, ou le moindre accent grave,
    casserait le délimiteur `code` : on les remplace tous (hors expression de
    f-string, où les antislashs sont interdits avant Python 3.12).
    """
    text = str(value).strip() if value is not None and str(value).strip() else "Non renseigné"
    return text.replace("`", "\u2019")


def value_code(value) -> str:
    """Valeur d’un champ entre accents graves (`code`), propre pour le Markdown."""
    return f"`{_clean_value(value)}`"


def boxed_value(value) -> str:
    """Valeur encadrée d’un champ de fiche : `➺ 【 ``Zuruï`` 】`.

    La double paire d’accents graves fait ressortir la valeur par le fond
    sombre et la police monospace, et l’encadrement lui donne un poids
    visuel équivalent au libellé gras souligné qui la surplombe.
    """
    return f"➺ 【 ``{_clean_value(value)}`` 】"


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


def banner_file(part: str = "debut") -> discord.File | None:
    """Copie fraîche de l’image de bannière locale.

    Un `discord.File` ne peut être envoyé qu’une seule fois : on en ouvre un
    nouveau à chaque envoi. Renvoie None si l’image locale est absente.

    La bannière de tête et celle de pied portent deux noms de fichier
    distincts (`banniere_jjk.png` / `banniere_jjk_fin.png`) : deux embeds
    d’un même message ne doivent jamais partager la même attachment, sinon
    Discord laisse l’un des deux sur son image de remplacement floutée.
    """
    path = Path(config.BANNER_PATH)
    if not path.is_file() or path.stat().st_size <= 0:
        return None
    filename = path.name if part != "fin" else f"{path.stem}_fin{path.suffix}"
    try:
        return discord.File(path, filename=filename)
    except OSError as error:  # pragma: no cover - dépend du disque
        logger.warning("Image de bannière illisible (%s) : %s", path, error)
        return None


def banner_embed(
    files: list[discord.File] | None = None,
    part: str = "debut",
) -> discord.Embed | None:
    """Embed de bannière : image locale en priorité, `BANNER_URL` en repli.

    L’image locale (`assets/banniere_jjk.png`) est jointe au message via
    `attachment://` : contrairement aux URL de CDN Discord, qui sont signées
    et expirent en quelques heures, elle n’a pas de date de péremption. Elle
    est donc prioritaire sur `BANNER_URL`.

    `part` choisit la variante jointe (`debut` ou `fin`) : chaque embed reçoit
    sa propre attachment, jamais deux embeds ne partagent le même fichier.

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
        file = banner_file(part)
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

    Chaque bannière a sa propre attachment (`banniere_jjk.png` et
    `banniere_jjk_fin.png`) : un même fichier référencé par deux embeds
    laisse l’un des deux sur son image floutée de remplacement.
    """
    top = banner_embed(files, part="debut")
    if top is None:
        return [content_embed]
    bottom = banner_embed(files, part="fin") or top
    return [top, content_embed, bottom]


# --- Images de résultat (Black Flash, Renaissance) ---------------------------
#
# Les deux évènements suivent la même règle : le fichier local est joint au
# message via `attachment://` (aucune expiration), l’URL ne servant que de repli
# si l’image est absente.


def _result_file(path: Path, label: str) -> discord.File | None:
    """Copie fraîche d’une image locale, ou None si elle est absente.

    Un `discord.File` ne peut être envoyé qu’une seule fois : on en ouvre donc
    un nouveau à chaque envoi.
    """
    if not path.is_file() or path.stat().st_size <= 0:
        return None
    try:
        return discord.File(path, filename=path.name)
    except OSError as error:  # pragma: no cover - dépend du disque
        logger.warning("Image %s illisible (%s) : %s", label, path, error)
        return None


def _result_image(
    path: Path,
    url: str | None,
    files: list[discord.File] | None,
    label: str,
) -> str | None:
    """URL d’une image de résultat : locale en `attachment://`, sinon repli `url`.

    Sans liste `files`, l’image locale ne pourrait pas être jointe : on renvoie
    None (ou l’URL de repli) plutôt qu’une image qui ne s’afficherait pas.
    """
    if path.is_file() and path.stat().st_size > 0:
        if files is None:
            return None
        file = _result_file(path, label)
        if file is None:  # pragma: no cover - le fichier vient d’être vérifié
            return None
        files.append(file)
        return f"attachment://{file.filename}"
    return url


def blackflash_file(success: bool) -> discord.File | None:
    """Copie fraîche de l’image de Black Flash (succès ou échec)."""
    return _result_file(
        Path(config.BLACKFLASH_OK_PATH if success else config.BLACKFLASH_KO_PATH),
        "de Black Flash",
    )


def blackflash_image(
    success: bool,
    files: list[discord.File] | None = None,
) -> str | None:
    """URL d’image du résultat du Black Flash (image locale, sinon URL de repli)."""
    return _result_image(
        Path(config.BLACKFLASH_OK_PATH if success else config.BLACKFLASH_KO_PATH),
        config.BLACKFLASH_OK_URL if success else config.BLACKFLASH_KO_URL,
        files,
        "de Black Flash",
    )


def renaissance_image(
    success: bool,
    files: list[discord.File] | None = None,
) -> str | None:
    """URL d’image du résultat de la Renaissance (image locale, sinon URL de repli)."""
    return _result_image(
        Path(config.RENAISSANCE_OK_PATH if success else config.RENAISSANCE_KO_PATH),
        config.RENAISSANCE_OK_URL if success else config.RENAISSANCE_KO_URL,
        files,
        "de Renaissance",
    )


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
