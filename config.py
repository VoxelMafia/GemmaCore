import os

MODEL = "gemma3:4b"

MAX_ITERATIONS = 3
HEADLESS_BROWSER = True

# Web search used when academic search returns no results: duckduckgo, parallel,
# or disabled. Explicit NAVIGATE actions still use Playwright.
WEB_SEARCH_PROVIDER = os.getenv("GEMMACORE_WEB_SEARCH_PROVIDER", "duckduckgo")

MEMORY_PATH = "./data/memory_db"
LOG_PATH = "./data/logs/agent.log"

REQUIRE_APPROVAL = True
