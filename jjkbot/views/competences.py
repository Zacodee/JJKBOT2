"""Rendu et vues interactives de l’arbre de compétences."""

from __future__ import annotations

import logging

import discord

from jjkbot import theme
from jjkbot.content.skill_tree import (
    BRANCHES,
    SKILL_TREE,
    Skill,
    can_unlock_skill,
    get_missing_prerequisites,
    get_skill,
    get_skills_for_branch,
)
from jjkbot.storage.profiles import Profile, get_profile, save_profile
from jjkbot.views.base import BaseView

logger = logging.getLogger(__name__)

VIEW_TIMEOUT = 15 * 60
MAX_SELECT_OPTIONS = 25


def _truncate(text: str, length: int = 100) -> str:
    return text if len(text) <= length else f"{text[: length - 1]}…"


def _skill_status(profile: Profile, skill: Skill) -> tuple[str, bool, bool]:
    """Renvoie (clé d’emoji, débloquée, achetable) pour un palier."""
    unlocked = skill.id in profile.unlocked_skills
    available = can_unlock_skill(profile, skill)
    if unlocked:
        return "debloque", True, False
    if available:
        return "disponible", False, True
    return "verrouille", False, False


# --- Embeds -------------------------------------------------------------------


def build_overview_embed(
    profile: Profile,
    target_user: discord.abc.User,
    guild: discord.Guild | None = None,
) -> discord.Embed:
    """Vue d’ensemble : progression par catégorie dans un tableau monospace."""
    rows = []
    for branch in BRANCHES:
        skills = get_skills_for_branch(branch)
        unlocked = sum(1 for skill in skills if skill.id in profile.unlocked_skills)
        rows.append(
            (
                branch,
                f"{unlocked}/{len(skills)}",
                theme.progress_bar(unlocked, len(skills)),
            )
        )

    embed = discord.Embed(
        colour=theme.color(theme.SECTION_COMPETENCES),
        description=theme.blocks(
            theme.title("competences", "Compétences", guild, suffix=f" : {target_user.display_name}"),
            theme.highlight("xp", f"XP disponible — **{profile.experience}**", guild),
            theme.highlight(
                "debloque",
                f"Compétences débloquées — **{len(profile.unlocked_skills)} / {len(SKILL_TREE)}**",
                guild,
            ),
            theme.divider(),
            theme.mono_table(rows),
        ),
    )
    embed.set_footer(text="✦ Choisis une catégorie dans le menu pour afficher ses paliers.")
    embed.set_author(name=target_user.display_name, icon_url=target_user.display_avatar.url)
    return embed


def build_category_embed(
    profile: Profile,
    target_user: discord.abc.User,
    branch: str,
    guild: discord.Guild | None = None,
) -> discord.Embed:
    """Détail des paliers d’une catégorie."""
    skills = get_skills_for_branch(branch)
    unlocked = sum(1 for skill in skills if skill.id in profile.unlocked_skills)

    lines = []
    for skill in skills:
        key, _is_unlocked, _is_available = _skill_status(profile, skill)
        line = theme.entry(key, skill.label, f"{skill.cost} XP", guild=guild)
        missing = get_missing_prerequisites(skill.id, profile.unlocked_skills)
        if missing and skill.id not in profile.unlocked_skills:
            names = ", ".join(prerequisite.label for prerequisite in missing)
            line += f"\n　　↳ *Prérequis : {_truncate(names, 80)}*"
        lines.append(line)

    embed = discord.Embed(
        colour=theme.color(theme.SECTION_COMPETENCES),
        description=theme.blocks(
            theme.title("competences", branch, guild),
            theme.highlight("xp", f"XP disponible — **{profile.experience}**", guild),
            theme.highlight(
                "progression",
                f"Progression — **{unlocked} / {len(skills)}** {theme.progress_bar(unlocked, len(skills))}",
                guild,
            ),
            theme.divider(),
            "\n".join(lines),
        ),
    )
    embed.set_footer(text="✦ Prérequis contrôlés automatiquement par le bot.")
    embed.set_author(name=target_user.display_name, icon_url=target_user.display_avatar.url)
    return embed


def _basket_lines(profile: Profile, skill_ids: list[str], guild: discord.Guild | None) -> tuple[str, int, list[Skill]]:
    skills = [skill for skill in (get_skill(skill_id) for skill_id in skill_ids) if skill is not None]
    total = sum(skill.cost for skill in skills)
    lines = [theme.entry("panier", skill.label, f"{skill.cost} XP", guild=guild) for skill in skills]
    return "\n".join(lines), total, skills


