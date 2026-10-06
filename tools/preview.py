"""Aperçu local des embeds, sans connexion à Discord.

Le fichier `tools/preview.html` est produit par le **vrai** code de rendu
(`jjkbot.views.profil.build_profile_embeds`) : ce que tu vois dans le panneau
Preview est ce que Discord affichera, aux polices près.

Deux colonnes sont produites pour chaque page :

- **Avant le correctif** : les embeds sont construits sans serveur, donc chaque
  emoji retombe sur son repli unicode exactement comme le bug le faisait ;
- **Après le correctif** : un serveur factice expose les emojis custom, qui sont
  alors insérés dans le texte (`<:jjk_xxx:id>`), comme sur Discord.

    python tools/preview.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from jjkbot.emojis import emojis as resolver  # noqa: E402
from jjkbot.storage.profiles import Profile  # noqa: E402
from jjkbot.views.profil import PAGES, build_profile_embeds  # noqa: E402

OUTPUT = Path(__file__).resolve().parent / "preview.html"


class _StubAvatar:
    url = ""


class _StubUser:
    """Utilisateur factice : `build_profile_embeds` ne lit que ces attributs."""

    id = 651499309933658116
    mention = "<@651499309933658116>"
    display_name = "izouk"
    display_avatar = _StubAvatar()


class _FakeEmoji:
    """Emoji de serveur factice, rendu comme Discord le ferait."""

    def __init__(self, name: str, emoji_id: int, animated: bool = False):
        self.name = name
        self.id = emoji_id
        self.animated = animated

    def __str__(self) -> str:
        return f"<{'a' if self.animated else ''}:{self.name}:{self.id}>"


class _FakeGuild:
    """Serveur factice portant tous les emojis du catalogue."""

    id = 424242

    def __init__(self) -> None:
        self.emojis = [
            _FakeEmoji(spec.name, 9000 + index)
            for index, spec in enumerate(resolver.catalog.values())
        ]


SAMPLE = Profile(
    name="Zuruï",
    age="1 an",
    race="Fléau",
    grade="Spécial",
    role="Fléaux",
    quote="Tricheur, menteur, porte malheur.. tout ces jolie nom pour parlé de moi... le quel choisit ?",
    traits=["Sournois", "Bavard"],
    flaws=["Imprévisible"],
)


def _collect(guild) -> list[dict]:
    user = _StubUser()
    panels: list[dict] = []
    for page, label, _key in PAGES:
        # Le contenu utile est le dernier embed : le premier est la bannière.
        embed = build_profile_embeds(SAMPLE, user, page, guild)[-1]
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
  .legend { font-size: 13px; color: #b5bac1; max-width: 720px; line-height: 1.5; }
  .section-label { font-size: 13px; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; }
  .section-label.bad { color: #f4a9a9; }
  .section-label.good { color: #a9f4c1; }
  .pair { display: flex; flex-wrap: wrap; gap: 20px; align-items: flex-start; }
  .column { display: flex; flex-direction: column; gap: 8px; }
  .tag { font-size: 12px; font-weight: 700; color: #949ba4; text-transform: uppercase; letter-spacing: .06em; }
  .tag.bad { color: #f4a9a9; }
  .tag.good { color: #a9f4c1; }
  .embed {
    background: #2b2d31; border-left: 4px solid var(--c, #5865f2); border-radius: 4px;
    padding: 12px 16px; width: 480px; display: flex; flex-direction: column; gap: 8px;
  }
  .author { display: flex; align-items: center; gap: 8px; font-size: 14px; font-weight: 600; color: #f2f3f5; }
  .avatar { width: 24px; height: 24px; border-radius: 50%; background: #5865f2; }
  .title { font-size: 16px; font-weight: 700; color: #f2f3f5; }
  .desc, .field-value { font-size: 14px; line-height: 1.45; white-space: pre-wrap; }
  .field-name { font-size: 14px; font-weight: 700; color: #f2f3f5; margin-top: 4px; }
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
  .cemoji {
    display: inline-block; background: #5865f2; color: #fff; border-radius: 4px;
    padding: 0 .35em; font-size: .82em; font-weight: 600; vertical-align: baseline;
  }
</style>
</head>
<body>
<h1>Aperçu généré par jjkbot — profil de Zuruï</h1>
<p class="legend">
  Les pastilles bleues <span class="cemoji">:nom:</span> représentent les
  <strong>emojis custom du serveur</strong> (rendus ici en texte, ils apparaissent
  en image sur Discord). Dans la colonne «&nbsp;Avant&nbsp;» le bot retombait sur
  les emojis unicode : c’est le bug de l’intent <code>emojis</code>.
</p>
<div class="section-label bad">Avant le correctif — replis unicode</div>
<div id="before" class="pair"></div>
<div class="section-label good">Après le correctif — emojis custom du serveur</div>
<div id="after" class="pair"></div>
<script>
const BEFORE = __BEFORE__;
const AFTER = __AFTER__;

function escapeHtml(text) {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function renderInline(text) {
  return text
    .replace(/\\*\\*([^*\\n]+)\\*\\*/g, "<strong>$1</strong>")
    .replace(/__([^_\\n]+)__/g, "<u>$1</u>")
    .replace(/`([^`\\n]+)`/g, "<code>$1</code>")
    .replace(/\\*([^*\\n]+)\\*/g, "<em>$1</em>")
    .replace(/&lt;a?:(\\w+):\\d+&gt;/g, '<span class="cemoji" title="emoji du serveur">:$1:</span>');
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
      const level = heading[1].length;
      out.push('<div class="h' + level + '">' + renderInline(heading[2]) + "</div>");
      continue;
    }
    out.push(renderInline(line));
  }
  if (inCode) { out.push('<pre class="codeblock">' + buffer.join("\\n") + "</pre>"); }
  return out.join("\\n");
}

function panel(entry, tone) {
  return `
  <div class="column">
    <span class="tag ${tone}">${escapeHtml(entry.label)}</span>
    <div class="embed" style="--c:${entry.colour}">
      <div class="author"><div class="avatar"></div>izouk</div>
      <div class="title">${markdown(entry.title)}</div>
      <div class="desc">${markdown(entry.description)}</div>
      ${entry.fields.map((field) => `
        <div>
          ${field.name.replace(/[\\u200b\\s]/g, "") ? `<div class="field-name">${markdown(field.name)}</div>` : ""}
          <div class="field-value">${markdown(field.value)}</div>
        </div>`).join("")}
      <div class="footer">${escapeHtml(entry.footer)}</div>
    </div>
  </div>`;
}

document.getElementById("before").innerHTML = BEFORE.map(e => panel(e, "bad")).join("");
document.getElementById("after").innerHTML = AFTER.map(e => panel(e, "good")).join("");
</script>
</body>
</html>
"""


def main() -> None:
    guild = _FakeGuild()
    # Pas de `resolver.refresh` ici : « Avant » doit montrer les replis unicode,
    # et « Après » se résout grâce aux emojis lus directement sur le serveur.
    resolver.refresh(())

    before = _collect(None)
    after = _collect(guild)

    page = TEMPLATE.replace("__BEFORE__", json.dumps(before, ensure_ascii=False))
    page = page.replace("__AFTER__", json.dumps(after, ensure_ascii=False))
    OUTPUT.write_text(page, encoding="utf-8")
    print(f"Aperçu écrit : {OUTPUT}")


if __name__ == "__main__":
    main()
