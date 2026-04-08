def planner_prompt(goal, memory_context="INITIAL_STATE: No research performed yet."):
    return f"""
### MISSION
Autonomous Research Engine. 
TARGET_SUBJECT: {goal}

### UNIVERSAL PIVOT PROTOCOLS
1. **COLD START:** If memory is "INITIAL_STATE", search ONLY for the TARGET_SUBJECT verbatim. 
2. **QUERY ATOMIZATION:** Use space-separated keywords. NEVER use quotation marks.
3. **THRESHOLD OF SUFFICIENCY:** If memory contains a 'Causality Map' and 3+ 'EPR Data' points, you MUST stop searching and use WRITE_DOC immediately.
4. **PULSE DEGRADATION:** If Iteration > 2, simplify to 2 broad keywords.
5. **DISCIPLINE SWAP:** If 2+ searches yield "Low Info Density", switch to an "Opposing Discipline".

### TOOLS
- SEARCH: query
- NAVIGATE: url
- WRITE_DOC: Title | CONTENT: [Final Synthesis]

### DISTILLED RESEARCH MEMORY
{memory_context}

### STRICT OUTPUT FORMAT (MANDATORY)
- If research is ongoing: COMMAND: SEARCH: [Keywords Only]
- If Threshold of Sufficiency is met: COMMAND: WRITE_DOC: [Title] | CONTENT: [Final Synthesis of all EPR Data and Causality Maps. Do NOT include JSON formatting.]
"""

def reflection_prompt(action, result, goal):
    return fr"""
    GOAL: {goal}
    ACTION: {action}
    RAW DATA: {result}

    ### EXTRACTION & VALIDATION ENHANCEMENTS
    1. **GAP ANALYSIS:** Identify the specific missing variable.
    2. **EPR EXTRACTION:** - **Entity:** Concept/Object. - **Property:** Numerical data + Units. - **Relation:** Interaction/Causality.
    3. **SOURCE AUDIT:** If results are empty/ads, respond: "ERROR: Low Info Density".

    ### CRITICAL ALIGNMENT & INTEGRITY
    - **SEMANTIC MATCH:** If result is unrelated to {goal}, respond "ERROR: Subject Drift".
    - **NO EXTRAPOLATION:** If no DOI/URL exists, citation MUST be 'THEORETICAL ESTIMATE - NO SOURCE FOUND'.

    ### COMPRESSION FOR MEMORY DISTILLATION
    - FORMAT: Dense Key:Value pairs. NO prose.
    - RETAIN: All DOIs, URLs, and Verbatim Clauses.

    ### SCIENTIFIC INTEGRITY OUTPUT
    - **GAP IDENTIFIED:** [Specific noun/number needed]
    - **EPR DATA:** [Entity] | [Properties] | [Relations]
    - **CAUSALITY MAP:** [Driver] -> [Mechanism] -> [Effect]
    - **CITATION:** Formal entry.
    - **CONSISTENCY SIGNATURE:** [Confirms/Contradicts/No Prior Data]
    - **VERBATIM CHECK:** If Source A and B contradict, label "CONTRADICTORY - REQUIRES PRIMARY SOURCE VALIDATION".
    
    OUTPUT: Provide ONLY the structured data above.
    """