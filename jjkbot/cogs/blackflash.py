"""Commandes `/blackflash` : outillage du staff pour tester l’évènement.

Le Black Flash est un tirage : à 5 % de base, enchaîner quatre réussites pour
déclencher le **Record Man du Rayon Noir** relève de l’exploit, et il est donc
impossible de vérifier l’évènement « à la main » en RP. Ces deux commandes,
réservées au staff, existent uniquement pour ça :

- `/blackflash chance` force la chance d’un joueur (`100` garantit chaque
  tentative), ou la lui rend ;
- `/blackflash record` montre son record personnel et peut le retirer, pour
  rejouer l’évènement depuis zéro ;
- `/blackflash buff` affiche, fixe ou retire le **buff de statistiques** du
  Rayon Noir (+10 % à toutes les stats attribuables pendant 3 tours), que le
  bot ne peut pas décompter seul — il ne suit pas les tours de combat.

Elles écrivent dans la **fiche** du joueur (mêmes champs que le jeu normal,
`blackflashChance`, `blackflashRecord` et `blackflashBuffTurns`) : rien de
spécifique aux tests n’est stocké, et `/jjk blackflash-reset` reste la façon
normale de clore un combat.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from jjkbot import permissions, theme
from jjkbot.content import blackflash as blackflash_rules
from jjkbot.storage.profiles import Profile, get_profile, save_profile
from jjkbot.views.blackflash import FOOTER


async def _load_profile(interaction: discord.Interaction, joueur: discord.Member) -> Profile | None:
    """Fiche du joueur, ou None après avoir prévenu le staff qu’elle manque."""
    profile = await get_profile(interaction.guild_id, joueur.id)
    if profile is None:
        await interaction.response.send_message(
            embed=theme.notice_embed(
                theme.SECTION_ALERTE,
                "alerte",
                f"{joueur.display_name} n’a pas encore de fiche : elle doit exister "
                "avant de pouvoir tester le Black Flash sur son personnage.",
                interaction.guild,
            ),
            ephemeral=True,
        )
    return profile


def _record_bonus(profile: Profile) -> int:
    """Bonus permanent du joueur s’il a décroché le titre de recordman."""
    if profile.blackflash_record >= blackflash_rules.RECORD_STREAK:
        return blackflash_rules.record_bonus()
    return 0


async def set_blackflash_chance(
    interaction: discord.Interaction,
    joueur: discord.Member,
    valeur: int | None = None,
    retirer: bool = False,
) -> None:
    """Fixe la chance de Black Flash d’un joueur, ou la lui rend (staff).

    `valeur` s’écrit directement dans la chance courante (`blackflashChance`),
    c’est-à-dire celle du prochain tirage : à `100`, chaque tentative réussit.
    `retirer` la ramène à la base effective de la fiche (traits, exception du
    staff et titre de recordman compris), exactement comme
    `/jjk blackflash-reset`.
    """
    if not await permissions.ensure_staff(interaction):
        return

    profile = await _load_profile(interaction, joueur)
    if profile is None:
        return

    base = blackflash_rules.effective_base(
        profile.traits,
        profile.blackflash_base,
        profile.blackflash_bonus,
        _record_bonus(profile),
    )
    before = blackflash_rules.normalize(profile.blackflash_chance)

    if retirer:
        profile.blackflash_chance = base
        action = "rendue à sa base effective"
    elif valeur is None:
        await interaction.response.send_message(
            embed=theme.notice_embed(
                theme.SECTION_ALERTE,
                "alerte",
                "Précise une **valeur** (0-100), ou coche `retirer` pour rendre au "
                "joueur sa chance normale.",
                interaction.guild,
                footer=FOOTER,
            ),
            ephemeral=True,
        )
        return
    else:
        profile.blackflash_chance = blackflash_rules.normalize(valeur)
        action = "fixée pour le test"

    profile.touch()
    await save_profile(interaction.guild_id, joueur.id, profile)

    after = profile.blackflash_chance
    note = (
        f"À **{blackflash_rules.MAX_CHANCE} %**, chaque `/jjk blackflash` réussit : "
        f"enchaîne-en {blackflash_rules.RECORD_STREAK} pour déclencher le titre de "
        "recordman. `retirer:Vrai` (ou `/jjk blackflash-reset`) rend la chance "
        "normale."
        if after >= blackflash_rules.MAX_CHANCE
        else "La chance retombe d’elle-même sur la base effective à la fin de la "
        "série (`/jjk blackflash-reset` la rend tout de suite)."
    )

    await interaction.response.send_message(
        embed=theme.notice_embed(
            theme.SECTION_BLACKFLASH,
            "blackflash",
            f"Chance de Black Flash de {joueur.mention} {action} : "
            f"`{before}%` → `{after}%`.\n{note}",
            interaction.guild,
            footer=FOOTER,
        ),
        ephemeral=True,
    )


async def set_blackflash_record(
    interaction: discord.Interaction,
    joueur: discord.Member,
    retirer: bool = False,
) -> None:
    """Affiche le record du joueur, ou le remet à zéro pour rejouer l’évènement."""
    if not await permissions.ensure_staff(interaction):
        return

    profile = await _load_profile(interaction, joueur)
    if profile is None:
        return

    if retirer:
        before = profile.blackflash_record
        profile.blackflash_record = 0
        profile.blackflash_streak = 0
        profile.touch()
        await save_profile(interaction.guild_id, joueur.id, profile)
        await interaction.response.send_message(
            embed=theme.notice_embed(
                theme.SECTION_ALERTE,
                "alerte",
                f"Titre de **recordman du Rayon Noir** retiré à {joueur.mention} "
                f"(record `{before}` → `0`), série du combat remise à zéro. Son bonus "
                "de chance disparaît avec le titre : l’évènement peut être rejoué "
                "depuis le début.",
                interaction.guild,
                footer=FOOTER,
            ),
            ephemeral=True,
        )
        return

    title = (
        "**recordman du Rayon Noir**"
        if profile.blackflash_record >= blackflash_rules.RECORD_STREAK
        else "pas encore recordman"
    )
    await interaction.response.send_message(
        embed=theme.notice_embed(
            theme.SECTION_BLACKFLASH,
            "blackflash",
            f"{joueur.mention} est {title} : record personnel "
            f"`{profile.blackflash_record}` Black Flash consécutifs, série en cours "
            f"`{profile.blackflash_streak}`. Le titre se décroche à "
            f"`{blackflash_rules.RECORD_STREAK}` et donne "
            f"**+{blackflash_rules.RECORD_BONUS} %** de chance à vie "
            f"(+{blackflash_rules.MORTAL_RECORD_BONUS} % en Combat Mortel).",
            interaction.guild,
            footer=FOOTER,
        ),
        ephemeral=True,
    )


async def set_blackflash_buff(
    interaction: discord.Interaction,
    joueur: discord.Member,
    tours: int | None = None,
    retirer: bool = False,
) -> None:
    """Affiche, fixe ou retire le buff de Noirceur d’un joueur (staff).

    Le bot ne suit pas les tours de combat : c’est donc au staff de faire
    avancer le compteur après chaque tour joué. `tours` fixe le nombre de tours
    restants, `retirer` l’éteint, et sans aucun des deux la commande se contente
    de montrer l’état. Le buff vit sur la fiche (`blackflashBuffTurns`) et
    s’affiche dans `/profil voir`.
    """
    if not await permissions.ensure_staff(interaction):
        return

    profile = await _load_profile(interaction, joueur)
    if profile is None:
        return

    if retirer:
        before = profile.blackflash_buff_turns
        profile.blackflash_buff_turns = 0
        profile.touch()
        await save_profile(interaction.guild_id, joueur.id, profile)
        await interaction.response.send_message(
            embed=theme.notice_embed(
                theme.SECTION_ALERTE,
                "blackflash",
                f"Buff de Noirceur retiré à {joueur.mention} : `{before}` → `0` "
                "tour(s). Ses statistiques affichées reprennent leurs valeurs "
                "normales.",
                interaction.guild,
                footer=FOOTER,
            ),
            ephemeral=True,
        )
        return

    if tours is None:
        state = (
            f"**{profile.blackflash_buff_turns} tour(s)** restant(s)"
            if profile.blackflash_buff_turns > 0
            else "**aucun buff actif**"
        )
        await interaction.response.send_message(
            embed=theme.notice_embed(
                theme.SECTION_BLACKFLASH,
                "blackflash",
                f"Buff de Noirceur de {joueur.mention} : {state}. "
                f"Rappel : +{blackflash_rules.BUFF_STAT_PERCENT} % à toutes les stats "
                f"(Réserve d’EO exceptée) pendant {blackflash_rules.BUFF_TURNS} tours "
                "après un Black Flash réussi.",
                interaction.guild,
                footer=FOOTER,
            ),
            ephemeral=True,
        )
        return

    before = profile.blackflash_buff_turns
    profile.blackflash_buff_turns = max(0, min(blackflash_rules.MAX_BUFF_TURNS, tours))
    profile.touch()
    await save_profile(interaction.guild_id, joueur.id, profile)
    await interaction.response.send_message(
        embed=theme.notice_embed(
            theme.SECTION_BLACKFLASH,
            "blackflash",
            f"Buff de Noirceur de {joueur.mention} : `{before}` → "
            f"`{profile.blackflash_buff_turns}` tour(s). À "
            f"`0`, le buff est éteint ; il s’affiche dans `/profil voir`.",
            interaction.guild,
            footer=FOOTER,
        ),
        ephemeral=True,
    )


class BlackflashCog(
    commands.GroupCog,
    group_name="blackflash",
    group_description="Outils du staff pour tester le Black Flash et son record",
):
    """Test du Black Flash et de l’évènement Record Man (staff)."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="chance",
        description="Forcer la chance de Black Flash d’un joueur, ou la lui rendre (staff)",
    )
    @app_commands.describe(
        joueur="Le joueur dont on veut forcer les chances",
        valeur="Chance du prochain tirage, en % (0-100). 100 garantit chaque réussite.",
        retirer="Rendre au joueur la chance normale de sa fiche",
    )
    # `default_permissions` masque la commande à tout le monde sauf au staff ;
    # `ensure_staff` protège l’exécution, même depuis un client qui l’aurait en cache.
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.guild_only()
    async def chance(
        self,
        interaction: discord.Interaction,
        joueur: discord.Member,
        valeur: app_commands.Range[int, 0, blackflash_rules.MAX_CHANCE] | None = None,
        retirer: bool = False,
    ) -> None:
        await set_blackflash_chance(interaction, joueur, valeur, retirer)

    @app_commands.command(
        name="buff",
        description="Afficher, fixer ou retirer le buff de stats du Black Flash (staff)",
    )
    @app_commands.describe(
        joueur="Le joueur concerné",
        tours="Tours restants du buff (0 pour l’éteindre). Vide : affiche l’état.",
        retirer="Retirer le buff d’un coup (équivaut à tours:0)",
    )
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.guild_only()
    async def buff(
        self,
        interaction: discord.Interaction,
        joueur: discord.Member,
        tours: app_commands.Range[int, 0, blackflash_rules.MAX_BUFF_TURNS] | None = None,
        retirer: bool = False,
    ) -> None:
        await set_blackflash_buff(interaction, joueur, tours, retirer)

    @app_commands.command(
        name="record",
        description="Afficher ou retirer le titre de recordman du Rayon Noir (staff)",
    )
    @app_commands.describe(
        joueur="Le joueur dont on veut voir ou retirer le titre",
        retirer="Retirer le titre et son bonus, pour rejouer l’évènement depuis zéro",
    )
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.guild_only()
    async def record(
        self,
        interaction: discord.Interaction,
        joueur: discord.Member,
        retirer: bool = False,
    ) -> None:
        await set_blackflash_record(interaction, joueur, retirer)


async def setup(bot: commands.Bot) -> None:
    """Chargement du cog par le bot."""
    await bot.add_cog(BlackflashCog(bot))
