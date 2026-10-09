"""Commandes `/train` : entraînement hebdomadaire et sa remise à zéro (staff).

`/train` offre **500 XP** au joueur, **une fois par semaine** (7 jours glissants
depuis son dernier entraînement — voir `content.train`). `/train-reset` rend la
séance à un joueur précis : utile pour un rattrapage, un test ou une date
erronée.

Note : ce module n’utilise volontairement pas les annotations différées, car
`app_commands.Range` doit être évalué au moment de la déclaration des options.
"""

import logging

import discord
from discord import app_commands
from discord.ext import commands

from jjkbot.content.train import TRAIN_XP
from jjkbot.views import train as train_views

logger = logging.getLogger(__name__)


class TrainCog(commands.Cog):
    """Entraînement hebdomadaire : `/train` et `/train-reset` (staff)."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="train",
        description=f"S’entraîner et gagner {TRAIN_XP} XP, une fois par semaine",
    )
    @app_commands.guild_only()
    async def train(self, interaction: discord.Interaction) -> None:
        await train_views.send_train(interaction)

    @app_commands.command(
        name="train-reset",
        description="Rendre son entraînement à un joueur (staff)",
    )
    @app_commands.describe(joueur="Le joueur dont on remet l’entraînement à zéro")
    # Masquée à tout le monde sauf au staff ; `ensure_staff` protège l’exécution.
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.guild_only()
    async def train_reset(
        self,
        interaction: discord.Interaction,
        joueur: discord.Member,
    ) -> None:
        await train_views.send_train_reset(interaction, joueur)


async def setup(bot: commands.Bot) -> None:
    """Chargement du cog par le bot."""
    await bot.add_cog(TrainCog(bot))
