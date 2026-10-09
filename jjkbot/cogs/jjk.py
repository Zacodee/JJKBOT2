"""Commande `/jjk` : guide, diagnostic, Black Flash, Renaissance et maintenance."""

import json
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from jjkbot import config, emojis as emojis_module, permissions, theme
from jjkbot.content import blackflash as blackflash_rules
from jjkbot.content import renaissance as renaissance_rules
from jjkbot.content import train as train_rules
from jjkbot.content import stats as stats_rules
from jjkbot.storage import profiles as profiles_module
from jjkbot.storage import settings
from jjkbot.storage.profiles import get_profile, save_profile
from jjkbot.views import blackflash as blackflash_views
from jjkbot.views import renaissance as renaissance_views


def build_help_embed(guild: discord.Guild | None = None) -> discord.Embed:
    """Guide de démarrage destiné aux nouveaux membres.

    Tout le contenu vit dans la description : c’est le seul endroit d’un embed
    où Discord rend les titres `##`, le gras et les blocs de code.
    """
    e = lambda key: theme.emoji(key, guild)  # noqa: E731 - raccourci de lisibilité

    sections = (
        (
            f"{e('profil')} Créer ton personnage",
            [
                f"`/profil creer` • étape 1 : {e('identite')} identité, {e('age')} âge, "
                f"{e('race')} race, {e('grade')} grade",
                f"`/profil creer` • étape 2 : {e('role')} rôle, {e('citation')} citation, "
                "traits et défauts",
                f"`/profil image` • {e('image')} ajoute une image PNG, JPG, WEBP ou un GIF",
            ],
        ),
        (
            f"{e('page_profil')} Consulter et modifier ta fiche",
            [
                f"`/profil voir` • {e('page_profil')} 3 pages navigables : profil, "
                f"{e('page_stats')} statistiques, {e('page_traits')} traits et défauts",
                "`/profil voir joueur:` • consulte la fiche d’un autre membre",
                "`/profil modifier` • mets ta fiche à jour",
            ],
        ),
        (
            f"{e('points')} Points de statistique",
            [
                f"`/profil attribuer-stat` • {e('points')} investis tes points dans "
                f"{e('force')} Force, {e('resistance')} Résistance, {e('vitesse')} Vitesse, "
                f"{e('manipulation_eo')} Manipulation occulte ou {e('sortie_eo')} Sortie d’EO",
                f"`/profil donner-points` • {e('aide')} le staff t’en attribue après un RP",
            ],
        ),
        (
            f"{e('competences')} Compétences",
            [
                f"`/competences voir` • {e('competences')} l’arbre complet, catégorie par catégorie",
                f"`/competences acheter` • {e('panier')} panier multi-compétences, "
                "prérequis vérifiés automatiquement",
                f"{e('xp')} l’XP s’obtient en RP : le staff l’attribue avec `/competences xp`",
            ],
        ),
        (
            f"{e('xp')} Expérience et demandes",
            [
                f"`/xp convertir` • {e('points')} échange de l’XP contre des points de "
                "statistique (1 XP = 1 point), à répartir ensuite",
                f"`/xp demande` • {e('demande_xp')} dépose une demande d’XP pour une scène "
                "(type, montant, description, lien) ; le staff la valide d’un clic",
                f"`/profil couleur` • {e('profil')} donne à ta fiche la couleur de ton choix "
                "(nuancier ou code hexadécimal)",
            ],
        ),
        (
            f"{e('train')} Entraînement",
            [
                f"`/train` • {e('xp')} entraîne-toi une fois par semaine pour gagner "
                f"**{train_rules.TRAIN_XP} XP**",
                f"{e('page_stats')} tes statistiques affichent le buff de Noirceur d'un "
                "Black Flash réussi, et les sous-statistiques (Perception, Vitesse de "
                "Projectile, Perception occulte) suivent tes stats principales.",
            ],
        ),
        (
            f"{e('blackflash')} Black Flash",
            [
                f"`/jjk blackflash` • {e('blackflash_chance')} tente le coup rarissime : "
                f"{blackflash_rules.BASE_CHANCE}% de base, +{blackflash_rules.CHANCE_STEP}% "
                f"par succès (max {blackflash_rules.MAX_CHANCE}%), retour à la base si tu rates",
                f"`/jjk blackflash-reset` • {e('blackflash_tentative')} remet tes chances à "
                f"{blackflash_rules.BASE_CHANCE}% quand le combat est fini",
                "Certains traits relèvent cette base (ex. fièvre, éveil du Black Flash) : "
                "le staff les reconnaît automatiquement ; un raté y revient.",
                f"{e('blackflash')} **Record Man du Rayon Noir** • "
                f"{blackflash_rules.RECORD_STREAK} Black Flash consécutifs dans un même "
                "combat te donnent ce titre, à toi et pour de bon : "
                f"**+{blackflash_rules.RECORD_BONUS}%** de chance à vie, "
                f"**+{blackflash_rules.MORTAL_RECORD_BONUS}%** en `Combat Mortel` "
                "(option `mortel` de `/jjk blackflash`, réservée aux recordmen).",
            ],
        ),
        (
            f"{e('renaissance')} Renaissance en Esprit Vengeur",
            [
                f"`/jjk renaissance` • {e('renaissance_chance')} tente la renaissance de ton "
                "personnage à sa **mort définitive** (dé de 100, réussite sur 5 ou moins)",
                f"`situation:` • {e('alerte')} relève le seuil selon la mort : "
                "ressentiment envers le responsable (10) ou rival (15)",
                f"{e('aide')} la renaissance n’est pas une résurrection : la nouvelle nature "
                "du personnage se développe avec le staff en RP",
            ],
        ),
        (
            f"{e('alerte')} Commandes du staff",
            [
                "`/profil donner-points` • points de statistique",
                "`/competences xp` • expérience",
                "`/profil reset` • profil complet, statistiques ou compétences",
                "`/jjk blackflash-chance` • plancher et bonus de Black Flash d’un joueur",
                "`/blackflash chance` et `/blackflash record` • forcer la chance d’un "
                "joueur et gérer son titre de recordman, pour tester l’évènement",
                "`/blackflash buff` • voir, fixer ou retirer le buff de stats d’un joueur",
                "`/train-reset` • rendre son entraînement hebdomadaire à un joueur",
                "`/jjk salon` • salon réservé au staff qui reçoit les demandes d’XP",
                "`/jjk eo` • Réserve d’EO d’un joueur, après validation de sa fiche",
                "`/jjk sauvegarde` et `/jjk restaurer` • copier ou remettre les fiches",
                "`/jjk emojis` • vérifier les emojis du serveur",
            ],
        ),
    )

    chunks = [
        theme.title("aide", "Guide du nouveau sorcier", guild),
        "Bienvenue dans le monde du jujutsu ! Ce guide t’explique pas à pas comment créer "
        "ton personnage et utiliser les commandes du bot.",
        theme.divider(),
    ]
    for heading, lines in sections:
        chunks.append(theme.heading(heading, 3, guild))
        chunks.append("\n".join(lines))

    embed = discord.Embed(
        colour=theme.color(theme.SECTION_AIDE),
        description=theme.blocks(*chunks),
    )
    embed.set_footer(text="✦ Bonne aventure, sorcier. Que ton énergie occulte te guide. ✦")
    if config.HELP_GIF_URL:
        embed.set_image(url=config.HELP_GIF_URL)
    return embed


