# GemmaCore

> **Local-first cognitive agent with persistent identity and adaptive behavior.**

GemmaCore is a production-grade, local AI agent runtime. It runs entirely on your machine — no cloud APIs, no data leaving your environment. The agent thinks, plans, acts, reflects, and remembers across sessions, evolving its own reasoning style over time.

---

## Value Proposition

| What exists today | What GemmaCore adds |
|---|---|
| Chatbots that forget everything | Persistent layered memory across sessions |
| Agents that call random functions | Typed skill registry with permission gates |
| Black-box LLM wrappers | Full reasoning trace: every phase, every step |
| Static prompting | Adaptive personality that evolves from outcomes |
| Single-model lock-in | Swappable LLM via abstract interface |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        GemmaCore Runtime                        │
│                                                                 │
│  ┌─────────────┐    ┌──────────────────────────────────────┐   │
│  │   CLI / UI  │───▶│            AgentCore Loop             │   │
│  └─────────────┘    │                                      │   │
│                     │  perception() → update_state()       │   │
│  ┌─────────────┐    │  reasoning()  → planning()           │   │
│  │  LLM Layer  │◀──▶│  action()     → reflection()         │   │
│  │ (Gemma via  │    │  memory_update()                     │   │
│  │  Ollama)    │    └──────────────┬───────────────────────┘   │
│  └─────────────┘                  │                            │
│                        ┌──────────▼──────────┐                 │
│  ┌─────────────┐        │    Canonical State   │                │
│  │ Personality │◀──────▶│   (single source of  │                │
│  │   Engine    │        │      truth)          │                │
│  └─────────────┘        └──────────┬──────────┘                │
│                                    │                            │
│         ┌──────────────────────────┼───────────────┐           │
│         ▼                          ▼               ▼           │
│  ┌─────────────┐        ┌─────────────────┐  ┌──────────┐     │
│  │   Planner   │        │  Memory Layers  │  │  Skills  │     │
│  │  (Decision  │        │                 │  │ Registry │     │
│  │   Engine)   │        │ ┌─────────────┐ │  │          │     │
│  └─────────────┘        │ │ Short-Term  │ │  │ browser  │     │
│                         │ ├─────────────┤ │  │ academic │     │
│  ┌─────────────┐        │ │  Episodic   │ │  │ file_ops │     │
│  │Observability│        │ ├─────────────┤ │  │ memory   │     │
│  │ logger.py   │        │ │  Semantic   │ │  └──────────┘     │
│  │  trace.py   │        │ ├─────────────┤ │                   │
│  └─────────────┘        │ │ Long-Term   │ │                   │
│                         │ └─────────────┘ │                   │
│                         └─────────────────┘                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Example Execution Trace

```
[09:14:01] [INFO ] [agent_core] [GOAL] Set: AI Ethics AND Healthcare Systems
[09:14:03] [INFO ] [agent_core] 🔬 Initiating research scan: AI Ethics AND Healthcare Systems
[09:14:09] [INFO ] [agent_core] 📋 Outline: Introduction → Literature Critique → Methodology → Synthesis → Conclusion
[09:14:09] [INFO ] [agent_core] 📖 Chapter 1/5: Introduction

[09:14:09] [INFO ] [agent_core] [PERCEPTION] GOAL: AI Ethics AND Healthcare Systems | CHAPTER: Introduction | SUB_GOAL: Deconstructing Introduction
[09:14:14] [INFO ] [agent_core] [THOUGHT] RIGOR GAP: No empirical grounding for ethical frameworks in clinical AI deployment...
[09:14:14] [INFO ] [agent_core] [PLAN] Action=SEARCH Skill=academic Confidence=0.72
[09:14:15] [INFO ] [academic]   OpenAlex: 5 results for 'AI ethics clinical decision support healthcare'
[09:14:15] [INFO ] [agent_core] [ACTION] SEARCH → DOI: https://doi.org/10.1016/j.ijmedinf.2022...
[09:14:22] [INFO ] [agent_core] [RESULT] DOI: ... RIGOR SCORE: 0.92 | GAP SATISFACTION: Addresses...
[09:14:22] [INFO ] [agent_core] [REFLECTION] Memory updated.

[09:14:22] [INFO ] [agent_core] [PERCEPTION] GOAL: AI Ethics AND Healthcare Systems | CHAPTER: Introduction | ITER: 1
[09:14:28] [INFO ] [agent_core] [PLAN] Action=NAVIGATE Skill=browser Confidence=0.61
⏳ APPROVAL REQUIRED
══════════════════════════════════════════════════
  NAVIGATE: https://www.nature.com/articles/s41591-021-01614-0
══════════════════════════════════════════════════
  [A]pprove / [R]eject: A
[09:14:31] [INFO ] [browser]    🌐 Browser navigation: https://www.nature.com/...
[09:14:34] [INFO ] [agent_core] [ACTION] NAVIGATE → SOURCE: nature.com GRADE 0.87
[09:14:41] [INFO ] [agent_core] [RESULT] Memory updated.

✍️  Synthesizing Introduction...
💾  Saved: Chapter_1_Introduction.md
```

---

## Demo Scenario

**User input:** `"AI & Healthcare Systems"`

The agent:
1. **Perceives** its context — current chapter, memory, retrieved sources
2. **Reasons** — generates a plan using a personality-biased LLM prompt
3. **Plans** — parses the plan into ranked, typed `PlanOption` objects
4. **Acts** — dispatches to a registered skill (Academic API, Browser, or File)
5. **Reflects** — LLM synthesizes findings into structured EPR triples
6. **Remembers** — stores results in semantic + episodic memory
7. **Evolves** — personality traits update: `curiosity += 0.05` on success

After 3 iterations per chapter × 5 chapters, a complete thesis is assembled from peer-reviewed sources, with every decision logged and traceable.

---

## Comparison

| System | Local | Persistent Memory | Personality | Typed Skills | Full Trace |
|---|---|---|---|---|---|
| AutoGPT | ✗ | Partial | ✗ | ✗ | ✗ |
| LangChain Agents | Optional | Plugin | ✗ | Partial | ✗ |
| CrewAI | Optional | ✗ | ✗ | ✗ | ✗ |
| **GemmaCore** | **✅** | **✅ (4 layers)** | **✅ (mathematical)** | **✅ (registry)** | **✅ (JSONL)** |

---

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
