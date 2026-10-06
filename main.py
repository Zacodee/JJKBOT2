"""Point d’entrée du bot Discord Jujutsu RP.

    python main.py           # démarre le bot et synchronise les commandes
    python main.py --sync    # synchronise les commandes puis quitte
"""

import argparse
import asyncio
import logging
import time

import discord
from discord import app_commands
from discord.ext import commands

from jjkbot import config, emojis as emojis_module, sessions
from jjkbot.storage import profiles
from jjkbot.views import xp_requests as xp_request_views
from jjkbot.views.base import GENERIC_ERROR_MESSAGE, notify_error

logger = logging.getLogger("jjkbot")

EXTENSIONS: tuple[str, ...] = (
    "jjkbot.cogs.jjk",
    "jjkbot.cogs.profil",
    "jjkbot.cogs.competences",
    "jjkbot.cogs.xp",
)

SWEEP_INTERVAL = 5 * 60  # Purge des attentes expirées.

# Délais (secondes) entre deux tentatives de connexion quand Discord refuse
# temporairement l’IP de l’hébergeur (HTTP 429 / Cloudflare « Error 1015 »).
# Sans cette attente, chaque crash est suivi d’un redémarrage automatique en
# quelques secondes : la nouvelle tentative REPOUSSE le blocage, qui se
# prolonge indéfiniment. On espace donc les essais, puis on garde le dernier
# palier.
RATE_LIMIT_BACKOFF = (120, 300, 900, 1800)

# Message expliqué au démarrage quand Discord refuse temporairement la connexion.
RATE_LIMIT_EXPLANATION = (
    "Discord refuse la connexion depuis cette machine : HTTP 429 / Cloudflare « Error 1015 ». "
    "Ce n’est PAS un bug du bot — Discord bloque TEMPORAIREMENT l’IP de l’hébergeur "
    "(souvent partagée) après trop de tentatives de connexion rapprochées. "
    "Chaque essai immédiat relance le compteur et prolonge le blocage. "
    "Le bot va donc attendre entre chaque tentative, puis se connecter tout seul "
    "dès que Discord lève le blocage (généralement sous 1 h). "
    "Si le blocage dure plus longtemps, arrête le serveur (pour ne plus insister), "
    "vérifie qu’une SEULE instance du bot tourne (aucun autre déploiement local actif), "
    "puis redémarre dans une heure."
)


def _is_rate_limited(error: BaseException) -> bool:
    """Vrai si l’erreur est un refus temporaire de Discord (429 / Cloudflare 1015).

    Une réponse HTTP explicite autre que 429 (401 token invalide, 403…) est
    définitive : on ne la réessaie pas.
    """
    status = getattr(error, "status", None)
    if status is not None:
        return status == 429
    # Erreur sans statut HTTP : on inspecte le texte au cas où le refus remonte
    # encapsulé (« Error 1015 », « rate limited »…).
    text = str(getattr(error, "text", "") or error).lower()
    return "error 1015" in text or "too many requests" in text or "rate limit" in text


