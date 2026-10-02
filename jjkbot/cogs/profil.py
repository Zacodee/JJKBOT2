"""Commande `/profil` : fiche de personnage, points et réinitialisation.

Note : ce module n’utilise volontairement pas les annotations différées, car
`app_commands.Range` doit être évalué au moment de la déclaration des options.
"""

import logging

import discord
from discord import app_commands
from discord.ext import commands

from jjkbot import permissions, sessions, theme
from jjkbot.content.stats import STAT_DEFINITIONS, get_stat
from jjkbot.storage.profiles import get_profile, save_profile
from jjkbot.views import profil as profil_views

logger = logging.getLogger(__name__)


class ProfilCog(
    commands.GroupCog,
    group_name="profil",
    group_description="Consulter ou créer une fiche de personnage",
):
    """Fiche de personnage : création guidée, statistiques et image."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # --- Consultation ----------------------------------------------------

    @app_commands.command(name="voir", description="Afficher une fiche de personnage")
    @app_commands.describe(joueur="Le joueur dont tu veux voir le profil")
    @app_commands.guild_only()
    async def voir(
        self,
        interaction: discord.Interaction,
        joueur: discord.Member | None = None,
    ) -> None:
        target = joueur or interaction.user
        await profil_views.send_profile(interaction, target)

    # --- Création et modification ----------------------------------------

    @app_commands.command(name="creer", description="Créer ta fiche avec l’aide du bot")
    @app_commands.guild_only()
    async def creer(self, interaction: discord.Interaction) -> None:
        existing = await get_profile(interaction.guild_id, interaction.user.id)
        if existing is not None:
            await interaction.response.send_message(
                embed=theme.notice_embed(
                    theme.SECTION_ALERTE,
                    "alerte",
                    "Tu as déjà un profil. Utilise `/profil modifier` pour le mettre à jour.",
                    interaction.guild,
                ),
                ephemeral=True,
            )
            return

        await profil_views.open_identity_modal(interaction, "create")

    @app_commands.command(name="modifier", description="Modifier ta fiche de personnage")
    @app_commands.guild_only()
    async def modifier(self, interaction: discord.Interaction) -> None:
        existing = await get_profile(interaction.guild_id, interaction.user.id)
        if existing is None:
            await interaction.response.send_message(
                embed=theme.notice_embed(
                    theme.SECTION_ALERTE,
                    "alerte",
                    "Tu n’as pas encore de profil. Utilise `/profil creer` pour le créer.",
                    interaction.guild,
                ),
                ephemeral=True,
            )
            return

        await profil_views.open_identity_modal(interaction, "edit")

    @app_commands.command(name="image", description="Ajouter ou remplacer l’image de ton personnage")
    @app_commands.describe(fichier="Une image PNG, JPG, WEBP ou un GIF de ton personnage")
    @app_commands.guild_only()
    async def image(self, interaction: discord.Interaction, fichier: discord.Attachment) -> None:
        await profil_views.set_profile_image(interaction, fichier)

    # --- Points de statistique -------------------------------------------

    @app_commands.command(
        name="donner-points",
        description="Donner des points de statistique à un joueur (staff uniquement)",
    )
    @app_commands.describe(
        joueur="Le joueur qui recevra les points",
        montant="Le nombre de points à donner",
    )
    @app_commands.guild_only()
    async def donner_points(
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

        profile.stat_points += montant
        profile.touch()
        profile = await save_profile(interaction.guild_id, joueur.id, profile)

        await interaction.response.send_message(
            embed=theme.notice_embed(
                theme.SECTION_SUCCES,
                "succes",
                f"**{montant} point(s)** de statistique ajouté(s) à {joueur.mention}. "
                f"Total disponible : **{profile.stat_points}**.",
                interaction.guild,
            ),
            ephemeral=True,
        )

    @app_commands.command(name="attribuer-stat", description="Dépenser tes points dans une statistique")
    @app_commands.describe(
        statistique="La statistique à améliorer",
        montant="Le nombre de points à investir",
    )
    @app_commands.choices(
        statistique=[
            app_commands.Choice(name=stat.label, value=stat.id) for stat in STAT_DEFINITIONS
        ]
    )
    @app_commands.guild_only()
    async def attribuer_stat(
        self,
        interaction: discord.Interaction,
        statistique: app_commands.Choice[str],
        montant: app_commands.Range[int, 1, 100000],
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

        stat = get_stat(statistique.value)
        if stat is None:
            await interaction.response.send_message(
                embed=theme.notice_embed(
                    theme.SECTION_ERREUR, "erreur", "Cette statistique n’existe pas.", interaction.guild
                ),
                ephemeral=True,
            )
            return

        if profile.stat_points < montant:
            await interaction.response.send_message(
                embed=theme.notice_embed(
                    theme.SECTION_ALERTE,
                    "alerte",
                    f"Tu n’as que **{profile.stat_points} point(s)** disponible(s).",
                    interaction.guild,
                ),
                ephemeral=True,
            )
            return

        profile.stat_points -= montant
        profile.stats[stat.id] = profile.stats.get(stat.id, 0) + montant
        profile.touch()
        profile = await save_profile(interaction.guild_id, interaction.user.id, profile)

        embeds, files = await profil_views.build_profile_message(
            profile,
            interaction.user,
            "stats",
            interaction.guild,
            interaction.guild_id,
        )
        await interaction.response.send_message(
            content=(
                f"{theme.emoji('succes', interaction.guild)} **{montant} point(s)** ajouté(s) en "
                f"**{stat.label}**. Il te reste **{profile.stat_points} point(s)**."
            ),
            embeds=embeds,
            files=files,
            view=profil_views.ProfileView(interaction.guild_id, interaction.user, "stats"),
            ephemeral=True,
        )

    # --- Réinitialisation ------------------------------------------------

    @app_commands.command(
        name="reset",
        description="Réinitialiser les données d’un joueur (staff uniquement)",
    )
    @app_commands.describe(joueur="Le joueur concerné", type="Que veux-tu réinitialiser ?")
    @app_commands.choices(
        type=[
            app_commands.Choice(name="Profil complet (supprime tout)", value="profil"),
            app_commands.Choice(name="Statistiques", value="stats"),
            app_commands.Choice(name="Compétences (et XP)", value="competences"),
        ]
    )
    @app_commands.guild_only()
    async def reset(
        self,
        interaction: discord.Interaction,
        joueur: discord.Member,
        type: app_commands.Choice[str],
    ) -> None:
        if not await permissions.ensure_staff(interaction):
            return

        profile = await get_profile(interaction.guild_id, joueur.id)
        if profile is None:
            await interaction.response.send_message(
                embed=theme.notice_embed(
                    theme.SECTION_ALERTE,
                    "alerte",
                    f"{joueur.display_name} n’a pas encore de profil à réinitialiser.",
                    interaction.guild,
                ),
                ephemeral=True,
            )
            return

        sessions.remember_reset(interaction.guild_id, interaction.user.id, joueur.id, type.value)

        await interaction.response.send_message(
            embed=theme.notice_embed(
                theme.SECTION_ALERTE,
                "alerte",
                f"Tu t’apprêtes à réinitialiser **{sessions.RESET_LABELS[type.value]}** de "
                f"{joueur.mention}. Cette action est **irréversible**. Confirme pour continuer.",
                interaction.guild,
                footer="✦ Confirmation demandée",
            ),
            view=profil_views.ResetView(interaction.user.id, profil_views.apply_reset),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    """Chargement du cog par le bot."""
    await bot.add_cog(ProfilCog(bot))
