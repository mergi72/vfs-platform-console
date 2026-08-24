from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import psutil
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from .config import load_config, load_packages


def create_app() -> FastAPI:
    settings = load_config()
    application = settings["application"]
    app = FastAPI(title=str(application["name"]), version=str(application["version"]))

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "service": application["id"], "version": application["version"]}

    @app.get("/api/packages")
    def packages() -> dict[str, Any]:
        return {"packages": [_package_status(item) for item in load_packages()]}

    @app.get("/", response_class=HTMLResponse)
    def dashboard() -> str:
        server = settings["server"]
        console_endpoint = f"{server['host']}:{server['port']}"
        return f"""<!doctype html>
<html lang=\"cs\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width\">
<title>{application['name']}</title><style>
body{{margin:0;background:#0d1620;color:#e8eef5;font-family:Segoe UI,Arial,sans-serif}}
header{{padding:22px 5%;background:#152231;border-bottom:1px solid #304154}}.console-info{{display:flex;gap:18px;flex-wrap:wrap;color:#aac0d5;font-size:.88rem}}
header h1{{margin:0 0 8px}}.console-info strong{{color:#e8eef5}}.self-healthy{{color:#65df8a;font-weight:600}}
main{{padding:28px 5%}}.layout{{display:grid;grid-template-columns:minmax(420px,1.4fr) minmax(300px,1fr);gap:20px}}
#overview{{width:100%;border-collapse:collapse;background:#132232}}
#overview th,#overview td{{padding:10px 12px;border-bottom:1px solid #30465b;text-align:left;vertical-align:top}}
#overview th{{color:#9fc5e8;font-size:.78rem;text-transform:uppercase}}#overview tbody tr{{cursor:pointer}}
#overview tbody tr:hover,#overview tbody tr.selected{{background:#203a50}}#detail{{min-height:230px}}
.card{{background:#18293a;border:1px solid #30465b;border-radius:8px;padding:20px}}
.head{{display:flex;justify-content:space-between;gap:10px}}.kind{{color:#9fc5e8;text-transform:uppercase;font-size:.75rem}}
.status{{font-weight:600}}.healthy,.enabled,.connected{{color:#65df8a}}.offline,.unhealthy{{color:#ff7777}}.not_applicable{{color:#aebccc}}
.meta{{display:grid;grid-template-columns:72px 1fr;gap:7px;margin:16px 0;font-size:.88rem}}.label{{color:#8fa4b8}}
.value{{overflow-wrap:anywhere}}a{{color:#6db7ff;margin-right:14px}}
@media(max-width:850px){{.layout{{grid-template-columns:1fr}}}}
</style></head><body><header><h1>{application['name']}</h1><div>{application['description']}</div><div class=\"console-info\"><span class=\"self-healthy\">● healthy</span><span>Version <strong>{application['version']}</strong></span><span>Endpoint <strong>{console_endpoint}</strong></span></div></header>
<main><div class=\"layout\"><table id=\"overview\"><thead><tr><th>Komponenta</th><th>Stav</th><th>Endpoint</th></tr></thead><tbody><tr><td colspan=\"3\">Načítám komponenty…</td></tr></tbody></table>
<section id=\"detail\" class=\"card\">Vyber komponentu.</section></div></main>
<script>
const esc = value => String(value ?? '').replace(/[&<>\"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}}[c]));
fetch('/api/packages').then(r => r.json()).then(data => {{
  const body = document.querySelector('#overview tbody');
  body.innerHTML = data.packages.map((p,i) => `<tr data-index=\"${{i}}\"><td><strong>${{esc(p.name)}}</strong><br><span class=\"kind\">${{esc(p.kind)}}</span></td>
    <td class=\"status ${{esc(p.status)}}\">${{esc(p.status)}}</td><td>${{esc(p.base_url || 'lokální klient')}}</td></tr>`).join('');
  const show = index => {{
    const p = data.packages[index];
    document.querySelectorAll('#overview tbody tr').forEach((row,i) => row.classList.toggle('selected', i === index));
    document.getElementById('detail').innerHTML = `<div class=\"head\"><span class=\"kind\">${{esc(p.kind)}}</span>
    <span class=\"status ${{esc(p.status)}}\">${{esc(p.status)}}</span></div><h2>${{esc(p.name)}}</h2>
    <div class=\"meta\"><span class=\"label\">Runtime</span><span class=\"value\">${{esc(p.runtime || 'neuvedeno')}}</span>
    <span class=\"label\">Verze</span><span class=\"value\">${{esc(p.version || 'neuvedena')}}</span>
    <span class=\"label\">Spuštěno</span><span class=\"value\">${{esc(formatStartedAt(p.started_at))}}</span>
    ${{p.installed === undefined ? '' : `<span class=\"label\">Instalace</span><span class=\"value\">${{p.installed ? 'nainstalován' : 'nenainstalován'}}</span>`}}
    ${{p.loaded === undefined ? '' : `<span class=\"label\">Načten</span><span class=\"value\">${{p.loaded ? 'ano' : 'ne'}}</span>`}}
    <span class=\"label\">Endpoint</span><span class=\"value\">${{esc(p.base_url || 'lokální klient')}}</span>
    <span class=\"label\">Projekt</span><span class=\"value\">${{esc(p.project_path || 'externí balíček')}}</span></div>
    ${{details(p)}}${{links(p)}}`;
  }};
  body.querySelectorAll('tr').forEach(row => row.addEventListener('click', () => show(Number(row.dataset.index))));
  if (data.packages.length) show(0);
}}).catch(() => {{ document.querySelector('#overview tbody').innerHTML = '<tr><td colspan="3">Komponenty se nepodařilo načíst.</td></tr>'; }});
function links(p) {{
  if (!p.base_url) return '';
  let out = `<a href=\"${{esc(p.base_url)}}\" target=\"_blank\" rel=\"noopener\">Open</a>`;
  for (const [label,key] of [['Config','config_path'],['Docs','docs_path']]) if (p[key])
    out += `<a href=\"${{esc(p.base_url.replace(/[/]$/, '') + '/' + p[key].replace(/^[/]/, ''))}}\" target=\"_blank\" rel=\"noopener\">${{label}}</a>`;
  return out;
}}
function details(p) {{
  if (!Array.isArray(p.details) || !p.details.length) return '';
  return `<div class="meta">${{p.details.map(item => `<span class="label">${{esc(item.label)}}</span><span class="value">${{esc(p[item.key] ?? 'neuvedeno')}}</span>`).join('')}}</div>`;
}}
function formatStartedAt(value) {{
  if (!value) return 'nelze zjistit';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('cs-CZ');
}}
</script></body></html>"""

    return app


