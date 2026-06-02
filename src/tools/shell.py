import json
import locale
import logging
import os
import re
import subprocess
from typing import Any, List, Optional, Type, Union
from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from langchain_community.tools import ShellTool
from pydantic import BaseModel, Field, model_validator

from .script_recorder import get_script_recorder
from .snapshot_interceptor import (
    detect_snapshot_command,
    detect_system_declaration,
    process_snapshot_stdout,
    set_system_name,
)

logger = logging.getLogger(__name__)

_SR_COMMAND_PATTERN = re.compile(
    r'python\s+(?:-c|/c)\s+".*script_recorder.*"',
    re.IGNORECASE,
)

_SR_SET_CTX_PATTERN = re.compile(
    r"set_recording_context\(\s*'([^']*)'\s*,\s*'([^']*)'\s*,\s*'([^']*)'\s*\)"
)

_SR_SAVE_PATTERN = re.compile(
    r"save_active_recording\(\s*(r)?'([^']*)'\s*\)"
)


def _detect_script_recorder_command(commands: str) -> bool:
    return bool(_SR_COMMAND_PATTERN.search(commands))


def _handle_script_recorder_command(commands: str) -> Optional[str]:
    from .script_recorder import set_recording_context, save_active_recording

    code_match = re.search(
        r'python\s+(?:-c|/c)\s+"([^"]*)"',
        commands, re.IGNORECASE,
    )
    if not code_match:
        return None
    code = code_match.group(1)

    if 'set_recording_context' in code:
        match = _SR_SET_CTX_PATTERN.search(code)
        if match:
            system, source, heading = match.groups()
            set_recording_context(system, source, heading)
            logger.info(
                "script_recorder in-process: set_recording_context(%r, %r, %r)",
                system, source, heading,
            )
            return ""

    elif 'save_active_recording' in code:
        match = _SR_SAVE_PATTERN.search(code)
        if match:
            project_root = match.group(2)
            result = save_active_recording(project_root)
            if result:
                msg = f"Script saved: {result}\r\n"
            else:
                msg = "No recording to save\r\n"
            logger.info("script_recorder in-process: save_active_recording → %s", msg.strip())
            return msg

    return None


class RubatoShellInput(BaseModel):
    commands: str = Field(
        ...,
        description="要执行的 shell 命令字符串，例如 'git status' 或 'dir'",
    )

    @model_validator(mode="after")
    def _unwrap_json_commands(self) -> "RubatoShellInput":
        commands = self.commands
        if not commands or not isinstance(commands, str):
            return self
        stripped = commands.strip()
        if stripped.startswith("["):
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, list):
                    if len(parsed) == 1:
                        unwrapped = parsed[0]
                        if isinstance(unwrapped, str):
                            logger.warning(
                                "RubatoShellInput auto-unwrapped JSON array with single element: %r -> %r",
                                commands,
                                unwrapped,
                            )
                            self.commands = unwrapped
                    elif len(parsed) > 1:
                        str_elements = [str(e) for e in parsed]
                        joined = " && ".join(str_elements)
                        logger.warning(
                            "RubatoShellInput auto-unwrapped JSON array with multiple elements: %r -> %r",
                            commands,
                            joined,
                        )
                        self.commands = joined
            except (json.JSONDecodeError, TypeError):
                pass
        elif stripped.startswith("{"):
            try:
                json.loads(stripped)
                logger.warning(
                    "RubatoShellInput received JSON object which is not a valid command: %r",
                    commands,
                )
            except (json.JSONDecodeError, TypeError):
                pass
        return self


_SYSTEM_ENCODING = locale.getpreferredencoding() or "utf-8"


class RubatoShellTool(ShellTool):
    name: str = "terminal"
    args_schema: Type[BaseModel] = RubatoShellInput

    @staticmethod
    def _decode_output(raw: bytes) -> str:
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            pass
        try:
            return raw.decode(_SYSTEM_ENCODING)
        except (UnicodeDecodeError, LookupError):
            return raw.decode("utf-8", errors="replace")

    def _run(
        self,
        commands: Union[str, List[str]],
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        if isinstance(commands, list):
            commands = " && ".join(commands)

        if _detect_script_recorder_command(commands):
            try:
                result = _handle_script_recorder_command(commands)
                if result is not None:
                    return result
            except Exception as exc:
                logger.debug("script_recorder in-process handling failed: %s", exc)

        try:
            result = subprocess.run(
                commands,
                shell=True,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            output = self._decode_output(result.stdout)
        except subprocess.CalledProcessError as e:
            output = self._decode_output(e.stdout) if e.stdout else str(e)

        # Auto-detect system name from LLM declaration
        system_decl = detect_system_declaration(commands)
        if system_decl:
            set_system_name(system_decl)

        # Auto-cache on playwright-cli snapshot
        if detect_snapshot_command(commands):
            try:
                project_root = os.getcwd()
                logger.info(
                    "Snapshot detected, command=%r, output_len=%d, output_preview=%s",
                    commands[:200], len(output), output[:200],
                )
                count, cache_file = process_snapshot_stdout(output, project_root)
                if count > 0 and cache_file:
                    logger.info(
                        "Snapshot interceptor: cached %d elements to %s",
                        count, cache_file,
                    )
                else:
                    logger.info(
                        "Snapshot processing returned 0 elements (no cache written), project_root=%s",
                        project_root,
                    )
            except Exception as exc:
                logger.warning(
                    "Snapshot interceptor failed: %s: %s", type(exc).__name__, exc
                )

        if "playwright-cli" in commands and not detect_snapshot_command(commands):
            try:
                recorder = get_script_recorder()
                recorder.record_command(commands, output, success=True)
            except Exception as exc:
                logger.debug("Script recorder callback failed: %s", exc)

        return output
