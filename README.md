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

## Debugger

The optional VFS debugger uses the external [Logdy](https://github.com/logdyhq/logdy-core) project under the Apache-2.0 license. Its pinned source tag, executable, local endpoint, safety flags, and log sources are declared in `config/packages.json`.

Start the configured debugger with:

```powershell
.\.venv\Scripts\vfs-platform-debugger.exe
```

Logdy remains an independent component; its source and license stay in the adjacent `logdy-core` checkout and are not copied into this MIT repository.
