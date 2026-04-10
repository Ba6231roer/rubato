import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from langchain_core.messages import BaseMessage, ToolMessage, AIMessage, HumanMessage

DEFAULT_MAX_RESULT_SIZE_CHARS = 50000
MAX_TOOL_RESULTS_PER_MESSAGE_CHARS = 200000
PREVIEW_SIZE_BYTES = 2000
PERSISTED_OUTPUT_TAG = '<persisted-output>'
PERSISTED_OUTPUT_CLOSING_TAG = '</persisted-output>'
TOOL_RESULT_CLEARED_MESSAGE = '[Old tool result content cleared]'
TOOL_RESULTS_SUBDIR = 'tool-results'


@dataclass
class PersistedToolResult:
    filepath: str
    original_size: int
    preview: str
    has_more: bool


class ToolResultStorage:
    def __init__(
        self,
        session_dir: str,
        persist_threshold: int = DEFAULT_MAX_RESULT_SIZE_CHARS,
        message_budget: int = MAX_TOOL_RESULTS_PER_MESSAGE_CHARS,
    ):
        self.session_dir = session_dir
        self.persist_threshold = persist_threshold
        self.message_budget = message_budget

    def persist_tool_result(self, content: str, tool_use_id: str) -> Optional[PersistedToolResult]:
        results_dir = self.ensure_tool_results_dir()
        filepath = os.path.join(results_dir, f"{tool_use_id}.txt")

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        preview, has_more = self.generate_preview(content)

        return PersistedToolResult(
            filepath=filepath,
            original_size=len(content),
            preview=preview,
            has_more=has_more,
        )

    def maybe_persist_large_tool_result(
        self, content: str, tool_name: str, tool_use_id: str
    ) -> str:
        if not content:
            return f"({tool_name} completed with no output)"

        if len(content) > self.persist_threshold:
            result = self.persist_tool_result(content, tool_use_id)
            if result:
                return self.build_large_tool_result_message(result)

        return content

    def build_large_tool_result_message(self, result: PersistedToolResult) -> str:
        more_indicator = " (truncated)" if result.has_more else ""
        return (
            f"{PERSISTED_OUTPUT_TAG}\n"
            f"Tool result persisted to: {result.filepath}\n"
            f"Original size: {result.original_size} characters{more_indicator}\n"
            f"Preview:\n{result.preview}\n"
            f"{PERSISTED_OUTPUT_CLOSING_TAG}"
        )

    def generate_preview(
        self, content: str, max_bytes: int = PREVIEW_SIZE_BYTES
    ) -> Tuple[str, bool]:
        content_bytes = content.encode("utf-8")

        if len(content_bytes) <= max_bytes:
            return content, False

        truncated_bytes = content_bytes[:max_bytes]
        truncated = truncated_bytes.decode("utf-8", errors="ignore")

        last_newline = truncated.rfind("\n")
        if last_newline > 0:
            truncated = truncated[:last_newline]

        return truncated, True

    def ensure_tool_results_dir(self) -> str:
        results_dir = os.path.join(self.session_dir, TOOL_RESULTS_SUBDIR)
        os.makedirs(results_dir, exist_ok=True)
        return results_dir


class ContentReplacementState:
    def __init__(self):
        self.seen_ids: Set[str] = set()
        self.replacements: Dict[str, str] = {}

    def mark_seen(self, tool_use_id: str) -> None:
        self.seen_ids.add(tool_use_id)

    def is_seen(self, tool_use_id: str) -> bool:
        return tool_use_id in self.seen_ids

    def set_replacement(self, tool_use_id: str, replacement: str) -> None:
        self.replacements[tool_use_id] = replacement

    def get_replacement(self, tool_use_id: str) -> Optional[str]:
        return self.replacements.get(tool_use_id)

    def is_replaced(self, tool_use_id: str) -> bool:
        return tool_use_id in self.replacements


def apply_tool_result_budget(
    messages: List[BaseMessage],
    state: ContentReplacementState,
    storage: ToolResultStorage,
    skip_tool_names: Set[str] = None,
) -> Tuple[List[BaseMessage], List[Dict]]:
    skip_tool_names = skip_tool_names or set()
    modified_messages: List[BaseMessage] = []
    newly_replaced: List[Dict] = []

    fresh_tool_results: List[Tuple[str, str, str]] = []
    fresh_indices: Dict[str, int] = {}

    for i, msg in enumerate(messages):
        if isinstance(msg, ToolMessage):
            tool_use_id = msg.tool_call_id
            tool_name = getattr(msg, "name", None) or ""

            if state.is_seen(tool_use_id):
                if state.is_replaced(tool_use_id):
                    replacement = state.get_replacement(tool_use_id)
                    new_msg = ToolMessage(
                        content=replacement,
                        tool_call_id=tool_use_id,
                        name=tool_name if tool_name else None,
                    )
                    modified_messages.append(new_msg)
                else:
                    modified_messages.append(msg)
            else:
                state.mark_seen(tool_use_id)

                if tool_name in skip_tool_names:
                    modified_messages.append(msg)
                else:
                    content = msg.content if isinstance(msg.content, str) else str(msg.content)
                    msg_index = len(modified_messages)
                    fresh_indices[tool_use_id] = msg_index
                    fresh_tool_results.append((tool_use_id, tool_name, content))
                    modified_messages.append(msg)
        else:
            modified_messages.append(msg)

    total_chars = sum(len(c) for _, _, c in fresh_tool_results)

    if total_chars <= storage.message_budget:
        return modified_messages, newly_replaced

    sorted_fresh = sorted(fresh_tool_results, key=lambda x: len(x[2]), reverse=True)

    chars_to_remove = total_chars - storage.message_budget
    ids_to_replace: Set[str] = set()

    for tool_use_id, tool_name, content in sorted_fresh:
        if chars_to_remove <= 0:
            break
        ids_to_replace.add(tool_use_id)
        chars_to_remove -= len(content)

    for tool_use_id in ids_to_replace:
        tool_name = None
        content = None
        for tid, tname, tcontent in fresh_tool_results:
            if tid == tool_use_id:
                tool_name = tname
                content = tcontent
                break

        result = storage.persist_tool_result(content, tool_use_id)
        replacement_text = storage.build_large_tool_result_message(result)

        state.set_replacement(tool_use_id, replacement_text)

        msg_index = fresh_indices[tool_use_id]
        new_msg = ToolMessage(
            content=replacement_text,
            tool_call_id=tool_use_id,
            name=tool_name if tool_name else None,
        )
        modified_messages[msg_index] = new_msg

        newly_replaced.append({
            "tool_use_id": tool_use_id,
            "tool_name": tool_name,
            "original_size": len(content),
            "filepath": result.filepath,
        })

    return modified_messages, newly_replaced
