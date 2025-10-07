"""Common messaging primitives for service feedback."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class MessageLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class ServiceMessage:
    level: MessageLevel
    text: str
