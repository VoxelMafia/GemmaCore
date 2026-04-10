"""
skills/browser_skill.py — Browser skill wrapped in the BaseSkill interface.

Delegates to the original BrowserSkill implementation (Playwright-based).
Permission level 1: browser actions are logged but don't block execution.
"""
from __future__ import annotations
from typing import Any, Dict, List

from skills.base_skill import BaseSkill


class BrowserSkillWrapper(BaseSkill):

    @property
    def name(self) -> str:
        return "browser"

    @property
    def description(self) -> str:
        return "Navigate URLs and perform web searches using a headless Chromium browser."

    @property
    def input_schema(self) -> Dict[str, str]:
        return {
            "action": "One of: search | navigate | stop",
            "query": "(search) Search query string.",
            "url": "(navigate) Full URL to visit.",
            "goal": "(search) Optional goal context for URL ranking.",
        }

    @property
    def output_schema(self) -> Dict[str, str]:
        return {"output": "Extracted page text content (up to 7000 chars)."}

    @property
    def side_effects(self) -> List[str]:
        return ["Opens browser sessions", "Makes HTTP requests to external URLs"]

    @property
    def permission_level(self) -> int:
        return 1  # notify

    def __init__(self, agent=None):
        self._agent = agent
        self._impl = None  # Lazy-loaded to avoid Playwright startup cost

    def _get_impl(self):
        if self._impl is None:
            from skills._browser_impl import BrowserSkill
            self._impl = BrowserSkill(self._agent)
        return self._impl

    def _run(self, inputs: Dict[str, Any]) -> Any:
        # 1. Properly extract the query from the dictionary
        if isinstance(inputs, dict):
            query = inputs.get("query", "")
            goal = inputs.get("goal", "")
            action = inputs.get("action", "search")
            url = inputs.get("url", "")
        else:
            query = str(inputs)
            goal = ""
            action = "search"
            url = ""

        # 2. Call the CORRECT implementation methods
        impl = self._get_impl()
        
        if action == "navigate" and url:
            return impl.navigate(url)
        
        # Fallback to search
        return impl.search(str(query), goal=str(goal))

    def stop(self):
        if self._impl:
            self._impl.stop()
