"""Demandes d’XP : formulaire joueur et validation par le staff.

Le point délicat est la durée de vie des boutons. Un embed posté dans le salon
du staff doit rester cliquable une heure ou deux plus tard, et même après un
redémarrage du bot (l’hébergeur redéploie et redémarre à chaque mise à jour).
Trois pièces s’en chargent :

1. `XPDecisionView` porte `timeout=None` : Discord ne désactive pas les boutons
   au bout des quinze minutes habituelles.
2. Ses `custom_id` sont FIXES et la vue est réenregistrée au démarrage via
   `bot.add_view(...)` (voir `main.py`) : après un redémarrage, le clic est
   routé vers cette vue au lieu de répondre « interaction échouée ».
3. La demande vit sur le disque (voir `storage.requests`), et non dans la vue :
   au clic, on la retrouve par l’identifiant du message cliqué, même longtemps
   après. C’est ce qui permet de créditer le bon joueur du bon montant.
"""

from __future__ import annotations

import logging

import discord

from jjkbot import permissions, theme
from jjkbot.content import xp as xp_rules
from jjkbot.storage import requests as requests_module
from jjkbot.storage import settings
from jjkbot.storage.profiles import get_profile, save_profile
from jjkbot.views.base import BaseModal, BaseView

logger = logging.getLogger(__name__)

# Identifiants fixes : c’est ce qui rend la vue persistante. Ne jamais les
# changer sans accepter que les messages déjà postés cessent de répondre.
APPROVE_CUSTOM_ID = "xp:approuver"
DECLINE_CUSTOM_ID = "xp:decliner"

# Le type d’interaction se choisit AVANT la modale. Discord n’accepte que des
# champs texte (type 4) dans une modale : un menu déroulant (type 3) y déclenche
# une erreur 50035 « Invalid Form Body ». Le menu vit donc dans une vue normale.
TYPE_SELECT_CUSTOM_ID = "xp:type"

FOOTER = "Jujutsu Kaisen RP • Demandes d’XP"


# --- Rendu --------------------------------------------------------------------


def build_request_embed(
    request: requests_module.XPRequest,
    guild: discord.Guild | None = None,
) -> discord.Embed:
    """Embed lu par le staff : tout ce qu’il faut pour trancher d’un coup d’œil."""
    embed = discord.Embed(
        colour=theme.color(theme.SECTION_DEMANDES),
        description=theme.blocks(
            theme.title(
                "demande_xp",
                "Demande d’XP",
                guild,
                suffix=f" : `{request.id}`",
            ),
            theme.highlight("xp", f"XP demandée — **{request.amount}**", guild),
            theme.entry("categorie", "Type d’interaction", xp_rules.label_of(request.interaction_type), guild=guild),
            theme.mention_entry("profil", "Joueur", request.user_id, guild, name=request.user_name),
            theme.divider(),
            theme.field_label("aide", "Description de la scène", guild),
            request.description or "*Aucune description fournie.*",
            theme.field_label("fleche", "Salon d’origine", guild),
            request.channel_link or "*Non précisé.*",
        ),
    )
    embed.set_footer(text=f"{FOOTER} • {request.created_at}")
    return embed


def build_decision_embed(
    request: requests_module.XPRequest,
    guild: discord.Guild | None = None,
    *,
    credited: bool = True,
) -> discord.Embed:
    """Embed d’une demande tranchée : plus de boutons, décision lisible."""
    approved = request.status == requests_module.STATUS_APPROVED
    key = "valider" if approved else "annuler"
    headline = "Demande approuvée" if approved else "Demande déclinée"
    decider = request.decided_by_name or (f"<@{request.decided_by}>" if request.decided_by else "le staff")

    lines = [
        theme.title("demande_xp", f"Demande d’XP — {headline}", guild, suffix=f" : `{request.id}`"),
        f"{theme.emoji(key, guild)} **{headline}** par {decider}.",
        theme.mention_entry("profil", "Joueur", request.user_id, guild),
        theme.entry("categorie", "Type d’interaction", xp_rules.label_of(request.interaction_type), guild=guild),
    ]
    if approved:
        lines.append(theme.entry("xp", "XP créditée", f"{request.amount}", guild=guild))
        if not credited:
            lines.append(
                f"{theme.emoji('alerte', guild)} **XP non créditée** : la fiche du joueur "
                "est introuvable. Ajoute l’XP à la main avec `/competences xp`."
            )
    lines.extend(
        [
            theme.divider(),
            theme.field_label("aide", "Description de la scène", guild),
            request.description or "*Aucune description fournie.*",
        ]
    )

    embed = discord.Embed(
        colour=theme.color(theme.SECTION_SUCCES if approved else theme.SECTION_ERREUR),
        description=theme.blocks(*lines),
    )
    embed.set_footer(text=f"{FOOTER} • {request.decided_at or request.created_at}")
    return embed


# --- Vue persistante (Approuver / Décliner) -----------------------------------


