from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any


def project_config_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "config"


def user_config_dir() -> Path | None:
    appdata = os.getenv("APPDATA")
    return Path(appdata) / "VFS Platform Console" / "config" if appdata else None


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Configuration must be a JSON object: {path}")
    return value


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def load_named(name: str) -> dict[str, Any]:
    base_path = project_config_dir() / f"{name}.json"
    result = _read_object(base_path)
    local_dir = user_config_dir()
    local_path = local_dir / f"{name}.local.json" if local_dir else None
    if local_path and local_path.is_file():
        result = _merge(result, _read_object(local_path))
    return result


def load_config() -> dict[str, Any]:
    return load_named("config")


def load_packages() -> list[dict[str, Any]]:
    packages = load_named("packages").get("packages")
    if not isinstance(packages, list):
        raise ValueError("packages.json must contain a packages array")
    enabled = [_expand_values(item) for item in packages if isinstance(item, dict) and item.get("enabled") is True]
    return sorted(enabled, key=lambda item: int(item.get("order", 1000)))


def _expand_values(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _expand_values(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_expand_values(item) for item in value]
    if isinstance(value, str):
        expanded = os.path.expandvars(value)
        return re.sub(
            r"%([^%]+)%",
            lambda match: os.getenv(match.group(1), str(Path.home()) if match.group(1) == "USERPROFILE" else match.group(0)),
            expanded,
        )
    return value
