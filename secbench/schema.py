"""Data records and JSONL helpers."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class Case:
    id: str
    category: str      # e.g. secret_exfiltration
    technique: str     # direct | roleplay | encoded | indirect | benign
    kind: str          # "attack" or "benign"
    prompt: str        # the user message sent to the target
    split: str = "dev"

    def to_dict(self) -> dict:
        return asdict(self)


def read_jsonl(path) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path, rows) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def append_jsonl(path, row: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def sha256_file(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_cases(path, split: str | None = None, limit: int | None = None) -> list[Case]:
    fields = Case.__dataclass_fields__.keys()
    cases = [Case(**{k: v for k, v in row.items() if k in fields}) for row in read_jsonl(path)]
    if split and split != "all":
        cases = [c for c in cases if c.split == split]
    if limit:
        cases = cases[:limit]
    return cases
