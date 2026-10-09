# Bot Discord Jujutsu RP

Bot Discord **Python** dédié au support d’un serveur de roleplay écrit francophone.
Fiches de personnage, statistiques, arbre de compétences et guide des nouveaux membres,
présentés dans des embeds mis en forme **avec le Markdown Discord** : titres `##`,
valeurs en `code`, barres de progression en fin de statistique. La page **Profil** est une
**grille de champs** (`inline`) : Discord aligne lui-même les colonnes, chaque valeur
tombe donc sous son libellé, en **gras souligné** (les grands titres `###` ne sont pas
rendus dans les champs d’embed, seulement dans les descriptions). Chaque réponse de
contenu est **encadrée par la bannière** : embed de bannière en tête, contenu, bannière
en pied — chacune avec sa propre image jointe.
Tous les éléments de l’interface utilisent les **emojis du serveur**.

## Prérequis

- Python **3.11 ou plus** (testé sur 3.13).
- Un bot Discord avec les permissions `Envoyer des messages`, `Intégrer des liens`,
  `Joindre des fichiers` et `Utiliser les commandes d’application`.
- **Aucun intent privilégié** n’est nécessaire. Le bot demande les intents `guilds`
  et `emojis` (⚠️ sans l’intent `emojis`, aucun emoji custom n’est détecté : voir
  [Emojis du serveur](#emojis-du-serveur)).

## Installation

```bash
python -m venv .venv
source .venv/Scripts/activate     # Windows (Git Bash) ; sur Linux/macOS : source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Renseigne `DISCORD_TOKEN`, `CLIENT_ID` et, de préférence, `GUILD_ID` dans `.env`.

## Lancement

```bash
python main.py --sync     # enregistre les commandes slash puis quitte
python main.py            # démarre le bot
```

`--sync` enregistre les commandes sur `GUILD_ID` si la variable est renseignée
(apparition immédiate), sinon globalement (jusqu’à 1 h de propagation).
`python main.py --verbose` active les logs de debug.

> ⚠️ **Un seul bot à la fois** : si le bot tourne déjà sur ton hébergeur, **ne lance
> pas aussi `python main.py` en local avec le même token**. Deux instances se
> partagent alors les mêmes interactions : elles se répondent l’une à l’autre
> (erreurs `40060` / `10062` dans les logs) et chacune affiche le rendu de *sa*
> version du code — la fiche « saute » entre l’ancien et le nouveau style selon
> qui gagne la course. Arrête l’instance locale (Gestion des tâches → `python.exe`)
> ou l’hébergeur avant de tester.

## Configuration

| Variable | Rôle |
|---|---|
| `DISCORD_TOKEN` | Token privé du bot (obligatoire) |
| `CLIENT_ID` | Identifiant de l’application Discord (facultatif, non utilisé au démarrage) |
| `GUILD_ID` | Serveur de test : les commandes y apparaissent immédiatement |
| `THEME` | `violet` (défaut) ou `noblesse` |
| `BANNER_URL` | Repli de la bannière si `assets/banniere_jjk.png` est absent |
| `HELP_GIF_URL` | GIF affiché dans `/jjk help` |
| `BLACKFLASH_OK_URL` | Repli de l’image de succès si `assets/blackflash_ok.png` est absent |
| `BLACKFLASH_KO_URL` | Repli de l’image d’échec si `assets/blackflash_ko.png` est absent |
| `RENAISSANCE_OK_URL` | Repli de l’image de succès de la Renaissance si `assets/renaissance_ok.png` est absent |
| `RENAISSANCE_KO_URL` | Repli de l’image d’échec de la Renaissance si `assets/renaissance_ko.png` est absent |
| `TRAIN_URL` | Repli de l’image de `/train` si `assets/train.png` est absent |
| `STAFF_ROLE_ID` | Facultatif : rôle autorisé à utiliser les commandes du staff |
| `DATA_DIR` | Dossier des fiches et images (défaut `data/`) : à placer **hors du dépôt cloné** sur un hébergeur |

La bannière s’affiche en **début et en fin** de chaque réponse de contenu (fiche,
compétences, guide), dans un embed séparé, exactement comme dans le visuel du
serveur. L’image `assets/banniere_jjk.png` est envoyée **localement** via
`attachment://` : contrairement aux URL de CDN Discord, qui sont signées et expirent
en quelques heures, elle n’a pas de date de péremption — c’est donc elle qui est
utilisée en priorité, et elle vit dans le dépôt. Les deux embeds de bannière
**n’en partagent jamais la même** : le pied utilise une seconde copie jointe sous
le nom `banniere_jjk_fin.png`, sinon Discord laisse l’un des deux sur son image de
remplacement floutée. `BANNER_URL` ne sert que de repli si ce fichier est absent :
il attend une URL directe (hébergeur d’images, salon Discord…). Pour changer de
bannière, remplace simplement le fichier `assets/`.

Les deux images du Black Flash (`assets/blackflash_ok.png` et `assets/blackflash_ko.png`,
envoyées par `/jjk blackflash`) suivent la même règle : elles sont jointes en local via
`attachment://`, `BLACKFLASH_OK_URL` et `BLACKFLASH_KO_URL` ne servant que de repli. Les
deux images de la Renaissance (`assets/renaissance_ok.png` / `assets/renaissance_ko.png`)
fonctionnent à l’identique, avec `RENAISSANCE_OK_URL` / `RENAISSANCE_KO_URL` en repli, et
l’image de l’entraînement (`assets/train.png`, envoyée par `/train`) suit encore la même
règle, avec `TRAIN_URL` en repli.

Ces médias partent **en pièce jointe à chaque réponse** : leur poids joue donc
directement sur la vitesse. Si les réponses tardent, allège-les avec
`python tools/optimize_assets.py` (nécessite Pillow : `pip install pillow`), qui
redimensionne la bannière et les images sans toucher au reste.

Changer de thème ne demande aucune modification de code : `THEME=noblesse` rétablit
l’identité visuelle d’origine (bordeaux et or), `THEME=violet` utilise la palette de
référence. Les couleurs sont définies dans `jjkbot/theme.py`.

## Emojis du serveur

Chaque élément de l’interface (identité, âge, race, grade, rôle, citation,
statistiques, panier, boutons…) possède une clé reliée à un **emoji custom** et à un
**emoji unicode de secours**, dans [config/emojis.json](config/emojis.json) :

```json
{
  "identite": { "name": "jjk_identite", "fallback": "🪪" },
  "age": { "name": "jjk_age", "fallback": "⏳" }
}
```

- Si l’emoji `jjk_identite` existe sur le serveur, le bot l’utilise ; sinon il affiche 🪪.
  Le bot fonctionne donc dès maintenant, même avant la création des emojis.
- Pour utiliser tes propres noms, change `name` dans le fichier : aucun code à modifier.
- La forme courte `"identite": "jjk_identite"` est également acceptée.
- Un emoji animé fonctionne aussi (le bot détecte le préfixe `a:`).
- `/jjk emojis` (staff, réponse éphémère) liste les emojis trouvés et **les noms exacts
  à créer** sur le serveur, avec le repli utilisé pour chacun.
- L’embed de Black Flash a ses propres clés : `blackflash` (titre réussi),
  `blackflash_rate` (titre raté), `blackflash_tentative` et `blackflash_chance`
  — seule la ligne de titre reste en repli unicode, le champ `title` d’un embed
  n’affichant pas toujours les emojis custom.
- L’embed de la Renaissance suit le même schéma : `renaissance` (titre réussi),
  `renaissance_rate` (titre raté), `renaissance_tentative` et `renaissance_chance`.
- Les **sous-statistiques** ont leurs clés : `perception`, `projectile` et
  `perception_occulte` ; l’entraînement utilise `train`.

> ⚠️ **Si le bot affiche les emojis de secours malgré la création des emojis**, vérifie
> que l’intent `emojis` est bien activé dans `main.py`. discord.py ne remplit
> `guild.emojis` **que** si cet intent est actif : sans lui, la liste est vide et tous
> les emojis retombent sur le repli unicode. L’intent `emojis` n’est pas privilégié,
> rien à cocher dans le portail développeur. Après un ajout d’emoji pendant que le bot
> tourne, relance `/jjk emojis` (le diagnostic rafraîchit le catalogue) ou redémarre le bot.
>
> **Filet de sécurité** : si le cache passerelle est vide (intent inactif ou ancien
> déploiement), le bot récupère désormais les emojis via l’**API REST**
> (`GET /guilds/{id}/emojis`), qui fonctionne même sans cet intent — au plus une fois
> toutes les 5 minutes par serveur. Au démarrage, la ligne de log
> `Emojis : intent actif=… • N emoji(s) custom indexé(s)` doit afficher `True` et le
> nombre d’emojis de ton serveur : si `intent actif=False` s’affiche, l’ancien code
> tourne encore, redéploie.

## Commandes

### Profil

| Commande | Effet |
|---|---|
| `/profil voir [joueur]` | Affiche une fiche en 3 pages navigables (Profil, Statistiques, Traits & défauts) |
| `/profil creer` | Création guidée en 2 modales : identité/âge/race/grade puis rôle/citation/traits/défauts |
| `/profil modifier` | Met à jour une fiche existante |
| `/profil image fichier:` | Image du personnage (PNG, JPG, WEBP ou GIF, 8 Mo max) |
| `/profil couleur [nom] [code] [defaut]` | Choisit la couleur d’embed de sa fiche : un nom du nuancier, un code hexadécimal, ou retour au thème |
| `/profil attribuer-stat statistique: montant:` | Dépense ses points de statistique |
| `/profil donner-points joueur: montant:` | Ajoute des points *(staff)* |
| `/profil reset joueur: type:` | Réinitialise profil, statistiques ou compétences, avec confirmation par boutons *(staff)* |

Les six statistiques sont définies dans `jjkbot/content/stats.py` : **Force**,
**Résistance**, **Vitesse**, **Manipulation occulte** et **Sortie d’EO** reçoivent
les points de statistique, tandis que **Réserve d’EO** est **figée à la création**
(« fixed ») : aucun point n’y est dépensé, elle n’entre ni dans le total réparti ni
dans les barres, et la page Statistiques l’affiche dans un bloc séparé, sous un
filet et avec un cadenas. Elle se pose à la **validation de la fiche RP**, par un
administrateur, avec `/jjk eo` (voir plus bas).

Trois **sous-statistiques** s’ajoutent sous les statistiques : **Perception**,
**Vitesse de Projectile** et **Perception Occulte**. Elles ne s’achètent **jamais**
avec des points : chacune suit une statistique principale et vaut exactement sa
valeur — Perception et Vitesse de Projectile valent la **Vitesse**, Perception
Occulte vaut la **Manipulation occulte**. Monter la statistique principale les fait
grandir ; la page Statistiques les affiche (nom et valeur) sous les barres, **sans
description** : leurs effets se découvrent en RP, guidés par le staff.

Quand le joueur profite du **buff de Noirceur** d’un Black Flash, la page Statistiques
affiche les valeurs **buffées** (`Force : 11 (+1)`) avec un rappel des tours restants :
le total réparti, lui, reste celui des points réellement dépensés.

### Compétences

| Commande | Effet |
|---|---|
| `/competences voir [joueur]` | Progression par catégorie, puis détail des paliers via un menu |
| `/competences acheter` | Panier multi-catégories : prérequis et XP revérifiés à la confirmation |
| `/competences xp joueur: montant:` | Ajoute de l’XP *(staff)* |

L’arbre complet (54 paliers, 6 catégories) est défini dans
[jjkbot/content/skill_tree.py](jjkbot/content/skill_tree.py) : chaque palier a un coût en
XP et des prérequis, qu’un niveau supérieur ne peut donc pas contourner.

### Expérience et demandes d’XP

L’XP s’obtient en RP et sert à deux choses : débloquer des compétences
(`/competences acheter`) ou être **convertie en points de statistique**
(1 XP = 1 point).

| Commande | Effet |
|---|---|
| `/xp convertir montant:` | Échange de l’XP contre des points de statistique, à répartir avec `/profil attribuer-stat` |
| `/xp demande` | Demande d’XP pour une scène de RP : choisit le type d’interaction, puis ouvre le formulaire |
| `/jjk salon salon: [retirer]` | Définit le salon du staff qui reçoit les demandes *(administrateurs, relançable pour changer de salon)* |
| `/jjk sauvegarde` | Télécharge une copie des fiches *(administrateurs)* |
| `/jjk restaurer fichier: confirmer:` | Remet les fiches d’une sauvegarde *(administrateurs)* |

- `/xp convertir` **consomme** l’XP : 1 XP = 1 point, le total baisse d’autant.
- `/xp demande` se déroule en **deux temps**. Un premier message éphémère propose
  le **type d’interaction** (interaction ou combat, personnelle / sérieuse /
  profonde, ou mission) dans un menu déroulant ; le choix ouvre aussitôt le
  formulaire, qui demande la **quantité d’XP attendue** (1 à 100000), une
  **description** de la scène et le **lien du salon** où elle s’est déroulée. Le
  joueur peut la lancer de n’importe où. (Le type est choisi avant la modale :
  Discord n’accepte que des champs texte dans une modale, un menu déroulant y
  étant refusé.)
- La demande part dans le salon défini par `/jjk salon`, que le bot **rend visible du
  staff uniquement** (permission `@everyone` retirée, rôle `STAFF_ROLE_ID` réautorisé
  s’il est configuré). La commande se relance autant de fois qu’on veut : chaque appel
  remplace le salon précédent.
- Le staff **approuve ou décline d’un clic**. Si approuvée, l’XP est créditée
  automatiquement et le joueur prévenu en message privé.
- **Durabilité** : les boutons n’expirent pas (`timeout=None`) et restent
  fonctionnels **après un redémarrage du bot** (vues persistantes réenregistrées au
  démarrage) et **des heures après** leur envoi : la demande vit dans
  `DATA_DIR/xp_requests.json` et est relue au moment du clic. Un second clic ne
  crédite jamais l’XP deux fois.

### Sauvegarde et restauration des fiches (administrateurs)

Les trois commandes de maintenance — `/jjk salon`, `/jjk sauvegarde` et
`/jjk restaurer` — sont **réservées aux administrateurs** : Discord ne les affiche
qu’aux membres ayant la permission « Administrateur », et le bot revérifie ce droit
à l’exécution.

- **`/jjk sauvegarde`** télécharge `profiles.json` tel qu’il est sur le serveur, en
  pièce jointe (visible de toi seul). C’est ta copie de secours : garde-la quelque
  part avant un redéploiement.
- **`/jjk restaurer fichier: confirmer:Vrai`** remplace **toute** la base par le
  fichier fourni. Sans `confirmer:Vrai`, la commande refuse et rappelle le risque.
  L’ancienne base n’est jamais perdue silencieusement : elle est conservée à côté sous
  `profiles.json.invalide-<horodatage>`.
- ⚠️ La sauvegarde contient **les fiches, pas les images** : celles-ci vivent dans
  `DATA_DIR/images/` et doivent être copiées séparément (via le gestionnaire de
  fichiers de l’hébergeur). Une image manquante n’empêche pas la fiche de s’afficher, la
  photo réapparaîtra seulement après réenvoi avec `/profil image`.

### Réserve d’EO (administrateurs)

| Commande | Effet |
|---|---|
| `/jjk eo joueur: montant:` | Fixe la **Réserve d’EO** d’un joueur, après validation de sa fiche RP *(administrateurs)* |

- La **Réserve d’EO** est la seule statistique **figée** du personnage : elle ne se
  répartit pas en points (`/profil attribuer-stat` la refuse explicitement). C’est donc
  l’administrateur qui la pose une fois la fiche jouée et validée, avec `/jjk eo`.
- `montant` est une **valeur absolue** (0 à 100000), pas un ajout : relancer la commande
  corrige une Réserve mal saisie. Le montant précédent est rappelé dans la
  confirmation, et le joueur doit avoir une fiche (`/profil creer`) pour recevoir son EO.
- Comme les autres statistiques, elle est stockée dans la fiche (`stats.reserveEO`) :
  elle suit la sauvegarde et la restauration de `profiles.json`.

### Black Flash

| Commande | Effet |
|---|---|
| `/jjk blackflash [mortel]` | Tente le coup rarissime : base **effective** du joueur, **+5 %** par succès (plafond 100 %), retour à cette base si tu rates. `mortel` : **Combat Mortel**, réservé au recordman |
| `/jjk blackflash-reset` | Remet tes chances à ta base effective quand le combat est fini (et clôt la série du combat) |
| `/jjk blackflash-chance joueur: [base] [bonus] [retirer]` | Fixe le plancher et/ou le bonus de Black Flash d’un joueur *(staff)* |

- La chance est stockée **dans ta fiche** (`blackflashChance`) : une fiche est donc
  obligatoire, et `/jjk blackflash-reset` remet la base effective.
- Un succès **rend 75 EO** (gain narratif, annoncé dans l’embed du coup : la fiche
  n’est pas modifiée) et donne un **buff de statistiques** : **+30 % de Force** sur
  le coup porté (effet instantané, écrit dans l’embed du coup), puis **+10 % à toutes les
  statistiques attribuables** (Force, Résistance, Vitesse, Manipulation occulte,
  Sortie d’EO — la **Réserve d’EO** en est exclue) pendant **3 tours**. Le buff vit
  sur la fiche (`blackflashBuffTurns`) et s’affiche dans `/profil voir` tant qu’il
  reste des tours ; un raté ne le retire pas.
- Le bot ne suit pas les tours de combat : c’est le staff qui fait avancer ou
  retire le buff avec `/blackflash buff`. `/jjk blackflash-reset` (fin de combat)
  le dissipe également.
- Le résultat est encadré par la bannière, avec l’image locale
  (`assets/blackflash_ok.png` en cas de succès, `assets/blackflash_ko.png` sinon).

#### Traits et évènements

La **base effective** vaut 5 % par défaut, mais certains traits de la fiche la
relèvent. La correspondance vit dans [config/blackflash.json](config/blackflash.json),
éditable sans toucher au code :

```json
{
  "Fièvre": { "bonus": 5 },
  "Béni de l'étincelle": {
    "base": 20,
    "exclusive": true,
    "aliases": ["beni etincelle", "beni de l etincelle"]
  },
  "Adepte du Black Flash": {
    "base": 10,
    "aliases": ["adepte du blackflash", "adepte black flash", "adepte bf"]
  }
}
```

- `base` impose un **plancher** (« Béni de l’étincelle » = 20), `bonus` ajoute des
  points à la base (« Fièvre » = +5).
- Les traits sont du texte libre : la reconnaissance ignore casse, accents,
  apostrophes et espaces multiples (« Fièvre », `FIEVRE`, `Fiévre` et
  « Béni de l’étincelle » / `Béni de l'étincelle` se rejoignent). En revanche une
  **vraie faute de frappe** (lettre manquante, mot collé) n’est **pas** devinée :
  il faut alors l’ajouter à la main en **alias** d’un trait déjà listé — `aliases`
  accepte les mots collés (`adepte du blackflash`), l’apostrophe remplacée par un
  espace (`beni de l etincelle`) ou les abréviations (`adepte bf`).
- `exclusive: true` fait qu’un trait ignore **tous** les autres traits BF :
  « Béni de l’étincelle » ne se cumule donc jamais avec « Fièvre », tandis que
  « Adepte du Black Flash » (10) **s’additionne** à « Fièvre » (+5) pour une base de 15.
- Plusieurs bases **ne s’additionnent pas** : la meilleure l’emporte.
- Un échec ramène à la base effective, pas à 5 % : un simple raté n’efface donc jamais
  le bonus d’un trait.
- Si le fichier est absent ou illisible, les trois traits par défaut restent reconnus.
- L’exception du staff (`/jjk blackflash-chance`) couvre les **évènements** ou corrige
  une fiche : elle fixe un plancher (`blackflashBase`) et un bonus additif
  (`blackflashBonus`) qui s’ajoutent aux traits, sans que le joueur modifie sa fiche.

#### Record Man du Rayon Noir

- **4 Black Flash consécutifs** dans un même combat décrochent le titre de **recordman du
  Rayon Noir**, et le second embed de la tentative l’annonce avec l’image locale
  `assets/record_rayon_noir.png`.
- Le titre donne une augmentation **permanente** de **+10 %** de chance de réussir un
  Rayon Noir ; elle est traitée comme un **plancher** (`base effective + 10`), donc elle
  survit à un raté, et s’ajoute aux traits et à l’exception du staff.
- Le recordman peut passer `mortel:Vrai` à `/jjk blackflash` pour un **Combat Mortel** :
  son augmentation passe alors à **+20 %**. L’option est **refusée** à tout joueur qui
  n’a pas décroché le titre.
- Le titre est **personnel** : chacun le décroche pour soi, autant de fois que de joueurs
  qui réussissent la série. Personne ne peut le reprendre à quelqu’un d’autre, et deux
  joueurs peuvent donc être recordmen en même temps.
- Il est **définitif** : ni un raté, ni une fin de combat, ni l’exploit d’un autre ne le
  retirent. Deux champs de la fiche suffisent — `blackflashStreak` (série en cours) et
  `blackflashRecord` (meilleure série jamais atteinte, d’où se déduit le titre).
- La **série en cours** s’incrémente à chaque succès, retombe à zéro à chaque échec, et
  `/jjk blackflash-reset` (fin de combat) la remet également à zéro. Un recordman qui bat
  **son propre** record met simplement à jour sa fiche, sans nouvel embed : le titre est
  déjà acquis.

#### Tester l’évènement (staff)

Le Black Flash est un tirage : à 5 % de base, enchaîner 4 réussites ne peut pas se
vérifier « à la main ». Deux commandes réservées au staff existent donc uniquement
pour ça — elles écrivent dans la **fiche** du joueur, avec les mêmes champs que le
jeu normal :

| Commande | Effet |
|---|---|
| `/blackflash chance joueur: [valeur] [retirer]` | Force la chance du prochain tirage (`100` = chaque tentative réussit), ou la rend |
| `/blackflash record joueur: [retirer]` | Montre le record personnel et le statut de recordman, ou retire le titre |
| `/blackflash buff joueur: [tours] [retirer]` | Montre, fixe les tours restants du buff de stats, ou le retire |

- `valeur` s’écrit dans `blackflashChance`, la chance **courante** : à `100`, enchaîne 4
  `/jjk blackflash` pour déclencher le titre de recordman sans rien espérer du hasard.
- `retirer` (sur `chance`) rend la **base effective** de la fiche — traits, exception du
  staff et bonus de recordman compris — soit exactement ce que fait `/jjk blackflash-reset`.
- `retirer` (sur `record`) remet à zéro le record personnel **et** la série en cours : le
  titre et son bonus disparaissent, l’évènement peut être rejoué depuis le début.
- Rien de spécifique aux tests n’est stocké : une fiche forcée reste une fiche normale, et
  un joueur garde ce que le test lui a donné jusqu’à ce qu’on le lui retire.

### Entraînement

| Commande | Effet |
|---|---|
| `/train` | S’entraîner : **+500 XP**, une fois par semaine |
| `/train-reset joueur:` | Rend son entraînement à un joueur *(staff)* |

- La semaine se calcule en **7 jours glissants** depuis le dernier `/train` : un
  joueur qui s’entraîne un mardi peut recommencer le mardi suivant, pas avant.
  Tant que le délai court, `/train` répond quand la séance revient.
- Le rendez-vous vit sur la fiche (`trainLastAt`). `/train-reset` l’efface, ce qui
  rend la séance immédiatement — utile pour un rattrapage, un test ou une date
  erronée.
- Le résultat est encadré par la bannière, avec l’image locale `assets/train.png`
  (repli `TRAIN_URL`).

### Renaissance en Esprit Vengeur

| Commande | Effet |
|---|---|
| `/jjk renaissance [situation]` | Tente la renaissance de ton personnage à sa **mort définitive** |

- Un dé de 100 décide : il faut **5 ou moins** pour une mort sans circonstance.
- L’option `situation` relève le seuil : **10 ou moins** si le personnage nourrissait du
  ressentiment envers la personne responsable de sa mort, **15 ou moins** si cette
  personne était son **rival**.
- Ce n’est pas une résurrection : en cas de réussite, le personnage renaît en **Esprit
  Vengeur**, sa personnalité altérée par les émotions de sa mort, et sa nouvelle nature
  (existence, potentiel, capacités) est redéfinie avec le staff en RP.
- Le résultat est encadré par la bannière, avec l’image locale
  `assets/renaissance_ok.png` en cas de succès, `assets/renaissance_ko.png` sinon.
- Aucune donnée n’est stockée : c’est un tirage ponctuel, contrairement au Black Flash
  dont la chance vit dans la fiche.

### Guide

| Commande | Effet |
|---|---|
| `/jjk help` | Guide de démarrage illustré (GIF optionnel) |
| `/jjk emojis` | Diagnostic des emojis du serveur *(staff)* |
| `/jjk blackflash-chance` | Plancher et bonus de Black Flash d’un joueur *(staff)* |
| `/blackflash chance` et `/blackflash record` | Forcer la chance de Black Flash et gérer le titre de recordman, pour tester l’évènement *(staff)* |
| `/blackflash buff` | Voir, fixer ou retirer le buff de stats du Black Flash d’un joueur *(staff)* |
| `/train-reset` | Rendre son entraînement hebdomadaire à un joueur *(staff)* |
| `/jjk renaissance` | Tente la Renaissance en Esprit Vengeur, à la mort définitive du personnage |
| `/jjk eo` | Réserve d’EO d’un joueur, après validation de sa fiche *(administrateurs)* |
| `/jjk salon` | Salon du staff qui reçoit les demandes d’XP *(administrateurs)* |
| `/jjk sauvegarde` | Copie téléchargeable des fiches *(administrateurs)* |
| `/jjk restaurer` | Remet les fiches d’une sauvegarde *(administrateurs)* |

## Données

> ⚠️ **Les données ne sont pas dans Git.** `.gitignore` exclut tout `data/*.json`
> (`profiles.json`, `settings.json`, `xp_requests.json`) et `data/images/` : un
> déploiement par **clone Git recrée le dossier à vide**, et toutes les fiches
> perdues — sauf celles recréées après la mise à jour. Sur un hébergeur qui
> remplace le dossier à chaque déploiement, pose donc `DATA_DIR` sur un chemin
> **persistant, hors du dépôt cloné** (voir ci-dessous).

> 🚑 **Si des fiches disparaissent à chaque redémarrage**, c’est presque toujours que
> le `data/profiles.json` livré avec le déploiement **remplace** celui du serveur : à
> chaque redéploiement, la base revient à l’instantané embarqué, et toutes les fiches
> créées depuis sont perdues. Deux réflexes :
> 1. ne jamais envoyer `data/profiles.json` avec le code (il est dans `.gitignore` —
>    vérifie que ton dépôt ne le contient pas et que tu ne l’envoies pas à la main) ;
> 2. faire une copie avant chaque déploiement avec `/jjk sauvegarde`, et la remettre
>    après avec `/jjk restaurer fichier: confirmer:Vrai`.
>
> Le log de démarrage `Fiches : N chargée(s) depuis <chemin>` dit immédiatement
> combien de fiches ont été lues et **d’où** : compare N à ce que tu attends pour
> savoir si la base a été remplacée.

- Le dossier des données se configure avec `DATA_DIR` (défaut `data/`) : il contient
  `profiles.json`, `images/`, le réglage `settings.json` (salon des demandes d’XP par
  serveur) et les demandes d’XP `xp_requests.json`. En le sortant du dépôt, une mise à
  jour ne peut plus toucher ni aux fiches ni aux demandes en attente. Le bot annonce au
  démarrage `Fiches : N chargée(s) depuis <chemin>` et émet un **avertissement si N = 0**,
  pour repérer immédiatement un déploiement qui a vidé le dossier.
- `settings.json` et `xp_requests.json` vivent **dans `DATA_DIR`, pas dans `config/`** :
  ce dernier est réécrit par le dépôt à chaque déploiement, ce qui effacerait le salon
  configuré et rendrait non cliquables les demandes déjà envoyées.
- Si `profiles.json` a une structure inattendue, le bot repart d’une base vide **sans
  rien détruire** : l’original est conservé à côté sous le nom
  `profiles.json.invalide-<horodatage>` et le journal enregistre l’erreur. Un JSON
  cassé, lui, empêche le démarrage des commandes plutôt que d’effacer les données.
- Pour regrouper les données, laisser `data/` dans le dépôt fonctionne (dépôt privé)
  mais reste fragile : le serveur n’écrit pas dans Git, donc la prochaine mise à jour
  **remettrait les fiches à l’état du dernier commit**. Un stockage persistant reste la
  seule solution fiable.
- Les fiches sont stockées dans `data/profiles.json` (enveloppe identique à l’ancienne
  version Node : `{"profiles": {userId: {…}}}`).
- Une fiche est rattachée au **joueur**, pas au serveur : déplacer le bot sur un autre
  serveur (ou changer d’identifiant de serveur de test) ne fait perdre **aucune** fiche
  ni aucune image. Les anciennes clés `guildId:userId` restent lues et sont migrées
  automatiquement à la première sauvegarde ; les images `guildId-userId.ext` sont de même
  retrouvées puis renommées en `userId.ext`, pour que la fiche et sa photo suivent le
  joueur.
- Les anciens profils sont **migrés automatiquement** à la lecture : `characterClass`
  devient `grade`, et les nouveaux champs `age` et `role` prennent la valeur « Non
  renseigné ». Le concept d’**alignement** (clés v1 `camp` et v2 `alignment`) a été
  retiré du bot : ces anciennes clés sont simplement ignorées et disparaissent des
  fiches à la prochaine sauvegarde.
- Les images de personnage sont téléchargées dans `data/images/` et envoyées via
  `attachment://`. C’est volontaire : les URL de pièces jointes Discord sont signées et
  **expirent**, donc stocker l’URL seule finissait par casser les fiches.
- Les écritures sont atomiques (fichier temporaire puis remplacement) et encodées en
  UTF-8, ce qui préserve les accents sous Windows.

## Structure

```
main.py                       point d’entrée (--sync, --verbose)
config/emojis.json            catalogue des emojis du serveur
config/blackflash.json        traits/évènements qui relèvent la chance de Black Flash
assets/banniere_jjk.png       bannière locale, jointe en tête et en pied des réponses
assets/blackflash_*.png       Images locales du Black Flash (succès / échec)
assets/record_rayon_noir.png  Image locale de l’évènement Record Man du Rayon Noir
assets/renaissance_*.png      Images locales de la Renaissance (succès / échec)
assets/train.png              Image locale de l’entraînement (/train)
jjkbot/
  config.py                   lecture du .env
  theme.py                    palettes et mise en forme des embeds
  emojis.py                   résolution emoji custom / repli unicode
  permissions.py              contrôle d’accès staff et administrateurs
  sessions.py                 états d’attente des parcours multi-étapes
  content/                    statistiques (et sous-stats), couleurs, arbre de compétences, Black Flash, Renaissance, entraînement et types d’interaction
  storage/                    fiches (profiles.py), images (images.py), demandes d’XP (requests.py) et réglages (settings.py)
  views/                      embeds et vues interactives (profil, compétences, blackflash, renaissance, train, demandes d’XP)
  cogs/                       commandes /profil, /competences, /jjk, /xp, /blackflash et /train (outils staff)
tests/                        tests unitaires (bibliothèque standard uniquement)
tools/preview.py              aperçu local des embeds (tools/preview.html)
tools/preview_blackflash.py   aperçu local du Black Flash (tools/blackflash.html)
tools/optimize_assets.py      allège bannière et images (nécessite Pillow)
```

## Déploiement (hébergeur type Eternodes)

### Ce qui doit être dans le dépôt GitHub

Le bot a besoin de ces fichiers et dossiers, et de rien d’autre :

```
main.py                  ← point d’entrée (commande de démarrage)
requirements.txt         ← dépendances, à la racine du dépôt
jjkbot/                  ← tout le code du bot
config/emojis.json       ← catalogue des emojis
assets/                  ← bannière du bot (banniere_jjk.png, servie en priorité)
tests/                   ← facultatif, utile pour tester avant de pousser
.env.example             ← modèle de configuration
.gitignore
README.md
```

### Alléger l’envoi (fichiers en trop)

Le projet **utile** fait une cinquantaine de fichiers. Les milliers de fichiers
qui ralentissent l’envoi viennent du dossier **`.venv/`** (l’environnement Python
local) et des caches `__pycache__/` — il ne faut **jamais** les envoyer : un
`git push` normal ne les inclut pas (ils sont dans `.gitignore`), mais un envoi du
dossier complet (glisser-déposer, zip, rar) les emporte et fait exploser le temps
d’upload.

Pour construire une archive propre, sans `.venv`, sans caches, sans données :

```bash
python tools/package.py          # dist/jjkbot-deploy.zip (~1,3 Mo, ~60 fichiers)
python tools/package.py --tar    # variante .tar.gz
python tools/package.py --folder # dist/upload/  ← à glisser sur GitHub
```

Cette archive est directement déposable sur l’hébergeur ; il ne reste qu’à lancer
`pip install -r requirements.txt` puis `python main.py`. `dist/` est ignoré par Git.

#### Envoi manuel sur GitHub (glisser-déposer)

Si tu envoies par l’interface web de GitHub, **ne glisse jamais le dossier du projet
entier** : il emporte le `.venv` (des milliers de fichiers, upload interminable) et
surtout **`data/`**, ce qui met tes fiches dans le dépôt — au redéploiement, seules
ces fiches-là reviennent, les autres sont perdues. Utilise plutôt
`python tools/package.py --folder`, ouvre `dist/upload/`, **sélectionne tout son
contenu** (pas le dossier) et dépose-le. Mieux encore, un `git push` classique
respecte `.gitignore` et ne fait partir que le code, en incrémental.

#### Après le clone sur l’hébergeur

Le dépôt ne contient **pas** `data/` : après un « tout supprimer puis cloner », la
base est donc vide. Conserve une copie de `data/profiles.json` et de `data/images/`,
et remets-les après le clone (ou définis `DATA_DIR` vers un dossier persistant).
`/jjk sauvegarde` te donne cette copie en un clic, `/jjk restaurer` la remet.

> 💡 **Dépôt Git lourd ?** L’historique peut conserver d’anciens gros fichiers
> (images supprimées, `__pycache__` autrefois suivis) et rendre le clone Wispbyte
> lent, même si le dépôt actuel est léger. Dans ce cas, purger l’historique avec
> `git filter-branch` (ou repartir d’un dépôt neuf à partir de cette archive)
> ramène le clone à quelques mégaoctets.

### Ce qui ne doit JAMAIS être dans le dépôt

| Élément | Pourquoi |
|---|---|
| `.env` | contient le **token du bot** : à saisir sur l’hébergeur, jamais sur GitHub |
| `data/profiles.json` | données vivantes du serveur : seraient écrasées à chaque déploiement |
| `data/images/` | images des personnages : lourdes et propres à l’instance qui tourne |
| `.venv/`, `__pycache__/`, `bot.log` | inutiles sur l’hébergeur, générés automatiquement |

Le `.gitignore` du projet exclut déjà tout cela.

### Réglages côté hébergeur

| Réglage | Valeur |
|---|---|
| Runtime | **Python 3.11 ou plus** (3.10 minimum ; `audioop-lts` est tiré automatiquement en 3.13+) |
| Commande d’installation | `pip install -r requirements.txt` |
| Commande de démarrage | `python main.py` |

Ne mets **jamais** `--sync` dans la commande de démarrage : le bot s’arrêterait aussitôt.
La synchronisation des commandes se fait toute seule à chaque démarrage.

Les variables d’environnement (`DISCORD_TOKEN`, `CLIENT_ID`, `GUILD_ID`, `THEME`, `BANNER_URL`…) se
renseignent dans le panneau de l’hébergeur. Créer un fichier `.env` à la main fonctionne aussi :
le bot lit les deux, et une variable du panneau a toujours la priorité sur le fichier. Ne mets
`GUILD_ID` que pendant les tests — laisse-le vide en production pour enregistrer les commandes
globalement.

#### Wispbyte (hébergeur Pterodactyl)

Le crash `La variable d’environnement DISCORD_TOKEN est manquante` signifie simplement que le
process n’a reçu aucun token — ni le clone git ni l’installation des dépendances ne sont en cause.

1. **Onglet « Startup »** → section **« Environment Variables »** → ajoute `DISCORD_TOKEN`
   (valeur = le token du portail développeur), puis `CLIENT_ID`, `GUILD_ID` et `THEME` si tu
   veux les fixer → **Save** → redémarre le serveur.
2. **Ou**, dans l’onglet **« Files »**, crée un fichier `.env` à la **racine** du serveur
   (au même niveau que `main.py`) et colle le contenu de [.env.example](.env.example) en le
   complétant. Il n’arrive jamais par `git` (il est dans `.gitignore`) : c’est normal, il faut
   le créer à la main.

Après un redéploiement qui reclone tout le dossier, vérifie que le `.env` est toujours là —
garde une copie quelque part. Le démarrage doit rester `python main.py` : **jamais** `--sync`.

#### `429 Too Many Requests` / Cloudflare « Error 1015 » au démarrage

Si la console affiche une page HTML **Cloudflare « Error 1015 »** avec
`You are being rate limited`, Discord refuse **temporairement** les connexions depuis
l’IP de l’hébergeur (souvent partagée entre plusieurs clients). Ce n’est **pas** un bug du
bot, ni un problème de token : la même IP est bloquée pour tout le monde pendant un moment.

Le piège est la **boucle** : le crash fait sortir le process en code 1, l’hébergeur le
relance en quelques secondes, la nouvelle tentative rapprochée **relance le compteur et
prolonge le blocage**. Depuis cette version, le bot gère le cas tout seul : il affiche une
explication claire, patiente (2 min, 5 min, 15 min, puis 30 min entre les essais) et se
connecte dès que Discord lève la limite — sans que tu aies à redémarrer quoi que ce soit.

Si tu veux forcer la main :

1. **Arrête** le serveur (pour ne plus insister) et laisse passer ~1 h.
2. Vérifie qu’**une seule** instance du bot tourne : un bot lancé en local avec le même
token fait aussi grimper le compteur.
3. Redémarre une fois. Si le 1015 revient encore, c’est l’IP partagée de l’hébergeur qui est
flaggée : contacte le support / change d’offre pour obtenir une IP différente.

### Ressources et persistance

- Le bot consomme environ **60 Mo de RAM** : les 512 Mo d’une offre gratuite sont largement suffisants.
- `data/profiles.json` et `data/images/` vivent sur le disque de l’instance. Si l’hébergeur
efface le dossier lors d’un redéploiement, pense à **télécharger régulièrement une copie de
`data/profiles.json`** comme sauvegarde, puis à la remettre en place en cas de réinitialisation.

## Tests

```bash
python -m unittest discover -s tests
```

Les tests couvrent la mise en forme des embeds, la résolution des emojis, la migration
des fiches, l’écriture UTF-8, l’intégrité de l’arbre de compétences, les règles du
Black Flash, le nuancier de couleurs, le stockage des demandes d’XP (et le crédit
unique au clic), les attentes de session et la reprise sur refus temporaire de Discord
(429 / Cloudflare 1015). Aucune connexion à Discord n’est nécessaire.

## Aperçu du rendu

Pour voir le rendu des embeds sans lancer le bot ni redéployer l’hébergeur :

```bash
python tools/preview.py     # écrit tools/preview.html
```

Le fichier est construit par le **vrai** code de rendu : c’est exactement ce que Discord
affichera, aux polices système et aux emojis custom près. Ouvre-le dans un navigateur
(ou dans le panneau Preview de l’éditeur).
