"""
ai/prompts.py — Finalized Academic Suite.
Features: Bulletproof Anchoring, Reference Mapping, and Rigor Enforcement.
"""
from __future__ import annotations


def planner_prompt(hierarchy: str, memory_context: str = "INITIAL_STATE") -> str:
    """
    Super-version of the planner prompt with dynamic termination, 
    loop-breaking logic, and phase-aware mission parameters.
    """
    # Detect the current phase to prevent infinite search loops in the Conclusion
    is_conclusion = any(x in hierarchy for x in ["Conclusion", "Chapter 5", "Final"])

    # Define the Mission based on Chapter context
    if is_conclusion:
        mission_mode = """
### MISSION: FINAL SYNTHESIS (CONCLUSION MODE)
- You are in the FINAL PHASE. DO NOT perform new SEARCH actions.
- Your goal is to synthesize existing [REF_X] anchors from your MEMORY into a final cohesive argument.
- Prioritize COMMAND: WRITE immediately."""
        termination_rule = "- MANDATORY: Trigger COMMAND: WRITE now. You have all required data."
        command_constraint = "- COMMAND: [WRITE: conclude findings]"
    else:
        mission_mode = """
### MISSION: THESIS TASK MASTER (RESEARCH MODE)
- Identify high-rigor evidence using OpenAlex/Peer-reviewed databases.
- Track all evidence using unique [REF_X] anchors and verified DOIs."""
        termination_rule = "- If 3+ relevant [REF_X] anchors are identified, you HAVE 'ground truth.' STOP searching and transition to COMMAND: WRITE."
        command_constraint = "- COMMAND: [SEARCH: keywords | WRITE: chapter content]"

    return f"""
{mission_mode}

### CONTEXT HIERARCHY
{hierarchy}

### EPISTEMIC HIERARCHY
1. ANCHORED API DATA (GOLD): Results with [REF_X] anchors and verified DOIs.
2. SYNTHESIZED MEMORY: Facts linked to specific anchors.
3. UNVERIFIED: Any claim lacking an [REF_X] or DOI (Avoid these).

### RECURSIVE GOAL SETTING
- ALWAYS associate facts with their specific [REF_X] anchor.
- If a DOI is missing, mark the anchor as [UNVERIFIED] and do not use it for "Ground Truth."
- If the current results are irrelevant (e.g., mismatched domains), explicitly state this in the RIGOR GAP.

### MEMORY & ANCHORS
{memory_context}

### TERMINATION LOGIC
{termination_rule}
- Avoid the 'Anchor Trap': If you have searched for the same topic twice without new results, move to synthesis.

### OUTPUT FORMAT (Strict JSON-like Structure)
- RIGOR GAP: [Count of verified anchors vs. needed (e.g., 3/5). Identify specific missing technical data.]
- SUB_GOAL: [One tactical sentence for the current iteration.]
- {command_constraint}
"""


def reflection_prompt(action: str, result: str, hierarchy: str) -> str:
    return f"""
CONTEXT: {hierarchy}
ACTION: {action}
RAW DATA: {result}

### DATA EXTRACTION PROTOCOL
1. ANCHOR MAPPING: Match the [REF_X] tag to the DOI and Title.
2. EVIDENCE EXTRACTION: Identify specific metrics or claims supported by the abstract.
3. CITATION LINE: Carry forward the exact 'citation_line' for the final bibliography.

### STRUCTURED OUTPUT (no prose, structured facts only)
- ANCHOR: [REF_X]
- DOI: [The permanent identifier]
- CITATION_LINE: [The ready-to-use IEEE string]
- EPR DATA: [Entity | Property | Relation triples linked to this ANCHOR]
- GAP SATISFACTION: [How does this specifically address the active Sub-Goal?]
- HALLUCINATION SHIELD: [Does this DOI match the ANCHOR in the raw data? Yes/No]
"""


def research_gaps_prompt(primary: str, intersection: str) -> str:
    return f"""
You are an expert research strategist and senior academic reviewer.
Task: Identify 3 top-tier, PhD-level research gaps at the intersection of "{primary}" and "{intersection}".

Requirements:
- Produce EXACTLY a JSON array of 3 strings and nothing else.
- Each string: concise title (<= 8 words), colon, then 2–3 sentence description.
- High technical density: state the specific limitation, why it matters, and a measurable objective.
- No vague language, no bullet points, no commentary outside the JSON array.
"""


def synthesis_prompt(chapter_title: str, goal: str, grounding: str, research_data: str) -> str:
    return (
        f"Act as a Rigorous Scientific Reviewer. Write Chapter: '{chapter_title}'.\n"
        f"THESIS GOAL: {goal}\n"
        f"CORE DEFINITIONS: {grounding}\n"
        f"RESEARCH DATA (ANCHORED):\n{research_data}\n\n"
        "STRICT CITATION PROTOCOL:\n"
        "1. USE ANCHORS: While writing, use the [REF_X] anchors provided in the RESEARCH DATA.\n"
        "2. DO NOT WRITE DOIs: Never attempt to type out a DOI in the body text. Use the anchor instead (e.g., 'As shown in [REF_1]...').\n"
        "3. FINAL PASS: After writing the text, create a 'References' section.\n"
        "4. BIBLIOGRAPHY: In the References section, list the full 'citation_line' provided in the data for each anchor used.\n"
        "5. RIGOR: If a claim is not supported by a specific [REF_X] entry in the data, delete the claim entirely.\n"
        "6. FORMAT: Ensure the final output is in clean Markdown."
    )