"""Contrôle d’accès aux commandes réservées au staff.

Les règles sont celles de l’ancienne version : permission « Administrateur »
ou « Modérer les membres ». Un rôle peut en plus être habilité via
`STAFF_ROLE_ID` dans `.env`.
"""

from __future__ import annotations

import discord

from jjkbot import config, theme

STAFF_DENIED_MESSAGE = (
    "Cette commande est réservée au staff : permission **Administrateur**, "
    "**Modérer les membres** ou rôle staff configuré."
)

ADMIN_DENIED_MESSAGE = "Cette commande est réservée aux **administrateurs** du serveur."


def is_admin(interaction: discord.Interaction) -> bool:
    """Indique si l’auteur dispose de la permission « Administrateur ».

    Plus strict que `is_staff` : réserver cette permission aux seuls
    administrateurs évite qu’un modérateur ne reconfigure un salon du serveur.
    """
    permissions = getattr(interaction, "permissions", None)
    return bool(permissions is not None and permissions.administrator)


async def ensure_admin(interaction: discord.Interaction) -> bool:
    """Répond avec un message d’erreur si l’auteur n’est pas administrateur."""
    if is_admin(interaction):
        return True

    await interaction.response.send_message(
        embed=theme.notice_embed(
            theme.SECTION_ERREUR,
            "erreur",
            ADMIN_DENIED_MESSAGE,
            interaction.guild,
        ),
        ephemeral=True,
    )
    return False


def is_staff(interaction: discord.Interaction) -> bool:
    """Indique si l’auteur d’une interaction appartient au staff."""
    permissions = getattr(interaction, "permissions", None)
    if permissions is not None and (permissions.administrator or permissions.moderate_members):
        return True

    member = interaction.user
    if config.STAFF_ROLE_ID and isinstance(member, discord.Member):
        return any(role.id == config.STAFF_ROLE_ID for role in member.roles)

    return False


async def ensure_staff(interaction: discord.Interaction) -> bool:
    """Répond avec un message d’erreur si l’auteur n’est pas du staff."""
    if is_staff(interaction):
        return True

    await interaction.response.send_message(
        embed=theme.notice_embed(
            theme.SECTION_ERREUR,
            "erreur",
            STAFF_DENIED_MESSAGE,
            interaction.guild,
        ),
        ephemeral=True,
    )
    return False
