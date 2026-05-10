"""
Memory manager — reads and writes all persistent memory files.
All file I/O goes through this module so routines stay clean.
"""

import os
import re
from pathlib import Path
from datetime import datetime, timezone

MEMORY_DIR = Path(__file__).parent.parent / "memory"


def _utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def read(filename: str) -> str:
    path = MEMORY_DIR / filename
    if not path.exists():
        return ""
    return path.read_text()


def write(filename: str, content: str) -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    (MEMORY_DIR / filename).write_text(content)


def append(filename: str, entry: str) -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    path = MEMORY_DIR / filename
    existing = path.read_text() if path.exists() else ""
    path.write_text(existing + "\n" + entry)


def load_all() -> dict[str, str]:
    return {
        "strategy": read("strategy.md"),
        "learnings": read("learnings.md"),
        "trade_log": read("trade_log.md"),
        "research_notes": read("research_notes.md"),
    }


def commit(message: str) -> None:
    os.system(
        f"cd {MEMORY_DIR.parent} && git add memory/ && git commit -m '{message}' 2>/dev/null"
    )