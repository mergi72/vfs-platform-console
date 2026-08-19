import json
from pathlib import Path

from fastapi.testclient import TestClient

from vfs_platform_console.app import create_app
from vfs_platform_console.config import load_config, load_packages
from vfs_platform_console.debugger import debugger_command


def test_default_config() -> None:
    settings = load_config()
    assert settings["application"]["name"] == "VFS Platform Console"
    assert settings["application"]["version"] == "0.2.3"
    assert settings["server"] == {"host": "127.0.0.1", "port": 8800}


def test_packages_are_enabled_and_ordered() -> None:
    packages = load_packages()
    assert [item["id"] for item in packages] == ["logdy", "bridge", "broker", "mcp", "demi", "tc-wfx"]
    assert packages[0]["runtime"] == "VFS Logdy 0.18.1 / local web UI"
    assert "%USERPROFILE%" not in packages[0]["project_path"]
    assert packages[0]["launch"]["log_sources"] == [
        str(packages[1]["project_path"] + "\\tmp\\bridge.stdout.log"),
        str(packages[1]["project_path"] + "\\tmp\\bridge.stderr.log"),
    ]


def test_debugger_command_comes_from_package_manifest(tmp_path) -> None:
    executable = tmp_path / "logdy.exe"
    log_file = tmp_path / "bridge.log"
    executable.write_bytes(b"")
    log_file.write_text("test", encoding="utf-8")
    command = debugger_command(
        [{"kind": "debugger", "launch": {"executable": str(executable), "arguments": ["follow", "--full-read"], "log_sources": [str(log_file)]}}]
    )
    assert command == [str(executable), "follow", "--full-read", str(log_file)]


def test_logdy_layout_is_configured() -> None:
    debugger = next(item for item in load_packages() if item["id"] == "logdy")
    arguments = debugger["launch"]["arguments"]
    configured_path = arguments[arguments.index("--config") + 1]
    assert configured_path.replace("\\", "/").endswith("/vfs-platform-console/config/logdy.json")
    config_path = Path(__file__).resolve().parents[1] / "config" / "logdy.json"
    layout = json.loads(config_path.read_text(encoding="utf-8"))
    assert [column["name"] for column in layout["columns"]] == [
        "Čas",
        "Level",
        "Komponenta",
        "Zpráva",
    ]
    assert layout["settings"]["middlewares"][0]["name"] == "Python log parser"
    parser = layout["settings"]["middlewares"][0]["handlerTsCode"]
    assert parser.count("component: 'bridge'") == 2
    assert "date.getFullYear()" in parser
    assert "date.getMilliseconds()" in parser
    assert "return;" not in parser


def test_health() -> None:
    response = TestClient(create_app()).get("/health")
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["service"] == load_config()["application"]["id"]
    assert response.json()["version"] == load_config()["application"]["version"]


def test_dashboard() -> None:
    response = TestClient(create_app()).get("/")
    assert response.status_code == 200
    assert "VFS Platform Console" in response.text
    assert "0.2.3" in response.text
    assert "127.0.0.1:8800" in response.text
    assert "● healthy" in response.text
    assert "fetch('/api/packages')" in response.text
    assert "Endpoint" in response.text
    assert 'id="overview"' in response.text
