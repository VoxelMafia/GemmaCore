from playwright.sync_api import sync_playwright
import random
import time
from config import HEADLESS_BROWSER

class BrowserSkill:
    def __init__(self, agent):
        self.agent = agent
        self._playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self._start_browser()

    def _start_browser(self):
        """Initializes a stealthy playwright session with anti-detection args."""
        try:
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
            # Create a context with a realistic mobile or desktop viewport
            self.context = self.browser.new_context(
                user_agent=self.random_user_agent(),
                viewport={"width": 1920, "height": 1080},
                device_scale_factor=1,
            )
            self.page = self.context.new_page()

            # Advanced Stealth: Override multiple navigator properties
            self.page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            """)
        except Exception as e:
            self.agent.ui.log(f"❌ Failed to start browser: {e}")
            self.close()
            raise e

    # ================================
    # HUMAN-LIKE BEHAVIOR
    # ================================

    def human_delay(self, a=0.5, b=1.5):
        time.sleep(random.uniform(a, b))

    def human_type(self, selector, text):
        """Types with varied delays to mimic human rhythm."""
        self.page.wait_for_selector(selector, timeout=5000)
        self.page.focus(selector)
        for char in text:
            self.page.type(selector, char, delay=random.randint(40, 120))
            if random.random() > 0.9: time.sleep(0.2) # Occasional pause

    def random_user_agent(self):
        agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ]
        return random.choice(agents)

    def random_scroll(self):
        """Scrolls naturally to trigger lazy-loading content."""
        for _ in range(random.randint(1, 3)):
            scroll_amt = random.randint(400, 800)
            self.page.mouse.wheel(0, scroll_amt)
            self.human_delay(0.3, 0.8)

    # ================================
    # CORE ACTIONS
    # ================================

    def search(self, query):
        """Performs a robust search with fallback selectors and error handling."""
        try:
            if self.page.is_closed():
                self._start_browser()

            self.agent.ui.log(f"🌐 Navigating to DuckDuckGo...")
            # Use 'domcontentloaded' for speed; 'networkidle' often hangs on trackers
            self.page.goto("https://duckduckgo.com", wait_until="domcontentloaded", timeout=20000)
            
            # SUPER FIX: Multiple selectors to handle DuckDuckGo layout variations
            search_input = "input[name='q'], input[type='text'], .search__input"
            
            try:
                self.page.wait_for_selector(search_input, timeout=7000)
            except Exception:
                # If we can't find the box, it might be a CAPTCHA or a splash page
                if "Checking your browser" in self.page.content():
                    return "Error: Blocked by Cloudflare/Bot-check. Try again later."
                return "Error: Search input not found on page."

            self.page.click(search_input)
            self.human_type(search_input, query)
            self.page.keyboard.press("Enter")

            # Wait for result links to appear
            result_selector = "a[data-testid='result-title-a'], .result__a"
            self.page.wait_for_selector(result_selector, timeout=10000)
            
            self.human_delay(1.0, 2.0)
            self.random_scroll()

            results = self.page.locator(result_selector).all()

            if results:
                # Pick from top 2 results to avoid ads/irrelevant clicks
                target_index = 0 if len(results) == 1 else random.randint(0, 1)
                selected_result = results[target_index]
                title = selected_result.inner_text()
                
                self.agent.ui.log(f"🖱️ Clicking: {title}")
                selected_result.click()
                
                # Use a combined wait for better reliability
                try:
                    self.page.wait_for_load_state("domcontentloaded", timeout=10000)
                except:
                    pass # Continue even if it doesn't 'fully' load, we might have enough text
                
                return self._get_refined_content()
            
            return "No search results found."

        except Exception as e:
            self.agent.ui.log(f"⚠️ Browser Error: {str(e)}")
            return f"Error during search: {str(e)}"

    def _get_refined_content(self):
        """Extracts high-value text while ignoring UI noise and ads."""
        try:
            # Remove junk elements before parsing
            self.page.evaluate("""
                () => {
                    const noise = ['nav', 'footer', 'header', 'aside', '.cookie-banner', '#ads', 'script', 'style', 'iframe'];
                    noise.forEach(s => document.querySelectorAll(s).forEach(el => el.remove()));
                }
            """)
            
            # Strategy: Find the largest block of text within relevant containers
            best_text = ""
            for selector in ["article", "main", "#content", ".post-content", "body"]:
                elements = self.page.locator(selector).all()
                for el in elements:
                    if el.is_visible():
                        txt = el.inner_text().strip()
                        if len(txt) > len(best_text):
                            best_text = txt
                if len(best_text) > 500: break

            # Clean and limit content to prevent token overflow
            lines = [l.strip() for l in best_text.splitlines() if len(l.strip()) > 40]
            final_text = "\n".join(lines)
            
            return final_text[:8000] if final_text else "Failed to extract meaningful text from page."
        except Exception:
            return "Failed to parse page content."

    def close(self):
        """Cleanly closes all browser resources."""
        try:
            if self.context: self.context.close()
            if self.browser: self.browser.close()
            if self._playwright: self._playwright.stop()
        except:
            pass