def _package_status(package: dict[str, Any]) -> dict[str, Any]:
    result = dict(package)
    result.update(_installation_status(package.get("installation"), package.get("process_names")))
    result.update(_metadata_status(package.get("metadata")))
    _apply_version_probe(result, package.get("version_probe"))
    base_url = _health_base_url(package)
    if base_url:
        result["base_url"] = base_url
    health_path = package.get("health_path")
    if not isinstance(base_url, str) or not isinstance(health_path, str):
        result["status"] = str(package.get("static_status", "not_applicable"))
        result["started_at"] = _named_process_started_at(package.get("process_names"))
        return result
    timeout = float(load_config().get("health", {}).get("timeout_seconds", 2.0))
    try:
        with httpx.Client(timeout=timeout, trust_env=False) as client:
            response = client.get(base_url.rstrip("/") + "/" + health_path.lstrip("/"))
        result["status"] = "healthy" if response.is_success else "unhealthy"
        result["status_code"] = response.status_code
        if response.is_success:
            try:
                health = response.json()
            except ValueError:
                health = None
            if isinstance(health, dict):
                _copy_response_fields(result, health, package.get("response_fields"))
                version = health.get("version")
                if isinstance(version, str) and version:
                    result["version"] = version
                started_at = health.get("started_at")
                if isinstance(started_at, str) and started_at:
                    result["started_at"] = started_at
        if "started_at" not in result:
            result["started_at"] = _process_started_at(base_url)
    except httpx.HTTPError:
        result["status"] = "offline"
    return result


def _apply_version_probe(result: dict[str, Any], probe: Any) -> None:
    if not isinstance(probe, dict):
        return
    executable = probe.get("executable")
    arguments = probe.get("arguments", [])
    pattern = probe.get("pattern")
    if not isinstance(executable, str) or not Path(executable).is_file():
        return
    if not isinstance(arguments, list) or not all(isinstance(item, str) for item in arguments):
        return
    if not isinstance(pattern, str) or not pattern:
        return
    try:
        timeout = min(max(float(probe.get("timeout_seconds", 1.0)), 0.1), 5.0)
        completed = subprocess.run(
            [executable, *arguments],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            shell=False,
        )
        output = completed.stdout + "\n" + completed.stderr
        match = re.search(pattern, output)
    except (OSError, ValueError, subprocess.SubprocessError, re.error):
        return
    if match is None:
        return
    try:
        version = match.group("version")
    except (IndexError, KeyError):
        return
    result["version"] = version
    runtime_template = probe.get("runtime_template")
    if isinstance(runtime_template, str):
        result["runtime"] = runtime_template.replace("{version}", version)
    tag_template = probe.get("tag_template")
    source = result.get("source")
    if isinstance(tag_template, str) and isinstance(source, dict):
        result["source"] = dict(source)
        result["source"]["tag"] = tag_template.replace("{version}", version)


