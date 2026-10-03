"""Commande `/competences` : arbre de compétences, achats et XP."""

import logging

import discord
from discord import app_commands
from discord.ext import commands

from jjkbot import emojis as emojis_module, permissions, theme
from jjkbot.storage.profiles import get_profile, save_profile
from jjkbot.views import competences as competences_views

logger = logging.getLogger(__name__)


class CompetencesCog(
    commands.GroupCog,
    group_name="competences",
    group_description="Consulter et faire progresser l’arbre de compétences",
):
    """Arbre de compétences : consultation par catégorie, panier et XP."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="voir", description="Afficher les compétences par catégorie")
    @app_commands.describe(joueur="Le joueur dont tu veux voir les compétences")
    @app_commands.guild_only()
    async def voir(
        self,
        interaction: discord.Interaction,
        joueur: discord.Member | None = None,
    ) -> None:
        target = joueur or interaction.user
        profile = await get_profile(interaction.guild_id, target.id)
        if profile is None:
            await interaction.response.send_message(
                embed=theme.notice_embed(
                    theme.SECTION_ALERTE,
                    "alerte",
                    "Tu n’as pas encore de profil. Lance `/profil creer`."
                    if target.id == interaction.user.id
                    else f"{target.display_name} n’a pas encore créé de profil.",
                    interaction.guild,
                ),
                ephemeral=True,
            )
            return

        embed = competences_views.build_overview_embed(profile, target, interaction.guild)
        await emojis_module.ensure_loaded(interaction.guild)
        await interaction.response.send_message(
            embeds=[embed],
            view=competences_views.OverviewView(interaction.guild_id, target),
        )

    @app_commands.command(name="acheter", description="Ouvrir le panier de compétences")
    @app_commands.guild_only()
    async def acheter(self, interaction: discord.Interaction) -> None:
        profile = await get_profile(interaction.guild_id, interaction.user.id)
        if profile is None:
            await interaction.response.send_message(
                embed=theme.notice_embed(
                    theme.SECTION_ALERTE,
                    "alerte",
                    "Tu n’as pas encore de profil. Lance `/profil creer`.",
                    interaction.guild,
                ),
                ephemeral=True,
            )
            return

        view = competences_views.ShopView(interaction.guild_id, interaction.user.id, profile)
        await emojis_module.ensure_loaded(interaction.guild)
        await interaction.response.send_message(
            embeds=[
                competences_views.build_shop_root_embed(profile, interaction.guild)
            ],
            view=view,
            ephemeral=True,
        )

    @app_commands.command(name="xp", description="Donner de l’XP à un joueur (staff uniquement)")
    @app_commands.describe(joueur="Le joueur qui recevra l’XP", montant="Le nombre d’XP à donner")
    @app_commands.guild_only()
    async def xp(
        self,
        interaction: discord.Interaction,
        joueur: discord.Member,
        montant: app_commands.Range[int, 1, 100000],
    ) -> None:
        if not await permissions.ensure_staff(interaction):
            return

        profile = await get_profile(interaction.guild_id, joueur.id)
        if profile is None:
            await interaction.response.send_message(
                embed=theme.notice_embed(
                    theme.SECTION_ALERTE,
                    "alerte",
                    f"{joueur.display_name} doit d’abord créer son profil avec `/profil creer`.",
                    interaction.guild,
                ),
                ephemeral=True,
            )
            return

        profile.experience += montant
        profile.touch()
        profile = await save_profile(interaction.guild_id, joueur.id, profile)

        await interaction.response.send_message(
            embed=theme.notice_embed(
                theme.SECTION_SUCCES,
                "succes",
                f"**{montant} XP** ajoutée(s) à {joueur.mention}. "
                f"Total : **{profile.experience} XP**.",
                interaction.guild,
            ),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    """Chargement du cog par le bot."""
    await bot.add_cog(CompetencesCog(bot))
