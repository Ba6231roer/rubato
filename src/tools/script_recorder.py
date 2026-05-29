"""Script recorder for recording playwright-cli commands during test execution.
Extracts Playwright code snippets, applies de-redundancy, and assembles executable scripts.
"""

import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_VERSION = "rubato-script-recorder v1.0"

_ACTION_PATTERNS: list[tuple[str, str]] = [
    (r'\.screenshot\(', 'snapshot'),
    (r'snapshot\b', 'snapshot'),
    (r'page\.goto\(', 'goto'),
    (r'\.click\(', 'click'),
    (r'\.fill\(', 'fill'),
    (r'\.type\(', 'type'),
    (r'\.press\(', 'other'),
    (r'\.selectOption\(', 'other'),
    (r'\.hover\(', 'other'),
    (r'\.check\(', 'click'),
    (r'\.uncheck\(', 'click'),
]

_VERIFY_PATTERNS: tuple[str, ...] = (
    r'\.isVisible\(',
    r'\.isHidden\(',
    r'\.isEnabled\(',
    r'\.isDisabled\(',
    r'\.isEditable\(',
    r'\.textContent\(',
    r'\.innerText\(',
    r'\.getAttribute\(',
    r'\.waitForSelector\(',
    r'\.waitFor\(',
    r'\.toMatchAriaSnapshot\(',
    r'\.toHaveText\(',
    r'\.toBeVisible\(',
    r'\.toBeEnabled\(',
    r'\.toBeDisabled\(',
    r'\.toHaveValue\(',
    r'\.toHaveCount\(',
    r'expect\(',
    r'\.assert\(',
    r'\.toContainText\(',
)


@dataclass
class RecordEntry:
    index: int
    command: str
    code_snippet: str
    success: bool
    timestamp: float
    action: str


def _derive_action(command: str, code_snippet: str) -> str:
    combined = f"{command} {code_snippet}"
    for pattern, action_type in _ACTION_PATTERNS:
        if re.search(pattern, combined):
            return action_type
    for pattern in _VERIFY_PATTERNS:
        if re.search(pattern, combined):
            return 'verify'
    return 'other'


_LLM_REVIEW_SYSTEM_PROMPT = """你是一个测试脚本质量审查助手。你的任务是审查录制的 Playwright 操作序列，识别其中的冗余和无效操作。

请分析以下操作序列，对每条操作返回 JSON 数组格式的审查结果：
[{"index": 0, "decision": "keep|remove", "reason": "原因"}]

判断规则：
- keep: 有效的操作步骤，保留
- remove: 冗余的、重复的、错误后重试的操作

注意：
- 宁可多保留，不可误删关键步骤
- 如果不确定，选择 keep
- 只返回 JSON 数组，不要其他文本"""


def _create_llm_client_from_config():
    import os
    import yaml
    config_path = os.path.join(os.getcwd(), 'config', 'model_config.yaml')
    if not os.path.exists(config_path):
        return None
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    model_config = config.get('models', config)
    if isinstance(model_config, list):
        model_config = model_config[0] if model_config else {}
    api_key = model_config.get('api_key', 'sk-placeholder')
    base_url = model_config.get('base_url')
    default_headers = model_config.get('default_headers')
    from openai import OpenAI as SyncOpenAI
    client_kwargs = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url
    if default_headers:
        client_kwargs["default_headers"] = default_headers
    return SyncOpenAI(**client_kwargs), model_config


