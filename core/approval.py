import threading

class ApprovalSystem:
    def __init__(self, ui):
        self.ui = ui
        self.event = threading.Event()
        self.approved = False

    def request(self, action):
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