class XPDecisionView(BaseView):
    """Boutons de validation d’une demande d’XP.

    Sans état (`timeout=None` + `custom_id` fixes) : une seule instance,
    réenregistrée au démarrage, sert tous les messages. La demande est retrouvée
    par l’identifiant du message cliqué.
    """

    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Approuver",
        style=discord.ButtonStyle.success,
        custom_id=APPROVE_CUSTOM_ID,
    )
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await _decide(interaction, requests_module.STATUS_APPROVED)

    @discord.ui.button(
        label="Décliner",
        style=discord.ButtonStyle.danger,
        custom_id=DECLINE_CUSTOM_ID,
    )
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await _decide(interaction, requests_module.STATUS_DECLINED)


async def _ephemeral(interaction: discord.Interaction, section: str, key: str, message: str) -> None:
    await interaction.response.send_message(
        embed=theme.notice_embed(section, key, message, interaction.guild),
        ephemeral=True,
    )


async def _decide(interaction: discord.Interaction, status: str) -> None:
    """Traite un clic sur Approuver ou Décliner."""
    # Le clic arrive via une vue persistante : l’auteur est vérifié ICI, jamais
    # à l’affichage (n’importe qui peut voir le salon s’il y est autorisé).
    if not permissions.is_staff(interaction):
        await _ephemeral(interaction, theme.SECTION_ERREUR, "erreur", permissions.STAFF_DENIED_MESSAGE)
        return

    message = interaction.message
    if message is None:  # pragma: no cover - un composant a toujours un message
        await _ephemeral(interaction, theme.SECTION_ERREUR, "erreur", "Message introuvable.")
        return

    request = await requests_module.get_request_by_message(message.id)
    if request is None:
        await _ephemeral(
            interaction,
            theme.SECTION_ALERTE,
            "alerte",
            "Cette demande est introuvable (fichier de données perdu ?).",
        )
        return

    decided, applied = await requests_module.decide(
        request.id,
        status,
        staff_id=interaction.user.id,
        staff_name=interaction.user.display_name,
    )
    if decided is None:
        await _ephemeral(interaction, theme.SECTION_ALERTE, "alerte", "Cette demande n’existe plus.")
        return
    if not applied:
        # Un autre membre du staff a tranché entre l’affichage et le clic (ou la
        # demande était déjà close) : on ne crédite surtout pas l’XP une 2e fois.
        decider = decided.decided_by_name or "le staff"
        state = requests_module.STATUS_LABELS.get(decided.status, decided.status).lower()
        await _ephemeral(
            interaction,
            theme.SECTION_ALERTE,
            "alerte",
            f"Cette demande a déjà été {state} par {decider}.",
        )
        return

    credited = True
    if status == requests_module.STATUS_APPROVED:
        credited = await _credit_xp(decided)

    embed = build_decision_embed(decided, interaction.guild, credited=credited)
    await interaction.response.edit_message(embed=embed, view=None)

    if status == requests_module.STATUS_APPROVED:
        await _notify_player(interaction, decided, credited=credited)


async def _credit_xp(request: requests_module.XPRequest) -> bool:
    """Crédite l’XP au joueur. Renvoie False si sa fiche est introuvable."""
    profile = await get_profile(request.guild_id, request.user_id)
    if profile is None:
        logger.warning(
            "Demande %s approuvée mais fiche du joueur %s introuvable : XP non créditée.",
            request.id,
            request.user_id,
        )
        return False

    profile.experience += request.amount
    profile.touch()
    await save_profile(request.guild_id, request.user_id, profile)
    return True


async def _notify_player(
    interaction: discord.Interaction,
    request: requests_module.XPRequest,
    *,
    credited: bool,
) -> None:
    """Prévient le joueur en message privé (au mieux : ses MP peuvent être fermés)."""
    client = interaction.client
    try:
        player = client.get_user(request.user_id) or await client.fetch_user(request.user_id)
    except discord.HTTPException:  # pragma: no cover - dépend de l’API
        logger.debug("Joueur %s introuvable pour la notification de demande.", request.user_id)
        return

    if credited:
        message = (
            f"{theme.emoji('succes')} Ta demande d’XP **{request.id}** a été approuvée : "
            f"**+{request.amount} XP**."
        )
    else:
        message = (
            f"{theme.emoji('succes')} Ta demande d’XP **{request.id}** a été approuvée, "
            "mais l’XP n’a pas pu être créditée (fiche introuvable) — le staff s’en occupe."
        )

    try:
        await player.send(embed=theme.notice_embed(theme.SECTION_DEMANDES, "demande_xp", message, footer=FOOTER))
    except discord.HTTPException:  # pragma: no cover - MP fermés
        logger.debug("MP impossibles pour le joueur %s.", request.user_id)


# --- Formulaire joueur --------------------------------------------------------


