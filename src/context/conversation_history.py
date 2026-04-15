import time
from dataclasses import dataclass, field
from typing import List, Optional

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, BaseMessage


@dataclass
class AssistantStep:
    assistant_message: AIMessage
    tool_results: List[ToolMessage] = field(default_factory=list)


@dataclass
class ConversationTurn:
    user_message: HumanMessage
    assistant_steps: List[AssistantStep] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


class ConversationHistory:

    def __init__(self):
        self._turns: List[ConversationTurn] = []
        self._compact_boundary_turn_idx: int = 0
        self._summary: Optional[str] = None
        self._pending_user_message: Optional[HumanMessage] = None
        self._pending_assistant_steps: List[AssistantStep] = []

    def start_turn(self, user_message: HumanMessage) -> None:
        if self._pending_user_message is not None:
            self.finish_turn()
        self._pending_user_message = user_message
        self._pending_assistant_steps = []

    def append_assistant_step(self, assistant_message: AIMessage, tool_results: List[ToolMessage] = None) -> None:
        step = AssistantStep(
            assistant_message=assistant_message,
            tool_results=tool_results if tool_results is not None else [],
        )
        self._pending_assistant_steps.append(step)

    def finish_turn(self) -> Optional[ConversationTurn]:
        if self._pending_user_message is None:
            return None
        turn = ConversationTurn(
            user_message=self._pending_user_message,
            assistant_steps=self._pending_assistant_steps,
        )
        self._turns.append(turn)
        self._pending_user_message = None
        self._pending_assistant_steps = []
        return turn

    def add_turn(self, turn: ConversationTurn) -> None:
        self._turns.append(turn)

    def get_turns_for_compression(self, keep_recent: int = 5) -> List[ConversationTurn]:
        active_turns = self.get_active_turns()
        if len(active_turns) <= keep_recent:
            return []
        return active_turns[:-keep_recent]

    def compress_old_turns(self, summary: str, keep_recent: int = 5) -> None:
        turns_for_compression = self.get_turns_for_compression(keep_recent)
        if turns_for_compression:
            self._summary = summary
            self._compact_boundary_turn_idx = len(self._turns) - len(self.get_active_turns()) + len(turns_for_compression)

    def get_active_turns(self) -> List[ConversationTurn]:
        if self._compact_boundary_turn_idx >= len(self._turns):
            return []
        return self._turns[self._compact_boundary_turn_idx:]

    def flatten_to_messages(self) -> List[BaseMessage]:
        messages: List[BaseMessage] = []
        if self._summary is not None:
            messages.append(HumanMessage(content=f"[之前的对话摘要]\n{self._summary}"))
        for turn in self.get_active_turns():
            messages.append(turn.user_message)
            for step in turn.assistant_steps:
                messages.append(step.assistant_message)
                messages.extend(step.tool_results)
        return messages

    def get_turn_count(self) -> int:
        return len(self._turns)

    def clear(self) -> None:
        self._turns = []
        self._compact_boundary_turn_idx = 0
        self._summary = None
        self._pending_user_message = None
        self._pending_assistant_steps = []
