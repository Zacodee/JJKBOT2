# Bot Discord Jujutsu RP

Bot Discord **Python** dédié au support d’un serveur de roleplay écrit francophone.
Fiches de personnage, statistiques, arbre de compétences et guide des nouveaux membres,
présentés dans des embeds sobres et carrés qui utilisent les **emojis du serveur**.

## Prérequis

- Python **3.11 ou plus** (testé sur 3.13).
- Un bot Discord avec les permissions `Envoyer des messages`, `Intégrer des liens`,
  `Joindre des fichiers` et `Utiliser les commandes d’application`.
- **Aucun intent privilégié** n’est nécessaire (le bot ne demande que l’intent `guilds`).

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

## Configuration

| Variable | Rôle |
|---|---|
| `DISCORD_TOKEN` | Token privé du bot (obligatoire) |
| `CLIENT_ID` | Identifiant de l’application Discord (obligatoire) |
| `GUILD_ID` | Serveur de test : les commandes y apparaissent immédiatement |
| `THEME` | `violet` (défaut) ou `noblesse` |
| `BANNER_URL` | Bannière décorative affichée en haut de chaque réponse |
| `HELP_GIF_URL` | GIF affiché dans `/jjk help` |
| `STAFF_ROLE_ID` | Facultatif : rôle autorisé à utiliser les commandes du staff |

`BANNER_URL` attend une URL directe : héberge `assets/banniere_jjk.png` sur un service
qui fournit une URL de fichier (salon Discord, hébergeur d’images…). Sans `BANNER_URL`,
les réponses s’affichent simplement sans bannière.

Changer de thème ne demande aucune modification de code : `THEME=noblesse` rétablit
l’identité visuelle d’origine (bordeaux et or), `THEME=violet` utilise la palette de
référence. Les couleurs sont définies dans `jjkbot/theme.py`.

## Emojis du serveur

Chaque élément de l’interface (identité, âge, race, grade, alignement, rôle, citation,
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

## Commandes

### Profil

| Commande | Effet |
|---|---|
| `/profil voir [joueur]` | Affiche une fiche en 3 pages navigables (Profil, Statistiques, Traits & défauts) |
| `/profil creer` | Création guidée en 2 modales : identité/âge/race/grade/alignement puis rôle/citation/traits/défauts |
| `/profil modifier` | Met à jour une fiche existante |
| `/profil image fichier:` | Image du personnage (PNG, JPG, WEBP ou GIF, 8 Mo max) |
| `/profil attribuer-stat statistique: montant:` | Dépense ses points de statistique |
| `/profil donner-points joueur: montant:` | Ajoute des points *(staff)* |
| `/profil reset joueur: type:` | Réinitialise profil, statistiques ou compétences, avec confirmation par boutons *(staff)* |

Les cinq statistiques sont **Force**, **Résistance**, **Vitesse**, **Réserve d’EO** et
**Sortie d’EO** (`jjkbot/content/stats.py`).

### Compétences

| Commande | Effet |
|---|---|
| `/competences voir [joueur]` | Progression par catégorie, puis détail des paliers via un menu |
| `/competences acheter` | Panier multi-catégories : prérequis et XP revérifiés à la confirmation |
| `/competences xp joueur: montant:` | Ajoute de l’XP *(staff)* |

L’arbre complet (54 paliers, 6 catégories) est défini dans
[jjkbot/content/skill_tree.py](jjkbot/content/skill_tree.py) : chaque palier a un coût en
XP et des prérequis, qu’un niveau supérieur ne peut donc pas contourner.

### Guide

| Commande | Effet |
|---|---|
| `/jjk help` | Guide de démarrage illustré (GIF optionnel) |
| `/jjk emojis` | Diagnostic des emojis du serveur *(staff)* |

## Données

- Les fiches sont stockées dans `data/profiles.json` (enveloppe identique à l’ancienne
  version Node : `{"profiles": {"guildId:userId": {…}}}`).
- Les anciens profils sont **migrés automatiquement** à la lecture : `characterClass`
  devient `grade`, `camp` devient `alignment`, et les nouveaux champs `age` et `role`
  prennent la valeur « Non renseigné ». Aucune donnée n’est perdue.
- Les images de personnage sont téléchargées dans `data/images/` et envoyées via
  `attachment://`. C’est volontaire : les URL de pièces jointes Discord sont signées et
  **expirent**, donc stocker l’URL seule finissait par casser les fiches.
- Les écritures sont atomiques (fichier temporaire puis remplacement) et encodées en
  UTF-8, ce qui préserve les accents sous Windows.

## Structure

```
main.py                       point d’entrée (--sync, --verbose)
config/emojis.json            catalogue des emojis du serveur
jjkbot/
  config.py                   lecture du .env
  theme.py                    palettes et mise en forme des embeds
  emojis.py                   résolution emoji custom / repli unicode
  permissions.py              contrôle d’accès staff
  sessions.py                 états d’attente des parcours multi-étapes
  content/                    statistiques et arbre de compétences
  storage/                    fiches (profiles.py) et images (images.py)
  views/                      embeds et vues interactives (profil, compétences)
  cogs/                       commandes /profil, /competences et /jjk
tests/                        tests unitaires (bibliothèque standard uniquement)
```

## Déploiement (hébergeur type Eternodes)

### Ce qui doit être dans le dépôt GitHub

Le bot a besoin de ces fichiers et dossiers, et de rien d’autre :

```
main.py                  ← point d’entrée (commande de démarrage)
requirements.txt         ← dépendances, à la racine du dépôt
jjkbot/                  ← tout le code du bot
config/emojis.json       ← catalogue des emojis
assets/                  ← bannière (facultatif, seulement si servie localement)
tests/                   ← facultatif, utile pour tester avant de pousser
.env.example             ← modèle de configuration
.gitignore
README.md
```

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
le bot lit les deux. Ne mets `GUILD_ID` que pendant les tests — laisse-le vide en production pour
enregistrer les commandes globalement.

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
des fiches, l’écriture UTF-8, l’intégrité de l’arbre de compétences et les attentes de
session. Aucune connexion à Discord n’est nécessaire.
