"""Small structured diagnostic log for unexpected application failures."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from threading import Lock
import traceback
import uuid


class DiagnosticLog:
    """Append JSON Lines records with bounded on-disk history."""

    def __init__(self, path, max_bytes=1_000_000, backup_count=3):
        self.path = Path(path)
        self.max_bytes = max(1_024, int(max_bytes))
        self.backup_count = max(1, int(backup_count))
        self._lock = Lock()

    def _rotate_if_needed(self, incoming_bytes):
        current_bytes = self.path.stat().st_size if self.path.exists() else 0
        if current_bytes + incoming_bytes <= self.max_bytes:
            return
        oldest = self.path.with_suffix(self.path.suffix + f".{self.backup_count}")
        if oldest.exists():
            oldest.unlink()
        for index in range(self.backup_count - 1, 0, -1):
            source = self.path.with_suffix(self.path.suffix + f".{index}")
            if source.exists():
                source.replace(self.path.with_suffix(self.path.suffix + f".{index + 1}"))
        if self.path.exists():
            self.path.replace(self.path.with_suffix(self.path.suffix + ".1"))

    def record_exception(self, context, exc, metadata=None, category="internal"):
        event_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
        record = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "event_id": event_id,
            "context": str(context),
            "category": str(category),
            "exception_type": type(exc).__name__,
            "message": str(exc),
            "metadata": dict(metadata or {}),
            "traceback": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
        }
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
        encoded_size = len(line.encode("utf-8"))
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._rotate_if_needed(encoded_size)
            with self.path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(line)
        return event_id
