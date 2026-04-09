from core.loop import AgentLoop
from core.memory import Memory
from core.approval import ApprovalSystem
from utils.logger import log
from utils.helpers import parse_goal_string

class OperatorAgent:
    def __init__(self, ui):
        self.ui = ui

        self.goal = ""  # Or None, depending on your logic
        # ... other initializations
        # Initialize Memory (defaults to Ephemeral/In-Memory based on your updated memory.py)
        self.memory = Memory()
        self.approval = ApprovalSystem(ui)

        self.loop = AgentLoop(self)

        self.running = False

    def start(self, metadata=None, start_auto_approve: bool = False):
        """Starts the agent loop and ensures a clean memory session.

        Accepts either a plain goal string (backwards compatible) or a
        metadata dict with keys: `primary_domain` and `intersection_domain`.
        """
        # Clear previous session state
        self.memory.clear_session()
        self.running = True  # mark running early

        # Normalize metadata vs legacy string
        self.metadata = {}
        if isinstance(metadata, dict):
            self.metadata = metadata
            # Build a convenience goal string for fallback logging
            pd = metadata.get('primary_domain', '') or ''
            idom = metadata.get('intersection_domain', '') or ''
            combined = f"{pd} AND {idom}" if pd and idom else (pd or idom or "")
            self.goal = combined
        else:
            # legacy string support: try to populate metadata from a simple
            # string goal like "AI & Climate" or "A ∩ B" so other code
            # relying on `agent.metadata` sees the correct domains.
            goal_str = (metadata or "").strip()
            self.goal = goal_str
            try:
                parsed = parse_goal_string(goal_str)
                if parsed:
                    # Only set metadata when we successfully extract at least primary
                    if parsed.get('primary_domain'):
                        self.metadata = {
                            'primary_domain': parsed.get('primary_domain'),
                            'intersection_domain': parsed.get('intersection_domain', '')
                        }
            except Exception:
                # Keep metadata empty on any parse failure; fallback handling
                # elsewhere will use `self.goal` string.
                self.metadata = {}

        # Pass metadata through to the loop for richer initialization
        self.loop.set_goal(self.metadata if self.metadata else self.goal)
        # Optionally enable auto-approve for the duration of this run.
        try:
            if start_auto_approve and hasattr(self, 'approval') and self.approval:
                self.approval.set_auto_approve(True)
        except Exception:
            pass

        self.loop.start()
        log(f"Agent started with goal/metadata: {self.goal} / {self.metadata}")

    def stop(self):
        """Stops the agent execution."""
        self.running = False
        self.loop.stop()
        log("Agent stopped")
        # Ensure auto-approve is cleared when agent stops
        try:
            if hasattr(self, 'approval') and self.approval:
                self.approval.set_auto_approve(False)
        except Exception:
            pass
        # Best-effort cleanup of any running browser skill created by the loop
        try:
            if hasattr(self.loop, 'browser') and self.loop.browser:
                self.loop.browser.close()
        except:
            pass