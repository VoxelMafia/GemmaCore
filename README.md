# GemmaCore

**Local-first cognitive agent with persistent identity and adaptive behavior.**

GemmaCore is a production-grade, local AI agent runtime. It runs entirely on your machine — no cloud APIs, no data leaving your environment. The agent thinks, plans, acts, reflects, and remembers across sessions, evolving its own reasoning style over time.


## Quickstart

**Prerequisites**
- Python 3.9+
- [Ollama](https://ollama.com) running locally with Gemma: `ollama pull gemma3:4b`
- Playwright (for browser automation)

```bash
git clone https://github.com/VoxelMafia/GemmaCore.git
cd GemmaCore
pip install -r requirements.txt
python -m playwright install chromium

# CLI mode
python main.py --goal "AI & Climate Science"

# Desktop UI
python main.py --ui

# Unattended (auto-approve all actions)
python main.py --goal "Quantum Computing & Drug Discovery" --auto-approve

# With reasoning trace printed at end
python main.py --goal "AI Ethics & Healthcare" --trace
```

---

## Configuration

All settings live in `config/settings.py` and can be overridden via environment variables:

```bash
export GEMMACORE_MODEL="gemma3:4b"        # Model to use
export GEMMACORE_APPROVAL="false"          # Disable approval gates
export GEMMACORE_MAX_ITER="5"              # Iterations per chapter
export GEMMACORE_LTM="true"               # Enable persistent long-term memory
```
Note for Windows Users: 
If your .env settings are being ignored, ensure your terminal is loading them. 
In VS Code, enable python.terminal.useEnvFile in settings, or manually set variables in CMD using 
set GEMMACORE_LOG_PATH=./data/logs/agent.log.
---

## Project Layout

```
/core
  agent.py          ← OperatorAgent façade (UI compatibility)
  agent_core.py     ← Deterministic 7-phase cognitive loop
  approval.py       ← Human-in-the-loop gate
  personality.py    ← Mathematical personality model (trait evolution)
  planner.py        ← Decision engine (ranked PlanOptions)
  state.py          ← Canonical AgentState (single source of truth)

/memory
  short_term.py     ← FIFO working memory buffer
  episodic.py       ← Timestamped action log (JSONL persistence)
  semantic.py       ← ChromaDB embedding retrieval
  long_term.py      ← Persistent key-value store (JSON on disk)

/skills
  registry.py       ← Central skill registry (no arbitrary dispatch)
  base_skill.py     ← Abstract base with schema + permission levels
  file_ops.py       ← Sandboxed workspace file operations
  memory_ops.py     ← Explicit memory read/write skill
  browser_skill.py  ← Playwright web navigation (wrapper)
  academic_skill.py ← OpenAlex API search (wrapper)

/llm
  interface.py      ← Abstract LLMInterface (swap any model)
  gemma_provider.py ← Ollama/Gemma implementation (streaming + retry)

/observability
  logger.py         ← Structured phase-tagged logger
  trace.py          ← JSONL trace recorder (per-session)

/config
  settings.py       ← Typed config with env var overrides

/ai
  prompts.py        ← All LLM prompt templates
  llm.py            ← Legacy shim (backwards compat)

/tests
  test_memory.py    ← Memory layer unit tests
  test_planner.py   ← Planner + personality unit tests
  test_skills.py    ← Skill execution unit tests

main.py             ← CLI entry point
```

---

## Running Tests

```bash
python -m pytest tests/ -v
python -m pytest tests/ --cov=. --cov-report=term-missing
```

---

## License

MIT — see LICENSE

## Acknowledgements

- [Ollama](https://ollama.com) — Local LLM backend
- [ChromaDB](https://www.trychroma.com) — Vector memory
- [Playwright](https://playwright.dev) — Browser automation
- [OpenAlex](https://openalex.org) — Open academic graph API
