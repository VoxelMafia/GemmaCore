import threading

class ApprovalSystem:
    def __init__(self, ui):
        self.ui = ui
        self.event = threading.Event()
        self.approved = False
        self.auto_approve = False

    def request(self, action):
        # If auto-approve is enabled, immediately approve without UI interaction
        if self.auto_approve:
            return True

        self.ui.ask_approval(action)

        self.event.clear()
        self.event.wait()

        return self.approved

    def approve(self):
        self.approved = True
        self.event.set()

    def reject(self):
        self.approved = False
        self.event.set()

    def set_auto_approve(self, flag: bool):
        self.auto_approve = bool(flag)
