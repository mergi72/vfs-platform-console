import json
import os
from pathlib import Path
import subprocess
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from vfs_platform_console.app import _metadata_status, _package_status, create_app
from vfs_platform_console.config import load_config, load_packages
from vfs_platform_console.debugger import debugger_command, main as debugger_main


def test_default_config() -> None:
    settings = load_config()
    assert settings["application"]["name"] == "VFS Platform Console"
    assert settings["application"]["version"] == "0.3.7"
    assert settings["server"] == {"host": "127.0.0.1", "port": 8800}


def test_packages_are_enabled_and_ordered() -> None:
    packages = load_packages()
    assert [item["id"] for item in packages] == [
        "logdy",
        "bridge",
        "broker",
        "mcp",
        "demi",
        "vfs-dms-chatgpt-plugin",
        "secure-mcp-tunnel",
        "tc-wfx",
    ]
    assert packages[0]["runtime"] == "VFS Logdy 0.18.8 / local web UI"
    assert packages[0]["version"] == "0.18.8"
    assert packages[-1]["process_names"] == ["TOTALCMD64", "TOTALCMD"]
    assert packages[-1]["installation"]["registry_key"] == "TC-VFS"
    assert "%USERPROFILE%" not in packages[0]["project_path"]
    log_sources = packages[0]["launch"]["log_sources"]
    assert log_sources[0]["alternatives"][0].replace("\\", "/").endswith("DMS Provider/logs/bridge-debug.log")
    assert log_sources[1]["alternatives"][0].replace("\\", "/").endswith("Credential Broker/logs/broker-debug.log")
    assert log_sources[2]["alternatives"][0].replace("\\", "/").endswith("DMS MCP/logs/mcp-debug.log")
    assert log_sources[3]["alternatives"][0].replace("\\", "/").endswith("DMS AI Client/logs/demi-debug.log")
    assert all("GHISLER/Plugins/wfx/TcWfxPlugin/logs/" in item.replace("\\", "/") for item in log_sources[4:8])


def test_debugger_command_comes_from_package_manifest(tmp_path) -> None:
    executable = tmp_path / "logdy.exe"
    log_file = tmp_path / "bridge.log"
    executable.write_bytes(b"")
    log_file.write_text("test", encoding="utf-8")
    command = debugger_command(
        [{"kind": "debugger", "launch": {"executable": str(executable), "arguments": ["follow", "--full-read"], "log_sources": [str(log_file)]}}]
    )
    assert command == [str(executable), "follow", "--full-read", str(log_file)]


def test_debugger_command_chooses_newest_log_alternative(tmp_path) -> None:
    executable = tmp_path / "logdy.exe"
    normal_log = tmp_path / "service.log"
    debug_log = tmp_path / "service-debug.log"
    executable.write_bytes(b"")
    debug_log.write_text("old debug", encoding="utf-8")
    normal_log.write_text("current normal", encoding="utf-8")
    os.utime(debug_log, (1, 1))
    os.utime(normal_log, (2, 2))
    command = debugger_command(
        [{
            "kind": "debugger",
            "launch": {
                "executable": str(executable),
                "arguments": ["follow"],
                "log_sources": [{"alternatives": [str(debug_log), str(normal_log)]}],
            },
        }]
    )
    assert command == [str(executable), "follow", str(normal_log)]


def test_debugger_command_loads_package_debug_config(tmp_path) -> None:
    executable = tmp_path / "logdy.exe"
    static_log = tmp_path / "bridge.log"
    plugin_logs = tmp_path / "plugin-logs"
    tunnel_log = plugin_logs / "vfs-dms-local.log"
    plugin_config = tmp_path / "plugin.json"
    executable.write_bytes(b"")
    static_log.write_text("bridge", encoding="utf-8")
    plugin_logs.mkdir()
    tunnel_log.write_text("tunnel", encoding="utf-8")
    plugin_config.write_text(
        json.dumps({"debug": {"enable": True, "path": str(plugin_logs), "files": [tunnel_log.name]}}),
        encoding="utf-8",
    )
    command = debugger_command(
        [
            {"kind": "plugin", "debug_config_path": str(plugin_config)},
            {
                "kind": "debugger",
                "launch": {
                    "executable": str(executable),
                    "arguments": ["follow"],
                    "log_sources": [str(static_log)],
                },
            },
        ]
    )
    assert command == [str(executable), "follow", str(static_log), str(tunnel_log)]


def test_debugger_launcher_hides_windows_console() -> None:
    with patch("vfs_platform_console.debugger.debugger_command", return_value=["logdy"]), patch(
        "vfs_platform_console.debugger.subprocess.run"
    ) as run:
        debugger_main()
    expected_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    run.assert_called_once_with(["logdy"], check=True, creationflags=expected_flags)


