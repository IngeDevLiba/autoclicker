"""
Microsoft Edge profile launcher.

Opens Microsoft Edge with a selected user profile so you can switch profiles
manually from the command line without automating searches or Rewards actions.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def _find_edge_binary() -> str:
    candidates = [
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    ]

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    raise RuntimeError(
        "No se encontró Microsoft Edge. Instala Edge o ajusta la ruta manualmente."
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Abrir Microsoft Edge con un perfil concreto."
    )
    parser.add_argument(
        "--user-data-dir",
        required=True,
        help="Ruta a la carpeta User Data de Edge.",
    )
    parser.add_argument(
        "--profile-directory",
        required=True,
        help="Nombre de perfil de Edge, por ejemplo Default o Profile 1.",
    )
    parser.add_argument(
        "--url",
        default="",
        help="URL opcional para abrir al iniciar Edge.",
    )
    parser.add_argument(
        "--start-minimized",
        action="store_true",
        help="Abrir la ventana minimizada.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    edge_binary = _find_edge_binary()

    command = [
        edge_binary,
        f"--user-data-dir={args.user_data_dir}",
        f"--profile-directory={args.profile_directory}",
        "--new-window",
    ]

    if args.start_minimized:
        command.append("--start-minimized")

    if args.url:
        command.append(args.url)

    subprocess.Popen(command)


if __name__ == "__main__":
    main()