class ScriptRecorder:
    def __init__(
        self,
        llm_config: dict | None = None,
        enable_llm_review: bool = True,
    ):
        self._llm_config = llm_config
        self._enable_llm_review = enable_llm_review
        self._buffer: list[RecordEntry] = []
        self._raw_buffer: list[RecordEntry] = []
        self._recording: bool = False
        self._system_name: str = ""
        self._case_description: str = ""
        self._start_time: float | None = None
        self._case_system: str = ""
        self._case_source: str = ""
        self._case_heading: str = ""

    def set_case_context(self, system: str, source: str, heading: str) -> None:
        self._case_system = system
        self._case_source = source
        self._case_heading = heading

    def start_recording(self, system_name: str, case_description: str = "") -> None:
        """Initialize recording session."""
        self._buffer = []
        self._raw_buffer = []
        self._recording = True
        self._system_name = system_name
        self._case_description = case_description
        self._start_time = time.time()
        logger.info(
            "Recording started: system=%s, case=%s",
            system_name, case_description[:50],
        )

    def record_command(self, command: str, output: str, success: bool = True) -> None:
        """Record a playwright-cli command and its output."""
        if not self._recording:
            from .snapshot_interceptor import get_system_name
            system = get_system_name() or "unknown"
            self.start_recording(system, "")

        code_snippet = self._extract_code_snippet(output)
        if code_snippet is None:
            return

        entry = RecordEntry(
            index=len(self._buffer) + 1,
            command=command,
            code_snippet=code_snippet,
            success=success,
            timestamp=time.time(),
            action=_derive_action(command, code_snippet),
        )
        self._buffer.append(entry)
        logger.debug(
            "Recorded entry #%d: action=%s, cmd=%s",
            entry.index, entry.action, command[:80],
        )

    def stop_recording(self) -> str:
        """Stop recording, apply de-duplication, assemble and return final script."""
        if not self._recording:
            return ""

        self._recording = False
        self._raw_buffer = list(self._buffer)
        logger.info(
            "Recording stopped: %d entries captured for system=%s",
            len(self._buffer), self._system_name,
        )

        self._apply_rule_dedup()

        if self._enable_llm_review and self._buffer:
            self._apply_llm_review()

        return self._assemble_script()

    def _extract_code_snippet(self, output: str) -> Optional[str]:
        marker = "Ran Playwright code"
        idx = output.find(marker)
        if idx == -1:
            return None

        after_marker = output[idx + len(marker):]
        lines = after_marker.splitlines()

        code_lines: list[str] = []
        in_code_block = False
        for line in lines:
            stripped = line.strip()
            if not in_code_block:
                if stripped.startswith('```'):
                    in_code_block = True
                    continue
                if stripped and not stripped.startswith('```'):
                    if stripped.startswith('###') or stripped.startswith('//') or stripped.startswith('/*'):
                        continue
                    in_code_block = True
                    code_lines.append(stripped)
                continue
            if stripped.startswith('```'):
                break
            if stripped.startswith('###'):
                break
            if stripped.startswith('//') or stripped.startswith('/*') or stripped.startswith('*'):
                continue
            code_lines.append(stripped)

        return '\n'.join(code_lines) if code_lines else None

    def _apply_rule_dedup(self) -> None:
        """Apply rule-based de-duplication to the buffer."""
        filtered = [e for e in self._buffer if e.action != 'snapshot']

        result: list[RecordEntry] = []
        consecutive_gotos: list[RecordEntry] = []

        for entry in filtered:
            if entry.action == 'goto':
                consecutive_gotos.append(entry)
            else:
                if consecutive_gotos:
                    result.append(consecutive_gotos[-1])
                    consecutive_gotos = []
                result.append(entry)

        if consecutive_gotos:
            result.append(consecutive_gotos[-1])

        removed = len(self._raw_buffer) - len(result)
        self._buffer = result
        logger.info(
            "Rule de-dup applied: %d -> %d entries (%d removed)",
            len(self._raw_buffer), len(self._buffer), removed,
        )

    def _apply_llm_review(self) -> None:
        if not self._buffer:
            return
        try:
            result = _create_llm_client_from_config()
            if result is None:
                logger.debug("No model config found, skipping LLM review")
                return
            client, model_config = result

            entries_text = ""
            for entry in self._buffer:
                entries_text += f"[{entry.index}] action={entry.action} success={entry.success}\n  code: {entry.code_snippet}\n"

            model_name = model_config.get('model', model_config.get('name', 'gpt-4'))
            retry_max = model_config.get('retry_max_count', 3)
            retry_initial = model_config.get('retry_initial_delay', 10.0)
            retry_max_delay = model_config.get('retry_max_delay', 60.0)

            delay = retry_initial
            last_error = None
            for attempt in range(retry_max + 1):
                try:
                    response = client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": _LLM_REVIEW_SYSTEM_PROMPT},
                            {"role": "user", "content": f"测试案例描述: {self._case_description}\n\n录制操作序列:\n{entries_text}"}
                        ],
                        temperature=0.3,
                        max_tokens=2000
                    )
                    content = response.choices[0].message.content.strip()
                    break
                except Exception as e:
                    last_error = e
                    if attempt < retry_max:
                        logger.debug("LLM review attempt %d failed: %s, retrying in %ss", attempt + 1, str(e)[:100], delay)
                        time.sleep(delay)
                        delay = min(delay * 2, retry_max_delay)
            else:
                logger.debug("LLM review failed after %d retries: %s", retry_max, last_error)
                return

            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if not json_match:
                logger.debug("LLM review response has no JSON array, skipping")
                return

            decisions = json.loads(json_match.group())
            indices_to_remove = set()
            for decision in decisions:
                idx = decision.get("index")
                action = decision.get("decision", "keep")
                if action == "remove" and idx is not None:
                    indices_to_remove.add(idx)

            self._buffer = [e for e in self._buffer if e.index not in indices_to_remove]
            logger.info("LLM review: removed %d entries from %d total", len(indices_to_remove), len(self._buffer) + len(indices_to_remove))
        except Exception as exc:
            logger.debug("LLM review failed, using rule-layer result: %s", exc)

    def _assemble_script(self) -> str:
        """Assemble the de-duped buffer into a standard async (page) => { ... } script."""
        if not self._buffer:
            return ""

        timestamp_str = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        lines: list[str] = ["async (page) => {"]

        lines.append("  // == META ==")
        if self._case_description:
            escaped = self._case_description.replace('*/', '').replace('/*', '')
            lines.append(f"  // case: {escaped}")
        lines.append(f"  // system: {self._system_name}")
        lines.append(f"  // recorded: {timestamp_str}")
        lines.append(f"  // generator: {_VERSION}")
        lines.append("")

        step_num = 0
        verify_buffer: list[str] = []

        for entry in self._buffer:
            if entry.action == 'verify':
                verify_buffer.append(entry.code_snippet)
                continue

            if verify_buffer:
                for v_idx, v_code in enumerate(verify_buffer, 1):
                    lines.append(f"  // -- verify step {step_num}.{v_idx} --")
                    lines.append(f"  {v_code}")
                lines.append("")
                verify_buffer = []

            step_num += 1
            cmd_short = entry.command[:60].replace('\n', ' ')
            lines.append(f"  // == STEP {step_num}: {cmd_short} ==")
            if not entry.success:
                lines.append("  // 预期: 此步骤之前执行失败")
            for code_line in entry.code_snippet.splitlines():
                lines.append(f"  {code_line}")
            if entry.action == 'goto':
                lines.append("  await page.waitForLoadState('networkidle');")
            lines.append("")

        if verify_buffer:
            for v_idx, v_code in enumerate(verify_buffer, 1):
                lines.append(f"  // -- verify step {step_num}.{v_idx} --")
                lines.append(f"  {v_code}")
            lines.append("")

        lines.append("  // == ALL STEPS PASSED ==")
        lines.append(
            "  return { status: 'PASS', message: 'All steps passed', "
            "url: await page.url() };"
        )
        lines.append("}")

        return '\n'.join(lines)


