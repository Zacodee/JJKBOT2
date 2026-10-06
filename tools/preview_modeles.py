"""Aperçu comparatif de modèles de mise en page pour la page Profil.

Le fichier `tools/modeles.html` présente côte à côte, rendus exactement comme
Discord les afficherait (police, titres, `code`, champs d’embed), plusieurs
propositions de structure pour la première page de la fiche. Le choix se fait
en discutant, puis le modèle retenu est implémenté dans
`jjkbot.views.profil.build_profile_embeds`.

    python tools/preview_modeles.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

OUTPUT = Path(__file__).resolve().parent / "modeles.html"

# Jeu de valeurs identique à celui de `preview.py`.
IDENTITE, AGE, RACE, GRADE = "Zuruï", "1 an", "Fléau", "Spécial"
ROLE = "Fléaux"
CITATION = "Tricheur, menteur, porte malheur.. tout ces jolie nom pour parlé de moi... le quel choisit ?"

# Citation tronquée (6e cellule) et valeur de démonstration pour une 6e cellule.
CITATION_COURTE = CITATION[:70].rstrip() + "…"
POINTS = "3"

MODELS: list[dict] = [
    {
        "label": "Modèle 1 — Compact : une ligne par paire",
        "note": "4 lignes au total, tout démarre à gauche sur la même colonne, aucune valeur orpheline.",
        "title": "## 📛 Profil : @izouk",
        "description": "\n\n".join(
            [
                f"🪪 **Identité :** `{IDENTITE}`   •   ⏳ **Âge :** `{AGE}`",
                f"🧬 **Race :** `{RACE}`   •   🎖️ **Grade :** `{GRADE}`",
                f"🎭 **Rôle :** `{ROLE}`",
                f"❯ **Citation** ❝ *{CITATION}* ❞",
            ]
        ),
        "fields": [],
    },
    {
        "label": "Modèle 2 — Grille d’embed (CHOISI) : libellé gras souligné, valeur encadrée",
        "note": "Champs inline alignés par Discord lui-même (3 par ligne). Discord n’affiche ni les titres ### ni le Markdown dans les noms de champ : le libellé vit donc en gras souligné dans la valeur, avec sa valeur encadrée en ``code`` dessous. 5 informations, l’alignement ayant été retiré du bot.",
        "title": "## 📛 Profil : @izouk",
        "description": "",
        "fields": [
            {"name": "​", "value": f"🪪 **__Identité__**\n➺ 【 ``{IDENTITE}`` 】", "inline": True},
            {"name": "​", "value": f"⏳ **__Âge__**\n➺ 【 ``{AGE}`` 】", "inline": True},
            {"name": "​", "value": f"🧬 **__Race__**\n➺ 【 ``{RACE}`` 】", "inline": True},
            {"name": "​", "value": f"🎖️ **__Grade__**\n➺ 【 ``{GRADE}`` 】", "inline": True},
            {"name": "​", "value": f"🎭 **__Rôle__**\n➺ 【 ``{ROLE}`` 】", "inline": True},
            {"name": "​", "value": f"❯ **Citation** ❝ *{CITATION}* ❞", "inline": False},
        ],
    },
    {
        "label": "Modèle 3 — Un grand titre `###` par champ",
        "note": "Chaque champ tient sur sa ligne : libellé géant et valeur ensemble, colonne de gauche toujours alignée.",
        "title": "## 📛 Profil : @izouk",
        "description": "\n\n".join(
            [
                f"### 🪪 __Identité__ : `{IDENTITE}`",
                f"### ⏳ __Âge__ : `{AGE}`",
                f"### 🧬 __Race__ : `{RACE}`",
                f"### 🎖️ __Grade__ : `{GRADE}`",
                f"### 🎭 __Rôle__ : `{ROLE}`",
                f"❯ **Citation** ❝ *{CITATION}* ❞",
            ]
        ),
        "fields": [],
    },
    {
        "label": "Modèle 4 — Un grand titre `###` par paire, tout sur une ligne",
        "note": "Titres aussi gros que demandé, mais libellés et valeurs restent sur la MÊME ligne : impossible de se décaler.",
        "title": "## 📛 Profil : @izouk",
        "description": "\n\n".join(
            [
                f"### 🪪 __Identité__ : `{IDENTITE}`   •   ⏳ __Âge__ : `{AGE}`",
                f"### 🧬 __Race__ : `{RACE}`   •   🎖️ __Grade__ : `{GRADE}`",
                f"### 🎭 __Rôle__ : `{ROLE}`",
                f"❯ **Citation** ❝ *{CITATION}* ❞",
            ]
        ),
        "fields": [],
    },
    {
        "label": "Modèle 5 — Tableau aligné (bloc de code)",
        "note": "Colonnes parfaitement calées, mais les emojis custom du serveur ne sont pas rendus dans un bloc de code (bug déjà connu sur Statistiques).",
        "title": "## 📛 Profil : @izouk",
        "description": "\n".join(
            [
                "```",
                "🪪 Identité      Zuruï",
                "⏳ Âge           1 an",
                "🧬 Race          Fléau",
                "🎖️ Grade         Spécial",
                "🎭 Rôle          Fléaux",
                "```",
                f"❯ **Citation** ❝ *{CITATION}* ❞",
            ]
        ),
        "fields": [],
    },
]

# --- Propositions : combler le trou laissé par le retrait de l’alignement ----
#
# Discord place 3 champs inline par rangée : 5 informations donnent 3 + 2, et la
# troisième case de la deuxième rangée reste vide. Voici quatre manières de la
# remplir, toutes dans le même style (emoji + libellé gras souligné + valeur
# encadrée).
CELL = lambda key, label, value: {  # noqa: E731 - littéral de mise en page
    "name": "\u200b",
    "value": f"{key} **__{label}__**\n➺ 【 ``{value}`` 】",
    "inline": True,
}
WIDE = lambda key, label, value: {  # noqa: E731 - littéral de mise en page
    "name": "\u200b",
    "value": f"{key} **__{label}__** ➺ 【 ``{value}`` 】",
    "inline": False,
}

PROPOSALS: list[dict] = [
    {
        "label": "Proposition A — La citation prend la 6e cellule",
        "note": "Les 5 informations + la citation occupent exactement 6 cellules : deux rangées pleines, aucun trou. La citation est tronquée à 70 caractères pour tenir dans une colonne — son texte intégral disparaît de la page.",
        "title": "## 📛 Profil : @izouk",
        "description": "",
        "fields": [
            CELL("🪪", "Identité", IDENTITE),
            CELL("⏳", "Âge", AGE),
            CELL("🧬", "Race", RACE),
            CELL("🎖️", "Grade", GRADE),
            CELL("🎭", "Rôle", ROLE),
            CELL("❯", "Citation", CITATION_COURTE),
        ],
    },
    {
        "label": "Proposition B — Une rangée en colonnes, le reste en pleine largeur",
        "note": "Rangée 1 complète (Identité · Âge · Race), puis Grade, Rôle et Citation chacun sur sa propre ligne pleine largeur. Aucun trou, hiérarchie nette, citation intégrale. Plus haut que la grille pure.",
        "title": "## 📛 Profil : @izouk",
        "description": "",
        "fields": [
            CELL("🪪", "Identité", IDENTITE),
            CELL("⏳", "Âge", AGE),
            CELL("🧬", "Race", RACE),
            WIDE("🎖️", "Grade", GRADE),
            WIDE("🎭", "Rôle", ROLE),
            {"name": "\u200b", "value": f"❯ **Citation** ❝ *{CITATION}* ❞", "inline": False},
        ],
    },
    {
        "label": "Proposition C — Tout en pleine largeur (aucune colonne)",
        "note": "Plus de grille du tout : chaque information tient sur sa ligne, donc aucun trou possible. Le plus lisible sur téléphone, mais c’est 6 blocs au lieu de 4 lignes.",
        "title": "## 📛 Profil : @izouk",
        "description": "",
        "fields": [
            WIDE("🪪", "Identité", IDENTITE),
            WIDE("⏳", "Âge", AGE),
            WIDE("🧬", "Race", RACE),
            WIDE("🎖️", "Grade", GRADE),
            WIDE("🎭", "Rôle", ROLE),
            {"name": "\u200b", "value": f"❯ **Citation** ❝ *{CITATION}* ❞", "inline": False},
        ],
    },
    {
        "label": "Proposition D — Deux rangées pleines + citation en dessous",
        "note": "La grille reste en 2 × 3 : la 6e cellule affiche les points de statistique disponibles (💠 `3`), et la citation garde toute sa place en pleine largeur sous la grille. Aucune donnée n’est tronquée.",
        "title": "## 📛 Profil : @izouk",
        "description": "",
        "fields": [
            CELL("🪪", "Identité", IDENTITE),
            CELL("⏳", "Âge", AGE),
            CELL("🧬", "Race", RACE),
            CELL("🎖️", "Grade", GRADE),
            CELL("🎭", "Rôle", ROLE),
            CELL("💠", "Points", POINTS),
            {"name": "\u200b", "value": f"❯ **Citation** ❝ *{CITATION}* ❞", "inline": False},
        ],
    },
]

TEMPLATE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Modèles de mise en page — profil JJK RP</title>
<style>
  :root { color-scheme: dark; }
  body {
    margin: 0; padding: 28px; background: #313338; color: #dbdee1;
    font-family: "gg sans", "Noto Sans", Helvetica, Arial, sans-serif;
    display: flex; flex-direction: column; gap: 20px; align-items: flex-start;
  }
  h1 { font-size: 15px; font-weight: 600; color: #949ba4; margin: 0; letter-spacing: .04em; text-transform: uppercase; }
  .legend { font-size: 13px; color: #b5bac1; max-width: 760px; line-height: 1.5; }
  .model { display: flex; flex-direction: column; gap: 8px; align-items: flex-start; }
  .tag { font-size: 13px; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; color: #a9f4c1; }
  .note { font-size: 13px; color: #b5bac1; max-width: 760px; line-height: 1.5; }
  .embed {
    background: #2b2d31; border-left: 4px solid #9a0a16; border-radius: 4px;
    padding: 12px 16px; width: 480px; display: flex; flex-direction: column; gap: 8px;
  }
  .author { display: flex; align-items: center; gap: 8px; font-size: 14px; font-weight: 600; color: #f2f3f5; }
  .avatar { width: 24px; height: 24px; border-radius: 50%; background: #5865f2; }
  .desc { font-size: 14px; line-height: 1.45; white-space: pre-wrap; }
  .field-name { font-size: 14px; font-weight: 700; color: #f2f3f5; }
  .field-value { font-size: 14px; color: #dbdee1; }
  .footer { font-size: 12px; color: #949ba4; }
  .h1 { font-size: 22px; font-weight: 700; color: #f2f3f5; }
  .h2 { font-size: 18px; font-weight: 700; color: #f2f3f5; }
  .h3 { font-size: 16px; font-weight: 700; color: #f2f3f5; }
  code {
    background: #1e1f22; border-radius: 4px; padding: .12em .32em;
    font-family: Consolas, "Courier New", monospace; font-size: .86em;
  }
  pre.codeblock {
    background: #1e1f22; border: 1px solid #232428; border-radius: 4px;
    padding: 8px 10px; margin: 4px 0; font-family: Consolas, "Courier New", monospace;
    font-size: 13px; line-height: 1.4; white-space: pre;
  }
  u { text-decoration-thickness: 1px; text-underline-offset: 2px; }
  /* Grille de 3 colonnes, comme Discord : une rangée incomplète laisse
     exactement le « trou » que l’on cherche à combler. */
  .fields { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px 16px; }
  .field { min-width: 0; }
</style>
</head>
<body>
<h1>Modèles proposés — page « Profil »</h1>
<p class="legend">
  Mises en page rendues comme Discord les affichera. Les pastilles
  <span class="cemoji" style="display:inline-block;background:#5865f2;color:#fff;border-radius:4px;padding:0 .35em;font-size:.82em;">:nom:</span>
  représentent les emojis custom du serveur.
</p>
<div id="models"></div>
<script>
const MODELS = __MODELS__;
const PROPOSALS = __PROPOSALS__;

function escapeHtml(text) {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function renderInline(text) {
  return text
    .replace(/\\*\\*([^*\\n]+)\\*\\*/g, "<strong>$1</strong>")
    .replace(/__([^_\\n]+)__/g, "<u>$1</u>")
    .replace(/``([^`\\n]+)``/g, "<code>$1</code>")
    .replace(/`([^`\\n]+)`/g, "<code>$1</code>")
    .replace(/\\*([^*\\n]+)\\*/g, "<em>$1</em>")
    .replace(/&lt;a?:(\\w+):\\d+&gt;/g, '<span style="display:inline-block;background:#5865f2;color:#fff;border-radius:4px;padding:0 .35em;font-size:.82em;">:$1:</span>');
}

function markdown(text) {
  const lines = escapeHtml(text).split("\\n");
  const out = [];
  let inCode = false;
  let buffer = [];
  for (const line of lines) {
    if (line.trim().startsWith("```")) {
      if (inCode) { out.push('<pre class="codeblock">' + buffer.join("\\n") + "</pre>"); buffer = []; inCode = false; }
      else { inCode = true; }
      continue;
    }
    if (inCode) { buffer.push(line); continue; }
    const heading = line.match(/^(#{1,3})\\s+(.*)$/);
    if (heading) {
      out.push('<div class="h' + heading[1].length + '">' + renderInline(heading[2]) + "</div>");
      continue;
    }
    out.push(renderInline(line));
  }
  if (inCode) { out.push('<pre class="codeblock">' + buffer.join("\\n") + "</pre>"); }
  return out.join("\\n");
}

function panel(entry) {
  const inline = entry.fields.filter((f) => f.inline);
  const wide = entry.fields.filter((f) => !f.inline);
  const label = (text) => (text.replace(/[\\u200b\\s]/g, "")
    ? `<div class="field-name">${markdown(text)}</div>` : "");
  const grid = inline.length
    ? '<div class="fields">' + inline.map((f) => `
        <div class="field">
          ${label(f.name)}
          <div class="field-value">${markdown(f.value)}</div>
        </div>`).join("") + "</div>"
    : "";
  const wideFields = wide.map((f) => `
        <div>
          ${label(f.name)}
          <div class="field-value">${markdown(f.value)}</div>
        </div>`).join("");
  return `
    <div class="model">
      <span class="tag">${escapeHtml(entry.label)}</span>
      <span class="note">${escapeHtml(entry.note)}</span>
      <div class="embed">
        <div class="author"><div class="avatar"></div>izouk</div>
        ${entry.title ? `<div class="desc">${markdown(entry.title)}</div>` : ""}
        ${entry.description ? `<div class="desc">${markdown(entry.description)}</div>` : ""}
        ${grid}
        ${wideFields}
        <div class="footer">Page 1 / 3</div>
      </div>
    </div>`;
}

document.getElementById("models").innerHTML =
  MODELS.map(panel).join("") +
  `<h1>Après le retrait de l’alignement — combler le trou de la rangée 2</h1>
   <p class="legend">Discord place <b>3 champs inline par rangée</b> : avec 5 informations,
   la deuxième rangée n’en contient que 2 et il reste une case vide à droite du Rôle.
   Quatre façons de la combler, en gardant le même style (emoji + libellé gras souligné +
   valeur encadrée). Dis la lettre que tu veux (ou un mélange) et je l’implémente.</p>` +
  PROPOSALS.map(panel).join("");
</script>
</body>
</html>
"""


def main() -> None:
    page = TEMPLATE.replace("__MODELS__", json.dumps(MODELS, ensure_ascii=False)).replace(
        "__PROPOSALS__", json.dumps(PROPOSALS, ensure_ascii=False)
    )
    OUTPUT.write_text(page, encoding="utf-8")
    print(f"Aperçu écrit : {OUTPUT}")


if __name__ == "__main__":
    main()
