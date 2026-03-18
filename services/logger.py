"""Structured execution logger — agent_log.json for hackathon compliance.

Records every decision, tool call, retry, and outcome. Required by the
"Agents With Receipts" and "Let the Agent Cook" tracks.
"""

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

LOG_FILE = "/app/agent_log.json"
MAX_ENTRIES = 10_000


class ExecutionLogger:
    """Thread-safe structured execution logger."""

    def __init__(self, log_path: str = LOG_FILE) -> None:
        self._path = Path(log_path)
        self._lock = threading.Lock()
        self._entries: list[dict] = []
        self._load()

    def _load(self) -> None:
        try:
            if self._path.exists():
                data = json.loads(self._path.read_text())
                self._entries = data.get("entries", [])
        except Exception:
            self._entries = []

    def log(
        self,
        action: str,
        description: str,
        outcome: str = "success",
        tool_calls: list[str] | None = None,
        details: dict | None = None,
        retry_count: int = 0,
    ) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "description": description,
            "outcome": outcome,
            "tool_calls": tool_calls or [],
            "retry_count": retry_count,
        }
        if details:
            entry["details"] = details

        with self._lock:
            self._entries.append(entry)
            if len(self._entries) > MAX_ENTRIES:
                self._entries = self._entries[-MAX_ENTRIES:]
            self._flush()

    def _flush(self) -> None:
        try:
            doc = {
                "agent_id": "agentproof-recruiter",
                "version": "0.1.0",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "total_entries": len(self._entries),
                "summary": self._summary(),
                "entries": self._entries,
            }
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(doc, indent=2, default=str))
        except Exception as e:
            logger.warning(f"Failed to write agent_log.json: {e}")

    def _summary(self) -> dict:
        if not self._entries:
            return {"total_actions": 0}

        outcomes: dict[str, int] = {}
        actions: dict[str, int] = {}
        for e in self._entries:
            o = e.get("outcome", "unknown")
            outcomes[o] = outcomes.get(o, 0) + 1
            a = e.get("action", "unknown")
            actions[a] = actions.get(a, 0) + 1

        return {
            "total_actions": len(self._entries),
            "outcomes": outcomes,
            "action_types": actions,
            "total_retries": sum(e.get("retry_count", 0) for e in self._entries),
            "total_tool_calls": sum(len(e.get("tool_calls", [])) for e in self._entries),
            "first_entry": self._entries[0]["timestamp"],
            "last_entry": self._entries[-1]["timestamp"],
        }

    def get_log(self) -> dict:
        with self._lock:
            return {
                "agent_id": "agentproof-recruiter",
                "version": "0.1.0",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "total_entries": len(self._entries),
                "summary": self._summary(),
                "entries": self._entries[-500:],
            }


_instance: ExecutionLogger | None = None


def get_execution_logger() -> ExecutionLogger:
    global _instance
    if _instance is None:
        _instance = ExecutionLogger()
    return _instance
