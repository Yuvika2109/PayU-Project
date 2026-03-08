"""
core/execution_engine.py
Safely executes generated Python code in a subprocess and captures output/errors.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from config.model_config import CODE_EXECUTION_TIMEOUT
from utils.logger import get_logger

logger = get_logger("core.execution_engine")


@dataclass
class ExecutionResult:
    """Holds the outcome of a single code execution attempt."""

    success: bool
    stdout: str = ""
    stderr: str = ""
    error_message: str = ""
    script_path: Optional[str] = None
    exit_code: int = 0


class ExecutionEngine:
    """
    Writes generated Python code to a temp file and runs it as a subprocess.
    Captures stdout, stderr, and the process exit code.

    Isolation strategy
    ------------------
    The generated code runs in its own subprocess with the same Python
    interpreter, but PATH-scoped to the current virtual environment.
    This keeps it away from the parent process's memory while still
    having access to installed packages (pandas, faker, etc.).
    """

    def __init__(
        self,
        timeout: int = CODE_EXECUTION_TIMEOUT,
        work_dir: Optional[str] = None,
    ):
        self.timeout = timeout
        self.work_dir = work_dir or str(Path.cwd())

    def execute(self, code: str, script_name: str = "generated_script.py") -> ExecutionResult:
        """
        Write *code* to a temp file and execute it.

        Parameters
        ----------
        code        : Python source code string.
        script_name : Filename hint for the temp script (for logging).

        Returns
        -------
        ExecutionResult
        """
        # Write code to a named temporary file
        script_path = self._write_temp_script(code, script_name)
        logger.info("Executing script: %s (timeout=%ds)", script_path, self.timeout)

        try:
            proc = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=self.work_dir,
                env={**os.environ},  # inherit full env (virtualenv, etc.)
            )

            if proc.returncode == 0:
                logger.info("Execution SUCCESS | stdout: %.200s", proc.stdout.strip())
                return ExecutionResult(
                    success=True,
                    stdout=proc.stdout,
                    stderr=proc.stderr,
                    script_path=script_path,
                    exit_code=proc.returncode,
                )
            else:
                error_msg = self._format_error(proc.stdout, proc.stderr)
                logger.warning(
                    "Execution FAILED (exit %d) | error: %.300s",
                    proc.returncode,
                    error_msg.replace("\n", " "),
                )
                return ExecutionResult(
                    success=False,
                    stdout=proc.stdout,
                    stderr=proc.stderr,
                    error_message=error_msg,
                    script_path=script_path,
                    exit_code=proc.returncode,
                )

        except subprocess.TimeoutExpired:
            error_msg = f"Script execution timed out after {self.timeout} seconds."
            logger.error(error_msg)
            return ExecutionResult(
                success=False,
                error_message=error_msg,
                script_path=script_path,
                exit_code=-1,
            )

        except Exception as exc:  # noqa: BLE001
            error_msg = f"Unexpected execution error: {exc}"
            logger.error(error_msg)
            return ExecutionResult(
                success=False,
                error_message=error_msg,
                script_path=script_path,
                exit_code=-1,
            )

    # ─── Private ─────────────────────────────────────────────────────────────

    def _write_temp_script(self, code: str, name: str) -> str:
        """Write code to a temp file and return its path."""
        tmp_dir = tempfile.gettempdir()
        script_path = os.path.join(tmp_dir, name)
        with open(script_path, "w", encoding="utf-8") as fh:
            fh.write(code)
        return script_path

    @staticmethod
    def _format_error(stdout: str, stderr: str) -> str:
        """Combine stdout + stderr into a single error message."""
        parts = []
        if stderr.strip():
            parts.append(stderr.strip())
        if stdout.strip():
            parts.append(f"[stdout]\n{stdout.strip()}")
        return "\n".join(parts) if parts else "Unknown error (no output captured)"
