from playwright.sync_api import sync_playwright
import random
import time
import re
import urllib.parse
from config import HEADLESS_BROWSER
from ai.llm import ask_llm
from utils.url import normalize_url
from utils import logger as ulogger

class BrowserSkill:
    def __init__(self, agent):
        self.agent = agent
        self._playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self._visited_by_query = {}
        # Initialize browser once at startup
        self._start_browser()

    def _start_browser(self):
        """Initializes a high-stealth playwright session."""
        if self._playwright:
            self.stop()
            
        self._playwright = sync_playwright().start()
        self.browser = self._playwright.chromium.launch(
            headless=HEADLESS_BROWSER,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--window-position=0,0",
            ]
        )
        
        # Create a fresh context with a real-world User Agent
        self.context = self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )

        # CRITICAL: This script wipes the 'bot' footprint before any page loads
        self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            window.chrome = { runtime: {} };
        """)
        
        self.page = self.context.new_page()

    def search(self, query, goal=None):
        """Semantic Search with automatic JS-Block recovery."""
        if not self.page or self.page.is_closed(): self._start_browser()
        
        self.agent.ui.log(f"🌐 Searching: {query}")
        
        try:
            # 1. Try standard DDG first (Better for agent reasoning)
            self.page.goto("https://duckduckgo.com", wait_until="networkidle", timeout=15000)
            self.page.fill("input[name='q']", query)
            self.page.keyboard.press("Enter")
            
            # Wait for results or detect block
            result_selector = "a[data-testid='result-title-a']"
            try:
                self.page.wait_for_selector(result_selector, timeout=7000)
            except:
                # 2. If blocked, fallback to HTML Gateway IMMEDIATELY
                self.agent.ui.log("⚠️ JS Blocked. Using HTML Gateway...")
                encoded = urllib.parse.quote(query)
                self.page.goto(f"https://html.duckduckgo.com/html/?q={encoded}")
                result_selector = ".result__title a.result__a"
                self.page.wait_for_selector(result_selector, timeout=5000)

            # Extract top 5 results
            results = self.page.locator(result_selector).all()
            links = []
            for i, res in enumerate(results[:5]):
                links.append({
                    "index": i, 
                    "title": res.inner_text(), 
                    "url": res.get_attribute("href")
                })
            
            if not links:
                ulogger.log(f"Browser search returned no links for '{query}'", level="INFO", component="Browser")
                self.agent.ui.log("⚠️ Browser search returned no results.")
                return ""

            # Use LLM to pick the most relevant academic link for the thesis
            choice = ask_llm(f"Goal: {goal or query}\nPick best index: {links}")
            target = int(re.search(r'\d+', choice).group()) if re.search(r'\d+', choice) else 0
            
            return self.navigate(links[target]["url"])

        except Exception as e:
            # Log detailed reason to persistent log and inform the UI concisely
            ulogger.log(f"Browser search exception for '{query}': {repr(e)}", level="ERROR", component="Browser")
            self.agent.ui.log("⚠️ Search error — check logs for details.")
            return ""

    def navigate(self, url):
        """Navigates with basic cleaning to look human."""
        try:
            url = normalize_url(url)
            self.page.goto(url, wait_until="domcontentloaded", timeout=20000)
            # Add a small delay to mimic reading and trigger lazy-loaders
            time.sleep(random.uniform(1, 2))
            return self._get_refined_content()
        except Exception as e:
            ulogger.log(f"Navigation error to {url}: {repr(e)}", level="WARN", component="Browser")
            self.agent.ui.log(f"⚠️ Navigation failed: {str(e)[:120]}")
            return ""

    def _get_refined_content(self):
        """Strips HTML noise for the LLM."""
        # Simple extraction of the main body text
        text = self.page.inner_text("body")
        # Basic cleanup: remove double newlines and trim
        clean_text = "\n".join([l.strip() for l in text.splitlines() if len(l.strip()) > 30])
        return clean_text[:7000]

    def stop(self):
        try:
            if self.browser: self.browser.close()
            if self._playwright: self._playwright.stop()
        except: pass