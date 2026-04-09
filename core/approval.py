import re
import threading
import config

class ApprovalSystem:
    def __init__(self, ui):
        self.ui = ui
        self.event = threading.Event()
        self.approved = False
        self.auto_approve = False
        self.pending_action = None

    def request(self, action):
            if not getattr(config, 'REQUIRE_APPROVAL', True) or self.auto_approve:
                return True

            # 1. Formatting: Extract only the readable 'PLAN' part for the UI
            clean_plan = self._extract_readable_plan(action)
            self.pending_action = clean_plan

            if hasattr(self.ui, 'set_pending_action'):
                # Push to UI thread
                self.ui.after(0, lambda: self.ui.set_pending_action(clean_plan))
                # 2. Render-Breath: Give the UI 100ms to draw before we block the thread

            # 3. Block execution until user clicks Approve/Reject
            self.event.clear()
            self.event.wait()

            self.pending_action = None
            return self.approved

    def _extract_readable_plan(self, raw_text):
        """Prevents raw LLM tags from cluttering the UI."""
        match = re.search(r"(PLAN|ACTION|THOUGHTS?):?\s*(.*)", raw_text, re.I | re.S)
        if match:
            return match.group(0).strip()
        return raw_text[:500] + "..."

    def approve(self):
        self.approved = True
        self.event.set()

    def reject(self):
        self.approved = False
        self.event.set()

    def set_auto_approve(self, flag: bool):
        self.auto_approve = bool(flag)

    def has_pending(self):
        return bool(self.pending_action)

    def get_pending(self):
        return self.pending_action
