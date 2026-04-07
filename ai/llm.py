import ollama
from config import MODEL

def ask_llm(prompt):
    res = ollama.chat(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}]
    )
    return res["message"]["content"]
