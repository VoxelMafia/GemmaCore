from core.loop import AgentLoop
from core.memory import Memory
from core.approval import ApprovalSystem
from utils.logger import log

class OperatorAgent:
    def __init__(self, ui):
        self.ui = ui

        # Initialize Memory (defaults to Ephemeral/In-Memory based on your updated memory.py)
        self.memory = Memory()
        self.approval = ApprovalSystem(ui)

        self.loop = AgentLoop(self)

        self.running = False

    def start(self, goal):
        """Starts the agent loop and ensures a clean memory session."""
        # FIX: Wipe old research data before starting a new goal
        self.memory.clear_session()
        self.running = True  # Set running before starting the thread
        self.loop.set_goal(goal)
        self.loop.start()
        log(f"Agent started with goal: {goal}")

    def stop(self):
        """Stops the agent execution."""
        self.running = False
        self.loop.stop()
        log("Agent stopped")