"""
skills/registry.py — Central skill registry.

The agent only ever calls skills through this registry.
No arbitrary function calls. No hidden dispatch.
"""
from __future__ import annotations
from typing import Dict, Optional, TYPE_CHECKING

from skills.base_skill import BaseSkill
from observability.logger import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class SkillRegistry:
    """
    Holds all registered skills and dispatches execution.

    Usage:
        registry = SkillRegistry(agent)
        registry.register(BrowserSkill(agent))
        result = registry.run("browser", {"action": "search", "query": "AI"})
    """

    def __init__(self, agent=None):
        self._agent = agent
        self._skills: Dict[str, BaseSkill] = {}

    def register(self, skill: BaseSkill) -> None:
        """Register a skill instance. Overwrites if same name exists."""
        self._skills[skill.name] = skill
        logger.info(f"[REGISTRY] Registered skill: {skill.name} (perm={skill.permission_level})")

    def get(self, name: str) -> Optional[BaseSkill]:
        """Retrieve a skill by name. Returns None if not found."""
        return self._skills.get(name)

    def run(self, skill_name: str, inputs: dict) -> any:
        """
        Execute a named skill. Raises KeyError if skill not found.
        All callers should use this method — never call skill._run() directly.
        """
        skill = self._skills.get(skill_name)
        if not skill:
            raise KeyError(f"Skill '{skill_name}' not registered. "
                           f"Available: {list(self._skills.keys())}")
        return skill.execute(inputs)

    def list_skills(self) -> Dict[str, dict]:
        """Return a summary of all registered skills."""
        return {
            name: {
                "description": skill.description,
                "permission_level": skill.permission_level,
                "side_effects": skill.side_effects,
            }
            for name, skill in self._skills.items()
        }

    def load_defaults(self) -> None:
        """
        Load the standard skill set. Called by AgentCore.start().
        Importing here avoids circular imports at module level.
        """
        from skills.file_ops import FileOpsSkill
        from skills.memory_ops import MemoryOpsSkill

        self.register(FileOpsSkill(self._agent))
        self.register(MemoryOpsSkill(self._agent))

        # Browser and Academic are heavier; load them with try/except
        try:
            from skills.browser_skill import BrowserSkillWrapper
            self.register(BrowserSkillWrapper(self._agent))
        except Exception as exc:
            logger.warning(f"[REGISTRY] BrowserSkill not loaded: {exc}")

        try:
            from skills.academic_skill import AcademicSkillWrapper
            self.register(AcademicSkillWrapper(self._agent))
        except Exception as exc:
            logger.warning(f"[REGISTRY] AcademicSkill not loaded: {exc}")

    def __len__(self) -> int:
        return len(self._skills)

    def __repr__(self) -> str:
        names = list(self._skills.keys())
        return f"SkillRegistry({names})"
