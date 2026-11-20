"""Tiny .env loader (no extra dependency). Real environment variables always win."""
from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(path: str | Path = ".env") -> bool:
    p = Path(path)
    if not p.is_file():
        return False
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip().removeprefix("export ").strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)
    return True
