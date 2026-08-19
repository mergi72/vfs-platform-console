from fastapi.testclient import TestClient

from vfs_platform_console.app import create_app
from vfs_platform_console.config import load_config, load_packages


def test_default_config() -> None:
    settings = load_config()
    assert settings["application"]["name"] == "VFS Platform Console"
    assert settings["application"]["version"] == "0.1.1"
    assert settings["server"] == {"host": "127.0.0.1", "port": 8800}


def test_packages_are_enabled_and_ordered() -> None:
    packages = load_packages()
    assert [item["id"] for item in packages] == ["bridge", "broker", "mcp", "demi", "tc-wfx"]
    assert packages[0]["runtime"] == "FastAPI / HTTP"
    assert "%USERPROFILE%" not in packages[0]["project_path"]


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
    assert "0.1.1" in response.text
    assert "127.0.0.1:8800" in response.text
    assert "● healthy" in response.text
    assert "fetch('/api/packages')" in response.text
    assert "Endpoint" in response.text
    assert 'id="overview"' in response.text