async def set_reserve_eo(
    interaction: discord.Interaction,
    joueur: discord.Member,
    montant: int,
) -> None:
    """Fixe la Réserve d’EO d’un joueur, une fois sa fiche RP validée.

    « Réserve d’EO » est la seule statistique `fixed` : aucun point de
    statistique ne s’y dépense (voir `content.stats`). C’est donc le staff
    administrateur qui la pose ici, après avoir validé la fiche du joueur.
    """
    if not await permissions.ensure_admin(interaction):
        return

    profile = await get_profile(interaction.guild_id, joueur.id)
    if profile is None:
        await interaction.response.send_message(
            embed=theme.notice_embed(
                theme.SECTION_ALERTE,
                "alerte",
                f"{joueur.display_name} n’a pas encore de fiche : elle doit exister "
                "avant que sa Réserve d’EO puisse être fixée.",
                interaction.guild,
            ),
            ephemeral=True,
        )
        return

    stat = stats_rules.RESERVE_EO
    previous = profile.stats.get(stat.id, 0)
    profile.stats[stat.id] = montant
    profile.touch()
    await save_profile(interaction.guild_id, joueur.id, profile)

    await interaction.response.send_message(
        embed=theme.notice_embed(
            theme.SECTION_STATS,
            stat.emoji,
            f"**{stat.label}** de {joueur.mention} fixée à **{montant}** "
            f"(avant : {previous}). Elle est propre au personnage : aucun point ne "
            "s’y dépense, `/profil attribuer-stat` ne la touche jamais, et relancer "
            "`/jjk eo` la corrige.",
            interaction.guild,
        ),
        ephemeral=True,
    )


