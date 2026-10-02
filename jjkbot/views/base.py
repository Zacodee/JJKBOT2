"""Base commune des vues et modales : gestion d’erreur homogène."""

from __future__ import annotations

import logging

import discord

from jjkbot import theme

logger = logging.getLogger(__name__)

GENERIC_ERROR_MESSAGE = (
    "Une erreur est survenue pendant cette action. Vérifie les logs du bot pour plus de détails."
)


async def notify_error(interaction: discord.Interaction, message: str = GENERIC_ERROR_MESSAGE) -> None:
    """Prévient l’utilisateur sans jamais lever d’exception."""
    embed = theme.notice_embed(theme.SECTION_ERREUR, "erreur", message, interaction.guild)
    try:
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)
    except discord.HTTPException:  # pragma: no cover - dépend de l’API
        logger.debug("Impossible d’envoyer le message d’erreur à l’utilisateur.")


class BaseView(discord.ui.View):
    """Vue qui journalise les erreurs et prévient l’utilisateur."""

    async def on_error(self, interaction: discord.Interaction, error: Exception, item) -> None:
        logger.error(
            "Erreur dans %s (%s) : %s",
            type(self).__name__,
            type(item).__name__ if item is not None else "vue",
            error,
            exc_info=error,
        )
        await notify_error(interaction)


class BaseModal(discord.ui.Modal):
    """Modale qui journalise les erreurs et prévient l’utilisateur."""

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        logger.error("Erreur dans %s : %s", type(self).__name__, error, exc_info=error)
        await notify_error(interaction)
