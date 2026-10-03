"""Rendu et vues interactives des fiches de personnage."""

from __future__ import annotations

import logging

import discord

from jjkbot import emojis as emojis_module, sessions, theme
from jjkbot.content.stats import DEFAULT_STATS, STAT_DEFINITIONS
from jjkbot.storage import images
from jjkbot.storage.profiles import (
    Profile,
    delete_profile,
    get_profile,
    now_iso,
    parse_timestamp,
    save_profile,
)
from jjkbot.views.base import BaseModal, BaseView

logger = logging.getLogger(__name__)

VIEW_TIMEOUT = 15 * 60

# Onglets de la fiche : (identifiant, libellé, clé d’emoji).
PAGES: tuple[tuple[str, str, str], ...] = (
    ("global", "Profil", "page_profil"),
    ("stats", "Statistiques", "page_stats"),
    ("traits", "Traits & défauts", "page_traits"),
)
PAGE_INDEX = {page: index for index, (page, _label, _key) in enumerate(PAGES)}
PAGE_KEYS = {page for page, _label, _key in PAGES}

IMAGE_FILENAME_STEM = "personnage"


# --- Rendu --------------------------------------------------------------------


def _page_footer(page: str) -> str:
    index = PAGE_INDEX.get(page, 0)
    return f"✦ Page {index + 1} / {len(PAGES)} • Fiche RP"


def build_profile_embeds(
    profile: Profile,
    target_user: discord.abc.User,
    page: str = "global",
    guild: discord.Guild | None = None,
) -> list[discord.Embed]:
    """Embeds de la fiche (bannière comprise)."""
    # Un onglet inconnu retombe sur la première page plutôt que de casser l’affichage.
    page = page if page in PAGE_KEYS else "global"
    section = {
        "global": theme.SECTION_PROFIL,
        "stats": theme.SECTION_STATS,
        "traits": theme.SECTION_COMPETENCES,
    }[page]

    if page == "global":
        embed = discord.Embed(
            colour=theme.color(section),
            description=theme.blocks(
                theme.title("profil", "Profil", guild, suffix=f" : @{target_user.display_name}"),
                theme.group(
                    ("identite", "Identité", profile.name),
                    ("age", "Âge", profile.age),
                    guild=guild,
                ),
                theme.divider(),
                theme.group(
                    ("race", "Race", profile.race),
                    ("grade", "Grade", profile.grade),
                    guild=guild,
                ),
                theme.divider(),
                theme.group(
                    ("alignement", "Alignement", profile.alignment),
                    ("role", "Rôle", profile.role),
                    guild=guild,
                ),
                theme.quote_block(profile.quote, guild),
            ),
        )
    elif page == "stats":
        total = sum(profile.stats.get(stat.id, 0) for stat in STAT_DEFINITIONS)
        # Tableau aligné dans un bloc de code, avec l’emoji de chaque stat en
        # tête de ligne. Dans un ``` seuls les replis unicode sont utilisés :
        # les emojis custom du serveur ne sont pas rendus à l’intérieur.
        label_width = max(len(stat.label) for stat in STAT_DEFINITIONS)
        value_width = max(len(str(profile.stats.get(stat.id, 0))) for stat in STAT_DEFINITIONS)
        rows = []
        for stat in STAT_DEFINITIONS:
            value = profile.stats.get(stat.id, 0)
            rows.append(
                f"{theme.fallback(stat.emoji)}  {stat.label.ljust(label_width)}  "
                f"{str(value).rjust(value_width)}  "
                f"{theme.progress_bar(value, total or 1)}"
            )
        table = theme.code_block(rows)
        embed = discord.Embed(
            colour=theme.color(section),
            description=theme.blocks(
                theme.title("stats", "Statistiques", guild, suffix=f" : {profile.name}"),
                theme.highlight("points", f"Points à attribuer — **{profile.stat_points}**", guild),
                theme.highlight("progression", f"Total réparti — **{total}** point(s)", guild),
                theme.divider(),
                table,
            ),
        )
    else:
        embed = discord.Embed(
            colour=theme.color(section),
            description=theme.blocks(
                theme.title("page_traits", "Traits & défauts", guild, suffix=f" : {profile.name}"),
                theme.field_label("debloque", "Traits", guild),
                theme.bullet_list(profile.traits),
                theme.field_label("alerte", "Défauts", guild),
                theme.bullet_list(profile.flaws),
            ),
        )

    embed.set_author(name=target_user.display_name, icon_url=target_user.display_avatar.url)
    embed.set_footer(text=_page_footer(page))
    timestamp = parse_timestamp(profile.updated_at) or parse_timestamp(profile.created_at)
    if timestamp is not None:
        embed.timestamp = timestamp

    # Pas de bannière au-dessus de la fiche : le visuel « Jujutsu Kaisen » a
    # été retiré à la demande (le mécanisme theme.with_banner reste dispo
    # pour en afficher une nouvelle).
    return [embed]


