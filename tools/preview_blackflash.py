"""Aperçu local de l’embed de Black Flash, sans connexion à Discord.

Le fichier `tools/blackflash.html` est produit par le **vrai** code de rendu
(`jjkbot.views.blackflash.build_blackflash_embed`) : ce que tu vois dans le
panneau Preview est ce que Discord affichera, aux polices et au GIF près.

Deux colonnes sont produites pour chaque issue :

- **Avec les emojis du serveur** : un serveur factice porte tous les emojis du
  catalogue, ils sont donc insérés en custom (`<:jjk_xxx:id>`) ;
- **Replis unicode** : aucun serveur, chaque emoji retombe sur son repli —
  c’est ce que verra un membre tant que les emojis ne sont pas créés.

    python tools/preview_blackflash.py
"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from jjkbot.emojis import emojis as resolver  # noqa: E402
from jjkbot.views.blackflash import (  # noqa: E402
    build_blackflash_embed,
    build_blackflash_record_embed,
)

OUTPUT = Path(__file__).resolve().parent / "blackflash.html"

# L’image est envoyée en `attachment://` : dans le HTML, on l’intègre en `data:`.
# Un chemin relatif (`../assets/…`) ne fonctionnerait que si la page est ouverte
# depuis le disque ; servie par un seul fichier, elle ne trouverait pas l’image.
ASSETS = {
    "attachment://blackflash_ok.png": "../assets/blackflash_ok.png",
    "attachment://blackflash_ko.png": "../assets/blackflash_ko.png",
    "attachment://record_rayon_noir.png": "../assets/record_rayon_noir.png",
}


def _data_uri(relative: str) -> str:
    """Image locale encodée en `data:`, ou chaîne vide si le fichier est absent."""
    path = (Path(__file__).resolve().parent / relative).resolve()
    if not path.is_file():
        return ""
    suffix = path.suffix.lstrip(".").lower()
    mime = "image/jpeg" if suffix in {"jpg", "jpeg"} else f"image/{suffix or 'png'}"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


GIFS = {key: _data_uri(path) for key, path in ASSETS.items()}


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
            _FakeEmoji(spec.name, 9500 + index)
            for index, spec in enumerate(resolver.catalog.values())
        ]


# Jeux d’essai : (succès, chance avant, chance après) / (échec, …).
CASES = (
    ("Succès", True, 15, 20),
    ("Échec", False, 15, 5),
)

# Second embed : (label, joueur, record personnel). Le titre est personnel :
# il n’y a ni détenteur unique, ni ancien record man à nommer.
RECORD_CASES = (
    ("Titre décroché", 7, "John zenin", 4),
    ("Record personnel amélioré", 9, "Mbappé", 6),
)


def _panel(label: str, guild, success: bool, before: int, after: int) -> dict:
    files = []
    embed = build_blackflash_embed(success, before, after, guild, files)
    # On ne transporte que la clé (`attachment://…`) : le HTML résout l’image
    # une seule fois, via `IMAGES`, au lieu de la dupliquer dans chaque panneau.
    gif = embed.image.url if embed.image else ""
    for file in files:
        file.close()
    return {
        "label": label,
        "title": embed.title or "",
        "description": embed.description or "",
        "footer": embed.footer.text or "",
        "colour": f"#{embed.colour.value:06x}",
        "gif": gif,
    }


def _collect(guild, suffix: str) -> list[dict]:
    return [_panel(f"{label} — {suffix}", guild, success, before, after) for label, success, before, after in CASES]


def _record_panel(
    label: str,
    guild,
    player_id: int,
    player_name: str,
    streak: int,
) -> dict:
    files = []
    embed = build_blackflash_record_embed(
        player_id, player_name, streak, guild, files
    )
    gif = embed.image.url if embed.image else ""
    for file in files:
        file.close()
    return {
        "label": label,
        "title": embed.title or "",
        "description": embed.description or "",
        "footer": embed.footer.text or "",
        "colour": f"#{embed.colour.value:06x}",
        "gif": gif,
    }


def _collect_record(guild, suffix: str) -> list[dict]:
    return [
        _record_panel(f"{label} — {suffix}", guild, player_id, player_name, streak)
        for label, player_id, player_name, streak in RECORD_CASES
    ]


TEMPLATE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Aperçu du Black Flash — JJK RP</title>
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
  .embed {
    background: #2b2d31; border-left: 4px solid var(--c, #5865f2); border-radius: 4px;
    padding: 12px 16px; width: 480px; display: flex; flex-direction: column; gap: 8px;
  }
  .title { font-size: 16px; font-weight: 700; color: #f2f3f5; }
  .desc { font-size: 14px; line-height: 1.45; white-space: pre-wrap; }
  .footer { font-size: 12px; color: #949ba4; }
  .gif { max-width: 100%; border-radius: 4px; display: block; }
  .h2 { font-size: 18px; font-weight: 700; color: #f2f3f5; }
  .h3 { font-size: 16px; font-weight: 700; color: #f2f3f5; }
  code {
    background: #1e1f22; border-radius: 4px; padding: .12em .32em;
    font-family: Consolas, "Courier New", monospace; font-size: .86em;
  }
  pre.codeblock {
    background: #1e1f22; border: 1px solid #232428; border-radius: 4px;
    padding: 8px 10px; margin: 4px 0; font-family: Consolas, "Courier New", monospace;
    font-size: 13px; line-height: 1.4; white-space: pre-wrap;
  }
  u { text-decoration-thickness: 1px; text-underline-offset: 2px; }
  .cemoji {
    display: inline-block; background: #5865f2; color: #fff; border-radius: 4px;
    padding: 0 .35em; font-size: .82em; font-weight: 600; vertical-align: baseline;
  }
  .mention {
    background: rgba(88, 101, 242, .3); color: #dee0fc; border-radius: 3px;
    padding: 0 2px; font-weight: 500;
  }
</style>
</head>
<body>
<h1>Aperçu généré par jjkbot — /jjk blackflash</h1>
<p class="legend">
  Les pastilles bleues <span class="cemoji">:nom:</span> représentent les
  <strong>emojis custom du serveur</strong> (rendus ici en texte, en image sur Discord).
  La colonne «&nbsp;Replis&nbsp;» montre ce que voit un membre tant que les emojis
  du catalogue ne sont pas créés sur le serveur.
</p>
<div class="section-label good">Avec les emojis du serveur</div>
<div id="custom" class="pair"></div>
<div class="section-label bad">Replis unicode (emojis absents)</div>
<div id="fallback" class="pair"></div>
<div class="section-label good">Second embed — Record Man du Rayon Noir (avec les emojis du serveur)</div>
<div id="record" class="pair"></div>
<div class="section-label bad">Second embed — Replis unicode</div>
<div id="record-fallback" class="pair"></div>
<script>
const CUSTOM = __CUSTOM__;
const FALLBACK = __FALLBACK__;
const RECORD = __RECORD__;
const RECORD_FALLBACK = __RECORD_FALLBACK__;
const IMAGES = __IMAGES__;

function escapeHtml(text) {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function renderInline(text) {
  return text
    .replace(/\\*\\*([^*\\n]+)\\*\\*/g, "<strong>$1</strong>")
    .replace(/__([^_\\n]+)__/g, "<u>$1</u>")
    .replace(/`([^`\\n]+)`/g, "<code>$1</code>")
    .replace(/\\*([^*\\n]+)\\*/g, "<em>$1</em>")
    .replace(/&lt;@!?(\\d+)&gt;/g, '<span class="mention" title="mention du joueur">@$1</span>')
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
      out.push('<div class="h' + heading[1].length + '">' + renderInline(heading[2]) + "</div>");
      continue;
    }
    out.push(renderInline(line));
  }
  if (inCode) { out.push('<pre class="codeblock">' + buffer.join("\\n") + "</pre>"); }
  return out.join("\\n");
}

function panel(entry) {
  return `
  <div class="column">
    <span class="tag">${escapeHtml(entry.label)}</span>
    <div class="embed" style="--c:${entry.colour}">
      <div class="title">${markdown(entry.title)}</div>
      <div class="desc">${markdown(entry.description)}</div>
      ${entry.gif && IMAGES[entry.gif] ? `<img class="gif" src="${IMAGES[entry.gif]}" alt="image du black flash">` : ""}
      <div class="footer">${escapeHtml(entry.footer)}</div>
    </div>
  </div>`;
}

document.getElementById("custom").innerHTML = CUSTOM.map(panel).join("");
document.getElementById("fallback").innerHTML = FALLBACK.map(panel).join("");
document.getElementById("record").innerHTML = RECORD.map(panel).join("");
document.getElementById("record-fallback").innerHTML = RECORD_FALLBACK.map(panel).join("");
</script>
</body>
</html>
"""


def main() -> None:
    guild = _FakeGuild()
    # « Avec emojis » se résout grâce aux emojis lus sur le serveur factice ;
    # « Replis » utilise un index vide, comme un serveur sans emoji.
    resolver.refresh([guild])
    custom = _collect(guild, "serveur")
    record = _collect_record(guild, "serveur")

    resolver.refresh(())
    fallback = _collect(None, "replis")
    record_fallback = _collect_record(None, "replis")

    page = TEMPLATE.replace("__CUSTOM__", json.dumps(custom, ensure_ascii=False))
    page = page.replace("__FALLBACK__", json.dumps(fallback, ensure_ascii=False))
    page = page.replace("__RECORD__", json.dumps(record, ensure_ascii=False))
    page = page.replace("__RECORD_FALLBACK__", json.dumps(record_fallback, ensure_ascii=False))
    page = page.replace("__IMAGES__", json.dumps(GIFS))
    OUTPUT.write_text(page, encoding="utf-8")
    print(f"Aperçu écrit : {OUTPUT}")


if __name__ == "__main__":
    main()
