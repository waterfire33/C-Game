from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class TaskResult:
    task_id: str
    success: bool
    output: Any = None
    error: str | None = None
    agent_name: str | None = None
