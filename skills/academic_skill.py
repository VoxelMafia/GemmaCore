"""
skills/academic_skill.py — OpenAlex academic search wrapped in BaseSkill.
"""
from __future__ import annotations
import os
from typing import Any, Dict, List
import requests

from skills.base_skill import BaseSkill
from observability.logger import get_logger

logger = get_logger("academic")

class AcademicSkillWrapper(BaseSkill):

    @property
    def name(self) -> str:
        return "academic"

    @property
    def description(self) -> str:
        return ("Search peer-reviewed literature via the OpenAlex API. "
                "Returns structured paper metadata including title, DOI, abstract, and year.")

    @property
    def input_schema(self) -> Dict[str, str]:
        return {
            "query": "Search query string (plain keywords, no boolean operators).",
            "limit": "Max results to return (default: 5).",
        }

    @property
    def output_schema(self) -> Dict[str, str]:
        return {
            "output": "List of paper dicts: {title, doi, url, year, abstract, type}",
        }

    @property
    def permission_level(self) -> int:
        return 0  # free

    def __init__(self, agent=None):
        self._agent = agent
        self._headers = {
            "User-Agent": "GemmaCore/2.0 (mailto:your-email@example.com)",
            "Accept": "application/json",
        }
        self._api_key = os.getenv("OPENALEX_API_KEY")

    # ── BaseSkill ──────────────────────────────────────────────────────────────

    def _run(self, inputs: Dict[str, Any]) -> Any:
        # Check if we got the new dict format or the old string format
        if isinstance(inputs, dict):
            query = inputs.get("query", "")
            # Safety: ensuring query is a string before stripping
            query = str(query).strip()
            limit_val = inputs.get("limit", 5)
        else:
            query = str(inputs).strip()
            limit_val = 5

        # Safety check for integer conversion
        try:
            limit = int(limit_val)
        except (ValueError, TypeError):
            limit = 5

        if not query:
            return []
        clean_query = query.replace('"', '').replace("'", "").strip()
        return self._search(clean_query, limit)
    # ── Implementation ─────────────────────────────────────────────────────────

    def _search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        if self._agent and hasattr(self._agent, "ui") and self._agent.ui:
            self._agent.ui.log(f"🔬 API Search: {query}")

        url = "https://api.openalex.org/works"
        params: Dict[str, Any] = {"search": query, "per_page": limit}
        if self._api_key:
            params["api_key"] = self._api_key

        try:
            resp = requests.get(url, params=params, headers=self._headers, timeout=15)
            if resp.status_code != 200:
                logger.warning(f"OpenAlex responded {resp.status_code}: {resp.text[:200]}")
                return []

            results = []
            for work in resp.json().get("results", []):
                results.append({
                    "title":    work.get("display_name"),
                    "doi":      work.get("doi"),
                    "url":      work.get("doi") or work.get("ids", {}).get("mag"),
                    "year":     work.get("publication_year"),
                    "abstract": self._parse_abstract(work.get("abstract_inverted_index")),
                    "type":     "Academic/Peer-Reviewed",
                })
            logger.info(f"OpenAlex: {len(results)} results for '{query}'")
            return results

        except requests.Timeout:
            logger.error(f"OpenAlex timeout for '{query}'")
            return []
        except Exception as exc:
            logger.error(f"OpenAlex error: {exc}")
            return []

    @staticmethod
    def _parse_abstract(inverted_index: Any) -> str:
        """Reconstructs the abstract from OpenAlex's inverted index format."""
        if not inverted_index:
            return "No abstract available."
        
        # OpenAlex provides abstracts as { "word": [positions] }
        words: Dict[int, str] = {}
        for word, positions in inverted_index.items():
            for pos in positions:
                words[pos] = word
                
        # Sort by position to reconstruct the sentence
        return " ".join(words[i] for i in sorted(words))