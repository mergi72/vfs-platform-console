from __future__ import annotations

import uvicorn

from .config import load_config


def main() -> None:
    server = load_config()["server"]
    uvicorn.run(
        "vfs_platform_console.app:create_app",
        factory=True,
        host=str(server["host"]),
        port=int(server["port"]),
    )


if __name__ == "__main__":
    main()

