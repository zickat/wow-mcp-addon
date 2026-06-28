#!/usr/bin/env python3
"""
build-mcp.py
Construit un exécutable standalone wow-mcp (aucune dépendance Python requise).

Usage :
    python3 build-mcp.py          # build pour la plateforme courante
    python3 build-mcp.py --clean  # supprime dist/ et build/ avant de builder

Sortie :
    dist/wow-mcp          (macOS / Linux)
    dist/wow-mcp.exe      (Windows)
"""

import subprocess
import sys
import shutil
import argparse
from pathlib import Path

ROOT = Path(__file__).parent
ENTRY = ROOT / "wow-mcp" / "server.py"
DATA_DIR = ROOT / "data"

def run(cmd: list[str]) -> None:
    print(">>", " ".join(str(c) for c in cmd))
    result = subprocess.run(cmd)
    if result.returncode != 0:
        sys.exit(result.returncode)

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean", action="store_true", help="Supprime dist/ et build/ avant le build")
    args = parser.parse_args()

    if args.clean:
        for d in ["dist", "build"]:
            p = ROOT / d
            if p.exists():
                shutil.rmtree(p)
                print(f"🗑  Supprimé {d}/")

    # Vérifie que PyInstaller est installé
    try:
        import PyInstaller  # noqa
    except ImportError:
        print("Installation de PyInstaller...")
        run([sys.executable, "-m", "pip", "install", "pyinstaller", "--break-system-packages"])

    # Séparateur de chemins PyInstaller (: sur Unix, ; sur Windows)
    sep = ";" if sys.platform == "win32" else ":"

    # Données à bundler dans l'exe
    add_data = [
        f"{DATA_DIR / 'items_db.json'}{sep}data",
        f"{DATA_DIR / 'stat_weights.json'}{sep}data",
    ]
    # loot.json est optionnel (legacy get_loot_table)
    if (DATA_DIR / "loot.json").exists():
        add_data.append(f"{DATA_DIR / 'loot.json'}{sep}data")

    # lua_parser.py est dans le même dossier que server.py — PyInstaller le détecte
    # automatiquement via l'analyse des imports.

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", "wow-mcp",
        "--distpath", str(ROOT / "dist"),
        "--workpath", str(ROOT / "build"),
        "--specpath", str(ROOT / "build"),
        "--noconfirm",
    ]
    for d in add_data:
        cmd += ["--add-data", d]
    cmd.append(str(ENTRY))

    run(cmd)

    # Résultat
    exe = ROOT / "dist" / ("wow-mcp.exe" if sys.platform == "win32" else "wow-mcp")
    if exe.exists():
        size_mb = exe.stat().st_size / 1_048_576
        print(f"\n✅ Build OK → {exe}  ({size_mb:.1f} MB)")
        print()
        print("Config Claude Desktop (claude_desktop_config.json) :")
        if sys.platform == "win32":
            print(f'  "command": "{exe}"')
        else:
            print(f'  "command": "{exe}"')
        print('  "args": []')
    else:
        print("❌ Exécutable introuvable après build.")
        sys.exit(1)

if __name__ == "__main__":
    main()
