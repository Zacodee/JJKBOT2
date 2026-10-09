"""Rendu et envoi de `/train` : l’entraînement hebdomadaire du personnage.

Comme les autres évènements (Black Flash, Renaissance), l’embed écrit son texte
en **gras** et joint son image localement (`attachment://`), avec l’URL de repli
seulement si le fichier est absent (voir `theme.train_image`).
"""

from __future__ import annotations

import logging

import discord

from jjkbot import emojis as emojis_module, permissions, theme
from jjkbot.content import train as rules
from jjkbot.storage.profiles import get_profile, now_iso, save_profile
from jjkbot.views.base import notify_error

logger = logging.getLogger(__name__)

FOOTER = "Jujutsu Kaisen RP • Entraînement"

NO_PROFILE_MESSAGE = (
    "Tu n’as pas encore de fiche : crée-la avec `/profil creer` avant de t’entraîner."
)


def _relative(moment) -> str:
    """Horodatage relatif Discord (`<t:…:R>`), ou chaîne vide."""
    if moment is None:
        return ""
    return f"<t:{int(moment.timestamp())}:R>"


def build_train_embed(
    profile,
    guild=None,
    files: list[discord.File] | None = None,
) -> discord.Embed:
    """Embed de l’entraînement réussi : gain d’XP, total et prochain rendez-vous."""
    chunks = [
        theme.title("train", "Entraînement", guild),
        theme.bold(
            "Tu répètes les exercices jusqu’à ce que ton corps et ton énergie "
            "occulte finissent par obéir. La sueur et la répétition forgent les "
            "sorciers : ce travail finira par payer."
        ),
        theme.code_block([f"[ +{rules.TRAIN_XP} XP ]"]),
        theme.bold(f"{theme.emoji('xp', guild)} XP total : {profile.experience}"),
    ]
    next_at = rules.next_available(profile.train_last_at)
    if next_at is not None:
        chunks.append(
            theme.bold(
                f"{theme.emoji('attente', guild)} Prochain entraînement {_relative(next_at)}"
            )
        )

    embed = discord.Embed(
        colour=theme.color(theme.SECTION_COMPETENCES),
        description=theme.blocks(*chunks),
    )
    image = theme.train_image(files)
    if image:
        embed.set_image(url=image)
    embed.set_footer(text=FOOTER)
    return embed


async def send_train(interaction: discord.Interaction) -> None:
    """Accorde l’entraînement hebdomadaire : +500 XP, une fois par semaine."""
    await emojis_module.ensure_loaded(interaction.guild)

    profile = await get_profile(interaction.guild_id, interaction.user.id)
    if profile is None:
        await notify_error(interaction, NO_PROFILE_MESSAGE)
        return

    if not rules.is_available(profile.train_last_at):
        ready = rules.next_available(profile.train_last_at)
        delay = rules.format_delay(rules.remaining(profile.train_last_at))
        await interaction.response.send_message(
            embed=theme.notice_embed(
                theme.SECTION_ALERTE,
                "attente",
                f"Tu t’es déjà entraîné cette semaine. Reviens {_relative(ready)} "
                f"(dans **{delay}**). L’entraînement se fait une fois par semaine, "
                f"et rapporte **{rules.TRAIN_XP} XP**.",
                interaction.guild,
                footer=FOOTER,
            ),
            ephemeral=True,
        )
        return

    profile.experience += rules.TRAIN_XP
    profile.train_last_at = now_iso()
    profile.touch()
    await save_profile(interaction.guild_id, interaction.user.id, profile)

    # L’image est jointe au message : on accuse réception avant l’upload pour
    # rester dans les 3 s de délai d’interaction (erreur 10062).
    if not interaction.response.is_done():
        await interaction.response.defer()

    files: list[discord.File] = []
    embeds = theme.with_banner(build_train_embed(profile, interaction.guild, files), files)
    try:
        await interaction.followup.send(embeds=embeds, files=files)
    except discord.HTTPException as error:
        # Upload refusé : l’XP est déjà créditée, on renvoie le résultat sans image.
        logger.warning("Image de /train refusée (%s) : envoi sans image", error)
        for file in files:
            file.close()
        await interaction.followup.send(
            embeds=theme.with_banner(build_train_embed(profile, interaction.guild))
        )


async def send_train_reset(
    interaction: discord.Interaction,
    joueur: discord.Member,
) -> None:
    """Rend son entraînement à un joueur (staff) en effaçant la date du dernier."""
    if not await permissions.ensure_staff(interaction):
        return

    profile = await get_profile(interaction.guild_id, joueur.id)
    if profile is None:
        await interaction.response.send_message(
            embed=theme.notice_embed(
                theme.SECTION_ALERTE,
                "alerte",
                f"{joueur.display_name} n’a pas encore de fiche : il n’y a aucune "
                "date d’entraînement à réinitialiser.",
                interaction.guild,
                footer=FOOTER,
            ),
            ephemeral=True,
        )
        return

    if profile.train_last_at is None:
        await interaction.response.send_message(
            embed=theme.notice_embed(
                theme.SECTION_NEUTRE,
                "train",
                f"{joueur.mention} n’a jamais utilisé `/train` : sa séance est déjà "
                "disponible.",
                interaction.guild,
                footer=FOOTER,
            ),
            ephemeral=True,
        )
        return

    profile.train_last_at = None
    profile.touch()
    await save_profile(interaction.guild_id, joueur.id, profile)

    await interaction.response.send_message(
        embed=theme.notice_embed(
            theme.SECTION_SUCCES,
            "succes",
            f"Entraînement de {joueur.mention} réinitialisé : il peut relancer "
            f"`/train` immédiatement (**+{rules.TRAIN_XP} XP**).",
            interaction.guild,
            footer=FOOTER,
        ),
        ephemeral=True,
    )
