from fastapi.testclient import TestClient

from vfs_platform_console.app import create_app
from vfs_platform_console.config import load_config, load_packages


def test_default_config() -> None:
    assert load_config()["server"] == {"host": "127.0.0.1", "port": 8800}


def test_packages_are_enabled_and_ordered() -> None:
    packages = load_packages()
    assert [item["id"] for item in packages] == ["bridge", "broker", "mcp", "demi", "tc-wfx"]
    assert packages[0]["runtime"] == "FastAPI / HTTP"
    assert "%USERPROFILE%" not in packages[0]["project_path"]


def test_health() -> None:
    response = TestClient(create_app()).get("/health")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_dashboard() -> None:
    response = TestClient(create_app()).get("/")
    assert response.status_code == 200
    assert "VFS Platform Console" in response.text
    assert "fetch('/api/packages')" in response.text
    assert "Endpoint" in response.text
    assert 'id="overview"' in response.text
