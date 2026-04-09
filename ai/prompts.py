def planner_prompt(hierarchy, memory_context="INITIAL_STATE"):
    return f"""
### MISSION: THESIS TASK MASTER (API-DRIVEN)
You are an autonomous researcher with direct access to OpenAlex, PubMed, and arXiv.
{hierarchy}

### EPISTEMIC HIERARCHY
1. API SOURCES (GOLD): Peer-reviewed metadata from OpenAlex, DOIs, and PubMed abstracts.
2. NAVIGATE (SILVER): Full-text reading of specific URLs/PDFs found via API.

### RECURSIVE GOAL SETTING
- Use SEARCH to identify relevant DOIs and peer-reviewed abstracts first.
- Only use NAVIGATE if the API abstract is insufficient or you need specific methodology details from a PDF.

### TOOLS
- SEARCH: [Specific keywords for API lookup - use technical nomenclature]
- NAVIGATE: [Direct URL to a PDF or full-text site if DOI lookup isn't enough]

### MEMORY
{memory_context}

### OUTPUT
- RIGOR GAP: [What specific data is missing?]
- SUB_GOAL: [Tactical task]
- COMMAND: [SEARCH: keywords OR NAVIGATE: url]
"""

def reflection_prompt(action, result, hierarchy):
    return fr"""
    CONTEXT: {hierarchy}
    ACTION: {action}
    RAW JSON DATA: {result}

    ### DATA EXTRACTION PROTOCOL
    1. METADATA: Map Title, DOI, and Publication Year.
    2. ABSTRACT ANALYSIS: Identify specific metrics, benchmarks, and "n-size" mentioned in the abstract.
    3. CROSS-REFERENCE: Check if this paper cites or is cited by previous memory entries.

    ### STRUCTURED OUTPUT (Strictly No Prose)
    - DOI: [The permanent identifier]
    - RIGOR SCORE: [Based on source and methodology described]
    - EPR DATA: [Detailed Entity | Property | Relation]
    - GAP SATISFACTION: [How does this specifically answer the active Sub-Goal?]
    - HALLUCINATION SHIELD: [Check: Are these findings in the API result? Yes/No]
    """

def research_gaps_prompt(primary, intersection):
    return f"""
You are an expert research strategist and senior academic reviewer. Task: Identify 3 top-tier, PhD-level research gaps at the intersection of "{primary}" and "{intersection}".

Requirements:
- Produce EXACTLY a JSON array of 3 strings and nothing else (e.g. ["Title: Gap description", ...]).
- Each string must begin with a concise title (<= 8 words), followed by a colon and a 2-3 sentence description (no more than 3 sentences total per item).
- Descriptions should be high technical density: state the specific limitation or unanswered question, explain why it matters (impact/metric), and give a clear, measurable research objective or evaluation criterion.
- Prefer references to methods/benchmarks (e.g., causal inference, formal verification, empirical benchmark) where relevant.
- Avoid vague language, list items, bullet points, or extra commentary outside the JSON array.

Output example:
["Sparse Architecture Verification: Current provable guarantees... (2-3 sentences)", "...", "..."]
"""