MODEL = "gemma3:4b"

MAX_ITERATIONS = 3
HEADLESS_BROWSER = True

MEMORY_PATH = "./data/memory_db"
LOG_PATH = "./data/logs/agent.log"

REQUIRE_APPROVAL = True

import os
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")
SEARCH_PROVIDER = os.environ.get("SEARCH_PROVIDER", "tavily")
