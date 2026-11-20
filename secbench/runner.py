"""Async runner: bounded concurrency, exponential backoff with jitter, resumable, append-as-you-go."""
from __future__ import annotations

import asyncio
import random
import time
from datetime import datetime, timezone
from pathlib import Path

from .schema import Case, append_jsonl, read_jsonl


def load_latest(path) -> dict[tuple[str, int], dict]:
    """Latest row per (case_id, repeat). Later rows (retries on resume) win."""
    latest: dict[tuple[str, int], dict] = {}
    for row in read_jsonl(path):
        latest[(row["case_id"], row["repeat"])] = row
    return latest


async def run_cases(cases: list[Case], target, system_prompt: str, out_path: str | Path, *,
                    run_id: str, model: str, concurrency: int = 4, max_retries: int = 3,
                    repeats: int = 1, dataset_hash: str = "", temperature=None, verbose: bool = True) -> int:
    out_path = Path(out_path)
    done = {k for k, v in load_latest(out_path).items() if v["status"] == "ok"}
    jobs = [(c, r) for c in cases for r in range(repeats) if (c.id, r) not in done]
    if verbose:
        print(f"[run] {len(jobs)} jobs to do ({len(done)} already done), concurrency={concurrency}")

    sem, lock = asyncio.Semaphore(concurrency), asyncio.Lock()
    counter = {"n": 0}

    async def one(case: Case, repeat: int) -> None:
        async with sem:
            status, error, response, t0 = "error", "", "", time.perf_counter()
            for attempt in range(max_retries + 1):
                try:
                    response = await target.generate(system_prompt, case.prompt)
                    status, error = "ok", ""
                    break
                except Exception as exc:  # noqa: BLE001 - we record every failure, never drop silently
                    error = f"{type(exc).__name__}: {exc}"[:300]
                    if attempt < max_retries:
                        await asyncio.sleep(min(30.0, 2 ** attempt + random.random()))
            row = {
                "run_id": run_id, "case_id": case.id, "repeat": repeat, "category": case.category,
                "technique": case.technique, "kind": case.kind, "split": case.split,
                "prompt": case.prompt, "response": response, "status": status, "error": error,
                "model": model, "temperature": temperature, "dataset_sha256": dataset_hash,
                "latency_s": round(time.perf_counter() - t0, 3),
                "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            async with lock:
                append_jsonl(out_path, row)
                counter["n"] += 1
                if verbose and counter["n"] % 10 == 0:
                    print(f"[run] {counter['n']}/{len(jobs)}")

    await asyncio.gather(*(one(c, r) for c, r in jobs))
    return len(jobs)
