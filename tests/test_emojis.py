"""Tests du catalogue d’emojis et du repli unicode."""

import json
import tempfile
import unittest
from pathlib import Path

from jjkbot.emojis import DEFAULT_CATALOG, EmojiResolver, load_catalog


class FakeEmoji:
    """Remplaçant minimal d’un emoji de serveur."""

    def __init__(self, name: str, emoji_id: int, animated: bool = False):
        self.name = name
        self.id = emoji_id
        self.animated = animated

    def __str__(self) -> str:
        return f"<{'a' if self.animated else ''}:{self.name}:{self.id}>"


class FakeGuild:
    def __init__(self, guild_id: int, emojis=()):
        self.id = guild_id
        self.emojis = list(emojis)


class CatalogLoadingTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "emojis.json"

    def tearDown(self):
        self.directory.cleanup()

    def write(self, payload) -> None:
        self.path.write_text(json.dumps(payload), encoding="utf-8")

    def test_fichier_absent_renvoie_le_catalogue_par_defaut(self):
        catalog = load_catalog(self.path)

        self.assertEqual(catalog["profil"].name, "jjk_profil")
        self.assertEqual(catalog["profil"].fallback, "📛")

    def test_json_invalide_renvoie_le_catalogue_par_defaut(self):
        self.path.write_text("{invalide", encoding="utf-8")

        self.assertEqual(load_catalog(self.path)["age"].fallback, "⏳")

    def test_nom_personnalise_et_repli_conserve(self):
        self.write({"profil": {"name": "mon_profil"}})

        spec = load_catalog(self.path)["profil"]
        self.assertEqual(spec.name, "mon_profil")
        self.assertEqual(spec.fallback, "📛")

    def test_forme_courte_acceptee(self):
        self.write({"force": "combat_force"})

        self.assertEqual(load_catalog(self.path)["force"].name, "combat_force")

    def test_repli_personnalise(self):
        self.write({"profil": {"fallback": "🎴"}})

        self.assertEqual(load_catalog(self.path)["profil"].fallback, "🎴")

    def test_cle_inconnue_est_conservee(self):
        self.write({"ma_cle": {"name": "jjk_ma_cle", "fallback": "✨"}})

        catalog = load_catalog(self.path)
        self.assertIn("ma_cle", catalog)
        self.assertEqual(catalog["ma_cle"].name, "jjk_ma_cle")

    def test_les_cles_par_defaut_restent_presentes(self):
        self.write({"profil": {"name": "mon_profil"}})

        catalog = load_catalog(self.path)
        self.assertGreaterEqual(len(catalog), len(DEFAULT_CATALOG))
        self.assertEqual(catalog["citation"].fallback, "❯")


class EmojiResolverTests(unittest.TestCase):
    def setUp(self):
        self.resolver = EmojiResolver(dict(DEFAULT_CATALOG))
        self.guild = FakeGuild(
            42,
            [
                FakeEmoji("jjk_profil", 111),
                FakeEmoji("jjk_force", 222, animated=True),
            ],
        )
        self.other_guild = FakeGuild(43, [])

    def test_repli_unicode_sans_emoji_sur_le_serveur(self):
        self.resolver.refresh([self.guild])

        self.assertEqual(self.resolver.get("age", self.guild), "⏳")

    def test_emoji_custom_utilise_quand_present(self):
        self.resolver.refresh([self.guild])

        self.assertEqual(self.resolver.get("profil", self.guild), "<:jjk_profil:111>")

    def test_emoji_anime(self):
        self.resolver.refresh([self.guild])

        self.assertEqual(self.resolver.get("force", self.guild), "<a:jjk_force:222>")

    def test_emoji_dun_autre_serveur_reste_utilisable(self):
        self.resolver.refresh([self.guild])

        self.assertEqual(self.resolver.get("profil", self.other_guild), "<:jjk_profil:111>")

    def test_sans_serveur_le_repli_est_utilise(self):
        self.assertEqual(self.resolver.get("profil"), "📛")

    def test_cle_inconnue(self):
        self.assertEqual(self.resolver.get("inexistant"), "❔")

    def test_as_partial_unicode_et_custom(self):
        self.resolver.refresh([self.guild])

        custom = self.resolver.as_partial("profil", self.guild)
        fallback = self.resolver.as_partial("age", self.guild)

        self.assertEqual(custom.name, "jjk_profil")
        self.assertEqual(custom.id, 111)
        self.assertEqual(str(fallback), "⏳")

    def test_status_et_cles_manquantes(self):
        self.resolver.refresh([self.guild])
        status = self.resolver.status(self.guild)

        self.assertEqual(len(status), len(DEFAULT_CATALOG))
        self.assertIn("age", self.resolver.missing_keys(self.guild))
        self.assertNotIn("profil", self.resolver.missing_keys(self.guild))

    def test_refresh_remplace_lindex_precedent(self):
        self.resolver.refresh([self.guild])
        self.resolver.refresh([FakeGuild(42, [])])

        self.assertEqual(self.resolver.get("profil", self.guild), "📛")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
