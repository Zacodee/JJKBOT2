"""Rendu et envoi du résultat d’une Renaissance en Esprit Vengeur.

Même structure que l’embed de Black Flash : titre, texte narratif, rappel du
seuil en bloc de code, état en lignes à emojis du catalogue, puis l’image du
résultat (fichier local joint via `attachment://`).
"""

from __future__ import annotations

import logging

import discord

from jjkbot import emojis as emojis_module, theme
from jjkbot.content import renaissance as rules

logger = logging.getLogger(__name__)

FOOTER = "Jujutsu Kaisen RP • Renaissance en Esprit Vengeur"


def situation_text(situation: rules.Situation) -> str:
    """Texte du bloc de code : seuil et libellé de la situation."""
    return f"[ Seuil de réussite : {situation.threshold} — {situation.label} ]"


def build_renaissance_embed(
    success: bool,
    die: int,
    situation_id=rules.DEFAULT_SITUATION,
    guild=None,
    files: list[discord.File] | None = None,
) -> discord.Embed:
    """Embed de résultat : réussite (Esprit Vengeur) ou échec (repos de l’âme).

    `die` est le résultat du dé de 100, affiché pour que la table voie d’où
    vient la décision, avec le seuil de la situation choisie.
    """
    situation = rules.get_situation(situation_id)
    threshold = situation.threshold
    verdict = "Réussit" if success else "Échoué"
    comparison = f"`{die}` ≤ seuil `{threshold}`" if success else f"`{die}` > seuil `{threshold}`"

    # Embed d’évènement : le texte est écrit en **gras** (voir `theme.bold`).
    if success:
        # Titre : repli unicode, car le champ `title` ne rend pas les emojis custom.
        title = f"{theme.fallback('renaissance')} Renaissance en Esprit Vengeur"
        description = theme.blocks(
            theme.bold(rules.SUCCESS_TEXT),
            theme.code_block([situation_text(situation)]),
            theme.bold(
                f"{theme.emoji('renaissance_tentative', guild)} Tentative de renaissance : {verdict}"
            ),
            theme.bold(f"{theme.emoji('renaissance_chance', guild)} Dé : {comparison}"),
            theme.bold(
                f"{theme.emoji('alerte', guild)} L’existence, le potentiel et les capacités "
                "de ton personnage sont redéfinis avec le staff."
            ),
        )
        embed = discord.Embed(colour=theme.color(theme.SECTION_RENAISSANCE), title=title)
    else:
        title = f"{theme.fallback('renaissance_rate')} Pas de renaissance"
        description = theme.blocks(
            theme.bold(rules.FAIL_TEXT),
            theme.code_block([situation_text(situation)]),
            theme.bold(
                f"{theme.emoji('renaissance_tentative', guild)} Tentative de renaissance : {verdict}"
            ),
            theme.bold(f"{theme.emoji('renaissance_chance', guild)} Dé : {comparison}"),
        )
        embed = discord.Embed(colour=theme.color(theme.SECTION_NEUTRE), title=title)

    embed.description = description

    image = theme.renaissance_image(success, files)
    if image:
        embed.set_image(url=image)
    embed.set_footer(text=FOOTER)
    return embed


async def send_renaissance(interaction: discord.Interaction, situation=rules.DEFAULT_SITUATION) -> None:
    """Tire le dé, décide de la renaissance et affiche le résultat."""
    # Les emojis du serveur doivent être indexés avant le rendu.
    await emojis_module.ensure_loaded(interaction.guild)

    die = rules.roll()
    success = rules.success(die, situation)

    # L’image est jointe au message : on accuse réception avant l’upload pour
    # rester dans les 3 s de délai d’interaction (erreur 10062).
    if not interaction.response.is_done():
        await interaction.response.defer()

    files: list[discord.File] = []
    embed = build_renaissance_embed(success, die, situation, interaction.guild, files)
    embeds = theme.with_banner(embed, files)
    try:
        await interaction.followup.send(embeds=embeds, files=files)
    except discord.HTTPException as error:
        # Upload refusé : le résultat est déjà tiré, on le renvoie sans image
        # plutôt que de faire échouer la commande.
        logger.warning("Image de Renaissance refusée (%s) : envoi sans image", error)
        for file in files:
            file.close()
        without_image = build_renaissance_embed(success, die, situation, interaction.guild)
        await interaction.followup.send(embeds=theme.with_banner(without_image))
