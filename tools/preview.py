"""Aperçu local des embeds, sans connexion à Discord.

Le fichier `tools/preview.html` est produit par le **vrai** code de rendu
(`jjkbot.views.profil.build_profile_embeds`) : ce que tu vois dans le panneau
Preview est ce que Discord affichera, aux polices système et aux emojis près.

    python tools/preview.py
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from jjkbot.storage.profiles import Profile  # noqa: E402
from jjkbot.views.profil import PAGES, build_profile_embeds  # noqa: E402

OUTPUT = Path(__file__).resolve().parent / "preview.html"


class _StubAvatar:
    url = ""


class _StubUser:
    """Utilisateur factice : `build_profile_embeds` ne lit que ces attributs."""

    id = 651499309933658116
    mention = "@izouk"
    display_name = "izouk"
    display_avatar = _StubAvatar()


SAMPLE = Profile(
    name="Zuruï",
    age="1 an",
    race="Fléau",
    grade="Spécial",
    alignment="Chaotique mauvais",
    role="Fléaux",
    quote="Tricheur, menteur, porte malheur.. tout ces jolie nom pour parlé de moi... le quel choisit ?",
    traits=["Sournois", "Bavard"],
    flaws=["Imprévisible"],
)

# Rendu d'avant la refonte, conservé pour comparer côte à côte.
BEFORE = "\n".join(
    [
        '📛 — __Profil__ : @izouk',
        '│ · 🪪 [Identité] → ["Zuruï"]',
        '╰ · ⏳ Âge : [1 an]',
        '',
        '│ · 🧬 [Race] → ["Fléau"]',
        '╰ · 🎖️ [Grade] : [Spécial]',
        '',
        '│ · ⚖️ [Alignement] → ["Chaotique mauvais"]',
        '╰ · 🎭 [Rôle] : [Fléaux]',
        '',
        '┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈',
        '',
        '❯ **Citation**',
        '❝ Tricheur, menteur, porte malheur.. ❞',
    ]
)


def _collect() -> list[dict]:
    user = _StubUser()
    panels: list[dict] = []
    for page, label, _key in PAGES:
        # Le contenu utile est le dernier embed : le premier est la bannière.
        embed = build_profile_embeds(SAMPLE, user, page, None)[-1]
        panels.append(
            {
                "label": label,
                "title": embed.title or "",
                "description": embed.description or "",
                "fields": [
                    {"name": field.name, "value": field.value, "inline": field.inline}
                    for field in embed.fields
                ],
                "footer": embed.footer.text or "",
                "colour": f"#{embed.colour.value:06x}",
            }
        )
    return panels


TEMPLATE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Aperçu des embeds — JJK RP</title>
<style>
  :root { color-scheme: dark; }
  body {
    margin: 0; padding: 28px; background: #313338; color: #dbdee1;
    font-family: "gg sans", "Noto Sans", Helvetica, Arial, sans-serif;
    display: flex; flex-direction: column; gap: 24px; align-items: flex-start;
  }
  h1 { font-size: 15px; font-weight: 600; color: #949ba4; margin: 0; letter-spacing: .04em; text-transform: uppercase; }
  .pair { display: flex; flex-wrap: wrap; gap: 20px; align-items: flex-start; }
  .column { display: flex; flex-direction: column; gap: 8px; }
  .tag { font-size: 12px; font-weight: 700; color: #949ba4; text-transform: uppercase; letter-spacing: .06em; }
  .embed {
    background: #2b2d31; border-left: 4px solid var(--c, #5865f2); border-radius: 4px;
    padding: 12px 16px; width: 480px; display: flex; flex-direction: column; gap: 8px;
  }
  .author { display: flex; align-items: center; gap: 8px; font-size: 14px; font-weight: 600; color: #f2f3f5; }
  .avatar { width: 24px; height: 24px; border-radius: 50%; background: #5865f2; }
  .title { font-size: 16px; font-weight: 700; color: #f2f3f5; }
  .desc { font-size: 14px; line-height: 1.45; white-space: pre-wrap; }
  .field-name { font-size: 14px; font-weight: 700; color: #f2f3f5; margin-top: 4px; }
  .field-value { font-size: 14px; line-height: 1.45; }
  .footer { font-size: 12px; color: #949ba4; }
  code {
    background: #1e1f22; border-radius: 4px; padding: .12em .32em;
    font-family: Consolas, "Courier New", monospace; font-size: .86em;
  }
  u { text-decoration-thickness: 1px; text-underline-offset: 2px; }
</style>
</head>
<body>
<h1>Aperçu généré par jjkbot — profil de Zuruï</h1>
<div class="pair">
  <div class="column">
    <span class="tag">Avant</span>
    <div class="embed" style="--c:#8B5CF6"><div class="desc" id="before"></div></div>
  </div>
</div>
<div id="panels" class="pair"></div>
<script>
const PANELS = __PANELS__;
const BEFORE = __BEFORE__;

function escapeHtml(text) {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function markdown(text) {
  const escaped = escapeHtml(text);
  return escaped.replace(/(`[^`\\n]+`|\\*\\*[^*\\n]+\\*\\*|__[^_\\n]+__|\\*[^*\\n]+\\*)/g, (match) => {
    if (match.startsWith("`")) return "<code>" + match.slice(1, -1) + "</code>";
    if (match.startsWith("**")) return "<strong>" + match.slice(2, -2) + "</strong>";
    if (match.startsWith("__")) return "<u>" + match.slice(2, -2) + "</u>";
    return "<em>" + match.slice(1, -1) + "</em>";
  });
}

document.getElementById("before").innerHTML = markdown(BEFORE);

document.getElementById("panels").innerHTML = PANELS.map((panel) => `
  <div class="column">
    <span class="tag">Après — ${escapeHtml(panel.label)}</span>
    <div class="embed" style="--c:${panel.colour}">
      <div class="author"><div class="avatar"></div>izouk</div>
      <div class="title">${markdown(panel.title)}</div>
      <div class="desc">${markdown(panel.description)}</div>
      ${panel.fields.map((field) => `
        <div>
          <div class="field-name">${markdown(field.name)}</div>
          <div class="field-value">${markdown(field.value)}</div>
        </div>`).join("")}
      <div class="footer">${escapeHtml(panel.footer)}</div>
    </div>
  </div>`).join("");
</script>
</body>
</html>
"""


def main() -> None:
    page = TEMPLATE.replace("__PANELS__", json.dumps(_collect(), ensure_ascii=False))
    page = page.replace("__BEFORE__", json.dumps(BEFORE, ensure_ascii=False))
    OUTPUT.write_text(page, encoding="utf-8")
    print(f"Aperçu écrit : {OUTPUT}")


if __name__ == "__main__":
    main()
