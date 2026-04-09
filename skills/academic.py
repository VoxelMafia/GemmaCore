import os
import requests
import re
from utils import logger as ulogger


class AcademicSkill:
    def __init__(self, agent):
        self.agent = agent
        # OpenAlex prefers an email to put you in the 'polite' fast-track pool
        self.headers = {
            "User-Agent": "ThesisAgent/1.0 (mailto:your-email@example.com)",
            "Accept": "application/json"
        }
        # Optional API key support via environment variable
        self.api_key = os.getenv("OPENALEX_API_KEY")

    def search(self, query, limit=5):
        """Unified search via OpenAlex (covers PubMed, CrossRef, etc.)"""
        self.agent.ui.log(f"🔬 API Search: {query}")
        url = "https://api.openalex.org/works"
        # Do not send an invalid 'sort' value; OpenAlex defaults to relevance
        params = {'search': query, 'per_page': limit}
        if self.api_key:
            params['api_key'] = self.api_key
        
        try:
            resp = requests.get(url, params=params, headers=self.headers, timeout=15)
            # Provide clear failure reason when API responds with non-200
            if resp.status_code != 200:
                reason = f"OpenAlex responded {resp.status_code}: {resp.text[:200]}"
                ulogger.log(reason, level="WARN", component="OpenAlex")
                self.agent.ui.log(f"⚠️ API responded {resp.status_code}. See logs for details.")
                return []

            data = resp.json()
            results = []
            for work in data.get('results', []):
                results.append({
                    "title": work.get('display_name'),
                    "doi": work.get('doi'),
                    "url": work.get('doi') or work.get('ids', {}).get('mag'),
                    "year": work.get('publication_year'),
                    # OpenAlex abstracts are 'inverted index' - simple join for LLM
                    "abstract": self._parse_abstract(work.get('abstract_inverted_index')),
                    "type": "Academic/Peer-Reviewed"
                })
            # Persist a short informative message to file log
            ulogger.log(f"OpenAlex: returned {len(results)} results for '{query}'", level="INFO", component="OpenAlex")
            return results
        except requests.Timeout as e:
            msg = f"OpenAlex timeout: {str(e)}"
            ulogger.log(msg, level="ERROR", component="OpenAlex")
            self.agent.ui.log("⚠️ API timeout — falling back to browser. See logs for details.")
            return []
        except Exception as e:
            msg = f"OpenAlex error: {str(e)}"
            ulogger.log(msg, level="ERROR", component="OpenAlex")
            self.agent.ui.log("⚠️ API error — falling back to browser. See logs for details.")
            return []

    def _parse_abstract(self, inverted_index):
        if not inverted_index: return "No abstract available."
        # Reconstruct abstract from OpenAlex's inverted index format
        words = {}
        for word, pos_list in inverted_index.items():
            for pos in pos_list: words[pos] = word
        return " ".join([words[i] for i in sorted(words.keys())])