"""Allège les médias joints aux réponses Discord.

La bannière et les images du Black Flash sont envoyées **en pièce jointe** à
chaque réponse : plus elles sont lourdes, plus l’envoi est lent. Ce script les
redimensionne sans toucher au code ni aux noms de fichier.

    python tools/optimize_assets.py

Nécessite Pillow — dépendance d’**outillage**, pas du bot :

    pip install pillow
"""

from __future__ import annotations

from pathlib import Path

try:
    from PIL import Image, ImageSequence
except ModuleNotFoundError:  # pragma: no cover - dépend de l’environnement
    raise SystemExit("Pillow est requis pour optimiser les médias : pip install pillow") from None

ROOT_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = ROOT_DIR / "assets"

# Images statiques : largeur visée (compromis taille/qualité). La bannière garde
# sa transparence, les autres sont opaques.
PNG_SETTINGS = {
    "banniere_jjk.png": (800, True),
    "blackflash_ok.png": (600, False),
    "blackflash_ko.png": (600, False),
    "renaissance_ok.png": (600, False),
    "renaissance_ko.png": (600, False),
}
# Anciens GIF animés : conservés au cas où un asset animé revienne un jour.
GIF_SETTINGS = {
    "blackflash_ok.gif": (600, 128),
    "blackflash_ko.gif": (480, 128),
}


def _report(path: Path, frames: int | None = None) -> None:
    size = path.stat().st_size
    unit = f"{size / 1024 / 1024:.2f} Mo" if size >= 1024 * 1024 else f"{size / 1024:.0f} Ko"
    extra = f" ({frames} images)" if frames is not None else ""
    print(f"{path.name} -> {unit}{extra}")


def optimize_image(path: Path, width: int, keep_alpha: bool = False) -> None:
    """Redimensionne et recompresse une image statique, au même format."""
    mode = "RGBA" if keep_alpha else "RGB"
    image = Image.open(path).convert(mode)
    if image.width > width:
        height = round(image.height * width / image.width)
        image = image.resize((width, height), Image.LANCZOS)
    image.save(path, "PNG", optimize=True)
    _report(path)


def optimize_gif(path: Path, width: int, colors: int) -> None:
    """Redimensionne un GIF animé et réduit sa palette, animation préservée."""
    source = Image.open(path)
    duration = source.info.get("duration", 80)
    size = (width, max(1, round(source.height * width / source.width)))
    frames = [
        frame.convert("RGBA")
        .resize(size, Image.LANCZOS)
        .convert("P", palette=Image.ADAPTIVE, colors=colors)
        for frame in ImageSequence.Iterator(source)
    ]
    frames[0].save(
        path,
        "GIF",
        save_all=True,
        append_images=frames[1:],
        duration=duration,
        loop=0,
        optimize=True,
        disposal=2,
    )
    _report(path, frames=len(frames))


def main() -> None:
    for name, (width, keep_alpha) in PNG_SETTINGS.items():
        path = ASSETS_DIR / name
        if path.is_file():
            optimize_image(path, width, keep_alpha)
    for name, (width, colors) in GIF_SETTINGS.items():
        path = ASSETS_DIR / name
        if path.is_file():
            optimize_gif(path, width, colors)


if __name__ == "__main__":
    main()