def build_shop_root_embed(
    profile: Profile,
    guild: discord.Guild | None = None,
    message: str | None = None,
    basket: list[str] = (),
) -> discord.Embed:
    """Écran d’accueil de la boutique de compétences."""
    available_branches = [
        branch for branch in BRANCHES if any(can_unlock_skill(profile, skill) for skill in get_skills_for_branch(branch))
    ]

    description = theme.blocks(
        message,
        theme.highlight("xp", f"XP disponible — **{profile.experience}**", guild),
    )

    if available_branches:
        description = theme.blocks(
            description,
            f"{theme.emoji('categorie', guild)} Choisis une catégorie pour sélectionner des compétences.",
        )
    else:
        description = theme.blocks(
            description,
            f"{theme.emoji('verrouille', guild)} Aucune compétence n’est achetable pour le moment. "
            "Vérifie tes prérequis ou demande de l’XP au staff.",
        )

    if basket:
        basket_lines, total, _skills = _basket_lines(profile, list(basket), guild)
        description = theme.blocks(
            description,
            theme.divider(),
            theme.highlight("panier", f"Panier en cours — **{total} XP**", guild),
            basket_lines,
        )

    embed = discord.Embed(
        colour=theme.color(theme.SECTION_PANIER),
        description=theme.blocks(
            theme.title("panier", "Panier de compétences", guild),
            description,
        ),
    )
    embed.set_footer(text="✦ La confirmation recalcule le coût et les prérequis avant l’achat.")
    return embed


def build_shop_category_embed(
    profile: Profile,
    branch: str,
    guild: discord.Guild | None = None,
    basket: list[str] = (),
) -> discord.Embed:
    """Sélection des compétences d’une catégorie."""
    available = [skill for skill in get_skills_for_branch(branch) if can_unlock_skill(profile, skill)]
    lines = [theme.entry("disponible", skill.label, f"{skill.cost} XP", guild=guild) for skill in available]

    description = theme.blocks(
        f"{theme.emoji('panier', guild)} Sélectionne une ou plusieurs compétences, puis confirme le panier.",
        theme.highlight("xp", f"XP disponible — **{profile.experience}**", guild),
    )
    if lines:
        description = theme.blocks(description, theme.divider(), "\n".join(lines))
    else:
        description = theme.blocks(
            description,
            f"{theme.emoji('verrouille', guild)} Aucune compétence de cette catégorie n’est disponible.",
        )

    if basket:
        _basket_lines_text, total, _skills = _basket_lines(profile, list(basket), guild)
        description = theme.blocks(
            description,
            theme.highlight("panier", f"Panier en cours — **{total} XP**", guild),
        )

    embed = discord.Embed(
        colour=theme.color(theme.SECTION_PANIER),
        description=theme.blocks(
            theme.title("panier", branch, guild),
            description,
        ),
    )
    embed.set_footer(text="✦ Les prérequis sont revérifiés à la confirmation.")
    return embed


def build_basket_embed(
    profile: Profile,
    skill_ids: list[str],
    guild: discord.Guild | None = None,
) -> discord.Embed:
    """Confirmation du panier."""
    basket_lines, total, _skills = _basket_lines(profile, skill_ids, guild)
    affordable = profile.experience >= total

    embed = discord.Embed(
        colour=theme.color(theme.SECTION_PANIER),
        description=theme.blocks(
            theme.title("panier", "Confirmation du panier", guild),
            theme.highlight("xp", f"XP disponible — **{profile.experience}**", guild),
            theme.highlight("points", f"Coût total — **{total} XP**", guild),
            f"{theme.emoji('valider' if affordable else 'erreur', guild)} "
            + ("Le panier est finançable." if affordable else "Tu n’as pas assez d’XP."),
            theme.divider(),
            basket_lines,
        ),
    )
    embed.set_footer(text="✦ L’achat est définitif une fois confirmé.")
    return embed


# --- Composants ---------------------------------------------------------------


class ActionButton(discord.ui.Button):
    """Bouton générique branché sur une action de la vue."""

    def __init__(self, *, action: str, label: str, style: discord.ButtonStyle, emoji_key: str | None = None):
        super().__init__(
            label=label,
            style=style,
            emoji=theme.partial_emoji(emoji_key) if emoji_key else None,
        )
        self.action = action

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if isinstance(view, ShopView):
            await view.handle_action(interaction, self.action)


