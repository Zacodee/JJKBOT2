"""Commande `/xp` : conversion en statistiques et demandes d’XP.

Le salon qui reçoit les demandes se configure côté staff, avec `/jjk salon`.

Note : ce module n’utilise volontairement pas les annotations différées, car
`app_commands.Range` doit être évalué au moment de la déclaration des options.
"""

import logging

import discord
from discord import app_commands
from discord.ext import commands

from jjkbot import theme
from jjkbot.content import xp as xp_rules
from jjkbot.storage.profiles import get_profile, save_profile
from jjkbot.views import xp_requests as xp_views

logger = logging.getLogger(__name__)


class XpCog(
    commands.GroupCog,
    group_name="xp",
    group_description="Expérience : conversion en statistiques et demandes au staff",
):
    """XP : conversion en points de statistique et demandes d’XP au staff."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # --- Conversion XP → statistiques ------------------------------------

    @app_commands.command(
        name="convertir",
        description="Échanger de l’XP contre des points de statistique (1 XP = 1 point)",
    )
    @app_commands.describe(montant="Nombre d’XP à convertir en points de statistique")
    @app_commands.guild_only()
    async def convertir(
        self,
        interaction: discord.Interaction,
        montant: app_commands.Range[int, xp_rules.MIN_AMOUNT, xp_rules.MAX_AMOUNT],
    ) -> None:
        profile = await get_profile(interaction.guild_id, interaction.user.id)
        if profile is None:
            await interaction.response.send_message(
                embed=theme.notice_embed(
                    theme.SECTION_ALERTE,
                    "alerte",
                    "Crée d’abord ton profil avec `/profil creer`.",
                    interaction.guild,
                ),
                ephemeral=True,
            )
            return

        if profile.experience < montant:
            await interaction.response.send_message(
                embed=theme.notice_embed(
                    theme.SECTION_ALERTE,
                    "alerte",
                    f"Tu n’as que **{profile.experience} XP** : impossible d’en convertir {montant}.",
                    interaction.guild,
                ),
                ephemeral=True,
            )
            return

        profile.experience -= montant
        profile.stat_points += montant
        profile.touch()
        profile = await save_profile(interaction.guild_id, interaction.user.id, profile)

        await interaction.response.send_message(
            embed=theme.notice_embed(
                theme.SECTION_SUCCES,
                "succes",
                f"**{montant} XP** convertie(s) en **{montant} point(s) de statistique**. "
                f"Il te reste **{profile.experience} XP** et **{profile.stat_points} point(s)** "
                "à répartir avec `/profil attribuer-stat`.",
                interaction.guild,
            ),
            ephemeral=True,
        )

    # --- Demande d’XP -----------------------------------------------------

    @app_commands.command(
        name="demande",
        description="Demander de l’XP au staff pour une scène de RP (formulaire)",
    )
    @app_commands.guild_only()
    async def demande(self, interaction: discord.Interaction) -> None:
        profile = await get_profile(interaction.guild_id, interaction.user.id)
        if profile is None:
            await interaction.response.send_message(
                embed=theme.notice_embed(
                    theme.SECTION_ALERTE,
                    "alerte",
                    "Crée d’abord ton profil avec `/profil creer`.",
                    interaction.guild,
                ),
                ephemeral=True,
            )
            return

        if interaction.guild is None:  # pragma: no cover - la commande est guild_only
            return

        # On ouvre d’abord le menu du type d’interaction : Discord n’accepte que
        # des champs texte dans une modale, donc le menu ne peut pas y figurer.
        await interaction.response.send_message(
            embed=theme.notice_embed(
                theme.SECTION_DEMANDES,
                "demande_xp",
                "Choisis le **type d’interaction** de la scène : le formulaire s’ouvrira juste après.",
                interaction.guild,
            ),
            view=xp_views.XPInteractionTypeView(interaction.guild),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    """Chargement du cog par le bot."""
    await bot.add_cog(XpCog(bot))
