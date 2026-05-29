import json
import locale
import logging
import os
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