def set_recording_context(system: str, source: str, heading: str) -> None:
    recorder = get_script_recorder()
    recorder.set_case_context(system, source, heading)


def save_active_recording(project_root: str, case_description: str = "") -> str | None:
    global _recorder_instance
    if _recorder_instance is None or not _recorder_instance._recording:
        return None

    script = _recorder_instance.stop_recording()
    if not script:
        logger.info("Recording stopped but script is empty (buffer had %d raw entries)", len(_recorder_instance._raw_buffer))
        _recorder_instance = None
        return None

    from .snapshot_interceptor import get_system_name
    from .script_manager import ScriptManager

    system = _recorder_instance._case_system or get_system_name() or "temp"
    source = _recorder_instance._case_source or "interactive"
    heading = _recorder_instance._case_heading or _generate_heading(case_description)

    manager = ScriptManager(project_root)

    duplicate = manager.check_duplicate(system, script)
    if duplicate:
        with open(duplicate, "w", encoding="utf-8") as f:
            f.write(script)
        step_count = manager._count_steps(script)
        manager.update_index(
            duplicate, source, heading, "updated", "recording", step_count
        )
        _recorder_instance = None
        logger.info("Updated existing script: %s", duplicate)
        return duplicate

    saved_path = manager.save_script(system, source, heading, script)

    if case_description and system != "temp":
        try:
            manager.save_case_text(system, heading, case_description)
        except Exception as exc:
            logger.debug("Case text save failed: %s", exc)

    _recorder_instance = None
    logger.info("Script saved: %s", saved_path)
    return saved_path


def _generate_heading(case_description: str) -> str:
    if not case_description:
        from datetime import datetime
        return f"case_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    heading = case_description[:50].strip()
    for ch in '<>\"|?*\\/:\n\r\t':
        heading = heading.replace(ch, "_")
    return heading or "unnamed_case"


_recorder_instance: ScriptRecorder | None = None


def get_script_recorder(**kwargs) -> ScriptRecorder:
    """Return a singleton ScriptRecorder instance."""
    global _recorder_instance
    if _recorder_instance is None:
        _recorder_instance = ScriptRecorder(**kwargs)
    return _recorder_instance
