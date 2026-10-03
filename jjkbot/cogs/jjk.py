"""Commande `/jjk` : guide de démarrage et diagnostic des emojis."""

import discord
from discord import app_commands
from discord.ext import commands

from jjkbot import config, emojis as emojis_module, permissions, theme


def build_help_embed(guild: discord.Guild | None = None) -> discord.Embed:
    """Guide de démarrage destiné aux nouveaux membres.

    Tout le contenu vit dans la description : c’est le seul endroit d’un embed
    où Discord rend les titres `##`, le gras et les blocs de code.
    """
    e = lambda key: theme.emoji(key, guild)  # noqa: E731 - raccourci de lisibilité

    sections = (
        (
            f"{e('profil')} Créer ton personnage",
            [
                f"`/profil creer` • étape 1 : {e('identite')} identité, {e('age')} âge, "
                f"{e('race')} race, {e('grade')} grade, {e('alignement')} alignement",
                f"`/profil creer` • étape 2 : {e('role')} rôle, {e('citation')} citation, "
                "traits et défauts",
                f"`/profil image` • {e('image')} ajoute une image PNG, JPG, WEBP ou un GIF",
            ],
        ),
        (
            f"{e('page_profil')} Consulter et modifier ta fiche",
            [
                f"`/profil voir` • {e('page_profil')} 3 pages navigables : profil, "
                f"{e('page_stats')} statistiques, {e('page_traits')} traits et défauts",
                "`/profil voir joueur:` • consulte la fiche d’un autre membre",
                "`/profil modifier` • mets ta fiche à jour",
            ],
        ),
        (
            f"{e('points')} Points de statistique",
            [
                f"`/profil attribuer-stat` • {e('points')} investis tes points dans "
                f"{e('force')} Force, {e('resistance')} Résistance, {e('vitesse')} Vitesse, "
                f"{e('reserve_eo')} Réserve d’EO ou {e('sortie_eo')} Sortie d’EO",
                f"`/profil donner-points` • {e('aide')} le staff t’en attribue après un RP",
            ],
        ),
        (
            f"{e('competences')} Compétences",
            [
                f"`/competences voir` • {e('competences')} l’arbre complet, catégorie par catégorie",
                f"`/competences acheter` • {e('panier')} panier multi-compétences, "
                "prérequis vérifiés automatiquement",
                f"{e('xp')} l’XP s’obtient en RP : le staff l’attribue avec `/competences xp`",
            ],
        ),
        (
            f"{e('alerte')} Commandes du staff",
            [
                "`/profil donner-points` • points de statistique",
                "`/competences xp` • expérience",
                "`/profil reset` • profil complet, statistiques ou compétences",
                "`/jjk emojis` • vérifier les emojis du serveur",
            ],
        ),
    )

    chunks = [
        theme.title("aide", "Guide du nouveau sorcier", guild),
        "Bienvenue dans le monde du jujutsu ! Ce guide t’explique pas à pas comment créer "
        "ton personnage et utiliser les commandes du bot.",
        theme.divider(),
    ]
    for heading, lines in sections:
        chunks.append(theme.heading(heading, 3, guild))
        chunks.append("\n".join(lines))

    embed = discord.Embed(
        colour=theme.color(theme.SECTION_AIDE),
        description=theme.blocks(*chunks),
    )
    embed.set_footer(text="✦ Bonne aventure, sorcier. Que ton énergie occulte te guide. ✦")
    if config.HELP_GIF_URL:
        embed.set_image(url=config.HELP_GIF_URL)
    return embed


def _chunk_lines(lines: list[str], limit: int = 1000) -> list[str]:
    """Regroupe des lignes en blocs de moins de `limit` caractères."""
    chunks: list[str] = []
    current: list[str] = []
    length = 0
    for line in lines:
        if current and length + len(line) + 1 > limit:
            chunks.append("\n".join(current))
            current = []
            length = 0
        current.append(line)
        length += len(line) + 1
    if current:
        chunks.append("\n".join(current))
    return chunks


def build_emoji_report_embed(
    guild: discord.Guild | None,
    rows: list[tuple[str, emojis_module.EmojiSpec, discord.Emoji | None]],
) -> discord.Embed:
    """État du catalogue d’emojis : ce qui est trouvé, ce qu’il reste à créer."""
    found = [(key, spec, emoji) for key, spec, emoji in rows if emoji is not None]
    missing = [(key, spec, emoji) for key, spec, emoji in rows if emoji is None]

    def lines_for(entries, show_fallback: bool) -> list[str]:
        lines = []
        for key, spec, emoji in entries:
            glyph = str(emoji) if emoji is not None else ("⚠️" if show_fallback else "")
            suffix = f" — repli {spec.fallback}" if show_fallback else ""
            lines.append(f"{glyph} `{spec.name}` ({key}){suffix}")
        return lines

    embed = discord.Embed(
        colour=theme.color(theme.SECTION_AIDE),
        title=theme.title("aide", "Emojis du serveur", guild),
        description=theme.blocks(
            f"**{len(found)} / {len(rows)}** emojis custom ont été trouvés sur le serveur.",
            theme.divider(),
        ),
    )
    # Les champs Discord sont limités à 1024 caractères : on découpe la liste.
    for title, entries, show_fallback in (("✅ Trouvés", found, False), ("⚠️ À créer", missing, True)):
        chunks = _chunk_lines(lines_for(entries, show_fallback))
        if not chunks:
            embed.add_field(name=title, value="*Rien à signaler.*", inline=False)
            continue
        for index, chunk in enumerate(chunks):
            name = title if index == 0 else f"{title} (suite)"
            embed.add_field(name=name, value=chunk, inline=False)
    embed.set_footer(
        text="✦ Crée les emojis manquants avec ces noms exacts, puis relance /jjk emojis."
    )
    return embed


class JjkCog(
    commands.GroupCog,
    group_name="jjk",
    group_description="Guide du bot et aide pour les nouveaux membres",
):
    """Guide du bot, utilité des commandes et diagnostic des emojis."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="help", description="Guide de démarrage et utilité des commandes")
    @app_commands.guild_only()
    async def help(self, interaction: discord.Interaction) -> None:
        await emojis_module.ensure_loaded(interaction.guild)
        await interaction.response.send_message(
            embeds=theme.with_banner(build_help_embed(interaction.guild))
        )

    @app_commands.command(name="emojis", description="Vérifier les emojis du serveur utilisés par le bot")
    @app_commands.guild_only()
    async def emojis(self, interaction: discord.Interaction) -> None:
        if not await permissions.ensure_staff(interaction):
            return

        # Répare l’index via l’API REST si le cache passerelle est vide, puis
        # dresse l’état du catalogue : aucun refresh brutal qui écraserait la réparation.
        await emojis_module.ensure_loaded(interaction.guild)
        rows = emojis_module.emojis.status(interaction.guild)
        await interaction.response.send_message(
            embed=build_emoji_report_embed(interaction.guild, rows),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    """Chargement du cog par le bot."""
    await bot.add_cog(JjkCog(bot))
