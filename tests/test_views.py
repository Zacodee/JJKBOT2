"""Tests du rendu des fiches et du panier de compétences."""

import tempfile
import unittest
import unittest.mock
from pathlib import Path

from jjkbot import config, theme
from jjkbot.content.stats import DEFAULT_STATS
from jjkbot.storage.profiles import Profile
from jjkbot.views import competences as competences_views
from jjkbot.views import profil as profil_views


class FakeAvatar:
    url = "https://exemple.test/avatar.png"


class FakeUser:
    id = 2
    display_name = "Izouk"
    display_avatar = FakeAvatar()

    @property
    def mention(self) -> str:
        return "<@2>"


class FakeEmoji:
    """Emoji de serveur factice, rendu comme Discord le ferait."""

    def __init__(self, name: str, emoji_id: int, animated: bool = False):
        self.name = name
        self.id = emoji_id
        self.animated = animated

    def __str__(self) -> str:
        return f"<{'a' if self.animated else ''}:{self.name}:{self.id}>"


class FakeGuild:
    """Serveur factice n’ayant que deux emojis custom (force et vitesse)."""

    id = 4242
    emojis = [FakeEmoji("jjk_force", 111), FakeEmoji("jjk_vitesse", 222)]


def make_profile(**overrides) -> Profile:
    data = {
        "name": "Zuruï",
        "age": "1 an",
        "race": "Fléau",
        "grade": "Spécial",
        "alignment": "Chaotique mauvais",
        "role": "Fléaux",
        "quote": "Tricheur, menteur, porte malheur.",
        "traits": ["Rusé"],
        "flaws": ["Impitoyable"],
        "stats": dict(DEFAULT_STATS),
    }
    data.update(overrides)
    return Profile.from_dict(data)


class ParseEntriesTests(unittest.TestCase):
    def test_lignes_et_virgules(self):
        self.assertEqual(profil_views.parse_entries("Rusé, Sournois\nPatient"), ["Rusé", "Sournois", "Patient"])

    def test_vide(self):
        self.assertEqual(profil_views.parse_entries(""), [])
        self.assertEqual(profil_views.parse_entries(None), [])

    def test_limite_a_dix_entrees_de_soixante_caracteres(self):
        entries = profil_views.parse_entries("\n".join(["x" * 80] * 12))

        self.assertEqual(len(entries), 10)
        self.assertEqual(len(entries[0]), 60)


