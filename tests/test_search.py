import asyncio
import json
import os
import runpy
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx

from config import MODEL
from core.loop import AgentLoop
from skills.browser import BrowserSkill
from skills.parallel_search import MCP_URL, PROTOCOL_VERSION, USER_AGENT


AsyncClient = httpx.AsyncClient
SOURCE = {"url": "https://example.edu/paper?year=2026&topic=climate",
          "title": "Climate evidence", "excerpts": ["Observed warming evidence."]}


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.agent = SimpleNamespace(running=True, ui=Mock(), memory=Mock(),
                                     approval=Mock(), metadata={})
        self.requests = []

    def response(self, request, tool_result=None):
        self.requests.append(request)
        p = json.loads(request.content)
        if p["method"] == "initialize":
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": p["id"],
                                  "result": {"protocolVersion": PROTOCOL_VERSION}},
                                  headers={"mcp-session-id": "transport-session"})
        if p["method"] == "notifications/initialized":
            return httpx.Response(202)
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": p["id"],
                              "result": tool_result or {"structuredContent": {"results": [SOURCE]}}})

    def transport(self, handler=None):
        handler = handler or self.response
        return patch("skills.parallel_search.httpx.AsyncClient",
                     side_effect=lambda **kw: AsyncClient(transport=httpx.MockTransport(handler), **kw))

    def skill(self, provider="parallel"):
        return BrowserSkill(self.agent, search_provider=provider)

    def test_anonymous_request_contract_and_repeated_session(self):
        with patch.dict(os.environ, {"PARALLEL_API_KEY": "unused-key"}), self.transport():
            skill = self.skill()
            first = skill.search("climate evidence", goal="Find recent climate research")
            second = skill.search("warming observations")
        self.assertIn("Observed warming evidence.", first)
        self.assertIn(SOURCE["url"], second)
        self.assertIsNone(skill.page)
        calls = []
        for r in self.requests:
            self.assertEqual(str(r.url), MCP_URL)
            self.assertEqual(r.headers["user-agent"], USER_AGENT)
            self.assertNotIn("authorization", r.headers)
            self.assertNotIn("x-api-key", r.headers)
            p = json.loads(r.content)
            if p["method"] != "initialize":
                self.assertEqual(r.headers["mcp-session-id"], "transport-session")
                self.assertEqual(r.headers["mcp-protocol-version"], PROTOCOL_VERSION)
            if p["method"] == "tools/call":
                self.assertEqual(p["params"]["name"], "web_search")
                calls.append(p["params"]["arguments"])
        self.assertEqual(calls[0]["objective"], "Find recent climate research")
        self.assertEqual(calls[0]["search_queries"], ["climate evidence"])
        self.assertEqual(calls[0]["model_name"], MODEL)
        self.assertEqual(calls[0]["session_id"], calls[1]["session_id"])

    def test_json_text_content(self):
        result = {"content": [{"type": "text", "text": json.dumps({"results": [SOURCE]})}]}
        with self.transport(lambda r: self.response(r, result)):
            self.assertIn(SOURCE["url"], self.skill().search("climate"))

    def test_sse_notifications_and_reply(self):
        def handler(r):
            if json.loads(r.content)["method"] != "tools/call":
                return self.response(r)
            self.requests.append(r)
            msg = {"jsonrpc": "2.0", "id": 2,
                   "result": {"structuredContent": {"results": [SOURCE]}}}
            stream = ': keepalive\n\ndata: {"jsonrpc":"2.0","method":"notice"}\n\n'
            stream += "event: message\ndata: " + json.dumps(msg) + "\n\n"
            return httpx.Response(200, text=stream, headers={"content-type": "text/event-stream"})
        with self.transport(handler):
            self.assertIn(SOURCE["url"], self.skill().search("climate"))

    def test_errors_do_not_fall_back_to_browser(self):
        variants = [
            {"isError": True, "content": [{"type": "text", "text": "Quota exceeded"}]},
            {"structuredContent": {"results": "bad"}},
            {"content": [{"type": "text", "text": "invalid JSON"}]},
        ]
        for result in variants:
            with self.subTest(result=result), self.transport(lambda r: self.response(r, result)), \
                    patch.object(BrowserSkill, "_start_browser") as browser:
                self.assertEqual(self.skill().search("climate"), "")
                browser.assert_not_called()

    def test_http_timeout_and_protocol_errors(self):
        def handler(r):
            raise httpx.ReadTimeout("timed out", request=r)
        def protocol_error(r):
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1,
                                            "error": {"code": -32602, "message": "bad params"}})
        for h in [handler, protocol_error, lambda r: httpx.Response(429, text="Rate limit"),
                  lambda r: httpx.Response(302, headers={"location": "https://other.example/mcp"}),
                  lambda r: httpx.Response(200, json={"jsonrpc": "2.0", "id": 99, "result": {}})]:
            with self.subTest(handler=h), self.transport(h):
                self.assertEqual(self.skill().search("climate"), "")

    def test_empty_results_and_invalid_urls(self):
        data = {"structuredContent": {"results": [dict(SOURCE, url="javascript:bad()"), SOURCE]}}
        with self.transport(lambda r: self.response(r, data)):
            text = self.skill().search("climate")
            self.assertNotIn("javascript:", text)
            self.assertIn(SOURCE["url"], text)
        with self.transport(lambda r: self.response(r, {"structuredContent": {"results": []}})):
            self.assertEqual(self.skill().search("climate"), "")

    def test_stopped_disabled_empty_and_unknown_do_not_request(self):
        with self.transport() as client:
            self.assertEqual(self.skill("disabled").search("climate"), "")
            self.assertEqual(self.skill("unknown").search("climate"), "")
            self.assertEqual(self.skill().search(" "), "")
            self.agent.running = False
            self.assertEqual(self.skill().search("climate"), "")
            client.assert_not_called()

    def test_stop_cancels_inflight_request(self):
        closed = []
        async def handler(r):
            self.agent.running = False
            try:
                await asyncio.Event().wait()
            finally:
                closed.append(True)
        with self.transport(handler):
            self.assertEqual(self.skill().search("climate"), "")
        self.assertEqual(closed, [True])

    def test_default_config_and_environment_override(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(runpy.run_path("config.py")["WEB_SEARCH_PROVIDER"], "duckduckgo")
        with patch.dict(os.environ, {"GEMMACORE_WEB_SEARCH_PROVIDER": "parallel"}):
            self.assertEqual(runpy.run_path("config.py")["WEB_SEARCH_PROVIDER"], "parallel")
        with patch("skills.browser.WEB_SEARCH_PROVIDER", "parallel"):
            self.assertEqual(BrowserSkill(self.agent).search_provider, "parallel")
            self.assertEqual(self.skill("duckduckgo").search_provider, "duckduckgo")
            self.assertEqual(self.skill("disabled").search_provider, "disabled")

    def test_default_duckduckgo_dispatch(self):
        skill = self.skill("duckduckgo")
        page = Mock()
        page.is_closed.return_value = False
        link = Mock()
        link.inner_text.return_value = "Paper"
        link.get_attribute.return_value = SOURCE["url"]
        page.locator.return_value.all.return_value = [link]
        skill.page = page
        with patch("skills.browser.ask_llm", return_value="0"), \
                patch.object(skill, "navigate", return_value="Browser content") as navigate, \
                self.transport() as client:
            self.assertEqual(skill.search("climate"), "Browser content")
        page.goto.assert_called_once_with("https://duckduckgo.com", wait_until="networkidle", timeout=15000)
        navigate.assert_called_once_with(SOURCE["url"])
        client.assert_not_called()

    def test_explicit_navigation_starts_browser_lazily(self):
        skill = self.skill()
        def start():
            skill.page = Mock()
        with patch.object(skill, "_start_browser", side_effect=start) as browser, \
                patch("skills.browser.time.sleep"), \
                patch.object(skill, "_get_refined_content", return_value="Page content"):
            self.assertEqual(skill.navigate(SOURCE["url"]), "Page content")
        browser.assert_called_once()
        skill.page.goto.assert_called_once()

    def run_loop(self, *, allowed=True, academic_results=None):
        loop = AgentLoop(self.agent)
        loop.set_goal("Climate evidence")
        self.agent.loop = loop
        def approval(plan):
            if not allowed:
                self.agent.running = False
            return allowed
        self.agent.approval.request.side_effect = approval
        prompts = []
        def model(prompt):
            prompts.append(prompt)
            return ['["Introduction"]', 'SEARCH: climate evidence', 'Grounded reflection'][len(prompts) - 1]
        with patch("core.loop.ask_llm", side_effect=model), \
                patch("core.loop.MAX_ITERATIONS", 1), patch("core.loop.time.sleep"), \
                patch("skills.browser.WEB_SEARCH_PROVIDER", "parallel"), \
                patch("skills.academic.AcademicSkill.search", return_value=academic_results or []), \
                patch("skills.filesystem.FilesystemSkill"), patch.object(loop, "_finalize_chapter"):
            loop.run()
        return prompts

    def test_actual_loop_dispatches_and_consumes_source_evidence(self):
        with self.transport():
            prompts = self.run_loop()
        self.assertEqual(len(self.requests), 3)
        self.assertIn(SOURCE["url"], prompts[2])
        self.assertIn("Observed warming evidence.", prompts[2])
        self.agent.memory.store.assert_any_call("CHAPTER_1_DATA: Grounded reflection")
        self.agent.approval.request.assert_called_once_with("SEARCH: climate evidence")

    def test_denied_approval_prevents_actual_loop_search(self):
        with self.transport() as client:
            self.run_loop(allowed=False)
        client.assert_not_called()
        self.agent.memory.store.assert_not_called()

    def test_academic_results_keep_precedence(self):
        with self.transport() as client:
            prompts = self.run_loop(academic_results=[{"url": SOURCE["url"], "abstract": "Academic evidence"}])
        client.assert_not_called()
        self.assertIn("Academic evidence", prompts[2])


if __name__ == "__main__":
    unittest.main()
