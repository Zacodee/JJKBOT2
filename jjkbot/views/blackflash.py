"""Rendu et envoi du résultat d’une tentative de Black Flash.

Rendu « classique » (modèle choisi) : titre d’embed, texte narratif, buffs en
bloc de code, état en lignes à emojis du catalogue, puis l’image du résultat.

Chaque emoji vient du catalogue (`config/emojis.json`) : les emojis custom du
serveur sont utilisés en priorité, le repli unicode si le bot ne les trouve pas.
Seul l’emoji du **titre** est toujours le repli, car le champ `title` d’un embed
est un champ brut : selon les versions du client Discord, un emoji custom y
s’affiche parfois en texte (`<:nom:id>`). Le repli reste modifiable dans
`config/emojis.json` (champ `fallback`), et `/jjk emojis` liste les emojis à
créer pour toutes les lignes de l’embed.
"""

from __future__ import annotations

import logging

import discord

from jjkbot import emojis as emojis_module, theme
from jjkbot.content import blackflash as rules
from jjkbot.storage.profiles import get_profile, save_profile
from jjkbot.views.base import notify_error

logger = logging.getLogger(__name__)

FOOTER = "Jujutsu Kaisen RP • Black Flash"

NO_PROFILE_MESSAGE = (
    "Tu n’as pas encore de fiche : crée-la avec `/profil creer` avant de tenter un Black Flash."
)
NO_PROFILE_RESET_MESSAGE = (
    "Tu n’as pas encore de fiche : crée-la avec `/profil creer` "
    "avant de réinitialiser tes chances."
)


def build_blackflash_embed(
    success: bool,
    chance_before: int,
    chance_after: int,
    guild=None,
    files: list[discord.File] | None = None,
) -> discord.Embed:
    """Embed de résultat, avec l’image jointe (`attachment://`) si possible.

    `chance_before` / `chance_after` sont les chances en pourcentage avant et
    après le tirage : l’embed montre donc ce que la tentative vient de changer.
    """
    # Titre : repli unicode, car le champ `title` ne rend pas les emojis custom.
    if success:
        title = f"{theme.fallback('blackflash')} Black Flash"
        description = theme.blocks(
            rules.SUCCESS_TEXT,
            theme.code_block([f"[ {rules.BUFFS_TEXT} ]"]),
            f"{theme.emoji('blackflash_tentative', guild)} Tentative de black flash : **Réussit**",
            f"{theme.emoji('blackflash_chance', guild)} Chance actuelle : "
            f"`{chance_before}%` → `{chance_after}%`",
            f"{theme.emoji('reserve_eo', guild)} Énergie occulte : **+400**  •  "
            f"{theme.emoji('sortie_eo', guild)} Sortie d’EO : **+1000**",
        )
        embed = discord.Embed(colour=theme.color(theme.SECTION_BLACKFLASH), title=title)
    else:
        title = f"{theme.fallback('blackflash_rate')} Raté"
        description = theme.blocks(
            rules.FAIL_TEXT,
            theme.code_block([f"[ {rules.NO_BUFF_TEXT} ]"]),
            f"{theme.emoji('blackflash_tentative', guild)} Tentative de black flash : **Échoué**",
            f"{theme.emoji('blackflash_chance', guild)} Chance actuelle : "
            f"`{chance_before}%` → `{chance_after}%`",
        )
        embed = discord.Embed(colour=theme.color(theme.SECTION_NEUTRE), title=title)

    embed.description = description

    image = theme.blackflash_image(success, files)
    if image:
        embed.set_image(url=image)
    embed.set_footer(text=FOOTER)
    return embed


async def send_blackflash(interaction: discord.Interaction) -> None:
    """Tire une tentative, met à jour les chances du joueur et affiche le résultat."""
    profile = await get_profile(interaction.guild_id, interaction.user.id)
    if profile is None:
        await notify_error(interaction, NO_PROFILE_MESSAGE)
        return

    # Les emojis du serveur doivent être indexés avant le rendu (réparation
    # REST si le cache passerelle est vide).
    await emojis_module.ensure_loaded(interaction.guild)

    # Base effective : traits de la fiche (et exception du staff) compris. Elle
    # sert à la fois de plancher au tirage et de valeur de retour en cas d’échec,
    # pour qu’un raté n’efface jamais le bonus d’un trait.
    base = rules.effective_base(
        profile.traits, profile.blackflash_base, profile.blackflash_bonus
    )
    chance_before = max(rules.normalize(profile.blackflash_chance), base)
    success = rules.roll(chance_before)
    chance_after = rules.next_chance(chance_before, success, base)

    profile.blackflash_chance = chance_after
    await save_profile(interaction.guild_id, interaction.user.id, profile)

    # L’image est jointe au message : on accuse réception avant l’upload
    # pour rester dans les 3 s de délai d’interaction (erreur 10062).
    if not interaction.response.is_done():
        await interaction.response.defer()

    files: list[discord.File] = []
    embed = build_blackflash_embed(success, chance_before, chance_after, interaction.guild, files)
    embeds = theme.with_banner(embed, files)
    try:
        await interaction.followup.send(embeds=embeds, files=files)
    except discord.HTTPException as error:
        # Upload refusé (limite de poids d’une pièce jointe, réseau) : la
        # tentative est déjà comptée et sauvegardée, on renvoie donc le même
        # résultat sans image plutôt que de faire échouer la commande.
        logger.warning("Image de Black Flash refusée (%s) : envoi sans image", error)
        for file in files:
            file.close()
        without_image = build_blackflash_embed(
            success, chance_before, chance_after, interaction.guild
        )
        await interaction.followup.send(embeds=theme.with_banner(without_image))


async def send_blackflash_reset(interaction: discord.Interaction) -> None:
    """Remet les chances du joueur à la base, à la fin d’un combat."""
    profile = await get_profile(interaction.guild_id, interaction.user.id)
    if profile is None:
        await notify_error(interaction, NO_PROFILE_RESET_MESSAGE)
        return

    base = rules.effective_base(
        profile.traits, profile.blackflash_base, profile.blackflash_bonus
    )
    chance_before = rules.normalize(profile.blackflash_chance)
    profile.blackflash_chance = base
    await save_profile(interaction.guild_id, interaction.user.id, profile)

    embed = theme.notice_embed(
        theme.SECTION_BLACKFLASH,
        "blackflash",
        f"Tes chances de Black Flash ont été réinitialisées : "
        f"`{chance_before}%` → `{base}%`.",
        interaction.guild,
        footer=FOOTER,
    )
    await interaction.response.send_message(embed=embed)