class BranchSelect(discord.ui.Select):
    """Menu de sélection d’une catégorie de compétences."""

    def __init__(self, view, *, placeholder: str, branches: list[str]):
        self._owner_view = view
        super().__init__(
            placeholder=placeholder,
            options=[
                discord.SelectOption(label=_truncate(branch, 100), value=branch)
                for branch in branches[:MAX_SELECT_OPTIONS]
            ],
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        await self._owner_view.handle_branch(interaction, self.values[0])


class SkillSelect(discord.ui.Select):
    """Menu de sélection de plusieurs compétences d’une catégorie."""

    def __init__(self, view, *, branch: str, skills: list[Skill], guild=None):
        self._owner_view = view
        self.branch = branch
        options = [
            discord.SelectOption(
                label=_truncate(skill.label, 100),
                value=skill.id,
                description=_truncate(f"{skill.cost} XP", 100),
                emoji=theme.partial_emoji("disponible", guild),
            )
            for skill in skills[:MAX_SELECT_OPTIONS]
        ]
        super().__init__(
            placeholder="Sélectionner des compétences",
            options=options,
            min_values=1,
            max_values=len(options) or 1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        await self._owner_view.handle_skills(interaction, self.branch, self.values)


# --- Vues ---------------------------------------------------------------------


class OverviewView(BaseView):
    """Navigation dans l’arbre de compétences d’un joueur."""

    def __init__(self, guild_id: int, target_user: discord.abc.User, selected_branch: str | None = None):
        super().__init__(timeout=VIEW_TIMEOUT)
        self.guild_id = int(guild_id)
        self.target_user = target_user
        self.selected_branch = selected_branch
        self.add_item(
            BranchSelect(
                self,
                placeholder=selected_branch or "Choisir une catégorie",
                branches=list(BRANCHES),
            )
        )

    async def handle_branch(self, interaction: discord.Interaction, branch: str) -> None:
        if branch not in BRANCHES:
            return

        profile = await get_profile(self.guild_id, self.target_user.id)
        if profile is None:
            await interaction.response.edit_message(
                content="Ce profil n’existe plus.", embeds=[], view=None
            )
            return

        embed = build_category_embed(profile, self.target_user, branch, interaction.guild)
        await interaction.response.edit_message(
            embeds=[embed],
            view=OverviewView(self.guild_id, self.target_user, branch),
        )

class ContinueShopView(BaseView):
    """Proposé après un achat pour enchaîner sur de nouveaux achats."""

    def __init__(self, guild_id: int, user_id: int):
        super().__init__(timeout=VIEW_TIMEOUT)
        self.guild_id = int(guild_id)
        self.user_id = int(user_id)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.user_id:
            return True
        await interaction.response.send_message(
            embed=theme.notice_embed(
                theme.SECTION_ERREUR, "erreur", "Ce panier appartient à un autre joueur."
            ),
            ephemeral=True,
        )
        return False

    @discord.ui.button(label="Continuer les achats", style=discord.ButtonStyle.primary)
    async def continue_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        profile = await get_profile(self.guild_id, self.user_id)
        if profile is None:
            await interaction.response.edit_message(
                content="Ton profil n’existe plus.", embeds=[], view=None
            )
            return

        view = ShopView(self.guild_id, self.user_id, profile)
        await interaction.response.edit_message(
            content=None,
            embeds=[build_shop_root_embed(profile, interaction.guild, basket=view.basket)],
            view=view,
        )


class ShopView(BaseView):
    """Parcours d’achat : catégorie, sélection, panier, confirmation."""

    def __init__(self, guild_id: int, user_id: int, profile: Profile):
        super().__init__(timeout=VIEW_TIMEOUT)
        self.guild_id = int(guild_id)
        self.user_id = int(user_id)
        self.profile = profile
        self.basket: list[str] = []
        self.branch: str | None = None
        self.step = "root"
        self.message: str | None = None
        self.render()

    # -- Sécurité ---------------------------------------------------------

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.user_id:
            return True
        await interaction.response.send_message(
            embed=theme.notice_embed(
                theme.SECTION_ERREUR, "erreur", "Ce panier appartient à un autre joueur."
            ),
            ephemeral=True,
        )
        return False

    # -- Rendu ------------------------------------------------------------

    def available_branches(self) -> list[str]:
        return [
            branch
            for branch in BRANCHES
            if any(
                can_unlock_skill(self.profile, skill) and skill.id not in self.basket
                for skill in get_skills_for_branch(branch)
            )
        ]

    def render(self) -> None:
        """Reconstruit les composants selon l’étape courante."""
        self.clear_items()

        if self.step == "category" and self.branch:
            skills = [
                skill
                for skill in get_skills_for_branch(self.branch)
                if can_unlock_skill(self.profile, skill) and skill.id not in self.basket
            ]
            if skills:
                self.add_item(SkillSelect(self, branch=self.branch, skills=skills))
        elif self.step == "root":
            branches = self.available_branches()
            if branches:
                self.add_item(
                    BranchSelect(self, placeholder="Choisir une catégorie", branches=branches)
                )

        if self.basket:
            self.add_item(
                ActionButton(
                    action="confirm",
                    label="Confirmer l’achat",
                    style=discord.ButtonStyle.success,
                    emoji_key="valider",
                )
            )
            if self.available_branches():
                self.add_item(
                    ActionButton(
                        action="add",
                        label="Ajouter une catégorie",
                        style=discord.ButtonStyle.primary,
                        emoji_key="categorie",
                    )
                )
            self.add_item(
                ActionButton(action="cancel", label="Annuler", style=discord.ButtonStyle.secondary, emoji_key="annuler")
            )

    def build_embeds(self, guild) -> list[discord.Embed]:
        if self.step == "category" and self.branch:
            embed = build_shop_category_embed(self.profile, self.branch, guild, self.basket)
        elif self.step == "basket":
            embed = build_basket_embed(self.profile, self.basket, guild)
        else:
            embed = build_shop_root_embed(self.profile, guild, self.message, self.basket)
        return [embed]

    # -- Actions ----------------------------------------------------------

    async def handle_branch(self, interaction: discord.Interaction, branch: str) -> None:
        if branch not in BRANCHES:
            return
        self.branch = branch
        self.step = "category"
        self.message = None
        self.render()
        await interaction.response.edit_message(embeds=self.build_embeds(interaction.guild), view=self)

    async def handle_skills(self, interaction: discord.Interaction, branch: str, skill_ids) -> None:
        self.branch = branch
        self.step = "basket"

        for skill_id in skill_ids:
            skill = get_skill(skill_id)
            if skill and skill.branch == branch and skill_id not in self.basket:
                self.basket.append(skill_id)

        self.message = None
        self.render()
        await interaction.response.edit_message(embeds=self.build_embeds(interaction.guild), view=self)

    async def handle_action(self, interaction: discord.Interaction, action: str) -> None:
        if action == "confirm":
            await self._confirm(interaction)
        elif action == "cancel":
            await self._cancel(interaction)
        elif action == "add":
            await self._add_category(interaction)

    async def _add_category(self, interaction: discord.Interaction) -> None:
        self.step = "root"
        self.branch = None
        self.message = None
        self.render()
        await interaction.response.edit_message(embeds=self.build_embeds(interaction.guild), view=self)

    async def _cancel(self, interaction: discord.Interaction) -> None:
        self.basket.clear()
        self.step = "root"
        self.branch = None
        self.message = None
        self.render()
        await interaction.response.edit_message(embeds=self.build_embeds(interaction.guild), view=self)

    async def _confirm(self, interaction: discord.Interaction) -> None:
        profile = await get_profile(self.guild_id, self.user_id)
        if profile is None:
            await interaction.response.edit_message(content="Ton profil n’existe plus.", embeds=[], view=None)
            return

        self.profile = profile
        skills = [skill for skill in (get_skill(skill_id) for skill_id in self.basket) if skill is not None]
        still_available = all(can_unlock_skill(profile, skill) for skill in skills)
        total = sum(skill.cost for skill in skills)

        if not skills or not still_available or profile.experience < total:
            self.basket = [
                skill.id for skill in skills if can_unlock_skill(profile, skill)
            ]
            self.step = "root"
            self.branch = None
            self.message = (
                f"{theme.emoji('alerte', interaction.guild)} Le panier n’est plus valide "
                "ou ton XP est insuffisante."
            )
            self.render()
            await interaction.response.edit_message(embeds=self.build_embeds(interaction.guild), view=self)
            return

        for skill in skills:
            profile.unlocked_skills.append(skill.id)
        profile.experience -= total
        profile.touch()
        await save_profile(self.guild_id, self.user_id, profile)
        self.profile = profile
        self.basket.clear()
        self.step = "done"

        overview = build_overview_embed(profile, interaction.user, interaction.guild)
        await interaction.response.edit_message(
            content=(
                f"{theme.emoji('succes', interaction.guild)} **{len(skills)}** compétence(s) débloquée(s) "
                f"pour **{total} XP**. Il te reste **{profile.experience} XP**."
            ),
            embeds=[overview],
            view=ContinueShopView(self.guild_id, self.user_id),
        )