class JJKBot(commands.Bot):
    """Bot du serveur, intents `guilds` + `emojis` — aucun intent privilégié."""

    def __init__(self, *, sync_only: bool = False) -> None:
        intents = discord.Intents.none()
        intents.guilds = True
        # Indispensable : discord.py ne peuple `guild.emojis` que si l’intent
        # « emojis » (alias « expressions » en 2.5+) est actif, et n’émet
        # `on_guild_emojis_update` que dans ce cas. Sans lui, `refresh_emojis`
        # indexe des listes vides et chaque emoji retombe sur son repli unicode.
        intents.emojis = True

        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
            help_command=None,
            allowed_mentions=discord.AllowedMentions(everyone=False, roles=False, users=True),
        )
        self.sync_only = sync_only
        self._sweeper: asyncio.Task | None = None

    # --- Cycle de vie ----------------------------------------------------

    async def setup_hook(self) -> None:
        for extension in EXTENSIONS:
            await self.load_extension(extension)
            logger.debug("Extension chargée : %s", extension)

        # Vue persistante : les boutons « Approuver / Décliner » d’une demande
        # d’XP doivent répondre même après un redémarrage. Sans cet
        # enregistrement, `timeout=None` ne tient que jusqu’au prochain
        # redéploiement, qui est fréquent — les demandes déjà postées
        # répondraient alors « interaction échouée ».
        self.add_view(xp_request_views.XPDecisionView())

        self.tree.on_error = self.on_tree_error
        await self.sync_commands()

        # Préchauffe les fiches en mémoire : la première commande n’attend pas
        # la lecture du fichier de données (disque parfois lent en conteneur).
        # Best-effort : un fichier illisible ne doit pas empêcher le démarrage,
        # l’erreur sera de toute façon signalée à la première commande.
        try:
            await profiles.warmup()
            await self._log_database_state()
        except (RuntimeError, OSError):
            logger.warning(
                "Préchauffage des fiches impossible ; lecture à la première commande.",
                exc_info=True,
            )

        self._sweeper = asyncio.create_task(self._sweeper_loop())

    async def _log_database_state(self) -> None:
        """Annonce d’où viennent les fiches et combien il y en a.

        Un déploiement qui **remplace** le dossier de données (clone Git sur un
        hébergeur) laisse une base vide : sans ce message, on ne s’en aperçoit
        qu’au moment où les joueurs découvrent leur fiche partie.
        """
        path, count = await profiles.database_state()
        logger.info("Fiches : %d chargée(s) depuis %s", count, path)
        if count == 0:
            logger.warning(
                "Aucune fiche au démarrage. Soit c’est un premier lancement, soit le "
                "déploiement a remplacé le dossier de données : vérifie que DATA_DIR "
                "pointe vers un stockage persistant hors du dépôt cloné."
            )

    async def close(self) -> None:
        if self._sweeper is not None:
            self._sweeper.cancel()
            self._sweeper = None
        await super().close()

    async def _sweeper_loop(self) -> None:
        while True:
            await asyncio.sleep(SWEEP_INTERVAL)
            sessions.sweep()

    async def on_ready(self) -> None:
        emojis_module.refresh_emojis(self.guilds)
        logger.info(
            "Bot connecté : %s • %d serveur(s) • thème « %s »",
            self.user,
            len(self.guilds),
            config.THEME,
        )

        # Repère de déploiement : si « intent actif=False », l’ancien code tourne.
        logger.info(
            "Emojis : intent actif=%s • %d emoji(s) custom indexé(s).",
            self.intents.emojis,
            emojis_module.emojis.index_count(),
        )

        missing = emojis_module.emojis.missing_keys(self.guilds[0] if self.guilds else None)
        if missing:
            names = ", ".join(
                emojis_module.emojis.catalog[key].name for key in missing if key in emojis_module.emojis.catalog
            )
            logger.info(
                "%d emoji(s) custom manquant(s) : %s — les replis unicode sont utilisés "
                "en attendant (/jjk emojis pour le détail).",
                len(missing),
                names or "?",
            )
        if not emojis_module.emojis.index_count() and self.guilds:
            logger.warning(
                "Aucun emoji custom indexé alors que le bot est sur %d serveur(s) : "
                "l’intent « emojis » est peut-être inactif ou le code déployé est ancien. "
                "Les commandes tenteront une réparation via l’API REST.",
                len(self.guilds),
            )

        if self.sync_only:
            logger.info("Synchronisation terminée, arrêt du bot.")
            await self.close()

    # --- Événements ------------------------------------------------------

    async def on_guild_emojis_update(self, guild, before, after) -> None:
        emojis_module.refresh_emojis(self.guilds)

    async def on_tree_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        """Erreur d’une commande slash : journalisée puis signalée à l’utilisateur."""
        original = error.original if isinstance(error, app_commands.CommandInvokeError) else error

        if isinstance(error, app_commands.CheckFailure) or isinstance(original, app_commands.CheckFailure):
            await notify_error(interaction, "Cette commande n’est pas disponible ici.")
            return

        logger.error(
            "Erreur pendant la commande /%s : %s",
            getattr(getattr(interaction, "command", None), "qualified_name", "?"),
            original,
            exc_info=original,
        )
        await notify_error(interaction, GENERIC_ERROR_MESSAGE)

    # --- Synchronisation -------------------------------------------------

    async def sync_commands(self) -> None:
        """Enregistre les commandes : sur le serveur de test, ou globalement."""
        try:
            if config.GUILD_ID:
                guild = discord.Object(id=config.GUILD_ID)
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                logger.info(
                    "%d commande(s) synchronisée(s) sur le serveur de test.", len(synced)
                )
            else:
                synced = await self.tree.sync()
                logger.info(
                    "%d commande(s) synchronisée(s) globalement (propagation jusqu’à 1 h).",
                    len(synced),
                )
        except discord.HTTPException:
            logger.exception("Impossible d’enregistrer les commandes slash.")


def _run_with_retry(*, sync_only: bool) -> None:
    """Démarre le bot ; en cas de 429 / 1015, patiente puis réessaie.

    La patience est le correctif : sur un hébergeur qui relance le process dès
    qu’il meurt, une sortie immédiate produit une boucle de connexions qui
    entretient le blocage Cloudflare. En dormant entre deux essais, le bot
    reste vivant et se connecte de lui-même dès que Discord lève la limite.
    """
    attempt = 0
    while True:
        bot = JJKBot(sync_only=sync_only)
        try:
            bot.run(config.token(), log_handler=None)
            return
        except KeyboardInterrupt:
            logger.info("Arrêt demandé.")
            return
        except discord.errors.HTTPException as error:
            if not _is_rate_limited(error):
                raise
            attempt += 1
            delay = RATE_LIMIT_BACKOFF[min(attempt - 1, len(RATE_LIMIT_BACKOFF) - 1)]
            logger.error(
                "%s\nTentative n°%d — nouvelle tentative dans %d min %02d s.",
                RATE_LIMIT_EXPLANATION,
                attempt,
                delay // 60,
                delay % 60,
            )
            time.sleep(delay)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="jjkbot",
        description="Bot Discord de support au roleplay Jujutsu Kaisen.",
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Synchronise les commandes slash puis quitte immédiatement.",
    )
    parser.add_argument("--verbose", action="store_true", help="Active les logs de debug.")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )

    try:
        config.check_required()
    except config.ConfigError as error:
        logger.error("%s", error)
        raise SystemExit(1) from error

    _run_with_retry(sync_only=args.sync)


if __name__ == "__main__":
    main()
