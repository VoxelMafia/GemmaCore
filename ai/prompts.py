def planner_prompt(goal, memory_context="No research yet."):
    return f"""
### MISSION
Autonomous Research Engine. Goal: {goal}

### UNIVERSAL PIVOT PROTOCOLS
1. **DISCIPLINE SWAP:** If 2+ searches in one "Discipline" fail, you MUST switch to an "Opposing Discipline."
2. **QUERY MUTATION (ANTI-LOOP):** Forbidden from repeating >2 keywords. If "Low Info Density" occurs, you MUST delete the failing keyword and replace it with a higher-level category or technical antonym.
3. **SPECIFICITY ANCHOR (VENUE PIVOT):** If conceptual searches fail, you MUST search for the specific venue using site operators (e.g., "site:nature.com [Keywords]" or "site:science.org [Keywords]") or search for "[Keywords] 2024 DOI".

### TOOLS
- SEARCH: query
- NAVIGATE: url
- WRITE_DOC: Title | CONTENT: [Final Synthesis]

### DISTILLED RESEARCH MEMORY
{memory_context}

### STRICT OUTPUT FORMAT
THOUGHT: [Identify Discipline of failure. State the GAP. Declare Mutation Strategy (e.g., "Replacing 'Scythian' with 'Pontic Steppe site:nature.com'").]
COMMAND: SEARCH: [Keywords Only]
"""

def reflection_prompt(action, result, goal):
    return fr"""
    GOAL: {goal}
    ACTION: {action}
    RAW DATA: {result}

    ### EXTRACTION & VALIDATION ENHANCEMENTS
    1. **GAP ANALYSIS:** Identify exactly what is missing (e.g., "Missing specific 2024 aDNA haplogroups").
    2. **EPR EXTRACTION:** - **Entity:** Concept/Object.
       - **Property:** Numerical data + Units (Critical: Mark missing units as "Unverified [Value]").
       - **Relation:** Interaction/Causality.
    3. **SOURCE AUDIT:** If results are empty, ads, or login walls, respond ONLY: "ERROR: Low Info Density".

    ### CRITICAL ALIGNMENT & INTEGRITY
    - **SEMANTIC MATCH:** Check for Subject Drift, mark "ERROR: Subject Drift".
    - **NO EXTRAPOLATION:** If no DOI/URL is found, citation MUST be 'THEORETICAL ESTIMATE - NO SOURCE FOUND'. Do not fabricate authors.

    ### COMPRESSION FOR MEMORY DISTILLATION
    - FORMAT: Dense Key:Value pairs. NO prose. NO conversational filler.
    - RETAIN: DOIs, URLs, and specific dates.

    ### SCIENTIFIC INTEGRITY OUTPUT
    - **GAP IDENTIFIED:** [Specific noun/number needed]
    - **EPR DATA:** [Entity] | [Properties] | [Relations]
    - **CAUSALITY MAP:** [Driver] -> [Mechanism] -> [Effect]
    - **CITATION:** Formal entry.
    - **CONSISTENCY SIGNATURE:** [Confirms/Contradicts/No Prior Data]
    - **VERBATIM CHECK:** If the GOAL requires a specific "Clause," "Law," or "Equation," you MUST find the verbatim text. If the text from Source A and Source B contradicts, you MUST label the data as "CONTRADICTORY - REQUIRES PRIMARY SOURCE VALIDATION."
    OUTPUT: Provide ONLY the structured data above.
    """