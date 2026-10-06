"""Tests du stockage local des images de personnage."""

import tempfile
import unittest
import unittest.mock
from pathlib import Path

from jjkbot import config
from jjkbot.storage import images


class FakeAttachment:
    def __init__(self, filename: str, content_type: str | None, size: int = 1024):
        self.filename = filename
        self.content_type = content_type
        self.size = size

    async def save(self, destination, *, spoiler: bool = False) -> None:
        Path(destination).write_bytes(b"contenu-image")


class ExtensionDetectionTests(unittest.TestCase):
    def test_type_mime_prioritaire(self):
        self.assertEqual(images.extension_for(FakeAttachment("photo", "image/png")), ".png")
        self.assertEqual(images.extension_for(FakeAttachment("photo", "image/gif")), ".gif")
        self.assertEqual(images.extension_for(FakeAttachment("photo", "image/webp")), ".webp")

    def test_jpeg_normalise_en_jpg(self):
        self.assertEqual(images.extension_for(FakeAttachment("photo.jpeg", "image/jpeg")), ".jpg")

    def test_extension_utilisee_si_le_type_mime_manque(self):
        self.assertEqual(images.extension_for(FakeAttachment("photo.PNG", None)), ".png")

    def test_type_mime_avec_parametres(self):
        self.assertEqual(
            images.extension_for(FakeAttachment("photo", "image/png; charset=binary")), ".png"
        )

    def test_formats_refuses(self):
        self.assertIsNone(images.extension_for(FakeAttachment("notes.txt", "text/plain")))
        self.assertIsNone(images.extension_for(FakeAttachment("video.mp4", "video/mp4")))


class ImageStorageTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.patch = unittest.mock.patch.object(
            config, "IMAGES_DIR", Path(self.directory.name) / "images"
        )
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.directory.cleanup()

    async def test_sauvegarde_et_lecture(self):
        filename, path = await images.save_image(1, 2, FakeAttachment("perso.png", "image/png"))

        # Nom indépendant du serveur : l’image suit le joueur.
        self.assertEqual(filename, "2.png")
        self.assertTrue(path.exists())
        self.assertEqual(images.find_image(1, 2), path)

    async def test_image_suit_le_joueur_dun_serveur_a_lautre(self):
        _name, path = await images.save_image(1, 2, FakeAttachment("perso.png", "image/png"))

        self.assertEqual(images.find_image(9, 2), path)

    async def test_ancienne_image_serveur_retrouvee(self):
        directory = images.images_dir()
        legacy = directory / "1-2.png"
        legacy.write_bytes(b"ancienne-image")

        # Fichier créé sous un autre serveur : on le retrouve quand même.
        self.assertEqual(images.find_image(9, 2), legacy)

    async def test_changement_de_format_supprime_lancien_fichier(self):
        _name, first = await images.save_image(1, 2, FakeAttachment("perso.png", "image/png"))
        _name, second = await images.save_image(1, 2, FakeAttachment("perso.gif", "image/gif"))

        self.assertFalse(first.exists())
        self.assertEqual(images.find_image(1, 2), second)

    async def test_profils_isoles(self):
        await images.save_image(1, 2, FakeAttachment("a.png", "image/png"))

        self.assertIsNone(images.find_image(1, 3))

    async def test_format_refuse(self):
        with self.assertRaises(ValueError):
            await images.save_image(1, 2, FakeAttachment("notes.txt", "text/plain"))

    async def test_fichier_trop_volumineux(self):
        attachment = FakeAttachment("lourd.png", "image/png", size=images.MAX_UPLOAD_SIZE + 1)

        with self.assertRaises(ValueError):
            await images.save_image(1, 2, attachment)

    async def test_suppression(self):
        _name, path = await images.save_image(1, 2, FakeAttachment("perso.png", "image/png"))
        images.delete_image(1, 2)

        self.assertFalse(path.exists())
        self.assertIsNone(images.find_image(1, 2))

    async def test_fichier_vide_ignore(self):
        directory = images.images_dir()
        (directory / "1-2.png").write_bytes(b"")

        self.assertIsNone(images.find_image(1, 2))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
