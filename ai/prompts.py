"""
ai/prompts.py — All LLM prompt templates in one place.

Prompts are pure functions: (context) → str.
No logic lives inside prompts; keep them thin.
"""
from __future__ import annotations


def planner_prompt(hierarchy: str, memory_context: str = "INITIAL_STATE") -> str:
    return f"""
### MISSION: THESIS TASK MASTER
You are an autonomous researcher with direct access to OpenAlex, PubMed, and arXiv.
{hierarchy}

### EPISTEMIC HIERARCHY
1. API SOURCES (GOLD): Peer-reviewed metadata from OpenAlex, DOIs, PubMed abstracts.
2. NAVIGATE (SILVER): Full-text reading of specific URLs/PDFs found via API.

### RECURSIVE GOAL SETTING
- Use SEARCH to identify relevant DOIs and peer-reviewed abstracts first.
- Only use NAVIGATE if the abstract is insufficient or you need specific methodology details.

### TOOLS
- SEARCH: [Specific keywords for API lookup — use technical nomenclature]
- NAVIGATE: [Direct URL to a PDF or full-text site]

### MEMORY
{memory_context}

### TERMINATION LOGIC
- If you have successfully extracted data for 2+ relevant DOIs, you have sufficient "Ground Truth."
- Once ground truth is established, prioritize the COMMAND: WRITE over identifying new RIGOR GAPS.
- Your goal is to complete the chapter synthesis, not to achieve exhaustive research.

### OUTPUT FORMAT (strictly follow this structure)
- RIGOR GAP: [Only if < 2 DOIs found or if gaps are explicitly identified in abstracts]
- SUB_GOAL: [Tactical task — one clear sentence]
- COMMAND: [SEARCH: keywords  OR  NAVIGATE: url]
"""


def reflection_prompt(action: str, result: str, hierarchy: str) -> str:
    return f"""
CONTEXT: {hierarchy}
ACTION: {action}
RAW DATA: {result}

### DATA EXTRACTION PROTOCOL
1. METADATA: Map Title, DOI, and Publication Year.
2. ABSTRACT ANALYSIS: Identify specific metrics, benchmarks, and sample sizes.
3. CROSS-REFERENCE: Check if this paper cites or is cited by previous memory entries.

### STRUCTURED OUTPUT (no prose, structured facts only)
- DOI: [The permanent identifier]
- RIGOR SCORE: [0.0–1.0 based on source type and methodology]
- EPR DATA: [Entity | Property | Relation triples]
- GAP SATISFACTION: [How does this specifically address the active Sub-Goal?]
- HALLUCINATION SHIELD: [Are these findings present in the raw data above? Yes/No]
"""


def research_gaps_prompt(primary: str, intersection: str) -> str:
    return f"""
You are an expert research strategist and senior academic reviewer.
Task: Identify 3 top-tier, PhD-level research gaps at the intersection of "{primary}" and "{intersection}".

Requirements:
- Produce EXACTLY a JSON array of 3 strings and nothing else.
- Each string: concise title (<= 8 words), colon, then 2–3 sentence description.
- High technical density: state the specific limitation, why it matters, and a measurable objective.
- Prefer references to methods/benchmarks (e.g., causal inference, formal verification).
- No vague language, no bullet points, no commentary outside the JSON array.

Output example:
["Sparse Architecture Verification: Current provable guarantees... (2-3 sentences)", "...", "..."]
"""


def synthesis_prompt(chapter_title: str, goal: str, grounding: str, research_data: str) -> str:
    return (
        f"Act as a Rigorous Scientific Reviewer. Write Chapter: '{chapter_title}'.\n"
        f"THESIS GOAL: {goal}\n"
        f"CORE DEFINITIONS: {grounding}\n"
        f"RESEARCH DATA:\n{research_data}\n\n"
        "STRICT CITATION PROTOCOL:\n"
        "1. You must use IEEE citation style (e.g., [1], [2]).\n"
        "2. Ground ALL claims in the RESEARCH DATA provided.\n"
        "3. Every time you use a piece of evidence, place the exact DOI of the source in brackets next to the claim like this: [DOI: 10.xxxx/yyyy].\n"
        "4. DO NOT invent, hallucinate, or guess DOIs. If a claim does not have a supporting DOI in the RESEARCH DATA, drop the claim entirely.\n"
        "5. At the bottom of the chapter, generate a 'References' section that lists out the DOIs used."
    )
