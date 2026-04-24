import json
import locale
import logging
import subprocess
from typing import Any, List, Optional, Type, Union
from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from langchain_community.tools import ShellTool
from pydantic import BaseModel, Field, model_validator

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
            return self._decode_output(result.stdout)
        except subprocess.CalledProcessError as e:
            return self._decode_output(e.stdout) if e.stdout else str(e)
