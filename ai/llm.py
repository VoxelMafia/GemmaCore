import ollama
import time
from config import MODEL

def ask_llm(prompt, max_retries=10, delay=3):
    """
    Sends a prompt to Ollama with a retry mechanism to survive server restarts.
    """
    attempts = 0
    while attempts < max_retries:
        try:
            res = ollama.chat(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                options={
                    "num_ctx": 8192,
                    "temperature": 0.7
                }
            )
            return res["message"]["content"]
            
        except Exception as e:
            attempts += 1
            print(f"\n[Warning] Failed to connect to Ollama: {e}")
            print(f"Retrying in {delay} seconds... (Attempt {attempts}/{max_retries})\n")
            time.sleep(delay)
            
    # If we exhaust all retries, raise an exception so we don't silently fail and corrupt the loop
    raise ConnectionError("Ollama server unreachable after multiple attempts. Please ensure it is running.")