def _health_base_url(package: dict[str, Any]) -> str | None:
    base_url = package.get("base_url")
    if isinstance(base_url, str) and base_url:
        return base_url
    url_file = package.get("health_url_file")
    if not isinstance(url_file, str) or not url_file:
        return None
    try:
        value = Path(url_file).read_text(encoding="utf-8").strip()
    except OSError:
        return None
    parsed = urlparse(value)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        return None
    return value.rstrip("/")


def _copy_response_fields(result: dict[str, Any], payload: dict[str, Any], mapping: Any) -> None:
    if not isinstance(mapping, dict):
        return
    for target, source in mapping.items():
        if not isinstance(target, str) or not isinstance(source, str):
            continue
        value: Any = payload
        for part in source.split("."):
            if isinstance(value, dict):
                value = value.get(part)
            elif isinstance(value, list) and part.isdigit() and int(part) < len(value):
                value = value[int(part)]
            else:
                value = None
                break
        if value is not None:
            result[target] = value


def _metadata_status(metadata: Any) -> dict[str, Any]:
    if not isinstance(metadata, dict):
        return {}
    path = metadata.get("path")
    fields = metadata.get("fields")
    if not isinstance(path, str) or not isinstance(fields, dict):
        return {}
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"installed": False}
    if not isinstance(payload, dict):
        return {"installed": False}
    result: dict[str, Any] = {"installed": True}
    _copy_response_fields(result, payload, fields)
    return result


def _process_started_at(base_url: str) -> str | None:
    parsed = urlparse(base_url)
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or parsed.port is None:
        return None
    try:
        connections = psutil.net_connections(kind="tcp")
    except (psutil.AccessDenied, psutil.Error):
        return None
    for connection in connections:
        if connection.status != psutil.CONN_LISTEN or connection.pid is None:
            continue
        if getattr(connection.laddr, "port", None) != parsed.port:
            continue
        try:
            started = psutil.Process(connection.pid).create_time()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.Error):
            return None
        return datetime.fromtimestamp(started, tz=timezone.utc).isoformat()
    return None


def _named_process_started_at(process_names: Any) -> str | None:
    if not isinstance(process_names, list):
        return None
    configured = {name.casefold() for name in process_names if isinstance(name, str) and name}
    if not configured:
        return None
    started: list[float] = []
    for process in psutil.process_iter(["name", "create_time"]):
        try:
            name = process.info.get("name")
            created = process.info.get("create_time")
            if isinstance(name, str) and name.casefold().removesuffix(".exe") in configured and isinstance(created, (int, float)):
                started.append(float(created))
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.Error):
            continue
    if not started:
        return None
    return datetime.fromtimestamp(max(started), tz=timezone.utc).isoformat()


def _installation_status(installation: Any, process_names: Any) -> dict[str, Any]:
    if not isinstance(installation, dict):
        return {}
    artifact = installation.get("artifact_path")
    registry_file = installation.get("registry_file")
    registry_section = installation.get("registry_section")
    registry_key = installation.get("registry_key")
    registered_path = _ini_value(registry_file, registry_section, registry_key)
    artifact_exists = isinstance(artifact, str) and Path(artifact).is_file()
    registered = isinstance(registered_path, str) and bool(registered_path)
    result: dict[str, Any] = {
        "installed": registered and artifact_exists,
        "registered": registered,
        "artifact_exists": artifact_exists,
    }
    module_name = installation.get("module_name")
    if isinstance(module_name, str) and module_name:
        result["loaded"] = _module_is_loaded(process_names, module_name)
    return result


def _ini_value(path: Any, section: Any, key: Any) -> str | None:
    if not all(isinstance(value, str) and value for value in (path, section, key)):
        return None
    ini_path = Path(path)
    if not ini_path.is_file():
        return None
    text = ini_path.read_bytes().decode("utf-8", errors="replace")
    active_section: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("[") and line.endswith("]"):
            active_section = line[1:-1]
            continue
        if active_section == section and "=" in line:
            candidate, value = line.split("=", 1)
            if candidate.strip() == key:
                return value.strip()
    return None


def _module_is_loaded(process_names: Any, module_name: str) -> bool:
    if not isinstance(process_names, list):
        return False
    configured = {name.casefold() for name in process_names if isinstance(name, str) and name}
    expected = module_name.casefold()
    for process in psutil.process_iter(["name"]):
        try:
            name = process.info.get("name")
            if not isinstance(name, str) or name.casefold().removesuffix(".exe") not in configured:
                continue
            if any(Path(mapping.path).name.casefold() == expected for mapping in process.memory_maps()):
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.Error):
            continue
    return False
