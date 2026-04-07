# GemmaCore

GemmaCore is an autonomous research agent framework that leverages LLMs and browser/file system skills to automate technical research, synthesis, and report generation. It features a modular architecture, persistent or ephemeral memory, and a Tkinter-based UI for interactive operation and approval workflows.

---

## Overview

GemmaCore is designed to:
- Automate technical research using LLMs (Large Language Models)
- Synthesize findings into structured Markdown reports
- Interact with the web and local files via modular skills
- Support approval workflows for safe autonomous operation
- Provide a user-friendly desktop UI (Tkinter)

**Key Components:**
- **Agent Loop:** Iterative research and synthesis, capped by a final report
- **Memory:** Pluggable persistent (ChromaDB) or ephemeral session memory
- **Skills:** Modular browser and filesystem automation
- **UI:** Tkinter app for goal input, logs, and approval prompts

---

## Setup

### Prerequisites
- Python 3.9+
- [Ollama](https://ollama.com/) (for LLM backend)
- [ChromaDB](https://www.trychroma.com/) (for persistent memory)
- [Playwright](https://playwright.dev/python/) (for browser automation)
- Tkinter (usually included with Python)

### Installation
1. **Clone the repository:**
   ```sh
   git clone https://github.com/yourusername/GemmaCore.git
   cd GemmaCore
   ```
2. **Install dependencies:**
   ```sh
   pip install -r requirements.txt
   playwright install
   ```
   *(This will install all required Python packages. The `playwright install` command is still needed to set up browser drivers.)*

3. **Configure Ollama:**
   - Ensure Ollama is running and the model in `config.py` (default: `gemma3:4b`) is available.

4. **(Optional) Configure ChromaDB:**
   - Persistent memory is enabled by default. Adjust `MEMORY_PATH` in `config.py` as needed.

---

## Running Locally

1. **Start the UI:**
   ```sh
   python main.py
   ```
2. **Enter a research goal in the UI and click START.**
3. **Monitor logs and approve/deny actions as prompted.**

---

## Project Structure

- `main.py` — Entry point, launches the Tkinter UI
- `config.py` — Configuration (model, paths, settings)
- `ai/` — LLM interface and prompt templates
- `core/` — Agent logic, memory, approval, and loop
- `skills/` — Modular skills (browser, filesystem)
- `ui/` — Tkinter UI and components
- `utils/` — Helpers and logging
- `workspace/` — Output sandbox for generated reports
- `data/` — Logs and persistent memory DB

---

## Features

- Autonomous research agent loop with approval workflow
- Modular skills for browser and filesystem automation
- LLM-powered synthesis and Markdown report generation
- Persistent or ephemeral memory (ChromaDB)
- Tkinter desktop UI for interactive operation

---

## License

[MIT License](LICENSE)

---

## Acknowledgements
- [Ollama](https://ollama.com/)
- [ChromaDB](https://www.trychroma.com/)
- [Playwright](https://playwright.dev/python/)
