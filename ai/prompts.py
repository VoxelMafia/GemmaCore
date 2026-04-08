def planner_prompt(goal, memory_context="INITIAL_STATE: No research performed yet."):
    return f"""
### MISSION
Autonomous Research Engine. 
TARGET_SUBJECT: {goal}

### UNIVERSAL PIVOT PROTOCOLS
1. **COLD START:** If memory is "INITIAL_STATE", search ONLY for the TARGET_SUBJECT. Do not add words.
2. **DISCIPLINE SWAP:** If 2+ searches fail, switch to an "Opposing Discipline."
3. **QUERY MUTATION:** Forbidden from repeating >2 keywords. Replace failing keywords with technical synonyms.
4. **SPECIFICITY ANCHOR:** If conceptual searches fail, use site operators (e.g., "site:nature.com").

### TOOLS
- SEARCH: query
- NAVIGATE: url
- WRITE_DOC: Title | CONTENT: [Final Synthesis]

### DISTILLED RESEARCH MEMORY
{memory_context}

### STRICT OUTPUT FORMAT
COMMAND: SEARCH: [Provide ONLY search keywords. Do NOT include the word "Goal" or the subject name label.]
"""

def reflection_prompt(action, result, goal):
    return fr"""
    GOAL: {goal}
    ACTION: {action}
    RAW DATA: {result}

    ### EXTRACTION & VALIDATION ENHANCEMENTS
    1. **GAP ANALYSIS:** Identify specific missing data (e.g., "Missing 2024 haplogroups").
    2. **EPR EXTRACTION:** - **Entity:** Concept/Object.
       - **Property:** Numerical data + Units (Mark missing as "Unverified [Value]").
       - **Relation:** Interaction/Causality.
    3. **SOURCE AUDIT:** If results are ONLY ads, paywalls, or 404s, respond: "ERROR: Low Info Density". If partial data exists, extract it; do NOT trigger error.

    ### CRITICAL ALIGNMENT & INTEGRITY
    - **SEMANTIC MATCH:** Check for Subject Drift; if the data is unrelated to {goal}, mark "ERROR: Subject Drift".
    - **NO EXTRAPOLATION:** If no DOI/URL exists, citation MUST be 'THEORETICAL ESTIMATE - NO SOURCE FOUND'.

    ### COMPRESSION FOR MEMORY DISTILLATION
    - FORMAT: Dense Key:Value pairs. NO prose. NO conversational filler.
    - RETAIN: DOIs, URLs, and specific dates.

    ### SCIENTIFIC INTEGRITY OUTPUT
    - **GAP IDENTIFIED:** [Specific noun/number needed]
    - **EPR DATA:** [Entity] | [Properties] | [Relations]
    - **CAUSALITY MAP:** [Driver] -> [Mechanism] -> [Effect]
    - **CITATION:** Formal entry.
    - **CONSISTENCY SIGNATURE:** [Confirms/Contradicts/No Prior Data]
    - **VERBATIM CHECK:** Find verbatim text for Laws/Equations. If Source A and B contradict, label "CONTRADICTORY - REQUIRES PRIMARY SOURCE VALIDATION".
    
    OUTPUT: Provide ONLY the structured data above.
    """