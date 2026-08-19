# VFS Platform Console

Modular FastAPI web console for discovering and viewing VFS Platform components.

The console does not own Bridge, Broker, MCP, Demi, or TC-WFX. Components remain independently deployable and are registered through `config/packages.json`.

## Configuration

Defaults live beside the application:

```text
config/config.json
config/packages.json
```

Per-user overrides live in:

```text
%APPDATA%/VFS Platform Console/config/config.local.json
%APPDATA%/VFS Platform Console/config/packages.local.json
```

## Development

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\vfs-platform-console.exe
```

Open `http://127.0.0.1:8800/`.

Logdy is registered as a disabled optional debugger component until its integration and distribution are verified.

