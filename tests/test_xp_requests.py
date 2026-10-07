"""Tests du stockage des demandes d’XP et des réglages par serveur."""

import json
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from jjkbot import config
from jjkbot.content import xp as xp_rules
from jjkbot.storage import requests as requests_module
from jjkbot.storage import settings as settings_module
from jjkbot.storage.profiles import Profile, get_profile, save_profile
from jjkbot.views import xp_requests as xp_views


class SettingsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "settings.json"
        self.patch = unittest.mock.patch.object(config, "SETTINGS_FILE", self.path)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.directory.cleanup()

    async def test_salon_absent_par_defaut(self):
        self.assertIsNone(await settings_module.get_xp_channel(1))

    async def test_definition_et_lecture(self):
        await settings_module.set_xp_channel(1, 555)

        self.assertEqual(await settings_module.get_xp_channel(1), 555)
        # Un réglage est propre à son serveur.
        self.assertIsNone(await settings_module.get_xp_channel(2))

    async def test_retrait(self):
        await settings_module.set_xp_channel(1, 555)
        await settings_module.set_xp_channel(1, None)

        self.assertIsNone(await settings_module.get_xp_channel(1))

    async def test_persiste_sur_le_disque(self):
        await settings_module.set_xp_channel(1, 555)

        raw = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(raw["guilds"]["1"]["xpChannel"], 555)


class RequestStorageTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "xp_requests.json"
        self.patch = unittest.mock.patch.object(config, "XP_REQUESTS_FILE", self.path)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.directory.cleanup()

    async def make_request(self, **overrides):
        data = dict(
            user_name="Izouk",
            interaction_type="combat_profond",
            amount=12,
            description="Scène de test",
            channel_link="#combat",
        )
        data.update(overrides)
        return await requests_module.create_request(1, 42, **data)

    async def test_creation_en_attente(self):
        request = await self.make_request()

        self.assertTrue(request.pending)
        self.assertEqual(request.amount, 12)
        self.assertEqual(len(request.id), 8)

        stored = await requests_module.get_request(request.id)
        self.assertEqual(stored.interaction_type, "combat_profond")
        self.assertEqual(stored.user_id, 42)
        self.assertEqual(stored.user_name, "Izouk")

    async def test_identifiants_uniques(self):
        first = await self.make_request()
        second = await self.make_request()

        self.assertNotEqual(first.id, second.id)

    async def test_retrouve_par_message(self):
        request = await self.make_request()
        await requests_module.attach_message(request.id, 999, 1234)

        found = await requests_module.get_request_by_message(1234)
        self.assertIsNotNone(found)
        self.assertEqual(found.id, request.id)
        self.assertEqual(found.channel_id, 999)
        self.assertIsNone(await requests_module.get_request_by_message(4321))

    async def test_decision_appliquee_une_seule_fois(self):
        request = await self.make_request()

        decided, applied = await requests_module.decide(
            request.id,
            requests_module.STATUS_APPROVED,
            staff_id=7,
            staff_name="Staff",
        )
        self.assertTrue(applied)
        self.assertEqual(decided.status, requests_module.STATUS_APPROVED)
        self.assertEqual(decided.decided_by, 7)
        self.assertIsNotNone(decided.decided_at)

        # Un second clic (même d’un autre membre du staff) ne rejoue rien : le
        # premier décideur reste celui qui a crédité l’XP.
        again, reapplied = await requests_module.decide(
            request.id,
            requests_module.STATUS_APPROVED,
            staff_id=8,
            staff_name="Autre",
        )
        self.assertFalse(reapplied)
        self.assertEqual(again.decided_by, 7)

    async def test_decision_refusee(self):
        request = await self.make_request()

        decided, applied = await requests_module.decide(
            request.id,
            requests_module.STATUS_DECLINED,
            staff_id=7,
            staff_name="Staff",
        )

        self.assertTrue(applied)
        self.assertEqual(decided.status, requests_module.STATUS_DECLINED)

    async def test_statut_de_decision_invalide_rejete(self):
        request = await self.make_request()

        with self.assertRaises(ValueError):
            await requests_module.decide(request.id, "peut-etre", staff_id=1, staff_name="x")

    async def test_decision_sur_demande_inexistante(self):
        decided, applied = await requests_module.decide(
            "inexistant",
            requests_module.STATUS_APPROVED,
            staff_id=1,
            staff_name="x",
        )

        self.assertIsNone(decided)
        self.assertFalse(applied)

    async def test_liste_des_attentes(self):
        first = await self.make_request()
        second = await self.make_request()
        await requests_module.decide(first.id, requests_module.STATUS_APPROVED, staff_id=1, staff_name="x")

        pending = await requests_module.list_pending()

        self.assertEqual([request.id for request in pending], [second.id])

    async def test_ecriture_atomique_sans_fichier_temporaire(self):
        await self.make_request()

        self.assertTrue(self.path.exists())
        self.assertFalse(self.path.with_suffix(".json.tmp").exists())

    async def test_aller_retour_json_stable(self):
        request = await self.make_request()

        restored = requests_module.XPRequest.from_dict(request.to_dict())

        self.assertEqual(restored.to_dict(), request.to_dict())

    async def test_fichier_illisible_ne_fait_pas_planter(self):
        self.path.write_text("{cassé", encoding="utf-8")

        # Une base corrompue repart vide sans lever : une demande perdue ne doit
        # pas empêcher le bot de fonctionner.
        self.assertIsNone(await requests_module.get_request("abc"))


