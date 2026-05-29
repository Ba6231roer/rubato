import json
import logging
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class ScriptLookupResult:
    path: str
    is_stale: bool = False


class ScriptManager:
    SCRIPTS_DIR = "webui_scripts"
    INDEX_FILE = "INDEX.yaml"

    def __init__(self, project_root: str):
        self.project_root = project_root
        self.scripts_dir = os.path.join(project_root, self.SCRIPTS_DIR)
        self.index_path = os.path.join(self.scripts_dir, self.INDEX_FILE)

    def save_script(
        self,
        system: str,
        source_file: str,
        heading_path: str,
        content: str,
        created_from: str = "recording",
        source_hash: str = None,
    ) -> str:
        rel_path = self._calculate_script_path(system, source_file, heading_path)
        abs_path = os.path.join(self.scripts_dir, rel_path)

        os.makedirs(os.path.dirname(abs_path), exist_ok=True)

        if os.path.exists(abs_path):
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = abs_path.replace('.js', f'.bak.{timestamp}.js')
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)
            import shutil
            shutil.copy2(abs_path, backup_path)
            logger.info("Backed up existing script: %s -> %s", abs_path, backup_path)

        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)

        step_count = self._count_steps(content)
        self.update_index(
            rel_path, source_file, heading_path, "pending", created_from, step_count, source_hash=source_hash
        )

        logger.info(
            "Script saved: %s (%d steps, created_from=%s)", rel_path, step_count, created_from
        )
        return abs_path

    def find_script(self, system: str, source_file: str, heading_path: str, source_text: str = None) -> Optional[ScriptLookupResult]:
        rel_path = self._calculate_script_path(system, source_file, heading_path)
        abs_path = os.path.join(self.scripts_dir, rel_path)

        if not os.path.exists(abs_path):
            return None

        is_stale = False
        if source_text is not None:
            stored_hash = self._get_stored_hash(abs_path)
            if stored_hash:
                import hashlib
                current_hash = hashlib.sha256(source_text.encode('utf-8')).hexdigest()
                is_stale = (current_hash != stored_hash)

        return ScriptLookupResult(path=abs_path, is_stale=is_stale)

    def execute_script(self, script_path: str, session_name: Optional[str] = None) -> dict:
        if not os.path.isabs(script_path):
            script_path = os.path.join(self.project_root, script_path)
        if not os.path.exists(script_path):
            return {"status": "FAIL", "message": f"Script not found: {script_path}"}

        if session_name:
            cmd = f'playwright-cli -s {session_name} run-code --filename="{script_path}"'
        else:
            try:
                check_cmd = 'playwright-cli status'
                check_result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=10, shell=True)
                if 'not open' in check_result.stdout.lower() or 'not open' in check_result.stderr.lower() or check_result.returncode != 0:
                    open_cmd = 'playwright-cli open --headed'
                    subprocess.run(open_cmd, capture_output=True, text=True, timeout=30, shell=True)
            except Exception:
                try:
                    open_cmd = 'playwright-cli open --headed'
                    subprocess.run(open_cmd, capture_output=True, text=True, timeout=30, shell=True)
                except Exception:
                    pass
            cmd = f'playwright-cli run-code --filename="{script_path}"'

        logger.info("Executing script: %s", cmd)

        result: dict = {
            "status": "FAIL",
            "message": "",
            "failedStep": None,
            "url": None,
        }

        try:
            proc = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=self.project_root,
            )
            output = proc.stdout or ""
            logger.info(
                "Script execution completed: exit_code=%d, output_len=%d",
                proc.returncode,
                len(output),
            )
        except subprocess.TimeoutExpired:
            result["message"] = "Script execution timed out (120s)"
            logger.warning("Script execution timed out: %s", script_path)
            return result
        except Exception as exc:
            result["message"] = f"Execution error: {exc}"
            logger.error("Script execution error: %s: %s", script_path, exc)
            return result

        parsed = self._parse_playwright_output(output)
        if parsed:
            result = parsed
        elif proc.returncode != 0:
            result["message"] = (proc.stderr or output)[:500] or f"Exit code: {proc.returncode}"
        else:
            result["status"] = "PASS"
            result["message"] = output[:500]

        self._update_index_status(script_path, result["status"])

        return result

    def check_duplicate(self, system: str, content: str) -> Optional[str]:
        new_locators = self._extract_locators(content)
        if not new_locators:
            return None

        new_step_count = self._count_steps(content)
        system_dir = os.path.join(self.scripts_dir, system)

        if not os.path.isdir(system_dir):
            return None

        for root, _dirs, files in os.walk(system_dir):
            for fname in files:
                if not fname.endswith(".js"):
                    continue

                existing_path = os.path.join(root, fname)
                try:
                    with open(existing_path, "r", encoding="utf-8") as f:
                        existing_content = f.read()
                except OSError:
                    continue

                existing_locators = self._extract_locators(existing_content)
                if not existing_locators:
                    continue

                existing_step_count = self._count_steps(existing_content)

                if abs(new_step_count - existing_step_count) > 2:
                    continue

                overlap = len(new_locators & existing_locators)
                union = len(new_locators | existing_locators)
                if union == 0:
                    continue

                ratio = overlap / union
                if ratio > 0.8:
                    logger.info(
                        "Duplicate detected: %s (overlap=%.2f, steps=%d vs %d)",
                        existing_path, ratio, new_step_count, existing_step_count,
                    )
                    return existing_path

        return None

    def update_index(
        self,
        script_path: str,
        source_file: str,
        heading_path: str,
        status: str,
        created_from: str,
        step_count: int,
        source_hash: str = None,
    ) -> None:
        os.makedirs(self.scripts_dir, exist_ok=True)

        index_data = self._load_index()

        scripts = index_data.get("scripts") or []
        normalized = script_path.replace("\\", "/")

        found = False
        for entry in scripts:
            if entry.get("path") == normalized:
                entry["last_run"] = datetime.now().isoformat(timespec="seconds")
                entry["last_status"] = status
                entry["created_from"] = created_from
                entry["step_count"] = step_count
                if source_hash:
                    entry["source_hash"] = source_hash
                found = True
                break

        if not found:
            scripts.append({
                "path": normalized,
                "source": source_file.replace("\\", "/"),
                "heading_path": heading_path,
                "last_run": datetime.now().isoformat(timespec="seconds"),
                "last_status": status,
                "created_from": created_from,
                "step_count": step_count,
            })
            if source_hash:
                scripts[-1]["source_hash"] = source_hash

        index_data["scripts"] = scripts

        with open(self.index_path, "w", encoding="utf-8") as f:
            yaml.dump(
                index_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False
            )

    def save_case_text(self, system: str, case_title: str, case_text: str) -> str:
        cases_dir = os.path.join(self.project_root, "workspace", "test_cases")
        system_dir = os.path.join(cases_dir, self._sanitize_name(system))
        os.makedirs(system_dir, exist_ok=True)

        safe_title = self._sanitize_name(case_title)
        file_path = os.path.join(system_dir, f"{safe_title}.md")

        content = f"# {case_title}\n\n{case_text}\n"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info("Case text saved: %s", file_path)
        return file_path

    def _calculate_script_path(self, system: str, source_file: str, heading_path: str) -> str:
        base_name = os.path.splitext(os.path.basename(source_file))[0]
        parts = heading_path.split("/")
        sanitized = [self._sanitize_name(p) for p in parts]

        if len(sanitized) >= 2:
            dirs = sanitized[:-1]
            filename = sanitized[-1]
        else:
            dirs = []
            filename = sanitized[0] if sanitized else "script"

        path_parts = [system, base_name] + dirs + [f"{filename}.js"]
        return os.path.join(*path_parts)

    @staticmethod
    def _sanitize_name(name: str) -> str:
        result = name.strip()
        for ch in '<>\"|?*\\/:':
            result = result.replace(ch, "_")
        result = re.sub(r"_+", "_", result)
        result = result.strip("_.")
        if not result:
            result = "unnamed"
        return result

    def _load_index(self) -> dict:
        if os.path.isfile(self.index_path):
            try:
                with open(self.index_path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            except Exception as exc:
                logger.warning("Failed to load INDEX.yaml: %s", exc)
        return {}

    def _update_index_status(self, script_path: str, status: str) -> None:
        index_data = self._load_index()
        scripts = index_data.get("scripts") or []

        normalized = script_path.replace("\\", "/")
        for root_dir in [self.scripts_dir, self.project_root]:
            if normalized.startswith(root_dir.replace("\\", "/")):
                normalized = normalized[len(root_dir.replace("\\", "/")):]
                if normalized.startswith("/"):
                    normalized = normalized[1:]
                break

        for entry in scripts:
            entry_path = entry.get("path", "").replace("\\", "/")
            if entry_path == normalized or entry_path.endswith(normalized):
                entry["last_run"] = datetime.now().isoformat(timespec="seconds")
                entry["last_status"] = status.lower()
                break

        index_data["scripts"] = scripts
        os.makedirs(self.scripts_dir, exist_ok=True)
        with open(self.index_path, "w", encoding="utf-8") as f:
            yaml.dump(
                index_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False
            )

    @staticmethod
    def _parse_playwright_output(output: str) -> Optional[dict]:
        result_match = re.search(r"Result:\s*(\{.*?\})", output, re.DOTALL)
        if not result_match:
            result_match = re.search(r"(\{[^{}]*\"status\"[^{}]*\})", output, re.DOTALL)

        if not result_match:
            return None

        raw = result_match.group(1)
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Failed to parse playwright result JSON: %s", raw[:200])
            return None

        status = parsed.get("status", "FAIL").upper()
        return {
            "status": "PASS" if status == "PASS" else "FAIL",
            "message": parsed.get("message", ""),
            "failedStep": parsed.get("failedStep"),
            "url": parsed.get("url"),
        }

    @staticmethod
    def _extract_locators(content: str) -> set[str]:
        patterns = [
            r"getByRole\([^)]+\)",
            r"getByText\([^)]+\)",
            r"getByTestId\([^)]+\)",
            r"getByPlaceholder\([^)]+\)",
            r"getByLabel\([^)]+\)",
            r"locator\([^)]+\)",
        ]
        locators: set[str] = set()
        for pattern in patterns:
            locators.update(re.findall(pattern, content))
        return locators

    @staticmethod
    def _count_steps(content: str) -> int:
        patterns = [
            r"\.(click|fill|type|select|check|uncheck|press|hover|screenshot)\(",
            r"\.(goto|waitFor|waitForSelector|waitForNavigation|waitForURL)\(",
            r"\.(toBeVisible|toBeHidden|toBeEnabled|toBeDisabled|toHaveText|toHaveValue)\(",
            r"\.(assert|expect)\(",
        ]
        count = 0
        for pattern in patterns:
            count += len(re.findall(pattern, content))
        return count

    def _get_stored_hash(self, script_path: str) -> Optional[str]:
        try:
            index = self._load_index()
            for entry in index.get("scripts", []):
                if entry.get("path", "").replace("\\", "/") == script_path.replace("\\", "/").split("webui_scripts/", 1)[-1] if "webui_scripts/" in script_path.replace("\\", "/") else entry.get("path") == script_path:
                    return entry.get("source_hash")
        except Exception:
            pass
        return None

    @staticmethod
    def extract_md_section(md_path: str, heading_path: str) -> Optional[str]:
        if not os.path.exists(md_path):
            return None
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()

        headings = heading_path.split('/')
        lines = content.splitlines()

        target_level = len(headings)
        start_idx = None
        end_idx = len(lines)

        search_heading = headings[-1]

        for i, line in enumerate(lines):
            stripped = line.strip()
            prefix = '#' * (target_level + 1) + ' '
            if stripped == f"{'#' * (target_level + 1)} {search_heading}" or stripped == f"{'#' * target_level} {search_heading}":
                start_idx = i
                continue
            if start_idx is not None:
                for level in range(1, target_level + 2):
                    if stripped.startswith(f"{'#' * level} ") and i > start_idx:
                        end_idx = i
                        break
                if end_idx < len(lines):
                    break

        if start_idx is None:
            return None
        return '\n'.join(lines[start_idx:end_idx])

    def staleness_llm_check(self, script_path: str, source_text: str) -> str:
        try:
            from .script_recorder import _create_llm_client_from_config
            result = _create_llm_client_from_config()
            if result is None:
                return "major_change"
            client, model_config = result

            with open(script_path, 'r', encoding='utf-8') as f:
                script_content = f.read()

            model_name = model_config.get('model', model_config.get('name', 'gpt-4'))
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "你是测试脚本变更分析助手。比较原始案例描述和当前脚本，判断变更程度。\n只返回以下之一：unchanged, minor_change, major_change"},
                    {"role": "user", "content": f"原始案例描述:\n{source_text}\n\n当前脚本:\n{script_content}"}
                ],
                temperature=0.1,
                max_tokens=50
            )
            verdict = response.choices[0].message.content.strip().lower()
            if verdict in ('unchanged', 'minor_change', 'major_change'):
                return verdict
            return "major_change"
        except Exception as exc:
            logger.debug("Staleness LLM check failed: %s", exc)
            return "major_change"


logger.info("Script manager loaded")
