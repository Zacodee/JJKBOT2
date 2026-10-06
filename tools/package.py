"""Prépare l'envoi du bot : archive de déploiement et dossier prêt à glisser.

Le dossier local contient le `.venv` (des milliers de fichiers), les caches
`__pycache__`, les données et les journaux. Un envoi du dossier complet
(glisser-déposer sur GitHub) les emporte tous — c'est ce qui rend l'upload
interminable, et c'est aussi ce qui envoie `data/profiles.json` (donc les fiches)
dans le dépôt. Ce script ne garde que ce qui fait tourner le bot.

    python tools/package.py            # dist/jjkbot-deploy.zip  (archive de déploiement)
    python tools/package.py --tar      # dist/jjkbot-deploy.tar.gz
    python tools/package.py --folder   # dist/upload/  ← à glisser sur GitHub

Pour le glisser-déposer GitHub : ouvre `dist/upload/`, sélectionne **tout son
contenu** (pas le dossier lui-même), et dépose-le dans la page d'upload.
"""

from __future__ import annotations

import argparse
import fnmatch
import shutil
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
ARCHIVE_STEM = "jjkbot-deploy"

# Le strict nécessaire au fonctionnement du bot. `tests` et `tools` sont
# facultatifs mais légers et utiles pour vérifier sur place.
INCLUDE_PATHS: tuple[str, ...] = (
    "main.py",
    "requirements.txt",
    ".env.example",
    ".gitignore",
    "README.md",
    "jjkbot",
    "config",
    "assets",
    "tests",
    "tools",
)

# Dossiers écartés où qu’ils soient (développement, données, caches, archives).
EXCLUDE_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "env",
        "__pycache__",
        "dist",
        "data",
        "node_modules",
        ".freebuff",
        ".vscode",
        ".idea",
    }
)

# Motifs de fichiers écartés (caches, secrets, archives, aperçus générés).
EXCLUDE_FILE_PATTERNS: tuple[str, ...] = (
    "*.pyc",
    "*.pyo",
    "*.log",
    "*.rar",
    "*.zip",
    "*.tar.gz",
    "*.tmp",
    "*.html",  # aperçus produits par tools/preview*.py
    ".env",
)


def should_include(path: Path) -> bool:
    """Indique si un fichier fait partie du déploiement."""
    relative = path.relative_to(ROOT)
    if any(part in EXCLUDE_DIRS for part in relative.parts):
        return False
    if path.name == ".env":  # secrets locaux : jamais embarqués
        return False
    return not any(fnmatch.fnmatch(path.name, pattern) for pattern in EXCLUDE_FILE_PATTERNS)


def collect_files() -> list[Path]:
    """Liste des fichiers à embarquer, dans un ordre stable."""
    files: list[Path] = []
    for entry in INCLUDE_PATHS:
        target = ROOT / entry
        if target.is_file():
            if should_include(target):
                files.append(target)
        elif target.is_dir():
            files.extend(
                path for path in sorted(target.rglob("*")) if path.is_file() and should_include(path)
            )
    return files


def build_zip(files: list[Path]) -> Path:
    DIST.mkdir(parents=True, exist_ok=True)
    archive = DIST / f"{ARCHIVE_STEM}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as handle:
        for path in files:
            handle.write(path, path.relative_to(ROOT).as_posix())
    return archive


def build_tar(files: list[Path]) -> Path:
    DIST.mkdir(parents=True, exist_ok=True)
    archive = DIST / f"{ARCHIVE_STEM}.tar.gz"
    with tarfile.open(archive, "w:gz") as handle:
        for path in files:
            handle.add(path, arcname=path.relative_to(ROOT).as_posix())
    return archive


def build_folder(files: list[Path]) -> Path:
    """Copie les fichiers dans `dist/upload/`, prêt à glisser sur GitHub.

    Le dossier est vidé à chaque appel : il ne contient donc jamais de fichier
    oublié d’une exécution précédente.
    """
    target = DIST / "upload"
    if target.exists():
        shutil.rmtree(target)
    for path in files:
        destination = target / path.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
    return target


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="package",
        description="Prépare l’envoi du bot sans `.venv`, caches, données ni journaux.",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--tar", action="store_true", help="Produire un .tar.gz au lieu d’un .zip")
    group.add_argument(
        "--folder",
        action="store_true",
        help="Copier les fichiers dans dist/upload/ (à glisser sur GitHub)",
    )
    args = parser.parse_args()

    files = collect_files()
    if args.folder:
        target = build_folder(files)
        print(f"{len(files)} fichier(s) copié(s) dans {target}")
        print("Sur GitHub : ouvre ce dossier, sélectionne TOUT son contenu et dépose-le.")
        print("Ne glisse jamais le projet entier (il emporte .venv et data/).")
        return

    archive = build_tar(files) if args.tar else build_zip(files)
    size_mb = archive.stat().st_size / (1024 * 1024)
    print(f"{len(files)} fichier(s) → {archive}")
    print(f"Taille de l’archive : {size_mb:.2f} Mo")
    print("Sur l’hébergeur : `pip install -r requirements.txt` puis `python main.py`.")


if __name__ == "__main__":
    main()