def _chunk_lines(lines: list[str], limit: int = 1000) -> list[str]:
    """Regroupe des lignes en blocs de moins de `limit` caractères."""
    chunks: list[str] = []
    current: list[str] = []
    length = 0
    for line in lines:
        if current and length + len(line) + 1 > limit:
            chunks.append("\n".join(current))
            current = []
            length = 0
        current.append(line)
        length += len(line) + 1
    if current:
        chunks.append("\n".join(current))
    return chunks


def build_emoji_report_embed(
    guild: discord.Guild | None,
    rows: list[tuple[str, emojis_module.EmojiSpec, discord.Emoji | None]],
) -> discord.Embed:
    """État du catalogue d’emojis : ce qui est trouvé, ce qu’il reste à créer."""
    found = [(key, spec, emoji) for key, spec, emoji in rows if emoji is not None]
    missing = [(key, spec, emoji) for key, spec, emoji in rows if emoji is None]

    def lines_for(entries, show_fallback: bool) -> list[str]:
        lines = []
        for key, spec, emoji in entries:
            glyph = str(emoji) if emoji is not None else ("⚠️" if show_fallback else "")
            suffix = f" — repli {spec.fallback}" if show_fallback else ""
            lines.append(f"{glyph} `{spec.name}` ({key}){suffix}")
        return lines

    embed = discord.Embed(
        colour=theme.color(theme.SECTION_AIDE),
        title=theme.title("aide", "Emojis du serveur", guild),
        description=theme.blocks(
            f"**{len(found)} / {len(rows)}** emojis custom ont été trouvés sur le serveur.",
            theme.divider(),
        ),
    )
    # Les champs Discord sont limités à 1024 caractères : on découpe la liste.
    for title, entries, show_fallback in (("✅ Trouvés", found, False), ("⚠️ À créer", missing, True)):
        chunks = _chunk_lines(lines_for(entries, show_fallback))
        if not chunks:
            embed.add_field(name=title, value="*Rien à signaler.*", inline=False)
            continue
        for index, chunk in enumerate(chunks):
            name = title if index == 0 else f"{title} (suite)"
            embed.add_field(name=name, value=chunk, inline=False)
    embed.set_footer(
        text="✦ Crée les emojis manquants avec ces noms exacts, puis relance /jjk emojis."
    )
    return embed


