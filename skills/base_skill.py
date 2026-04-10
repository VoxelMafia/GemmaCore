"""
skills/base_skill.py — Base class for all agent skills.

Every skill must declare:
  - name & description
  - input/output schema
  - side_effects (human-readable list)
  - permission_level (0=free, 1=notify, 2=require_approval)

The agent MUST NOT call arbitrary functions — only registered skills.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    pass


class SkillResult:
    """Structured return type from skill execution."""

    def __init__(self, success: bool, output: Any, error: Optional[str] = None, metadata: Optional[dict] = None):
        self.success = success
        self.output = output
        self.error = error
        self.metadata = metadata or {}

    def __str__(self) -> str:
        if self.success:
            return str(self.output)
        return f"[ERROR] {self.error}"

    def __bool__(self) -> bool:
        return self.success


class BaseSkill(ABC):
    """
    Abstract base for all GemmaCore skills.

    Subclasses implement `_run(inputs)` and declare their schema.
    The public `execute(inputs)` method handles validation and logging.
    """

    # ── Skill Metadata (must be overridden) ───────────────────────────────────

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for the skill (used in SkillRegistry)."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what this skill does."""
        ...

    @property
    def input_schema(self) -> Dict[str, str]:
        """Describe expected inputs: {field_name: description}."""
        return {}

    @property
    def output_schema(self) -> Dict[str, str]:
        """Describe outputs: {field_name: description}."""
        return {"output": "The result of the skill execution."}

    @property
    def side_effects(self) -> List[str]:
        """Human-readable list of side effects (e.g., 'writes to disk')."""
        return []

    @property
    def permission_level(self) -> int:
        """
        0 = free (no approval needed)
        1 = notify (log but don't block)
        2 = require_approval (block until user approves)
        """
        return 0

    # ── Execution ─────────────────────────────────────────────────────────────

    def execute(self, inputs: Dict[str, Any]) -> Any:
        """
        Public entry point. Validates inputs then delegates to _run().
        Returns the raw output value (not SkillResult) for backwards compat.
        """
        from observability.logger import get_logger
        logger = get_logger(self.name)

        missing = [k for k in self.input_schema if k not in inputs]
        if missing:
            logger.warning(f"[{self.name}] Missing inputs: {missing}")

        try:
            result = self._run(inputs)
            logger.debug(f"[{self.name}] executed OK")
            return result
        except Exception as exc:
            logger.error(f"[{self.name}] execution failed: {exc}")
            return f"[SKILL ERROR] {self.name}: {exc}"

    @abstractmethod
    def _run(self, inputs: Dict[str, Any]) -> Any:
        """
        Implement the actual skill logic here.
        Receive validated inputs dict, return any output value.
        """
        ...

    def __repr__(self) -> str:
        return f"Skill({self.name}, perm={self.permission_level})"
