from playwright.sync_api import sync_playwright
import random
import time
import re
import json
import os
import urllib.parse
from config import HEADLESS_BROWSER
from ai.llm import ask_llm
from utils.url import normalize_url

class BrowserSkill:
    def __init__(self, agent):
        self.agent = agent
        # Tracks visited (normalized) URLs per search query to avoid re-clicking
        self._visited_by_query = {}
        self._playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self._start_browser()

    def _start_browser(self):
        """Initializes a high-stealth playwright session with deep fingerprint masking."""
        try:
            if self._playwright:
                try: self._playwright.stop()
                except: pass

            self._playwright = sync_playwright().start()
            self.browser = self._playwright.chromium.launch(
                headless=HEADLESS_BROWSER,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-infobars",
                    "--window-position=0,0",
                    "--ignore-certificate-errors",
                ]
            )
            
            self.context = self.browser.new_context(
                user_agent=self.random_user_agent(),
                viewport={"width": 1920, "height": 1080},
                device_scale_factor=1,
            )

            # 2026 Stealth: Deep Navigator & WebGL Overrides
            self.context.add_init_script("""
                // Mask Webdriver
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                
                // Restore missing languages and plugins (Major bot signals)
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });

                // Add Chrome Runtime Mock
                window.chrome = { runtime: {} };

                // WebGL Vendor Spoofing
                const getParameter = HTMLCanvasElement.prototype.getContext;
                HTMLCanvasElement.prototype.getContext = function(type) {
                    const context = getParameter.apply(this, arguments);
                    if (type === 'webgl' || type === 'experimental-webgl') {
                        const debugInfo = context.getExtension('WEBGL_debug_renderer_info');
                        if (debugInfo) {
                            const opt = context.getParameter;
                            context.getParameter = function(param) {
                                if (param === debugInfo.UNMASKED_VENDOR_WEBGL) return 'Intel Inc.';
                                if (param === debugInfo.UNMASKED_RENDERER_WEBGL) return 'Intel(R) Iris(TM) Graphics 6100';
                                return opt.apply(this, arguments);
                            };
                        }
                    }
                    return context;
                };
            """)

            self.page = self.context.new_page()

        except Exception as e:
            self.agent.ui.log(f"❌ Critical Browser Failure: {e}")
            self.close()
            raise e

    def human_delay(self, a=0.5, b=1.5):
        time.sleep(random.uniform(a, b))

    def human_type(self, selector, text):
        """Mimics human typing rhythm with natural pauses."""
        self.page.wait_for_selector(selector, state="visible", timeout=8000)
        self.page.focus(selector)
        for char in text:
            # Vary delay significantly per character
            self.page.keyboard.type(char, delay=random.randint(40, 160))
            # 10% chance of a long pause (mimics thinking or correction)
            if random.random() > 0.9:
                time.sleep(random.uniform(0.1, 0.4))
        self.human_delay(0.2, 0.5)

    def random_user_agent(self):
        agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ]
        return random.choice(agents)

    def random_scroll(self):
        """Natural scrolling to trigger lazy-loads and look human."""
        for _ in range(random.randint(2, 4)):
            scroll_amt = random.randint(300, 700)
            self.page.mouse.wheel(0, scroll_amt)
            self.human_delay(0.4, 0.9)

    def navigate(self, url):
        """Navigates to a URL with strict sanitation and delay logic."""
        url = url.strip().strip('`').strip('"').strip("'")
        url = re.sub(r'\.$', '', url)
        url = normalize_url(url)
        
        try:
            if self.page.is_closed(): self._start_browser()
            self.agent.ui.log(f"🚀 Navigating: {url}")
            
            response = self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            if not response or response.status >= 400:
                return f"ERROR: Status {response.status if response else 'No Response'} at {url}"

            # Post-navigation human behavior
            self.human_delay(1.5, 3.0)
            self.random_scroll()
            content = self._get_refined_content()
            return f"CURRENT_LOCATION: {url}\nPAGE_TITLE: {self.page.title()}\n--- PAGE CONTENT ---\n{content}"

        except Exception as e:
            return f"Error navigating to {url}: {str(e).splitlines()[0]}"

    def search(self, query, goal=None, raw: bool = False):
        """Semantic Search utilizing standard DDG for higher trust (HTML as fallback).

        If `raw` is True, the query is used verbatim (no additional canonicalization).
        """
        if goal is None: goal = query
        
        try:
            if self.page.is_closed(): self._start_browser()
            
            # Use the query exactly as provided by the plan (no internal transformation)
            transformed_query = query
            self.agent.ui.log(f"🌐 Searching: {transformed_query}")
            
            # Navigate to standard DDG for better reputation (not just the HTML gateway)
            self.page.goto("https://duckduckgo.com", wait_until="domcontentloaded", timeout=20000)
            
            search_input = "input[name='q']"
            self.human_type(search_input, transformed_query)
            self.page.keyboard.press("Enter")
            
            # Selector for the results
            result_selector = "a[data-testid='result-title-a']"
            try:
                self.page.wait_for_selector(result_selector, timeout=12000)
            except:
                # Fallback to HTML-only mode if the JS version fails or is blocked
                self.agent.ui.log("⚠️ JS Search Blocked. Falling back to HTML Gateway.")
                search_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(transformed_query)}"
                self.page.goto(search_url, wait_until="domcontentloaded")
                result_selector = ".result__title a.result__a"

            result_locators = self.page.locator(result_selector).all()
            found_links = []
            
            for i, res in enumerate(result_locators[:6]):
                try:
                    title = res.inner_text().strip()
                    raw_url = res.get_attribute("href")
                    if raw_url:
                        norm = normalize_url(raw_url)
                        found_links.append({"index": i, "title": title, "url": raw_url, "norm_url": norm})
                except: continue

            if not found_links: return "No search results found."

            # Selection logic with per-query visited filtering
            qkey = transformed_query
            visited = self._visited_by_query.get(qkey, set())

            # Filter out already-visited normalized URLs for this query
            available = [f for f in found_links if f.get("norm_url") not in visited]

            if not available:
                self.agent.ui.log(f"ℹ️ All top results already visited for query: {qkey}")
                return "No new links found for this query."

            # Ask LLM to pick among available links
            choice = ask_llm(f"GOAL: {goal}\nLINKS: {available}\nSelect index (0-{len(available)-1}). Output ONLY the integer.").strip()
            target_index = int(choice) if choice.isdigit() and int(choice) < len(available) else 0

            final_norm = available[target_index]["norm_url"]
            final_url = available[target_index]["url"]

            # Navigate and mark visited on success
            nav_result = self.navigate(final_url)
            if isinstance(nav_result, str) and nav_result.startswith("CURRENT_LOCATION:"):
                self._visited_by_query.setdefault(qkey, set()).add(final_norm)
            return nav_result

        except Exception as e:
            self.agent.ui.log(f"⚠️ Search Error: {e}")
            return "Search failed."

    def _get_refined_content(self):
        """Purges UI noise and extracts content with better fallback logic."""
        try:
            self.page.evaluate("""() => { 
                const noise = ['nav', 'footer', 'header', 'aside', 'script', 'style', '.ads', '#cookie-consent'];
                noise.forEach(s => document.querySelectorAll(s).forEach(el => el.remove())); 
            }""")
            
            for sel in ["article", "main", ".content", "body"]:
                elements = self.page.locator(sel).all()
                for el in elements:
                    text = el.inner_text().strip()
                    if len(text) > 300:
                        lines = [l.strip() for l in text.splitlines() if len(l.strip()) > 40]
                        return "\n".join(lines)[:8000]
            return "Low content detected."
        except:
            return "Content extraction failed."

    def close(self):
        try:
            if self.context: self.context.close()
            if self.browser: self.browser.close()
            if self._playwright: self._playwright.stop()
        except: pass