class JjkCog(
    commands.GroupCog,
    group_name="jjk",
    group_description="Guide du bot, diagnostic des emojis et Black Flash",
):
    """Guide du bot, utilité des commandes, emojis et Black Flash."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="help", description="Guide de démarrage et utilité des commandes")
    @app_commands.guild_only()
    async def help(self, interaction: discord.Interaction) -> None:
        await emojis_module.ensure_loaded(interaction.guild)
        files: list[discord.File] = []
        embeds = theme.with_banner(build_help_embed(interaction.guild), files)
        await interaction.response.send_message(embeds=embeds, files=files)

    @app_commands.command(name="emojis", description="Vérifier les emojis du serveur utilisés par le bot")
    @app_commands.guild_only()
    async def emojis(self, interaction: discord.Interaction) -> None:
        if not await permissions.ensure_staff(interaction):
            return

        # Répare l’index via l’API REST si le cache passerelle est vide, puis
        # dresse l’état du catalogue : aucun refresh brutal qui écraserait la réparation.
        await emojis_module.ensure_loaded(interaction.guild)
        rows = emojis_module.emojis.status(interaction.guild)
        files: list[discord.File] = []
        embeds = theme.with_banner(build_emoji_report_embed(interaction.guild, rows), files)
        await interaction.response.send_message(embeds=embeds, files=files, ephemeral=True)

    # --- Black Flash ------------------------------------------------------

    @app_commands.command(
        name="blackflash",
        description=(
            f"Tenter un Black Flash : {blackflash_rules.BASE_CHANCE}% de base, "
            f"+{blackflash_rules.CHANCE_STEP}% par succès, retour à la base si tu rates"
        ),
    )
    @app_commands.describe(
        mortel=(
            "Combat Mortel : le buff du recordman passe à "
            f"+{blackflash_rules.MORTAL_RECORD_BONUS}% (réservé au détenteur du record)"
        )
    )
    @app_commands.guild_only()
    async def blackflash(
        self, interaction: discord.Interaction, mortel: bool = False
    ) -> None:
        await blackflash_views.send_blackflash(interaction, mortal=mortel)

    @app_commands.command(
        name="blackflash-reset",
        description=(
            f"Réinitialiser ses chances de Black Flash à "
            f"{blackflash_rules.BASE_CHANCE}% (fin de combat)"
        ),
    )
    @app_commands.guild_only()
    async def blackflash_reset(self, interaction: discord.Interaction) -> None:
        await blackflash_views.send_blackflash_reset(interaction)

    @app_commands.command(
        name="blackflash-chance",
        description="Fixer le plancher et le bonus de Black Flash d’un joueur (staff)",
    )
    @app_commands.describe(
        joueur="Le joueur concerné",
        base="Plancher imposé (5-100). Vide : seuls les traits de la fiche comptent.",
        bonus="Points ajoutés à la base (0 par défaut)",
        retirer="Retirer l’exception et revenir aux traits de la fiche",
    )
    @app_commands.guild_only()
    async def blackflash_chance(
        self,
        interaction: discord.Interaction,
        joueur: discord.Member,
        base: app_commands.Range[
            int, blackflash_rules.BASE_CHANCE, blackflash_rules.MAX_CHANCE
        ]
        | None = None,
        bonus: app_commands.Range[int, 0, blackflash_rules.MAX_CHANCE] | None = None,
        retirer: bool = False,
    ) -> None:
        if not await permissions.ensure_staff(interaction):
            return

        profile = await get_profile(interaction.guild_id, joueur.id)
        if profile is None:
            await interaction.response.send_message(
                embed=theme.notice_embed(
                    theme.SECTION_ALERTE,
                    "alerte",
                    f"{joueur.display_name} n’a pas encore de profil.",
                    interaction.guild,
                ),
                ephemeral=True,
            )
            return

        if retirer:
            profile.blackflash_base = None
            profile.blackflash_bonus = 0
        else:
            if base is None and bonus is None:
                await interaction.response.send_message(
                    embed=theme.notice_embed(
                        theme.SECTION_ALERTE,
                        "alerte",
                        "Précise une **base**, un **bonus**, ou coche `retirer` "
                        "pour revenir aux traits de la fiche.",
                        interaction.guild,
                    ),
                    ephemeral=True,
                )
                return
            profile.blackflash_base = base
            profile.blackflash_bonus = bonus or 0

        profile.touch()
        profile = await save_profile(interaction.guild_id, joueur.id, profile)
        # Le bonus du recordman vient de sa meilleure série (un titre personnel,
        # définitif) et non de l’exception du staff : le rappeler ici évite de
        # croire à une valeur oubliée en voyant une base effective plus haute.
        record_bonus = (
            blackflash_rules.record_bonus()
            if profile.blackflash_record >= blackflash_rules.RECORD_STREAK
            else 0
        )
        effective = blackflash_rules.effective_base(
            profile.traits,
            profile.blackflash_base,
            profile.blackflash_bonus,
            record_bonus,
        )
        override = (
            f"base `{profile.blackflash_base}` • bonus `{profile.blackflash_bonus}`"
            if profile.blackflash_base is not None or profile.blackflash_bonus
            else "aucune exception : traits de la fiche uniquement"
        )
        if record_bonus:
            override += f" • recordman du Rayon Noir (+{record_bonus})"
        await interaction.response.send_message(
            embed=theme.notice_embed(
                theme.SECTION_BLACKFLASH,
                "blackflash",
                f"Chance de Black Flash de {joueur.mention} réglée : plancher "
                f"effectif **{effective}%** ({override}).",
                interaction.guild,
                footer=blackflash_views.FOOTER,
            ),
            ephemeral=True,
        )

    @app_commands.command(
        name="renaissance",
        description="Tenter une Renaissance en Esprit Vengeur (à la mort définitive du personnage)",
    )
    @app_commands.describe(
        situation="Circonstance de la mort : relève le seuil de réussite"
    )
    @app_commands.choices(
        situation=[
            app_commands.Choice(name="Mort sans circonstance (réussite sur 5 ou moins)", value="base"),
            app_commands.Choice(name="Ressentiment envers le responsable (10 ou moins)", value="ressentiment"),
            app_commands.Choice(name="Le responsable était son rival (15 ou moins)", value="rival"),
        ]
    )
    @app_commands.guild_only()
    async def renaissance(
        self,
        interaction: discord.Interaction,
        situation: app_commands.Choice[str] | None = None,
    ) -> None:
        await renaissance_views.send_renaissance(
            interaction,
            situation.value if situation is not None else renaissance_rules.DEFAULT_SITUATION,
        )


    # --- Réserve d’EO (administrateurs) ----------------------------------

    @app_commands.command(
        name="eo",
        description=(
            "Fixer la Réserve d’EO d’un joueur après validation de sa fiche "
            "(administrateurs)"
        ),
    )
    @app_commands.describe(
        joueur="Le joueur dont la fiche RP vient d’être validée",
        montant="La Réserve d’EO définitive de son personnage",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def eo(
        self,
        interaction: discord.Interaction,
        joueur: discord.Member,
        montant: app_commands.Range[int, 0, stats_rules.MAX_RESERVE_EO],
    ) -> None:
        await set_reserve_eo(interaction, joueur, montant)

    # --- Salon des demandes d’XP (administrateurs) -----------------------

    @app_commands.command(
        name="salon",
        description="Définir le salon réservé au staff qui reçoit les demandes d’XP",
    )
    @app_commands.describe(
        salon="Le salon qui recevra les demandes (rendu visible du staff uniquement)",
        retirer="Retirer la configuration actuelle",
    )
    # `default_permissions` masque la commande aux non-administrateurs dans le
    # sélecteur Discord ; l’autre barrière (`ensure_admin`) protège l’exécution,
    # même si un client en cache tente encore de l’appeler.
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def salon(
        self,
        interaction: discord.Interaction,
        salon: discord.TextChannel | None = None,
        retirer: bool = False,
    ) -> None:
        if not await permissions.ensure_admin(interaction):
            return

        guild = interaction.guild
        if guild is None:  # pragma: no cover - la commande est guild_only
            return

        if retirer:
            await settings.set_xp_channel(guild.id, None)
            await interaction.response.send_message(
                embed=theme.notice_embed(
                    theme.SECTION_DEMANDES,
                    "demande_xp",
                    "Le salon des demandes d’XP a été retiré : `/xp demande` est désactivée "
                    "jusqu’à ce qu’un nouveau salon soit défini.",
                    guild,
                ),
                ephemeral=True,
            )
            return

        if salon is None:
            await interaction.response.send_message(
                embed=theme.notice_embed(
                    theme.SECTION_ALERTE,
                    "alerte",
                    "Précise un **salon**, ou coche `retirer` pour désactiver les demandes.",
                    guild,
                ),
                ephemeral=True,
            )
            return

        # Relancer la commande sur un autre salon REMPLACE simplement le réglage
        # précédent : c’est le comportement attendu pour tester, et le salon
        # abandonné n’est pas modifié pour autant.
        private_note = "Salon rendu **visible du staff uniquement**."
        try:
            await salon.set_permissions(guild.default_role, view_channel=False)
            if config.STAFF_ROLE_ID:
                role = guild.get_role(config.STAFF_ROLE_ID)
                if role is not None:
                    await salon.set_permissions(role, view_channel=True)
        except discord.Forbidden:
            private_note = (
                "⚠️ Je n’ai pas pu restreindre l’accès à ce salon : vérifie qu’il n’est "
                "visible que du staff."
            )
        except discord.HTTPException:  # pragma: no cover - dépend de l’API
            private_note = "⚠️ Les permissions du salon n’ont pas pu être modifiées."

        await settings.set_xp_channel(guild.id, salon.id)

        await interaction.response.send_message(
            embed=theme.notice_embed(
                theme.SECTION_DEMANDES,
                "demande_xp",
                f"{salon.mention} reçoit désormais les demandes d’XP. {private_note}\n"
                "Les joueurs les déposent avec `/xp demande` ; le staff valide d’un clic, "
                "même longtemps après. Relance `/jjk salon` autant de fois que tu veux "
                "pour changer de salon.",
                guild,
            ),
            ephemeral=True,
        )

    # --- Sauvegarde et restauration des fiches (staff) -------------------

    @app_commands.command(
        name="sauvegarde",
        description="Télécharger une copie des fiches (administrateurs)",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def sauvegarde(self, interaction: discord.Interaction) -> None:
        if not await permissions.ensure_admin(interaction):
            return

        path = Path(config.DATA_FILE)
        if not path.is_file() or path.stat().st_size <= 0:
            await interaction.response.send_message(
                embed=theme.notice_embed(
                    theme.SECTION_ALERTE,
                    "alerte",
                    "Aucune fiche à sauvegarder pour le moment.",
                    interaction.guild,
                ),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            content=(
                "# Copie des fiches\n"
                "Conserve ce fichier : il se rejoue tel quel avec `/jjk restaurer`."
            ),
            file=discord.File(path, filename="profiles.json"),
            ephemeral=True,
        )

    @app_commands.command(
        name="restaurer",
        description="Restaurer les fiches depuis un fichier profiles.json (administrateurs)",
    )
    @app_commands.describe(
        fichier="Le fichier profiles.json exporté par /jjk sauvegarde",
        confirmer="Confirme le remplacement de TOUTES les fiches actuelles",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def restaurer(
        self,
        interaction: discord.Interaction,
        fichier: discord.Attachment,
        confirmer: bool = False,
    ) -> None:
        if not await permissions.ensure_admin(interaction):
            return

        if not confirmer:
            await interaction.response.send_message(
                embed=theme.notice_embed(
                    theme.SECTION_ALERTE,
                    "alerte",
                    "Cette commande **remplace toutes les fiches actuelles** par celles du "
                    "fichier. Relance avec `confirmer:Vrai` si c’est bien ce que tu veux.",
                    interaction.guild,
                ),
                ephemeral=True,
            )
            return

        if fichier.size > 8 * 1024 * 1024:
            await interaction.response.send_message(
                embed=theme.notice_embed(
                    theme.SECTION_ERREUR, "erreur", "Le fichier est trop volumineux (8 Mo max).", interaction.guild
                ),
                ephemeral=True,
            )
            return

        try:
            raw = await fichier.read()
            database = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            await interaction.response.send_message(
                embed=theme.notice_embed(
                    theme.SECTION_ERREUR,
                    "erreur",
                    "Ce fichier n’est pas un `profiles.json` valide.",
                    interaction.guild,
                ),
                ephemeral=True,
            )
            return

        try:
            count = await profiles_module.replace_database(database)
        except ValueError as error:
            await interaction.response.send_message(
                embed=theme.notice_embed(theme.SECTION_ERREUR, "erreur", str(error), interaction.guild),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            embed=theme.notice_embed(
                theme.SECTION_SUCCES,
                "succes",
                f"**{count} fiche(s)** restaurée(s). L’ancienne base a été conservée à côté "
                "(`profiles.json.invalide-<horodatage>`) au cas où.",
                interaction.guild,
            ),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    """Chargement du cog par le bot."""
    await bot.add_cog(JjkCog(bot))
