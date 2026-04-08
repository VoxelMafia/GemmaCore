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

## License
MIT — see [LICENSE](LICENSE)

## Acknowledgements
- Ollama — LLM backend
- ChromaDB — optional persistent memory
- Playwright — browser automation