def _attach_character_image(
    embed: discord.Embed,
    profile: Profile,
    guild_id: int,
    user_id: int,
    files: list[discord.File],
) -> None:
    """Ajoute l’image du personnage : fichier local en priorité, sinon URL."""
    local = images.find_image(guild_id, user_id)
    if local is not None:
        filename = f"{IMAGE_FILENAME_STEM}{local.suffix}"
        try:
            files.append(discord.File(local, filename=filename))
            embed.set_image(url=f"attachment://{filename}")
            return
        except (OSError, discord.HTTPException) as error:  # pragma: no cover - disque/HTTP
            logger.warning("Image locale illisible pour %s : %s", local, error)

    if profile.image_url:
        embed.set_image(url=profile.image_url)


async def build_profile_message(
    profile: Profile,
    target_user: discord.abc.User,
    page: str = "global",
    guild: discord.Guild | None = None,
    guild_id: int | None = None,
) -> tuple[list[discord.Embed], list[discord.File]]:
    """Embeds et fichiers prêts à être envoyés."""
    # Filet de sécurité : si le cache des emojis est vide (ancien déploiement
    # sans intent, ou emoji créé juste avant un redémarrage), on va le chercher
    # via l’API REST avant de rendre.
    await emojis_module.ensure_loaded(guild)
    embeds = build_profile_embeds(profile, target_user, page, guild)
    files: list[discord.File] = []

    if page == "global" and guild_id is not None:
        content = embeds[-1]
        _attach_character_image(content, profile, guild_id, target_user.id, files)
        if not files and not profile.image_url:
            content.add_field(
                name=f"{theme.emoji('image', guild)} Image du personnage",
                value="Aucune image ajoutée. Utilise `/profil image` avec un PNG, un JPG ou un GIF.",
                inline=False,
            )

    return embeds, files


class ProfileView(BaseView):
    """Navigation entre les trois onglets d’une fiche."""

    def __init__(self, guild_id: int, target_user: discord.abc.User, page: str = "global"):
        super().__init__(timeout=VIEW_TIMEOUT)
        self.guild_id = int(guild_id)
        self.target_user = target_user
        self.page = page if page in PAGE_KEYS else "global"
        self._build_buttons()

    def _build_buttons(self) -> None:
        for page, label, key in PAGES:
            button = discord.ui.Button(
                label=label,
                emoji=theme.partial_emoji(key, None),
                style=discord.ButtonStyle.primary if page == self.page else discord.ButtonStyle.secondary,
                disabled=page == self.page,
                custom_id=f"profil:page:{page}",
            )
            button.callback = self._make_callback(page)
            self.add_item(button)

    def _make_callback(self, page: str):
        async def callback(interaction: discord.Interaction) -> None:
            await self._show_page(interaction, page)

        return callback

    async def _show_page(self, interaction: discord.Interaction, page: str) -> None:
        profile = await get_profile(self.guild_id, self.target_user.id)
        if profile is None:
            await interaction.response.edit_message(
                content="Ce profil n’existe plus.",
                embeds=[],
                attachments=[],
                view=None,
            )
            return

        embeds, files = await build_profile_message(
            profile,
            self.target_user,
            page,
            interaction.guild,
            self.guild_id,
        )
        await interaction.response.edit_message(
            content=None,
            embeds=embeds,
            attachments=files,
            view=ProfileView(self.guild_id, self.target_user, page),
        )

    async def on_timeout(self) -> None:  # pragma: no cover - dépend du runtime
        for item in self.children:
            item.disabled = True