class _FakeModalResponse:
    def __init__(self):
        self.modal = None

    async def send_modal(self, modal):
        self.modal = modal


class _FakeComponentInteraction:
    def __init__(self):
        self.response = _FakeModalResponse()


class DemandFormTests(unittest.IsolatedAsyncioTestCase):
    """Le formulaire de demande doit respecter les contraintes des modales.

    Discord n’accepte que des champs texte (type 4) dans une modale : un menu
    déroulant placé dedans fait échouer l’ouverture de `/xp demande` avec
    « Value of field "type" must be one of (4,) » (erreur 50035).
    """

    def test_modale_ne_contient_que_des_champs_texte(self):
        modal = xp_views.XPDemandModal(None, "mission")

        components = modal.to_components()

        self.assertTrue(components)
        self.assertLessEqual(len(components), 5)  # limite Discord d’une modale
        for row in components:
            self.assertEqual(row["type"], 1)  # ActionRow
            self.assertEqual(len(row["components"]), 1)
            self.assertEqual(row["components"][0]["type"], 4)  # TextInput

    def test_modale_reprend_le_type_choisi(self):
        modal = xp_views.XPDemandModal(None, "combat_profond")

        self.assertEqual(modal.interaction_type, "combat_profond")

    async def test_menu_propose_tous_les_types(self):
        view = xp_views.XPInteractionTypeView(None)
        select = view.children[0]

        self.assertEqual(
            [option.value for option in select.options],
            [item.id for item in xp_rules.INTERACTION_TYPES],
        )

    async def test_choisir_un_type_ouvre_la_modale(self):
        view = xp_views.XPInteractionTypeView(None)
        select = view.children[0]
        select._values = ["combat_serieux"]

        interaction = _FakeComponentInteraction()
        await select.callback(interaction)

        self.assertIsInstance(interaction.response.modal, xp_views.XPDemandModal)
        self.assertEqual(interaction.response.modal.interaction_type, "combat_serieux")


class PlayerLabelTests(unittest.TestCase):
    """Le joueur doit apparaître en **pseudo cliquable**, jamais en `<@id>` brut.

    Les libellés passaient par `theme.entry`, qui encadre la valeur d’accents
    graves ; or Discord ne résout aucune mention dans du code inline : le staff
    lisait donc `<@651499309933658116>` au lieu de la mention colorée.
    """

    def _request(self, **overrides):
        data = dict(
            id="3b035882",
            guild_id=1,
            user_id=651499309933658116,
            user_name="izouk",
            interaction_type="interaction_personnelle",
            amount=67,
            description="Test ne valider pas cette demande",
        )
        data.update(overrides)
        return requests_module.XPRequest(**data)

    def test_demande_affiche_la_mention_du_joueur(self):
        embed = xp_views.build_request_embed(self._request())

        self.assertIn("<@651499309933658116>", embed.description)
        self.assertIn("izouk", embed.description)
        # Hors du `code` : c’est ce qui la fait résoudre en pseudo cliquable.
        self.assertNotIn("`<@", embed.description)

    def test_decision_affiche_la_mention_du_joueur(self):
        request = self._request(
            status=requests_module.STATUS_APPROVED,
            decided_by=7,
            decided_by_name="izouk",
        )

        embed = xp_views.build_decision_embed(request)

        self.assertIn("<@651499309933658116>", embed.description)
        self.assertNotIn("`<@", embed.description)


