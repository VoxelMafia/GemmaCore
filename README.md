# GemmaCore

A lightweight autonomous research agent framework for iterative technical research, synthesis, and report generation. GemmaCore combines an LLM interface, modular skills (browser and filesystem), and a desktop UI to run semi-autonomous research tasks with human-in-the-loop approvals.

Key principles
- Modular: skills and memory backends are pluggable.
- Safe-by-design: approval prompts gate sensitive actions.
- Portable: runs locally with optional persistent memory.

## Quickstart

Prerequisites
- Python 3.9 or newer
- Ollama (local or remote LLM service) — optional but recommended
- Playwright (for browser automation)

Python packages (installed from `requirements.txt`)
- ollama
- chromadb
- playwright
- customtkinter
- httpx
- psutil

Install
```bash
git clone https://github.com/yourusername/GemmaCore.git
cd GemmaCore
python -m pip install -r requirements.txt
python -m playwright install
```

Notes
- If your Python distribution lacks Tkinter, install the OS package that provides Tk/Tkinter.
- Ensure Ollama is running and the model configured in `config.py` is available if you plan to use local LLM inference.

## Running
Start the UI:
```bash
python main.py
```
Use the UI to submit a research goal and follow the approval prompts shown during execution.

### Optional Parallel web search

When OpenAlex returns no academic results, GemmaCore uses DuckDuckGo browser
search by default. To use [Parallel Search MCP](https://docs.parallel.ai/integrations/mcp/search-mcp)
instead, set `GEMMACORE_WEB_SEARCH_PROVIDER=parallel` before starting the UI:

```bash
GEMMACORE_WEB_SEARCH_PROVIDER=parallel python main.py
```

Parallel provides free web search powered by Fast mode, with no account or API
key. Search excerpts and source URLs go directly to the research reflection step;
Chromium starts only for DuckDuckGo search or an explicit `NAVIGATE` action.
The existing plan approval still applies. Queries and research sub-goals are sent
to `https://search.parallel.ai/mcp`. Free service usage limits apply, and failures
are reported in the UI and logs without switching to another provider. Requests
time out after 30 seconds overall; stopping the agent cancels an in-flight search.

Set the variable to `duckduckgo` to select the existing browser search, or
`disabled` to disable web search fallback. This does not disable OpenAlex or
explicit navigation. You can also set `WEB_SEARCH_PROVIDER` in `config.py`.

## Project layout
- `main.py` — application entrypoint
- `config.py` — runtime configuration and paths
- `ai/` — LLM wrapper and prompts
- `core/` — agent loop, memory, approval system
- `skills/` — browser and filesystem automation modules
- `ui/` — desktop UI and components
- `utils/` — helper utilities and logging
- `workspace/` — generated reports and outputs
- `data/` — logs and persistent memory storage

## Development
- Lint and static-check with your preferred tools (e.g., flake8, mypy).
- Run Playwright tests or scripts after `python -m playwright install`.
- Run search provider tests with `python -m unittest discover -s tests -v`.

## License
MIT — see [LICENSE](LICENSE)

## Acknowledgements
- Ollama — LLM backend
- ChromaDB — optional persistent memory
- Playwright — browser automation
