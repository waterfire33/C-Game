from __future__ import annotations

from abc import ABC, abstractmethod

from result import TaskResult
from tasks import Task


class BaseAgent(ABC):
    name: str = "base"

    @abstractmethod
    def handle(self, task: Task) -> TaskResult:
        raise NotImplementedError
   