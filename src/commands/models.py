from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum


class ResultType(Enum):
    SUCCESS = "success"
    ERROR = "error"
    INFO = "info"
    EXIT = "exit"


@dataclass
class CommandResult:
    type: ResultType
    message: str = ""
    data: Optional[Dict[str, Any]] = None
    actions: List[str] = field(default_factory=list)
    
    def to_text(self) -> str:
        return self.message
    
    def to_dict(self) -> dict:
        return {
            "type": self.type.value,
            "message": self.message,
            "data": self.data,
            "actions": self.actions
        }
