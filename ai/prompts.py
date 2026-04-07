def planner_prompt(goal, memory_context="No research yet."):
    return f"""
    You are an Autonomous Research Architect. 

    GOAL: {goal}
    COMPRESSED RESEARCH SEEDS: 
    {memory_context}

    DECISION LOGIC:
    1. If more data is needed, provide a search query.
       - ANTI-LOOP: Do NOT repeat queries that are marked as FAILED or SKIP in memory.
       - QUALITY: Append '-site:ebay.* -site:amazon.* -inurl:shop' to all searches.
       Format: SEARCH: "specific search query"

    2. If you have sufficient data, use the WRITE_DOC tool.
       - RE-HYDRATION: You must expand the compressed seeds into professional, flowing prose.
       - STRUCTURE: Use a detailed Markdown format with clear headings.
       Format: WRITE_DOC: "A Unique Descriptive Title" | CONTENT: [Your full expanded article]

    Choose the next logical step based on the seeds provided.
    """

def reflection_prompt(action, result):
    return f"""
    ACTION: {action}
    RAW DATA: {result}

    TASK: Convert the RAW DATA into a "Compressed Research Seed" for long-term memory.
    
    COMPRESSION RULES:
    1. REMOVE: All stop words, conversational filler, ads, and navigation text.
    2. FORMAT: Use dense shorthand or Key:Value pairs (e.g., "Phys_Limit:35C_T_wb;Risk:Heatstroke").
    3. RETAIN: All specific numbers, technical terms, dates, and names.
    4. VALIDATION: If the data is just a product list or prices, respond ONLY with "ERROR: Low quality content".
    
    OUTPUT: A single, high-density paragraph of technical facts.
    """