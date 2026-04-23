import os
from typing import Optional

import tiktoken
from langchain_core.messages import HumanMessage

TASK_INTENT_FILENAME = "task-intent.txt"


class TaskIntentManager:

    def __init__(
        self,
        session_dir: str = "",
        full_threshold: int = 2000,
        token_budget: int = 10000,
        large_input_token_threshold: int = 10000,
    ):
        self.session_dir = session_dir
        self.full_threshold = full_threshold
        self.token_budget = token_budget
        self.large_input_token_threshold = large_input_token_threshold

        self._mode: Optional[str] = None
        self._full_content: Optional[str] = None
        self._preview: Optional[str] = None
        self._file_path: Optional[str] = None
        self._token_count: int = 0
        self._encoding = tiktoken.get_encoding("cl100k_base")

    def _estimate_tokens(self, text: str) -> int:
        return len(self._encoding.encode(text))

    def extract_task_intent(self, user_message: str) -> None:
        if self._mode is not None:
            return

        self._token_count = self._estimate_tokens(user_message)
        is_large_input = self._token_count > self.large_input_token_threshold

        if len(user_message) <= self.full_threshold and not is_large_input:
            self._mode = "full"
            self._full_content = user_message
            self._preview = None
            self._file_path = None
        else:
            self._mode = "persisted"
            self._full_content = user_message
            self._preview = user_message[:self.full_threshold]

            if self.session_dir:
                os.makedirs(self.session_dir, exist_ok=True)
                self._file_path = os.path.join(self.session_dir, TASK_INTENT_FILENAME)
                with open(self._file_path, "w", encoding="utf-8") as f:
                    f.write(user_message)

    def build_recovery_message(self, compressor=None) -> Optional[HumanMessage]:
        if self._mode is None:
            return None

        if self._token_count > self.large_input_token_threshold:
            if self.session_dir and not self._file_path:
                os.makedirs(self.session_dir, exist_ok=True)
                self._file_path = os.path.join(self.session_dir, TASK_INTENT_FILENAME)
                with open(self._file_path, "w", encoding="utf-8") as f:
                    f.write(self._full_content)

            content = (
                f"[Task Intent - PRESERVED]\n"
                f"{self._preview}\n"
                f"...\n"
                f"[Full task specification persisted to: {self._file_path}]"
            )
            return HumanMessage(content=content)

        if self._mode == "full":
            content = f"[Task Intent - PRESERVED]\n{self._full_content}"
            file_path = self._file_path
        else:
            content = (
                f"[Task Intent - PRESERVED]\n"
                f"{self._preview}\n"
                f"...\n"
                f"[Full task specification persisted to: {self._file_path}]"
            )
            file_path = self._file_path

        if compressor is not None:
            token_count = compressor.count_text_tokens(content)
            if token_count > self.token_budget:
                if self._mode == "full" and self.session_dir and not self._file_path:
                    os.makedirs(self.session_dir, exist_ok=True)
                    self._file_path = os.path.join(self.session_dir, TASK_INTENT_FILENAME)
                    with open(self._file_path, "w", encoding="utf-8") as f:
                        f.write(self._full_content)
                    file_path = self._file_path

                truncation_notice = f"[Task intent truncated, full content at: {file_path}]"
                truncation_notice_tokens = compressor.count_text_tokens(truncation_notice)
                header = "[Task Intent - PRESERVED]\n"
                header_tokens = compressor.count_text_tokens(header)

                budget_for_content = self.token_budget - header_tokens - truncation_notice_tokens

                source_text = self._full_content if self._mode == "full" else self._preview
                truncated = self._truncate_to_token_budget(source_text, compressor, budget_for_content)

                content = f"{header}{truncated}\n{truncation_notice}"

        return HumanMessage(content=content)

    def _truncate_to_token_budget(self, text: str, compressor, max_tokens: int) -> str:
        if max_tokens <= 0:
            return ""

        if compressor.count_text_tokens(text) <= max_tokens:
            return text

        low = 0
        high = len(text)
        result = ""

        while low <= high:
            mid = (low + high) // 2
            candidate = text[:mid]
            if compressor.count_text_tokens(candidate) <= max_tokens:
                result = candidate
                low = mid + 1
            else:
                high = mid - 1

        return result

    def has_task_intent(self) -> bool:
        return self._mode is not None

    def clear(self) -> None:
        self._mode = None
        self._full_content = None
        self._preview = None
        self._file_path = None
        self._token_count = 0