async def send_profile(
    interaction: discord.Interaction,
    target_user: discord.abc.User,
    page: str = "global",
    ephemeral: bool = False,
    content: str | None = None,
) -> None:
    """Affiche la fiche d’un joueur (ou prévient qu’elle n’existe pas)."""
    # On accuse réception immédiatement : lecture du profil et envoi de l’image
    # peuvent dépasser les 3 s du délai d’interaction (erreur 10062), surtout au
    # redémarrage quand le disque du conteneur est lent.
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=ephemeral)

    profile = await get_profile(interaction.guild_id, target_user.id)
    if profile is None:
        message = (
            "Tu n’as pas encore de profil. Lance `/profil creer` pour être guidé par le bot."
            if target_user.id == interaction.user.id
            else f"{target_user.display_name} n’a pas encore créé de profil."
        )
        await interaction.followup.send(
            embed=theme.notice_embed(theme.SECTION_ALERTE, "alerte", message, interaction.guild),
            ephemeral=True,
        )
        if not ephemeral:
            # Le message public différé n’a pas de contenu : on le retire.
            try:
                await interaction.delete_original_response()
            except discord.HTTPException:  # pragma: no cover - dépend de l’API
                pass
        return

    embeds, files = await build_profile_message(
        profile,
        target_user,
        page,
        interaction.guild,
        interaction.guild_id,
    )
    await interaction.edit_original_response(
        content=content,
        embeds=embeds,
        attachments=files,
        view=ProfileView(interaction.guild_id, target_user, page),
    )


# --- Création et modification -------------------------------------------------


def _text_input(
    custom_id: str,
    label: str,
    *,
    placeholder: str | None = None,
    value: str | None = None,
    required: bool = True,
    style: discord.TextStyle = discord.TextStyle.short,
    max_length: int = 100,
) -> discord.ui.TextInput:
    text = discord.ui.TextInput(
        custom_id=custom_id,
        label=label,
        placeholder=placeholder,
        required=required,
        style=style,
        max_length=max_length,
    )
    if value:
        text.default = value[:max_length]
    return text


def _clean(value: str | None, fallback: str) -> str:
    text = (value or "").strip()
    return text or fallback


def parse_entries(value: str | None) -> list[str]:
    """Découpe un champ « une entrée par ligne (ou virgule) »."""
    if not value:
        return []
    entries: list[str] = []
    for raw in value.replace(",", "\n").splitlines():
        entry = raw.strip()
        if entry:
            entries.append(entry[:60])
    return entries[:10]


