from __future__ import annotations

from typing import Any

import httpx
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
.status{{font-weight:600}}.healthy{{color:#65df8a}}.offline,.unhealthy{{color:#ff7777}}.not_applicable{{color:#aebccc}}
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
    <span class=\"label\">Endpoint</span><span class=\"value\">${{esc(p.base_url || 'lokální klient')}}</span>
    <span class=\"label\">Projekt</span><span class=\"value\">${{esc(p.project_path || 'externí balíček')}}</span></div>
    ${{links(p)}}`;
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
</script></body></html>"""

    return app


def _package_status(package: dict[str, Any]) -> dict[str, Any]:
    result = dict(package)
    base_url = package.get("base_url")
    health_path = package.get("health_path")
    if not isinstance(base_url, str) or not isinstance(health_path, str):
        result["status"] = "not_applicable"
        return result
    timeout = float(load_config().get("health", {}).get("timeout_seconds", 2.0))
    try:
        with httpx.Client(timeout=timeout, trust_env=False) as client:
            response = client.get(base_url.rstrip("/") + "/" + health_path.lstrip("/"))
        result["status"] = "healthy" if response.is_success else "unhealthy"
        result["status_code"] = response.status_code
    except httpx.HTTPError:
        result["status"] = "offline"
    return result
