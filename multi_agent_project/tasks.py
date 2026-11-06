from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TaskType(str, Enum):
    MATH = "math"
    TEXT = "text"
    IMAGE = "image"
    GREETING = "greeting"
    ECHO = "echo"


class TaskStatus(str, Enum):
    PENDING = "pending"
    ROUTED = "routed"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(slots=True)
class Task:
    type: TaskType
    payload: dict[str, Any]
    id: str = field(default_factory=lambda: str(uuid4()))
    status: TaskStatus = field(default=TaskStatus.PENDING)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def set_status(self, status: TaskStatus) -> None:
        self.status = status
        self.updated_at = utc_now()