class XPDemandModal(BaseModal):
    """Formulaire de demande d’XP, ouvert APRÈS le choix du type d’interaction.

    La modale ne contient que des champs texte (`TextInput`, type 4) : c’est la
    seule famille de composants que Discord accepte ici. Le type est donc choisi
    en amont, par le menu de `XPInteractionTypeView`.
    """

    def __init__(self, guild: discord.Guild | None, interaction_type: str):
        super().__init__(title="Demande d’XP")
        self.guild = guild
        self.interaction_type = interaction_type

        self.amount = discord.ui.TextInput(
            label="XP attendue",
            placeholder="Un nombre entier, par exemple 12",
            required=True,
            max_length=6,
        )
        self.add_item(self.amount)

        self.scene = discord.ui.TextInput(
            label="Description de la scène",
            style=discord.TextStyle.paragraph,
            placeholder="Quelques lignes : contexte, ce qui s’est passé, enjeu.",
            required=True,
            max_length=900,
        )
        self.add_item(self.scene)

        self.channel_link = discord.ui.TextInput(
            label="Lien du salon où ça s’est passé",
            placeholder="Colle le lien du salon ou sa mention (#salon)",
            required=False,
            max_length=200,
        )
        self.add_item(self.channel_link)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        guild_id = interaction.guild_id
        if guild_id is None:  # pragma: no cover - la commande est guild_only
            await _ephemeral(interaction, theme.SECTION_ERREUR, "erreur", "Serveur introuvable.")
            return

        channel = await _staff_channel(interaction, guild_id)
        if channel is None:
            await _ephemeral(
                interaction,
                theme.SECTION_ALERTE,
                "alerte",
                "Aucun salon de demandes n’est configuré sur ce serveur. "
                "Un administrateur doit le définir avec `/xp salon`.",
            )
            return

        raw_amount = str(self.amount.value).strip()
        if not raw_amount.isdigit():
            await _ephemeral(
                interaction,
                theme.SECTION_ERREUR,
                "erreur",
                "L’XP attendue doit être un **nombre entier** (sans décimales ni texte).",
            )
            return
        amount = int(raw_amount)
        if not (xp_rules.MIN_AMOUNT <= amount <= xp_rules.MAX_AMOUNT):
            await _ephemeral(
                interaction,
                theme.SECTION_ERREUR,
                "erreur",
                f"L’XP attendue doit être comprise entre {xp_rules.MIN_AMOUNT} "
                f"et {xp_rules.MAX_AMOUNT}.",
            )
            return

        request = await requests_module.create_request(
            guild_id,
            interaction.user.id,
            user_name=interaction.user.display_name,
            interaction_type=self.interaction_type,
            amount=amount,
            description=str(self.scene.value).strip(),
            channel_link=str(self.channel_link.value or "").strip(),
        )

        try:
            message = await channel.send(embed=build_request_embed(request, interaction.guild), view=XPDecisionView())
        except discord.HTTPException:
            logger.exception("Envoi de la demande %s dans le salon staff impossible.", request.id)
            await _ephemeral(
                interaction,
                theme.SECTION_ERREUR,
                "erreur",
                "Impossible d’envoyer la demande au staff (salon inaccessible). Réessaie plus tard.",
            )
            return

        await requests_module.attach_message(request.id, channel.id, message.id)

        await _ephemeral(
            interaction,
            theme.SECTION_SUCCES,
            "demande_xp",
            f"Ta demande **{request.id}** a été transmise au staff "
            f"({amount} XP attendus). Tu seras prévenu en message privé de la décision.",
        )


class XPInteractionTypeSelect(discord.ui.Select):
    """Menu du type d’interaction, affiché AVANT la modale.

    Le choix de l’utilisateur ouvre directement le formulaire.
    """

    def __init__(self, guild: discord.Guild | None) -> None:
        super().__init__(
            custom_id=TYPE_SELECT_CUSTOM_ID,
            placeholder="Type d’interaction",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(label=item.label, value=item.id)
                for item in xp_rules.INTERACTION_TYPES
            ],
        )
        self.guild = guild

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(XPDemandModal(self.guild, self.values[0]))


class XPInteractionTypeView(BaseView):
    """Vue éphémère ouverte par `/xp demande` : on y choisit le type d’interaction.

    Une fois le type retenu, `XPInteractionTypeSelect` ouvre la modale. Séparer
    les deux étapes est une contrainte de l’API, pas un choix de design.
    """

    def __init__(self, guild: discord.Guild | None) -> None:
        super().__init__(timeout=180)
        self.add_item(XPInteractionTypeSelect(guild))


async def _staff_channel(interaction: discord.Interaction, guild_id: int) -> discord.abc.Messageable | None:
    """Salon des demandes du serveur, s’il est configuré et accessible."""
    channel_id = await settings.get_xp_channel(guild_id)
    if channel_id is None:
        return None

    guild = interaction.guild
    channel = guild.get_channel(channel_id) if guild is not None else None
    if channel is None:
        try:
            channel = await interaction.client.fetch_channel(channel_id)
        except discord.HTTPException:
            logger.warning("Salon de demandes %s introuvable sur le serveur %s.", channel_id, guild_id)
            return None

    return channel if isinstance(channel, discord.abc.Messageable) else None
