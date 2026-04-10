"""
skills/_browser_impl.py — Playwright browser implementation.

This is the internal implementation. Access it only through BrowserSkillWrapper.
Preserved from the original browser.py with minor cleanup.
"""
from __future__ import annotations
import random
import re
import time
import urllib.parse

from config.settings import settings
from observability.logger import get_logger

logger = get_logger("browser")


class BrowserSkill:
    def __init__(self, agent=None):
        self._agent = agent
        self._playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self._visited_by_query: dict = {}
        self._start_browser()

    def _start_browser(self) -> None:
        from playwright.sync_api import sync_playwright
        if self._playwright:
            self.stop()
        self._playwright = sync_playwright().start()
        self.browser = self._playwright.chromium.launch(
            headless=settings.agent.headless_browser,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--window-position=0,0",
            ],
        )
        self.context = self.browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
        )
        self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            window.chrome = { runtime: {} };
        """)
        self.page = self.context.new_page()

    def search(self, query: str, goal: str = "") -> str:
        if not self.page or self.page.is_closed():
            self._start_browser()
        self._emit(f"🌐 Browser search: {query}")
        try:
            self.page.goto("https://duckduckgo.com", wait_until="networkidle", timeout=15000)
            self.page.fill("input[name='q']", query)
            self.page.keyboard.press("Enter")
            result_selector = "a[data-testid='result-title-a']"
            try:
                self.page.wait_for_selector(result_selector, timeout=7000)
            except Exception:
                self._emit("⚠️ JS blocked. Using HTML gateway.")
                encoded = urllib.parse.quote(query)
                self.page.goto(f"https://html.duckduckgo.com/html/?q={encoded}")
                result_selector = ".result__title a.result__a"
                self.page.wait_for_selector(result_selector, timeout=5000)

            results = self.page.locator(result_selector).all()
            links = []
            for i, res in enumerate(results[:5]):
                links.append({
                    "index": i,
                    "title": res.inner_text(),
                    "url": res.get_attribute("href"),
                })

            if not links:
                return ""

            # LLM picks best link
            from llm.gemma_provider import GemmaProvider
            llm = GemmaProvider()
            choice = llm.complete(f"Goal: {goal or query}\nPick best index (integer only): {links}")
            idx = int(re.search(r"\d+", choice).group()) if re.search(r"\d+", choice) else 0
            idx = min(idx, len(links) - 1)
            return self.navigate(links[idx]["url"])

        except Exception as exc:
            logger.error(f"Browser search error for '{query}': {exc}")
            self._emit("⚠️ Search error — check logs.")
            return ""

    def navigate(self, url: str) -> str:
        try:
            from utils.url import normalize_url
            url = normalize_url(url)
            self.page.goto(url, wait_until="domcontentloaded", timeout=20000)
            time.sleep(random.uniform(1, 2))
            return self._get_content()
        except Exception as exc:
            logger.warning(f"Navigation error to {url}: {exc}")
            self._emit(f"⚠️ Navigation failed: {str(exc)[:120]}")
            return ""

    def _get_content(self) -> str:
        text = self.page.inner_text("body")
        clean = "\n".join(line.strip() for line in text.splitlines() if len(line.strip()) > 30)
        return clean[:7000]

    def stop(self) -> None:
        try:
            if self.browser:
                self.browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass

    def _emit(self, msg: str) -> None:
        logger.info(msg)
        if self._agent and hasattr(self._agent, "ui") and self._agent.ui:
            self._agent.ui.log(msg)
