from __future__ import annotations

import glob
import os
import subprocess
from pathlib import Path
from typing import Any

from .config import load_packages


def debugger_command(packages: list[dict[str, Any]] | None = None) -> list[str]:
    configured = packages if packages is not None else load_packages()
    debugger = next((item for item in configured if item.get("kind") == "debugger"), None)
    if debugger is None:
        raise RuntimeError("No enabled debugger package is configured.")
    launch = debugger.get("launch")
    if not isinstance(launch, dict):
        raise ValueError("Debugger package requires a launch object.")
    executable = launch.get("executable")
    arguments = launch.get("arguments")
    sources = launch.get("log_sources")
    if not isinstance(executable, str) or not isinstance(arguments, list) or not isinstance(sources, list):
        raise ValueError("Debugger launch requires executable, arguments and log_sources.")
    if not Path(executable).is_file():
        raise FileNotFoundError(f"Debugger executable not found: {executable}")
    log_files: list[str] = []
    for source in sources:
        if not isinstance(source, str):
            raise ValueError("Debugger log source must be a string.")
        for matched in glob.glob(source):
            if Path(matched).is_file() and matched not in log_files:
                log_files.append(matched)
    if not log_files:
        raise FileNotFoundError("No configured debugger log files were found.")
    return [executable, *[str(item) for item in arguments], *log_files]


def main() -> None:
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    subprocess.run(debugger_command(), check=True, creationflags=creationflags)


if __name__ == "__main__":
    main()