class ProfileEmbedTests(unittest.TestCase):
    def setUp(self):
        self.patch = unittest.mock.patch.object(config, "BANNER_URL", None)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()

    def test_page_profil_tient_en_six_lignes(self):
        embed = profil_views.build_profile_embeds(make_profile(), FakeUser(), "global", None)[0]

        # Le titre stylé vit dans la description (seul endroit où Discord
        # rend le Markdown), pas dans embed.title.
        self.assertIsNone(embed.title)
        self.assertTrue(embed.description.startswith("## 📛"))
        self.assertIn("@Izouk", embed.description)
        # Chaque paire devient un titre `###` sur deux lignes : libellés
        # agrandis (« plus gros »), valeurs en `code` dessous, et un large
        # espace d’em-spaces entre les deux champs qui élargit l’embed.
        lines = embed.description.splitlines()
        label_line = next(line for line in lines if "__Identité__" in line)
        self.assertTrue(label_line.startswith("### "))
        self.assertIn("__Âge__", label_line)
        self.assertIn(theme.PAIR_GAP + "•" + theme.PAIR_GAP, label_line)
        values_line = lines[lines.index(label_line) + 1]
        self.assertIn("`Zuruï`", values_line)
        self.assertIn("`1 an`", values_line)
        self.assertIn("__Race__", embed.description)
        self.assertIn("__Grade__", embed.description)
        self.assertIn("__Alignement__", embed.description)
        self.assertIn("Chaotique mauvais", embed.description)
        # Trois paires = trois titres espacés.
        self.assertEqual(embed.description.count("### "), 3)
        self.assertIn(theme.EM_SPACE, embed.description)
        self.assertIn("citation", embed.description.lower())
        self.assertIn("Page 1 / 3", embed.footer.text)

    def test_page_statistiques_sans_bloc_de_code(self):
        embed = profil_views.build_profile_embeds(make_profile(), FakeUser(), "stats", None)[0]

        self.assertEqual(len(embed.fields), 0)
        self.assertIn("## 📊", embed.description)
        self.assertIn("Points à attribuer", embed.description)
        # Plus de bloc de code : Discord n’y rend pas les emojis custom.
        self.assertNotIn("```", embed.description)
        for label in ("Force", "Résistance", "Vitesse", "Réserve d'EO", "Sortie d'EO"):
            self.assertIn(label, embed.description)
        # Sans serveur, chaque ligne ouvre sur l’emoji unicode de repli.
        for glyph in ("⚔️", "🛡️", "💨", "🔮", "🌀"):
            self.assertIn(glyph, embed.description)
        self.assertIn("Page 2 / 3", embed.footer.text)

    def test_page_statistiques_utilise_les_emojis_du_serveur(self):
        # Le bug corrigé : sur le serveur, l’emoji custom remplace le repli
        # (jjk_force pour Force, jjk_vitesse pour Vitesse).
        embed = profil_views.build_profile_embeds(
            make_profile(), FakeUser(), "stats", FakeGuild()
        )[0]

        self.assertIn("<:jjk_force:111>", embed.description)
        self.assertIn("<:jjk_vitesse:222>", embed.description)
        # Les autres statistiques n’ont pas d’emoji custom : repli unicode.
        self.assertIn("🛡️", embed.description)
        self.assertNotIn("```", embed.description)

    def test_page_traits_et_defauts(self):
        embed = profil_views.build_profile_embeds(make_profile(), FakeUser(), "traits", None)[0]

        self.assertEqual(len(embed.fields), 0)
        self.assertIn("### ✅ __Traits__", embed.description)
        self.assertIn("### ⚠️ __Défauts__", embed.description)
        self.assertIn("Rusé", embed.description)
        self.assertIn("Impitoyable", embed.description)
        self.assertIn("Page 3 / 3", embed.footer.text)

    def test_page_inconnue_retombe_sur_le_profil(self):
        embed = profil_views.build_profile_embeds(make_profile(), FakeUser(), "???", None)[0]

        self.assertTrue(embed.description.startswith("## 📛"))


