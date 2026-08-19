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
        if isinstance(source, str):
            candidates = [Path(matched) for matched in glob.glob(source) if Path(matched).is_file()]
        elif isinstance(source, dict) and isinstance(source.get("alternatives"), list):
            alternatives = source["alternatives"]
            if not all(isinstance(item, str) for item in alternatives):
                raise ValueError("Debugger log source alternatives must be strings.")
            candidates = [
                Path(matched)
                for alternative in alternatives
                for matched in glob.glob(alternative)
                if Path(matched).is_file()
            ]
            candidates = [max(candidates, key=lambda path: path.stat().st_mtime)] if candidates else []
        else:
            raise ValueError("Debugger log source must be a string or an alternatives object.")
        for candidate in candidates:
            matched = str(candidate)
            if matched not in log_files:
                log_files.append(matched)
    if not log_files:
        raise FileNotFoundError("No configured debugger log files were found.")
    return [executable, *[str(item) for item in arguments], *log_files]


def main() -> None:
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    subprocess.run(debugger_command(), check=True, creationflags=creationflags)


if __name__ == "__main__":
    main()