class _FakeResponse:
    def __init__(self):
        self.sent = None
        self.edited = None

    async def send_message(self, **kwargs):
        self.sent = kwargs

    async def edit_message(self, **kwargs):
        self.edited = kwargs


class _FakePermissions:
    def __init__(self, *, staff=True):
        self.administrator = False
        self.moderate_members = staff


class _FakeUser:
    def __init__(self, user_id, name):
        self.id = user_id
        self.display_name = name


class _FakeMessage:
    def __init__(self, message_id):
        self.id = message_id


class _FakeDM:
    def __init__(self):
        self.messages = []

    async def send(self, **kwargs):
        self.messages.append(kwargs)


class _FakeClient:
    def __init__(self, dm):
        self.dm = dm

    def get_user(self, user_id):
        return self.dm

    async def fetch_user(self, user_id):
        return self.dm


class _FakeInteraction:
    def __init__(self, message_id, *, staff=True):
        self.permissions = _FakePermissions(staff=staff)
        self.user = _FakeUser(7, "Staff")
        self.message = _FakeMessage(message_id)
        self.response = _FakeResponse()
        self.guild = None
        self.client = _FakeClient(_FakeDM())


class DecisionFlowTests(unittest.IsolatedAsyncioTestCase):
    """Le clic sur « Approuver » doit créditer l’XP — et une seule fois."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        base = Path(self.directory.name)
        self.patches = [
            unittest.mock.patch.object(config, "XP_REQUESTS_FILE", base / "xp_requests.json"),
            unittest.mock.patch.object(config, "DATA_FILE", base / "profiles.json"),
        ]
        for patch in self.patches:
            patch.start()

    def tearDown(self):
        for patch in self.patches:
            patch.stop()
        self.directory.cleanup()

    async def make_pending(self, amount=15):
        await save_profile(1, 42, Profile.from_dict({"name": "Izouk"}))
        request = await requests_module.create_request(
            1,
            42,
            user_name="Izouk",
            interaction_type="mission",
            amount=amount,
            description="Scène",
            channel_link="#mission",
        )
        await requests_module.attach_message(request.id, 999, 777)
        return request

    async def test_approuver_credite_lxp_une_seule_fois(self):
        request = await self.make_pending(amount=15)
        interaction = _FakeInteraction(777)

        await xp_views._decide(interaction, requests_module.STATUS_APPROVED)

        self.assertEqual((await get_profile(1, 42)).experience, 15)
        self.assertEqual(
            (await requests_module.get_request(request.id)).status,
            requests_module.STATUS_APPROVED,
        )
        # Le message du staff est édité avec les boutons retirés, et le joueur
        # reçoit un message privé.
        self.assertIsNotNone(interaction.response.edited)
        self.assertIsNone(interaction.response.edited["view"])
        self.assertEqual(len(interaction.client.dm.messages), 1)

        # Second clic : le verrou de `decide` bloque le double crédit.
        await xp_views._decide(_FakeInteraction(777), requests_module.STATUS_APPROVED)
        self.assertEqual((await get_profile(1, 42)).experience, 15)

    async def test_decliner_ne_credite_rien(self):
        request = await self.make_pending(amount=15)

        await xp_views._decide(_FakeInteraction(777), requests_module.STATUS_DECLINED)

        self.assertEqual((await get_profile(1, 42)).experience, 0)
        self.assertEqual(
            (await requests_module.get_request(request.id)).status,
            requests_module.STATUS_DECLINED,
        )

    async def test_non_staff_ne_peut_pas_trancher(self):
        request = await self.make_pending(amount=5)

        await xp_views._decide(_FakeInteraction(777, staff=False), requests_module.STATUS_APPROVED)

        self.assertEqual((await get_profile(1, 42)).experience, 0)
        self.assertTrue((await requests_module.get_request(request.id)).pending)

    async def test_fiche_introuvable_refuse_le_credit_sans_planter(self):
        request = await requests_module.create_request(
            1,
            999,
            user_name="Fantôme",
            interaction_type="mission",
            amount=5,
            description="d",
            channel_link="",
        )
        await requests_module.attach_message(request.id, 999, 777)

        interaction = _FakeInteraction(777)
        await xp_views._decide(interaction, requests_module.STATUS_APPROVED)

        # La demande est bien close, mais l’embed signale que l’XP n’a pas pu
        # être créditée (le staff la rajoutera à la main).
        self.assertEqual(
            (await requests_module.get_request(request.id)).status,
            requests_module.STATUS_APPROVED,
        )
        self.assertIn("non créditée", interaction.response.edited["embed"].description)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