def test_logdy_layout_is_configured() -> None:
    debugger = next(item for item in load_packages() if item["id"] == "logdy")
    arguments = debugger["launch"]["arguments"]
    configured_path = arguments[arguments.index("--config") + 1]
    assert configured_path.replace("\\", "/").endswith("/vfs-platform-console/config/logdy.json")
    assert arguments[arguments.index("--max-message-count") + 1] == "10000"
    assert arguments[arguments.index("--initial-message-count") + 1] == "1000"
    config_path = Path(__file__).resolve().parents[1] / "config" / "logdy.json"
    layout = json.loads(config_path.read_text(encoding="utf-8"))
    assert layout["settings"]["maxMessages"] == 1000
    assert [column["name"] for column in layout["columns"]] == [
        "ID",
        "Čas",
        "Level",
        "Komponenta",
        "Zpráva",
    ]
    assert layout["columns"][3]["width"] == 125
    assert layout["settings"]["middlewares"][0]["name"] == "Python log parser"
    parser = layout["settings"]["middlewares"][0]["handlerTsCode"]
    assert "component: sourceComponent" in parser
    assert "correlation_id: correlationId" in parser
    assert "? 'tc-wfx'" in parser
    assert "replace(/\\.(stdout|stderr)\\.log$/i, '')" in parser
    assert "replace(/-debug\\.log$/i, '')" in parser
    assert "date.getFullYear()" in parser
    assert "date.getMilliseconds()" in parser
    assert "JSON.parse(clean)" in parser
    assert "typeof originalJson.msg === 'string' ? originalJson : JSON.parse(clean)" in parser
    assert "vfs-dms-local\\.log" in parser
    assert "? 'tunnel'" in parser
    assert "request_id" in parser
    assert "...ids" not in parser
    assert "return;" not in parser


def test_health() -> None:
    response = TestClient(create_app()).get("/health")
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["service"] == load_config()["application"]["id"]
    assert response.json()["version"] == load_config()["application"]["version"]


def test_package_status_includes_health_version_and_process_start() -> None:
    response = httpx.Response(200, json={"ok": True, "version": "3.2.1"})
    with patch("vfs_platform_console.app.httpx.Client.get", return_value=response), patch(
        "vfs_platform_console.app._process_started_at", return_value="2026-08-19T18:00:00+00:00"
    ):
        status = _package_status({"base_url": "http://127.0.0.1:9000", "health_path": "/health"})
    assert status["version"] == "3.2.1"
    assert status["started_at"] == "2026-08-19T18:00:00+00:00"


def test_package_status_uses_configured_process_for_local_client() -> None:
    with patch(
        "vfs_platform_console.app._named_process_started_at", return_value="2026-08-19T17:18:47+00:00"
    ) as process_start:
        status = _package_status({"process_names": ["TOTALCMD64", "TOTALCMD"]})
    assert status["status"] == "not_applicable"
    assert status["started_at"] == "2026-08-19T17:18:47+00:00"
    process_start.assert_called_once_with(["TOTALCMD64", "TOTALCMD"])


def test_plugin_version_is_loaded_from_manifest(tmp_path) -> None:
    manifest = tmp_path / "plugin.json"
    manifest.write_text('{"version":"0.1.1"}', encoding="utf-8")
    status = _metadata_status({"path": str(manifest), "fields": {"version": "version"}})
    assert status == {"installed": True, "version": "0.1.1"}


def test_tunnel_status_uses_dynamic_local_health_url(tmp_path) -> None:
    url_file = tmp_path / "tunnel.url"
    url_file.write_text("http://127.0.0.1:53794\n", encoding="utf-8")
    response = httpx.Response(
        200,
        json={
            "version": "0.0.12",
            "started_at": "2026-08-23T17:39:29+02:00",
            "control_plane_tunnel_id": "tunnel_test",
            "mcp_server_url": "http://127.0.0.1:8781/mcp",
            "channels": [{"probe_status": "ok"}],
        },
    )
    package = {
        "health_url_file": str(url_file),
        "health_path": "/api/status",
        "response_fields": {
            "tunnel_id": "control_plane_tunnel_id",
            "target_url": "mcp_server_url",
            "channel_status": "channels.0.probe_status",
        },
    }
    with patch("vfs_platform_console.app.httpx.Client.get", return_value=response):
        status = _package_status(package)
    assert status["status"] == "healthy"
    assert status["base_url"] == "http://127.0.0.1:53794"
    assert status["version"] == "0.0.12"
    assert status["tunnel_id"] == "tunnel_test"
    assert status["target_url"] == "http://127.0.0.1:8781/mcp"
    assert status["channel_status"] == "ok"


def test_named_process_lookup_is_case_insensitive_for_windows_executable() -> None:
    process = type("Process", (), {"info": {"name": "TOTALCMD64.EXE", "create_time": 1_755_625_127.0}})()
    with patch("vfs_platform_console.app.psutil.process_iter", return_value=[process]):
        from vfs_platform_console.app import _named_process_started_at

        assert _named_process_started_at(["TOTALCMD64"]) is not None


def test_installation_status_uses_manifest_paths(tmp_path) -> None:
    artifact = tmp_path / "Plugin.wfx64"
    artifact.write_bytes(b"plugin")
    ini = tmp_path / "wincmd.ini"
    ini.write_text(f"[FileSystemPlugins]\nTC-VFS={artifact}\n", encoding="utf-8")
    from vfs_platform_console.app import _installation_status

    with patch("vfs_platform_console.app._module_is_loaded", return_value=True):
        status = _installation_status(
            {
                "registry_file": str(ini),
                "registry_section": "FileSystemPlugins",
                "registry_key": "TC-VFS",
                "artifact_path": str(artifact),
                "module_name": artifact.name,
            },
            ["TOTALCMD64"],
        )
    assert status == {"installed": True, "registered": True, "artifact_exists": True, "loaded": True}


def test_dashboard() -> None:
    response = TestClient(create_app()).get("/")
    assert response.status_code == 200
    assert "VFS Platform Console" in response.text
    assert "0.3.7" in response.text
    assert "127.0.0.1:8800" in response.text
    assert "● healthy" in response.text
    assert "fetch('/api/packages')" in response.text
    assert "Endpoint" in response.text
    assert "formatStartedAt(p.started_at)" in response.text
    assert 'id="overview"' in response.text
