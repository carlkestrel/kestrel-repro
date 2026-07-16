from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Iterable


class EventJournal:
    """Durable append-only JSONL mirror used to inspect and recover events."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def append(self, event: dict) -> None:
        line = json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n"
        with self._lock, self.path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())

    def read(self) -> list[dict]:
        if not self.path.exists():
            return []
        events: list[dict] = []
        with self.path.open(encoding="utf-8") as handle:
            for number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    # A crash can leave only the final append torn. Earlier lines remain valid.
                    if any(rest.strip() for rest in handle):
                        raise ValueError(f"corrupt journal record at line {number}")
                    break
        return events

    def missing_from(self, sqlite_events: Iterable[dict]) -> list[dict]:
        journal_seqs = {event.get("seq") for event in self.read()}
        return [event for event in sqlite_events if event.get("seq") not in journal_seqs]

    def repair_from(self, sqlite_events: Iterable[dict]) -> int:
        missing = self.missing_from(sqlite_events)
        for event in missing:
            self.append(event)
        return len(missing)