class ProfileBannerTests(unittest.IsolatedAsyncioTestCase):
    async def test_banniere_encadre_chaque_page_de_la_fiche(self):
        # Chaque page est encadrée : bannière, fiche, même bannière en pied.
        for page in ("global", "stats", "traits"):
            with self.subTest(page=page):
                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / "banniere_jjk.png"
                    path.write_bytes(b"image")
                    with unittest.mock.patch.object(config, "BANNER_PATH", path), (
                        unittest.mock.patch.object(config, "BANNER_URL", None)
                    ):
                        embeds, files = await profil_views.build_profile_message(
                            make_profile(), FakeUser(), page, None, 2
                        )

                    self.assertEqual(len(embeds), 3)
                    self.assertEqual(embeds[0].image.url, "attachment://banniere_jjk.png")
                    # Pied de fiche : SECONDE attachment — jamais de fichier
                    # partagé entre deux embeds (sinon l’un reste flouté).
                    self.assertEqual(embeds[2].image.url, "attachment://banniere_jjk_fin.png")
                    self.assertEqual(len(files), 2)
                    self.assertEqual(
                        [file.filename for file in files],
                        ["banniere_jjk.png", "banniere_jjk_fin.png"],
                    )
                    for file in files:
                        file.close()

    async def test_banniere_absente_sans_image_ni_url(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "banniere_jjk.png"
            with unittest.mock.patch.object(config, "BANNER_PATH", missing):
                with unittest.mock.patch.object(config, "BANNER_URL", None):
                    embeds, files = await profil_views.build_profile_message(
                        make_profile(), FakeUser(), "stats", None, 2
                    )

            self.assertEqual(len(embeds), 1)
            self.assertEqual(files, [])


class ProfileImageTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.banner_patches = [
            # Bannière retirée ici : ces tests ne mesurent que l’image du
            # personnage, pas l’encadrement du message.
            unittest.mock.patch.object(
                config, "BANNER_PATH", Path(self.directory.name) / "banniere_jjk.png"
            ),
            unittest.mock.patch.object(config, "BANNER_URL", None),
        ]
        self.patch = unittest.mock.patch.object(
            config, "IMAGES_DIR", Path(self.directory.name) / "images"
        )
        for banner_patch in self.banner_patches:
            banner_patch.start()
        self.patch.start()
        Path(config.IMAGES_DIR).mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.patch.stop()
        for banner_patch in self.banner_patches:
            banner_patch.stop()
        self.directory.cleanup()

    async def test_image_locale_jointe_a_la_fiche(self):
        Path(config.IMAGES_DIR, "2-2.png").write_bytes(b"image")

        embeds, files = await profil_views.build_profile_message(
            make_profile(), FakeUser(), "global", None, 2
        )

        self.assertEqual(len(files), 1)
        self.assertEqual(embeds[-1].image.url, "attachment://personnage.png")
        for file in files:
            file.close()

    async def test_ancienne_url_utilisee_sans_image_locale(self):
        profile = make_profile(imageUrl="https://exemple.test/ancien.png")

        embeds, files = await profil_views.build_profile_message(
            profile, FakeUser(), "global", None, 2
        )

        self.assertEqual(files, [])
        self.assertEqual(embeds[-1].image.url, "https://exemple.test/ancien.png")

    async def test_rappel_sans_aucune_image(self):
        profile = make_profile()

        embeds, files = await profil_views.build_profile_message(
            profile, FakeUser(), "global", None, 2
        )

        self.assertEqual(files, [])
        self.assertTrue(any("Image du personnage" in field.name for field in embeds[-1].fields))


class CompetenceEmbedTests(unittest.TestCase):
    def test_vue_densemble_lite_les_categories(self):
        embed = competences_views.build_overview_embed(make_profile(), FakeUser(), None)

        for branch in ("Énergie occulte", "Domaines"):
            self.assertIn(branch, embed.description)
        self.assertIn("Compétences débloquées", embed.description)
        self.assertIn("▱", embed.description)

    def test_detail_categorie_affiche_les_premiers_paliers(self):
        embed = competences_views.build_category_embed(
            make_profile(), FakeUser(), "Stats physiques", None
        )

        self.assertIn("Force I", embed.description)
        self.assertIn("0 XP", embed.description)

    def test_panier_indique_sil_est_financable(self):
        profile = make_profile(experience=30)
        rich = competences_views.build_basket_embed(profile, ["manipulation_occult_2"], None)

        self.assertIn("Coût total — **20 XP**", rich.description)
        self.assertIn("finançable", rich.description)

    def test_panier_signale_lxp_insuffisante(self):
        profile = make_profile(experience=0)
        poor = competences_views.build_basket_embed(profile, ["manipulation_occult_2"], None)

        self.assertIn("pas assez d’XP", poor.description)

    def test_racine_du_panier_liste_le_panier_en_cours(self):
        profile = make_profile(experience=50)
        embed = competences_views.build_shop_root_embed(
            profile, None, None, ["manipulation_occult_1"]
        )

        self.assertIn("Panier en cours", embed.description)
        self.assertIn("Manipulation occulte I", embed.description)


class ShopViewTests(unittest.TestCase):
    def make_view(self, profile=None):
        return competences_views.ShopView(42, 2, profile or make_profile(experience=100))

    def test_racine_propose_les_categories_disponibles(self):
        view = self.make_view()

        self.assertEqual(view.step, "root")
        self.assertEqual(len(view.children), 1)
        self.assertIsInstance(view.children[0], competences_views.BranchSelect)

    def test_selection_de_competences_alimente_le_panier(self):
        view = self.make_view()
        view.branch = "Stats physiques"
        view.step = "category"

        # Ajout direct, comme le ferait le menu déroulant.
        view.basket.append("strength_1")
        view.render()

        self.assertEqual(view.basket, ["strength_1"])
        self.assertTrue(any(isinstance(item, competences_views.ActionButton) for item in view.children))

    def test_les_categories_sans_competence_achetable_sont_masquees(self):
        view = self.make_view(make_profile(experience=0))

        self.assertEqual(view.available_branches(), ["Énergie occulte", "Stats physiques"])

    def test_annulation_vide_le_panier(self):
        view = self.make_view()
        view.basket = ["strength_1"]
        view.step = "basket"

        view.basket.clear()
        view.step = "root"
        view.render()

        self.assertEqual(view.basket, [])
        self.assertEqual(view.step, "root")

    def test_une_categorie_videe_par_le_panier_disparait(self):
        view = self.make_view(make_profile(experience=0))
        view.basket = ["strength_1", "speed_1", "resistance_1", "heavenly_restriction"]

        self.assertEqual(view.available_branches(), ["Énergie occulte"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