class IdentityModal(BaseModal):
    """Première étape : identité, âge, race, grade et alignement."""

    def __init__(self, mode: str, profile: Profile | None = None, guild_id: int | None = None):
        super().__init__(
            title="Créer ton profil — 1/2" if mode == "create" else "Modifier ton profil — 1/2",
            timeout=VIEW_TIMEOUT,
        )
        self.mode = mode
        self.guild_id = guild_id
        existing = profile or Profile()

        self.character_name = _text_input(
            "characterName",
            "Identité (nom du personnage)",
            placeholder="Ex. Zuruï",
            value=existing.name if profile else None,
            max_length=60,
        )
        self.age = _text_input(
            "age",
            "Âge",
            placeholder="Ex. 1 an, 17 ans…",
            value=existing.age if profile else None,
            max_length=40,
        )
        self.character_race = _text_input(
            "race",
            "Race",
            placeholder="Ex. Humain, Fléau…",
            value=existing.race if profile else None,
            max_length=40,
        )
        self.grade = _text_input(
            "grade",
            "Grade",
            placeholder="Ex. Spécial, Étudiant…",
            value=existing.grade if profile else None,
            max_length=60,
        )
        self.alignment = _text_input(
            "alignment",
            "Alignement",
            placeholder="Ex. Chaotique mauvais",
            value=existing.alignment if profile else None,
            max_length=60,
        )

        self.add_item(self.character_name)
        self.add_item(self.age)
        self.add_item(self.character_race)
        self.add_item(self.grade)
        self.add_item(self.alignment)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        guild_id = interaction.guild_id or self.guild_id
        existing = (
            await get_profile(guild_id, interaction.user.id) if self.mode == "edit" else None
        )

        sessions.remember_profile(
            guild_id,
            interaction.user.id,
            self.mode,
            {
                "name": _clean(self.character_name.value, "Personnage sans nom"),
                "age": _clean(self.age.value, "Non renseigné"),
                "race": _clean(self.character_race.value, "Race inconnue"),
                "grade": _clean(self.grade.value, "Grade non défini"),
                "alignment": _clean(self.alignment.value, "Alignement inconnu"),
            },
            existing,
        )

        await interaction.response.send_message(
            embeds=[
                theme.notice_embed(
                    theme.SECTION_PROFIL,
                    "succes",
                    "Étape **1 / 2** enregistrée. Passe aux traits, défauts et citation.",
                    interaction.guild,
                    footer="✦ Étape 2 sur 2",
                )
            ],
            view=ContinueView(self.mode),
            ephemeral=True,
        )


