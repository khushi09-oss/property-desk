"""Prepare only reviewed runtime files; never copy credentials or overwrite output."""

import argparse
import shutil
from pathlib import Path

FILES = {
    "Dockerfile": "Dockerfile",
    ".dockerignore": ".dockerignore",
    "vercel.json": "vercel.json",
    "requirements.txt": "requirements.txt",
    "constraints.txt": "constraints.txt",
    "app/__init__.py": "app/__init__.py",
    "app/main.py": "app/main.py",
    "app/chat.py": "app/chat.py",
    "app/cache.py": "app/cache.py",
    "app/knowledge.py": "app/knowledge.py",
    "app/collect.py": "app/collect.py",
    "app/run.py": "app/run.py",
    "data/knowledge.json": "data/knowledge.json",
    "web/index.html": "web/index.html",
    "web/style.css": "web/style.css",
    "web/app.js": "web/app.js",
    "web/history.mjs": "web/history.mjs",
    "web/fonts/newsreader-latin.woff2": "web/fonts/newsreader-latin.woff2",
    "web/fonts/public-sans-latin.woff2": "web/fonts/public-sans-latin.woff2",
    "web/fonts/newsreader-OFL.txt": "web/fonts/newsreader-OFL.txt",
    "web/fonts/public-sans-OFL.txt": "web/fonts/public-sans-OFL.txt",
}


def prepare_release(root: Path, destination: Path) -> None:
    root = root.resolve()
    destination = destination.resolve()
    if destination.is_relative_to(root) and not destination.is_relative_to(root / ".private"):
        raise ValueError("Use a private output directory or a directory outside the repository.")
    if destination.exists():
        raise FileExistsError("Output already exists; choose a fresh directory.")
    for name in FILES.values():
        source = root / name
        if not source.is_file() or source.resolve() != source:
            raise ValueError(f"Missing file or unsupported source symlink: {name}")
    destination.mkdir(parents=True)
    for name, source_name in FILES.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / source_name, target)
    allowlist = ["**", *[f"!{name}" for name in ("app", "data", "web", "web/fonts")], *[f"!{name}" for name in FILES]]
    (destination / ".vercelignore").write_text("\n".join(allowlist) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        prepare_release(Path(__file__).resolve().parent.parent, args.output)
    except (ValueError, OSError) as error:
        parser.exit(1, f"Release preparation failed: {error}\n")
    print(f"Prepared {len(FILES)} runtime files. Nothing was deployed.")
