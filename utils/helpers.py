def truncate(text, n=5000):
    return text[:n]


def parse_goal_string(goal_str, max_parts=2):
    """Parse a user-provided goal string into domain metadata.

    Attempts to split common two-part goal formats such as:
    - "AI & Climate"
    - "Emerging Tech ∩ Sustainability"
    - "Topic A / Topic B" or "Topic A, Topic B"
    - "Primary - Secondary" (hyphen / dash variants)

    Returns a dict with keys `primary_domain`, `intersection_domain`, and
    `domains` (list of parsed parts). If parsing fails, returns an empty dict.
    """
    if not goal_str or not isinstance(goal_str, str):
        return {}

    s = goal_str.strip()
    # Remove surrounding quotes/brackets
    s = s.strip("\"'[]()")

    # Normalize whitespace
    import re
    s = re.sub(r"\s+", " ", s)

    # Separator pattern: common intersection tokens, punctuation, dashes, vs, and
    sep_pattern = r"\s*(?:∩|&|/|,|;|—|–|-|\bvs\.?\b|\bversus\b|\bAND\b|\band\b)\s*"

    parts = re.split(sep_pattern, s)
    # Clean and remove empties
    parts = [p.strip(" \"'()[]") for p in parts if p and p.strip()]

    if not parts:
        return {}

    # If too many parts, keep up to max_parts but include full list
    domains = parts
    primary = parts[0].strip()
    intersection = parts[1].strip() if len(parts) >= 2 else ""

    return {
        'primary_domain': primary,
        'intersection_domain': intersection,
        'domains': domains
    }
