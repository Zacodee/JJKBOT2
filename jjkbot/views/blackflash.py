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
RECORD_FOOTER = "Jujutsu Kaisen RP • Record Man du Rayon Noir"

NO_PROFILE_MESSAGE = (
    "Tu n’as pas encore de fiche : crée-la avec `/profil creer` avant de tenter un Black Flash."
)
NO_PROFILE_RESET_MESSAGE = (
    "Tu n’as pas encore de fiche : crée-la avec `/profil creer` "
    "avant de réinitialiser tes chances."
)

# Le Combat Mortel double le buff du recordman : il ne se déclenche donc que
# pour un joueur qui a déjà décroché le titre (voir `send_blackflash`).
MORTAL_DENIED_MESSAGE = (
    "Le **Combat Mortel** est réservé au **recordman du Rayon Noir**, dont il "
    f"porte le buff à +{rules.MORTAL_RECORD_BONUS} au lieu de "
    f"+{rules.RECORD_BONUS}. Réussis {rules.RECORD_STREAK} Black Flash "
    "consécutifs dans un même combat pour décrocher le titre."
)

# Textes de l’embed de titre (adaptés de la description de l’évènement).
RECORD_INTRO = (
    "Quatre Rayons Noirs d’affilée. Pour la plupart des exorcistes, cela "
    "relèverait de l’exploit ; pour toi, c’est devenu un record. Peut-être "
    "était-ce simplement de la chance… ou peut-être qu’à cet instant, tu avais "
    "compris quelque chose que les autres ne pouvaient qu’effleurer."
)
RECORD_LESSON = (
    "Après avoir atteint une maîtrise aussi exceptionnelle du phénomène, ton "
    "personnage comprend instinctivement les conditions nécessaires à la "
    "réalisation d’un Rayon Noir, même s’il n’en avait pas pleinement "
    "conscience auparavant."
)
RECORD_PERMANENCE = (
    "Le titre et son buff sont acquis définitivement : ils ne se perdent ni "
    "sur un raté, ni à la fin d’un combat, et aucun autre joueur ne peut te les "
    "reprendre."
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
        # Embed d’évènement : le texte est écrit en **gras** (voir `theme.bold`).
        description = theme.blocks(
            theme.bold(rules.SUCCESS_TEXT),
            theme.code_block([f"[ {rules.BUFFS_TEXT} ]"]),
            theme.bold(
                f"{theme.emoji('blackflash_tentative', guild)} Tentative de black flash : Réussit"
            ),
            theme.bold(
                f"{theme.emoji('blackflash_chance', guild)} Chance actuelle : "
                f"`{chance_before}%` → `{chance_after}%`"
            ),
            theme.bold(
                f"{theme.emoji('force', guild)} Coup porté : "
                f"+{rules.STRIKE_FORCE_PERCENT}% de Force"
            ),
            theme.bold(
                f"{theme.emoji('reserve_eo', guild)} Énergie occulte : "
                f"+{rules.EO_RESTORE} EO"
            ),
            theme.bold(
                f"{theme.emoji('stats', guild)} Buff : +{rules.BUFF_STAT_PERCENT}% à toutes "
                f"les stats (Réserve d’EO exceptée) pendant {rules.BUFF_TURNS} tours"
            ),
            theme.bold(
                f"{theme.emoji('profil', guild)} Visible sur `/profil voir` tant qu’il "
                "reste des tours"
            ),
        )
        embed = discord.Embed(colour=theme.color(theme.SECTION_BLACKFLASH), title=title)
    else:
        title = f"{theme.fallback('blackflash_rate')} Raté"
        description = theme.blocks(
            theme.bold(rules.FAIL_TEXT),
            theme.code_block([f"[ {rules.NO_BUFF_TEXT} ]"]),
            theme.bold(
                f"{theme.emoji('blackflash_tentative', guild)} Tentative de black flash : Échoué"
            ),
            theme.bold(
                f"{theme.emoji('blackflash_chance', guild)} Chance actuelle : "
                f"`{chance_before}%` → `{chance_after}%`"
            ),
        )
        embed = discord.Embed(colour=theme.color(theme.SECTION_NEUTRE), title=title)

    embed.description = description

    image = theme.blackflash_image(success, files)
    if image:
        embed.set_image(url=image)
    embed.set_footer(text=FOOTER)
    return embed


def build_blackflash_record_embed(
    player_id: int,
    player_name: str,
    streak: int,
    guild=None,
    files: list[discord.File] | None = None,
) -> discord.Embed:
    """Embed de l’évènement « Record Man du Rayon Noir ».

    Le titre est **personnel** : chaque joueur qui réussit sa série le décroche
    pour lui-même, définitivement, sans le prendre à personne. L’embed ne
    s’envoie donc qu’une fois, à la première série de ``RECORD_STREAK`` succès.
    """
    chunks = [
        theme.title("blackflash", "Record Man du Rayon Noir", guild),
        theme.bold(RECORD_INTRO),
        theme.mention_entry("blackflash", "Nouveau recordman", player_id, guild, player_name),
        theme.entry(
            "blackflash_tentative", "Record personnel", f"{streak} Black Flash consécutifs"
        ),
        theme.divider(),
        theme.heading("Effets du titre", 3, guild, "succes"),
        theme.bold(RECORD_LESSON),
        theme.entry(
            "blackflash_chance",
            "Buff permanent",
            f"+{rules.RECORD_BONUS} % de chance de réussir un Rayon Noir",
        ),
        theme.entry(
            "succes",
            "En Combat Mortel",
            f"+{rules.MORTAL_RECORD_BONUS} % au lieu de +{rules.RECORD_BONUS} %",
        ),
        theme.bold(RECORD_PERMANENCE),
    ]

    embed = discord.Embed(
        colour=theme.color(theme.SECTION_BLACKFLASH),
        description=theme.blocks(*chunks),
    )
    image = theme.blackflash_record_image(files)
    if image:
        embed.set_image(url=image)
    embed.set_footer(text=RECORD_FOOTER)
    return embed


async def send_blackflash(interaction: discord.Interaction, mortal: bool = False) -> None:
    """Tire une tentative, met à jour les chances du joueur et affiche le résultat.

    `mortal` demande le buff de **Combat Mortel** : il n’est ouvert qu’aux
    joueurs qui ont décroché le titre de recordman du Rayon Noir, et double alors
    leur augmentation permanente (+20 au lieu de +10).
    """
    profile = await get_profile(interaction.guild_id, interaction.user.id)
    if profile is None:
        await notify_error(interaction, NO_PROFILE_MESSAGE)
        return

    # Le titre est personnel et permanent : il est lu sur la fiche du joueur,
    # jamais sur celle d’un autre.
    is_record_man = profile.blackflash_record >= rules.RECORD_STREAK

    if mortal and not is_record_man:
        await interaction.response.send_message(
            embed=theme.notice_embed(
                theme.SECTION_ALERTE, "alerte", MORTAL_DENIED_MESSAGE, interaction.guild
            ),
            ephemeral=True,
        )
        return

    # Les emojis du serveur doivent être indexés avant le rendu (réparation
    # REST si le cache passerelle est vide).
    await emojis_module.ensure_loaded(interaction.guild)

    # Base effective : traits de la fiche (et exception du staff) compris, plus
    # l’augmentation permanente du recordman. Elle sert à la fois de plancher au
    # tirage et de valeur de retour en cas d’échec : un raté n’efface donc ni le
    # bonus d’un trait, ni celui du record.
    base = rules.effective_base(
        profile.traits,
        profile.blackflash_base,
        profile.blackflash_bonus,
        rules.record_bonus(mortal) if is_record_man else 0,
    )
    chance_before = max(rules.normalize(profile.blackflash_chance), base)
    success = rules.roll(chance_before)
    chance_after = rules.next_chance(chance_before, success, base)

    profile.blackflash_chance = chance_after
    # Série en cours : un raté la casse, et `/jjk blackflash-reset` aussi (fin
    # de combat). C’est sur cette série que se joue le titre de recordman.
    profile.blackflash_streak = profile.blackflash_streak + 1 if success else 0
    if success:
        # Le coup relance le buff : +10 % à toutes les statistiques attribuables
        # (Réserve d’EO exceptée) pendant `BUFF_TURNS` tours. Il s’affiche dans
        # `/profil voir` et le staff le retire avec `/blackflash buff`.
        profile.blackflash_buff_turns = rules.BUFF_TURNS

    # Titre de recordman : personnel et définitif. Le premier embed s’envoie à
    # la toute première série de `RECORD_STREAK` succès ; ensuite, battre son
    # propre record ne fait que mettre à jour la fiche, sans nouvel embed — le
    # joueur est déjà recordman.
    record_streak: int | None = None
    if success and profile.blackflash_streak >= rules.RECORD_STREAK:
        was_record_man = profile.blackflash_record >= rules.RECORD_STREAK
        if profile.blackflash_streak > profile.blackflash_record:
            profile.blackflash_record = profile.blackflash_streak
            if not was_record_man:
                record_streak = profile.blackflash_streak
    await save_profile(interaction.guild_id, interaction.user.id, profile)

    # L’image est jointe au message : on accuse réception avant l’upload
    # pour rester dans les 3 s de délai d’interaction (erreur 10062).
    if not interaction.response.is_done():
        await interaction.response.defer()

    def build_embeds(files: list[discord.File] | None) -> list[discord.Embed]:
        """Résultat du Black Flash, suivi de l’embed du record le cas échéant."""
        embeds = [
            build_blackflash_embed(
                success, chance_before, chance_after, interaction.guild, files
            )
        ]
        if record_streak is not None:
            embeds.append(
                build_blackflash_record_embed(
                    interaction.user.id,
                    profile.name,
                    record_streak,
                    interaction.guild,
                    files,
                )
            )
        return theme.with_banner_many(embeds, files)

    files: list[discord.File] = []
    try:
        await interaction.followup.send(embeds=build_embeds(files), files=files)
    except discord.HTTPException as error:
        # Upload refusé (limite de poids d’une pièce jointe, réseau) : la
        # tentative est déjà comptée et sauvegardée, on renvoie donc le même
        # résultat sans image plutôt que de faire échouer la commande.
        logger.warning("Image de Black Flash refusée (%s) : envoi sans image", error)
        for file in files:
            file.close()
        await interaction.followup.send(embeds=build_embeds(None))


async def send_blackflash_reset(interaction: discord.Interaction) -> None:
    """Remet les chances du joueur à la base, à la fin d’un combat.

    C’est aussi ce qui clôt le combat pour la série de Black Flash : le titre de
    recordman se gagne sur ``RECORD_STREAK`` succès consécutifs **dans un même
    combat**, la série en cours repart donc de zéro.
    """
    profile = await get_profile(interaction.guild_id, interaction.user.id)
    if profile is None:
        await notify_error(interaction, NO_PROFILE_RESET_MESSAGE)
        return

    base = rules.effective_base(
        profile.traits,
        profile.blackflash_base,
        profile.blackflash_bonus,
        rules.record_bonus()
        if profile.blackflash_record >= rules.RECORD_STREAK
        else 0,
    )
    chance_before = rules.normalize(profile.blackflash_chance)
    streak_before = profile.blackflash_streak
    buff_before = profile.blackflash_buff_turns
    profile.blackflash_chance = base
    profile.blackflash_streak = 0
    # Fin de combat : le buff de Noirceur ne survit pas au combat qu’il a embrasé.
    profile.blackflash_buff_turns = 0
    await save_profile(interaction.guild_id, interaction.user.id, profile)

    embed = theme.notice_embed(
        theme.SECTION_BLACKFLASH,
        "blackflash",
        f"Tes chances de Black Flash ont été réinitialisées : "
        f"`{chance_before}%` → `{base}%`."
        + (
            f"\nLa série du combat est close : `{streak_before}` succès consécutifs "
            "remis à zéro."
            if streak_before
            else ""
        )
        + (
            f"\nLe buff de Noirceur est dissipé ({buff_before} tour(s) restant(s) "
            "annulé(s))."
            if buff_before
            else ""
        ),
        interaction.guild,
        footer=FOOTER,
    )
    await interaction.response.send_message(embed=embed)
