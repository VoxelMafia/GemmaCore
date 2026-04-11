"""
ai/prompts.py — Refined Academic Suite (v2.0)
Features: Technical Expansion, Cross-Chapter Persistence, and Physics-Grounded Rigor.
"""
from __future__ import annotations

def planner_prompt(hierarchy: str, memory_context: str = "INITIAL_STATE") -> str:
    """
    Enhanced planner with Technical Term Expansion and State Persistence.
    Prevents "Zero-Result" loops by forcing specific technical jargon.
    """
    is_conclusion = any(x in hierarchy for x in ["Conclusion", "Chapter 5", "Final"])

    if is_conclusion:
        mission_mode = """
CRITICAL: 
If the RAW DATA from the academic skill is empty, do not generate placeholders or "hallucinated" citations. Instead, you must issue a COMMAND: SEARCH with a broader technical scope or decomposed keywords.
If the API returns a 500 error or 0 results, you MUST simplify the search terms or pivot to a for your research area specific sub-domain with simplified search terms.
### MISSION: FINAL SYNTHESIS
- MANDATORY: Access all previously verified [REF_X] anchors from MEMORY.
- Do not search. Synthesize the trajectory of the entire thesis.
- Address any 'Unverified' gaps from previous chapters as 'Areas for Future Rigor'."""
        termination_rule = "- ACTION: COMMAND: WRITE. Do not exit until all MEMORY anchors are cited."
        command_constraint = "- COMMAND: [WRITE: final synthesis]"
    else:
        # Update this section in planner_prompt
        mission_mode = """
        - YOUR GOAL: Accumulate minimum 15 verified DOIs before the first WRITE command.
        - SEARCH PROTOCOL: Do not repeat queries. If 'PINNs' is searched, pivot to 'Neural Operators' then 'Fourier Neural Operators'.
        - PIVOT LOGIC: If results < 5, decompose keywords into (Components) + (Methods) + (Variables).
        - Once a source is verified and assigned an [REF_X], you MUST issue a COMMAND: [memory: store] for the anchor and DOI.
        - After storing, you MUST consider the RAW DATA 'consumed' and do not include it in the next plan.
        - Only keep the ANCHOR LIST in your active memory context.
        """
        
        termination_rule = "- If MEMORY contains < 15 [REF_X] anchors with verified DOIs, continue COMMAND: SEARCH."
        command_constraint = "- COMMAND: [SEARCH: <technical_keywords> | WRITE: chapter]"

    return f"""
{mission_mode}

### CONTEXT HIERARCHY
{hierarchy}

### SEARCH EXPANSION PROTOCOL
- DO NOT use broad terms. Use domain-specific jargon (e.g., 'Radiative Transfer Neural Network' instead of 'Climate AI').
- Reference specific model generations like 'CMIP6' or 'ERA5' for higher hits.

### MEMORY & PERSISTENT ANCHORS
{memory_context}

### TERMINATION LOGIC
{termination_rule}

### OUTPUT FORMAT (JSON)
- RIGOR GAP: [Anchors found/needed. List specific technical missingness.]
- SUB_GOAL: [Next tactical step.]
- {command_constraint}
"""

def reflection_prompt(action: str, result: str, hierarchy: str) -> str:
    """
    UNIVERSAL HARVESTER V3.0
    Optimized for high-volume (30+) citation gathering and recursive expansion.
    """
    return f"""
CONTEXT: {hierarchy}
ACTION: {action}
RAW DATA: {result}

### DATA EXTRACTION PROTOCOL (STRICT)
1. ANCHOR MAPPING: Assign consecutive [REF_X] anchors. Target: [REF_1] through [REF_15].
2. PHYSICS-INFORMED CHECK: Look for 'Conservation', 'Mass-Balance', 'Stochastics', or 'PINNs'. 
3. CROSS-CITATION SNOWBALLING: Identify the "Primary Referenced Work" within each snippet to seed the next search.
4. HALLUCINATION SHIELD: Compare the 'RAW DATA' snippet text against the DOI. If the snippet is generic or doesn't mention the DOI's core topic, flag as 'FAILED'.

### STRUCTURED OUTPUT
- ANCHOR: [REF_X]
- DOI: [Verified DOI]
- CITATION_LINE: [IEEE String]
- EPR DATA: [Subject | Predicate | Object]
- PHYSICAL_GROUNDING: [Yes/No/Unclear]
- HALLUCINATION SHIELD: [PASSED/FAILED]
- SNOWBALL_TARGET: [Foundational paper or author mentioned in this snippet for recursive search]
"""

def research_gaps_prompt(primary: str, intersection: str) -> str:
    """
    PhD-level gap identification focusing on technical limitations.
    """
    return f"""
Task: Identify high-density research gaps for: "{primary}" ∩ "{intersection}".
Format: JSON array of strings.

Requirements:
- Focus on: Computational bottlenecks, Lack of physical consistency, or Data sparsity.
- Example: "Stochastic Parameterization: Using GANs to represent sub-grid scale uncertainties in CMIP6 models."
"""

def synthesis_prompt(chapter_title: str, goal: str, grounding: str, research_data: str) -> str:
    """
    Scientific Writer: Optimized for High-Density Synthesis and Cross-Reference Logic.
    """
    return f"""
Act as a Senior Research Scientist. Write: '{chapter_title}'.
THESIS GOAL: {goal}
CORE DEFINITIONS: {grounding}

### RESEARCH DATA (GROUND TRUTH):
{research_data}

### MANDATORY WRITING RULES:
1. ANCHOR DENSITY: Every thematic paragraph MUST synthesize at least 4 unique [REF_X] anchors. Do not list them; weave them into a critical argument.
2. SOURCE EXHAUSTION: You must use at least 90% of the provided [REF_X] anchors in this chapter. If a reference is irrelevant, explain why it represents a 'Noise Gap' in the literature.
3. PHYSICS-AI DUALITY: For every AI method cited, explicitly state its 'Physical Grounding' status based on the EPR DATA. If it lacks mass/energy conservation, critique it as a 'Black-Box' vulnerability.
4. ANTI-HALLUCINATION: If a claim is made that is not explicitly supported by a [REF_X] in the RESEARCH DATA, the agent will fail the audit.

### STRUCTURAL REQUIREMENTS:
- Use H3 headers for sub-sections.
- Ensure the argument moves from 'Standard Methodologies' to 'Strategic Obfuscation' (the Hallucination Shield).
- BIBLIOGRAPHY: Generate a complete IEEE list of all cited DOIs.

### STYLE:
- Tone: Critically analytical, cold, and forensic.
- Language: High-register academic English (e.g., 'obviates', 'stratagem', 'epistemological').
"""