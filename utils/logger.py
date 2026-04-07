from config import LOG_PATH
import os

os.makedirs("data/logs", exist_ok=True)

def log(msg):
    with open(LOG_PATH, "a") as f:
        f.write(msg + "\n")
