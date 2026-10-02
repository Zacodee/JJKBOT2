"""Point d’entrée du bot Discord Jujutsu RP.

    python main.py           # démarre le bot et synchronise les commandes
    python main.py --sync    # synchronise les commandes puis quitte
"""

import argparse
import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import commands

from jjkbot import config, emojis as emojis_module, sessions
from jjkbot.views.base import GENERIC_ERROR_MESSAGE, notify_error

logger = logging.getLogger("jjkbot")

EXTENSIONS: tuple[str, ...] = (
    "jjkbot.cogs.jjk",
    "jjkbot.cogs.profil",
    "jjkbot.cogs.competences",
)

SWEEP_INTERVAL = 5 * 60  # Purge des attentes expirées.


class JJKBot(commands.Bot):
    """Bot du serveur, avec un seul intent (guilds) — aucun intent privilégié."""

    def __init__(self, *, sync_only: bool = False) -> None:
        intents = discord.Intents.none()
        intents.guilds = True

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

        self.tree.on_error = self.on_tree_error
        await self.sync_commands()

        self._sweeper = asyncio.create_task(self._sweeper_loop())

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

        missing = emojis_module.emojis.missing_keys(self.guilds[0] if self.guilds else None)
        if missing:
            logger.info(
                "%d emoji(s) custom manquant(s) : les emojis unicode de secours sont utilisés "
                "(voir /jjk emojis).",
                len(missing),
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
        bot = JJKBot(sync_only=args.sync)
        bot.run(config.token(), log_handler=None)
    except config.ConfigError as error:
        logger.error("%s", error)
        raise SystemExit(1) from error
    except KeyboardInterrupt:
        logger.info("Arrêt demandé.")


if __name__ == "__main__":
    main()