class TraitsModal(BaseModal):
    """Seconde étape : rôle, citation, traits et défauts."""

    def __init__(self, mode: str, profile: Profile | None = None):
        super().__init__(
            title="Créer ton profil — 2/2" if mode == "create" else "Modifier ton profil — 2/2",
            timeout=VIEW_TIMEOUT,
        )
        self.mode = mode
        existing = profile or Profile()

        self.role = _text_input(
            "role",
            "Rôle",
            placeholder="Ex. Fléaux, Sorcier de Tokyo…",
            value=existing.role if profile else None,
            max_length=60,
        )
        self.quote = _text_input(
            "quote",
            "Citation personnelle",
            placeholder="Une phrase qui représente ton personnage",
            value=existing.quote if profile else None,
            required=False,
            style=discord.TextStyle.paragraph,
            max_length=300,
        )
        self.traits = _text_input(
            "traits",
            "Traits (facultatif)",
            placeholder="Une entrée par ligne",
            value="\n".join(existing.traits) if profile else None,
            required=False,
            style=discord.TextStyle.paragraph,
            max_length=500,
        )
        self.flaws = _text_input(
            "flaws",
            "Défauts (facultatif)",
            placeholder="Une entrée par ligne",
            value="\n".join(existing.flaws) if profile else None,
            required=False,
            style=discord.TextStyle.paragraph,
            max_length=500,
        )

        self.add_item(self.role)
        self.add_item(self.quote)
        self.add_item(self.traits)
        self.add_item(self.flaws)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        pending = sessions.get_pending_profile(interaction.guild_id, interaction.user.id)
        if pending is None or pending.mode != self.mode:
            await interaction.response.send_message(
                embed=theme.notice_embed(
                    theme.SECTION_ALERTE,
                    "alerte",
                    "Cette création a expiré. Relance `/profil creer`.",
                    interaction.guild,
                ),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        sessions.clear_pending_profile(interaction.guild_id, interaction.user.id)

        previous = pending.existing or Profile()
        previous.name = pending.identity["name"]
        previous.age = pending.identity["age"]
        previous.race = pending.identity["race"]
        previous.grade = pending.identity["grade"]
        previous.alignment = pending.identity["alignment"]
        previous.role = _clean(self.role.value, "Rôle non défini")
        previous.quote = (self.quote.value or "").strip()[:300]
        previous.traits = parse_entries(self.traits.value)
        previous.flaws = parse_entries(self.flaws.value)
        if not previous.stats:
            previous.stats = dict(DEFAULT_STATS)
        previous.created_at = previous.created_at or now_iso()
        previous.touch()

        profile = await save_profile(interaction.guild_id, interaction.user.id, previous)

        embeds, files = await build_profile_message(
            profile,
            interaction.user,
            "global",
            interaction.guild,
            interaction.guild_id,
        )
        await interaction.edit_original_response(
            content=(
                f"{theme.emoji('succes', interaction.guild)} Ton profil a été créé ! "
                "Ajoute ton image avec `/profil image`."
                if self.mode == "create"
                else f"{theme.emoji('succes', interaction.guild)} Ton profil a été modifié."
            ),
            embeds=embeds,
            attachments=files,
            view=ProfileView(interaction.guild_id, interaction.user, "global"),
        )


class ContinueView(BaseView):
    """Bouton qui ouvre la seconde modale."""

    def __init__(self, mode: str):
        super().__init__(timeout=VIEW_TIMEOUT)
        self.mode = mode
        self.continue_button.label = "Continuer vers traits et défauts"
        self.continue_button.emoji = theme.partial_emoji("continuer", None)

    @discord.ui.button(label="Continuer", style=discord.ButtonStyle.primary, custom_id="profil:continue:traits")
    async def continue_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        pending = sessions.get_pending_profile(interaction.guild_id, interaction.user.id)
        if pending is None or pending.mode != self.mode:
            await interaction.response.send_message(
                embed=theme.notice_embed(
                    theme.SECTION_ALERTE,
                    "alerte",
                    "Cette création a expiré. Relance `/profil creer`.",
                    interaction.guild,
                ),
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(TraitsModal(self.mode, pending.existing))


async def open_identity_modal(interaction: discord.Interaction, mode: str) -> None:
    """Ouvre la première modale de création ou de modification."""
    existing = await get_profile(interaction.guild_id, interaction.user.id) if mode == "edit" else None
    await interaction.response.send_modal(IdentityModal(mode, existing, interaction.guild_id))


# --- Gestion de l’image -------------------------------------------------------


async def set_profile_image(
    interaction: discord.Interaction,
    attachment: discord.Attachment | None = None,
) -> None:
    """Enregistre localement l’image envoyée par le joueur."""
    # On accuse réception avant de télécharger : une image volumineuse peut
    # dépasser les 3 s du délai d’interaction (erreur 10062).
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True)

    profile = await get_profile(interaction.guild_id, interaction.user.id)
    if profile is None:
        await interaction.followup.send(
            embed=theme.notice_embed(
                theme.SECTION_ALERTE,
                "alerte",
                "Crée d’abord ton profil avec `/profil creer`, puis ajoute ton image.",
                interaction.guild,
            ),
            ephemeral=True,
        )
        return

    attachment = attachment or interaction.options.get_attachment("fichier")
    if attachment is None:
        await interaction.followup.send(
            embed=theme.notice_embed(theme.SECTION_ERREUR, "erreur", "Aucun fichier reçu.", interaction.guild),
            ephemeral=True,
        )
        return

    try:
        filename, _path = await images.save_image(interaction.guild_id, interaction.user.id, attachment)
    except (ValueError, OSError, discord.HTTPException) as error:
        reason = (
            "Le fichier est trop volumineux (8 Mo maximum)."
            if "volumineux" in str(error)
            else "Le fichier doit être une image PNG, JPG, WEBP ou un GIF."
        )
        logger.warning("Image refusée pour %s : %s", interaction.user.id, error)
        await interaction.followup.send(
            embed=theme.notice_embed(theme.SECTION_ERREUR, "erreur", reason, interaction.guild),
            ephemeral=True,
        )
        return

    profile.image_file = filename
    profile.image_name = attachment.filename
    profile.image_url = None
    profile.touch()
    await save_profile(interaction.guild_id, interaction.user.id, profile)

    await send_profile(
        interaction,
        interaction.user,
        "global",
        ephemeral=True,
        content=f"{theme.emoji('succes', interaction.guild)} Image enregistrée sur ton profil.",
    )


# --- Réinitialisation ---------------------------------------------------------


class ResetView(BaseView):
    """Confirmation en deux boutons avant une réinitialisation."""

    def __init__(self, owner_id: int, on_confirm):
        super().__init__(timeout=VIEW_TIMEOUT)
        self.owner_id = owner_id
        self.on_confirm = on_confirm
        self.confirm_button.emoji = theme.partial_emoji("valider", None)
        self.cancel_button.emoji = theme.partial_emoji("annuler", None)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message(
            embed=theme.notice_embed(theme.SECTION_ERREUR, "erreur", "Cette confirmation ne t’appartient pas."),
            ephemeral=True,
        )
        return False

    @discord.ui.button(label="Oui, réinitialiser", style=discord.ButtonStyle.danger, custom_id="profil:reset:confirm")
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.on_confirm(interaction)

    @discord.ui.button(label="Annuler", style=discord.ButtonStyle.secondary, custom_id="profil:reset:cancel")
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        sessions.clear_pending_reset(interaction.guild_id, interaction.user.id)
        await interaction.response.edit_message(
            content=None,
            embeds=[
                theme.notice_embed(
                    theme.SECTION_NEUTRE,
                    "annuler",
                    "Réinitialisation annulée.",
                    interaction.guild,
                )
            ],
            view=None,
        )


async def apply_reset(interaction: discord.Interaction) -> None:
    """Applique la réinitialisation confirmée."""
    pending = sessions.get_pending_reset(interaction.guild_id, interaction.user.id)
    if pending is None:
        await interaction.response.edit_message(
            content=None,
            embeds=[
                theme.notice_embed(
                    theme.SECTION_ALERTE,
                    "alerte",
                    "Cette demande a expiré. Relance `/profil reset`.",
                    interaction.guild,
                )
            ],
            view=None,
        )
        return

    sessions.clear_pending_reset(interaction.guild_id, interaction.user.id)

    if pending.reset_type == "profil":
        await delete_profile(interaction.guild_id, pending.target_user_id)
        images.delete_image(interaction.guild_id, pending.target_user_id)
        await interaction.response.edit_message(
            content=None,
            embeds=[
                theme.notice_embed(
                    theme.SECTION_SUCCES,
                    "succes",
                    f"Le profil de <@{pending.target_user_id}> a été supprimé.",
                    interaction.guild,
                )
            ],
            view=None,
        )
        return

    profile = await get_profile(interaction.guild_id, pending.target_user_id)
    if profile is None:
        await interaction.response.edit_message(
            content=None,
            embeds=[
                theme.notice_embed(
                    theme.SECTION_ERREUR,
                    "erreur",
                    "Ce profil n’existe plus.",
                    interaction.guild,
                )
            ],
            view=None,
        )
        return

    if pending.reset_type == "stats":
        profile.stats = dict(DEFAULT_STATS)
        profile.stat_points = 0
        profile.touch()
        await save_profile(interaction.guild_id, pending.target_user_id, profile)

        await interaction.response.defer()
        try:
            target_user = await interaction.client.fetch_user(pending.target_user_id)
        except discord.HTTPException:  # pragma: no cover - dépend de l’API
            target_user = interaction.user
        embeds, files = await build_profile_message(
            profile,
            target_user,
            "stats",
            interaction.guild,
            interaction.guild_id,
        )
        await interaction.edit_original_response(
            content=f"{theme.emoji('succes', interaction.guild)} Les **statistiques** de "
            f"<@{pending.target_user_id}> ont été réinitialisées.",
            embeds=embeds,
            attachments=files,
            view=ProfileView(interaction.guild_id, target_user, "stats"),
        )
        return

    profile.unlocked_skills = []
    profile.experience = 0
    profile.touch()
    await save_profile(interaction.guild_id, pending.target_user_id, profile)
    await interaction.response.edit_message(
        content=None,
        embeds=[
            theme.notice_embed(
                theme.SECTION_SUCCES,
                "succes",
                f"Les **compétences** de <@{pending.target_user_id}> ont été réinitialisées (XP remise à 0).",
                interaction.guild,
            )
        ],
        view=None,
    )
