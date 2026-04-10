import tiktoken
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from typing import List, Optional, Set, Tuple, Dict

from .tool_result_storage import ToolResultStorage, ContentReplacementState, apply_tool_result_budget, TOOL_RESULT_CLEARED_MESSAGE
from .compact_prompt import get_compact_prompt, format_compact_summary, get_compact_user_summary_message
from ..utils.logger import get_llm_logger


class ContextCompressor:

    def __init__(
        self,
        llm_caller=None,
        max_context_tokens: int = 80000,
        autocompact_buffer_tokens: int = 13000,
        manual_compact_buffer_tokens: int = 3000,
        warning_threshold_buffer_tokens: int = 20000,
        keep_recent: int = 6,
        summary_max_length: int = 300,
        history_summary_count: int = 10,
        snip_keep_recent: int = 6,
        max_consecutive_failures: int = 3,
        tool_result_storage=None,
        content_replacement_state=None,
        logger=None,
    ):
        self.llm_caller = llm_caller
        self.max_context_tokens = max_context_tokens
        self.autocompact_buffer_tokens = autocompact_buffer_tokens
        self.manual_compact_buffer_tokens = manual_compact_buffer_tokens
        self.warning_threshold_buffer_tokens = warning_threshold_buffer_tokens
        self.keep_recent = keep_recent
        self.summary_max_length = summary_max_length
        self.history_summary_count = history_summary_count
        self.snip_keep_recent = snip_keep_recent
        self.max_consecutive_failures = max_consecutive_failures
        self.tool_result_storage = tool_result_storage
        self.content_replacement_state = content_replacement_state
        self.logger = logger or get_llm_logger()

        self.encoding = tiktoken.get_encoding("cl100k_base")
        self._last_api_usage_tokens: int = 0
        self._consecutive_failures: int = 0

    def _get_content_str(self, content) -> str:
        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    if 'text' in item:
                        parts.append(item['text'])
                    else:
                        parts.append(str(item))
                else:
                    parts.append(str(item))
            return " ".join(parts)
        else:
            return str(content)

    def count_tokens(self, messages: List[BaseMessage]) -> int:
        total = 0
        for message in messages:
            content_str = self._get_content_str(message.content)
            total += len(self.encoding.encode(content_str))
        return total

    def count_text_tokens(self, text: str) -> int:
        return len(self.encoding.encode(text))

    def estimate_tokens(self, messages: List[BaseMessage]) -> int:
        if self._last_api_usage_tokens > 0:
            return self._last_api_usage_tokens + sum(
                len(self._get_content_str(m.content)) // 4
                for m in messages
            )
        return sum(len(self._get_content_str(m.content)) // 4 for m in messages)

    def update_usage_from_response(self, response: AIMessage) -> None:
        usage_metadata = getattr(response, 'usage_metadata', None)
        if usage_metadata and isinstance(usage_metadata, dict):
            self._last_api_usage_tokens = usage_metadata.get('input_tokens', 0) or usage_metadata.get('total_tokens', 0)
        response_metadata = getattr(response, 'response_metadata', None)
        if response_metadata and isinstance(response_metadata, dict):
            token_usage = response_metadata.get('token_usage', {})
            if isinstance(token_usage, dict):
                prompt_tokens = token_usage.get('prompt_tokens', 0)
                if prompt_tokens:
                    self._last_api_usage_tokens = prompt_tokens

    def needs_compression(self, messages: List[BaseMessage]) -> bool:
        token_count = self.estimate_tokens(messages)
        return token_count >= self.max_context_tokens - self.autocompact_buffer_tokens

    def compress(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        if not self.needs_compression(messages):
            return messages

        system_messages = [m for m in messages if isinstance(m, SystemMessage)]
        non_system_messages = [m for m in messages if not isinstance(m, SystemMessage)]

        if len(non_system_messages) <= self.keep_recent * 2:
            return messages

        recent_messages = non_system_messages[-self.keep_recent * 2:]
        middle_messages = non_system_messages[:-self.keep_recent * 2]

        valid_recent = self._ensure_message_chain_valid(recent_messages)

        summary = self._create_summary(middle_messages)

        return system_messages + [summary] + valid_recent

    def snip_compact(self, messages: List[BaseMessage]) -> Tuple[List[BaseMessage], int]:
        tool_messages = [(i, msg) for i, msg in enumerate(messages) if isinstance(msg, ToolMessage)]

        if not tool_messages:
            return messages, 0

        recent_tool_ids = set()
        for _, msg in tool_messages[-self.snip_keep_recent:]:
            recent_tool_ids.add(msg.tool_call_id)

        modified_messages = list(messages)
        tokens_freed = 0

        for idx, msg in tool_messages:
            if msg.tool_call_id not in recent_tool_ids:
                old_content = self._get_content_str(msg.content)
                old_tokens = len(old_content) // 4
                new_msg = ToolMessage(
                    content=TOOL_RESULT_CLEARED_MESSAGE,
                    tool_call_id=msg.tool_call_id,
                    name=getattr(msg, 'name', None),
                )
                modified_messages[idx] = new_msg
                new_tokens = len(TOOL_RESULT_CLEARED_MESSAGE) // 4
                tokens_freed += max(0, old_tokens - new_tokens)

        return modified_messages, tokens_freed

    async def auto_compact(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        pre_tokens = self.estimate_tokens(messages)

        messages_to_summarize = self._strip_images_from_messages(messages)

        from .compact_prompt import get_compact_prompt, format_compact_summary, get_compact_user_summary_message
        compact_prompt = get_compact_prompt()

        summary_text = await self._call_llm_for_summary(messages_to_summarize, compact_prompt)

        formatted_summary = format_compact_summary(summary_text)
        user_summary = get_compact_user_summary_message(
            formatted_summary,
            suppress_follow_up_questions=True,
            recent_messages_preserved=True,
        )

        system_messages = [m for m in messages if isinstance(m, SystemMessage) and not m.content.startswith("[compact_boundary]")]
        non_system_messages = [m for m in messages if not isinstance(m, SystemMessage)]

        recent_messages = non_system_messages[-self.keep_recent:] if len(non_system_messages) > self.keep_recent else non_system_messages
        valid_recent = self._ensure_message_chain_valid(recent_messages)

        boundary = self._create_compact_boundary_message("auto", pre_tokens)
        summary_msg = self._create_summary_message(user_summary)

        if self.tool_result_storage and hasattr(self.tool_result_storage, 'read_file_state') and self.tool_result_storage.read_file_state is not None:
            self.tool_result_storage.read_file_state.clear()

        return system_messages + [boundary, summary_msg] + valid_recent

    async def auto_compact_if_needed(self, messages: List[BaseMessage], snip_tokens_freed: int = 0) -> List[BaseMessage]:
        current_tokens = self.estimate_tokens(messages) - snip_tokens_freed
        autocompact_threshold = self.max_context_tokens - self.autocompact_buffer_tokens

        if current_tokens < autocompact_threshold:
            return messages

        if self._consecutive_failures >= self.max_consecutive_failures:
            self.logger.log_agent_action("auto_compact_skipped", {
                "reason": "max_consecutive_failures_reached",
                "failures": self._consecutive_failures,
            })
            return messages

        try:
            result = await self.auto_compact(messages)
            self._consecutive_failures = 0
            return result
        except Exception as e:
            self._consecutive_failures += 1
            self.logger.log_error("auto_compact", e)
            return messages

    def get_messages_after_compact_boundary(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        last_boundary_idx = -1
        for i, msg in enumerate(messages):
            if isinstance(msg, SystemMessage) and isinstance(msg.content, str) and msg.content.startswith("[compact_boundary]"):
                last_boundary_idx = i

        if last_boundary_idx == -1:
            return messages

        return messages[last_boundary_idx + 1:]

    def _strip_images_from_messages(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        stripped = []
        for msg in messages:
            if isinstance(msg.content, list):
                new_blocks = []
                for block in msg.content:
                    if isinstance(block, dict):
                        if block.get('type') == 'image_url' or block.get('type') == 'image':
                            new_blocks.append({'type': 'text', 'text': '[image]'})
                        elif block.get('type') == 'document' or (block.get('type') == 'file' and block.get('source', {}).get('type') == 'base64'):
                            new_blocks.append({'type': 'text', 'text': '[document]'})
                        else:
                            new_blocks.append(block)
                    else:
                        new_blocks.append(block)
                new_msg = msg.__class__(
                    content=new_blocks,
                    **{k: v for k, v in msg.__dict__.items() if k not in ('content', 'type', 'id') and not k.startswith('_')},
                )
                stripped.append(new_msg)
            else:
                stripped.append(msg)
        return stripped

    def _ensure_message_chain_valid(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        if not messages:
            return messages

        valid_messages = []
        pending_tool_call_ids: Set[str] = set()

        for msg in messages:
            if isinstance(msg, AIMessage):
                valid_messages.append(msg)
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    for tc in msg.tool_calls:
                        pending_tool_call_ids.add(tc.get('id'))
            elif isinstance(msg, ToolMessage):
                if msg.tool_call_id in pending_tool_call_ids:
                    valid_messages.append(msg)
                    pending_tool_call_ids.discard(msg.tool_call_id)
                else:
                    content_str = self._get_content_str(msg.content)
                    content = content_str[:200] + "..." if len(content_str) > 200 else content_str
                    valid_messages.append(HumanMessage(content=f"[工具结果摘要]: {content}"))
            else:
                valid_messages.append(msg)

        return valid_messages

    def calculate_token_warning_state(self, token_usage: int) -> Dict[str, bool]:
        return {
            "is_above_warning_threshold": token_usage >= self.max_context_tokens - self.warning_threshold_buffer_tokens,
            "is_above_autocompact_threshold": token_usage >= self.max_context_tokens - self.autocompact_buffer_tokens,
            "is_at_blocking_limit": token_usage >= self.max_context_tokens - self.manual_compact_buffer_tokens,
        }

    def _create_compact_boundary_message(self, trigger: str, pre_tokens: int) -> SystemMessage:
        content = f"[compact_boundary] trigger={trigger} pre_tokens={pre_tokens}"
        return SystemMessage(content=content)

    def _create_summary_message(self, summary_text: str) -> HumanMessage:
        return HumanMessage(content=summary_text)

    def apply_tool_result_budget(self, messages: List[BaseMessage]) -> Tuple[List[BaseMessage], List[Dict]]:
        if self.tool_result_storage is not None and self.content_replacement_state is not None:
            return apply_tool_result_budget(
                messages,
                self.content_replacement_state,
                self.tool_result_storage,
            )
        return messages, []

    async def _call_llm_for_summary(self, messages: List[BaseMessage], prompt: str) -> str:
        current_messages = messages
        for attempt in range(3):
            try:
                summary_messages = [SystemMessage(content=prompt)] + current_messages
                response = await self.llm_caller.invoke(summary_messages, use_tools=False)
                return response.content if response.content else ""
            except Exception as e:
                error_str = str(e).lower()
                if ('prompt' in error_str and 'too long' in error_str) or 'context_length_exceeded' in error_str or 'max_tokens' in error_str:
                    truncated = self._truncate_head_for_ptl_retry(current_messages)
                    if len(truncated) < len(current_messages):
                        current_messages = truncated
                        continue
                raise
        return ""

    def _truncate_head_for_ptl_retry(self, messages: List[BaseMessage], max_retries: int = 3) -> List[BaseMessage]:
        groups = self._group_messages_by_api_round(messages)
        if len(groups) <= 1:
            return messages
        truncated = groups[1:]
        result = []
        for group in truncated:
            result.extend(group)
        return result

    def _group_messages_by_api_round(self, messages: List[BaseMessage]) -> List[List[BaseMessage]]:
        groups: List[List[BaseMessage]] = []
        current_group: List[BaseMessage] = []
        last_ai_id: Optional[str] = None

        for msg in messages:
            if isinstance(msg, AIMessage):
                msg_id = getattr(msg, 'id', None)
                if msg_id and msg_id != last_ai_id and current_group:
                    groups.append(current_group)
                    current_group = []
                    last_ai_id = msg_id
                elif msg_id:
                    last_ai_id = msg_id
                current_group.append(msg)
            else:
                current_group.append(msg)

        if current_group:
            groups.append(current_group)

        return groups if groups else [messages]

    def _create_summary(self, messages: List[BaseMessage]) -> HumanMessage:
        summary_parts = []
        for msg in messages:
            role = "用户" if isinstance(msg, HumanMessage) else "助手"
            content_str = self._get_content_str(msg.content)
            content = content_str[:200] + "..." if len(content_str) > 200 else content_str
            summary_parts.append(f"[{role}]: {content}")

        summary_content = f"[历史摘要]\n" + "\n".join(summary_parts)
        return HumanMessage(content=summary_content)
