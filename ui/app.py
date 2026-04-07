import tkinter as tk
from tkinter import scrolledtext
import threading # Use this to move the agent off the UI thread
from core.agent import OperatorAgent

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("⚡ Operator Agent")
        self.root.geometry("900x600")

        self.agent = OperatorAgent(self)
        self.build_ui()

    def build_ui(self):
        top = tk.Frame(self.root)
        top.pack(fill="x")

        self.entry = tk.Entry(top, font=("Arial", 14))
        self.entry.pack(fill="x", padx=10, pady=5)

        btns = tk.Frame(self.root)
        btns.pack()

        tk.Button(btns, text="START", bg="green", fg="white",
                  command=self.start).pack(side="left", padx=5)

        tk.Button(btns, text="STOP", bg="red", fg="white",
                  command=self.agent.stop).pack(side="left", padx=5)

        self.logbox = scrolledtext.ScrolledText(self.root, font=("Consolas", 10))
        self.logbox.pack(fill="both", expand=True, padx=10, pady=10)

        self.approval_label = scrolledtext.ScrolledText(self.root, height=4,
                                   font=("Consolas", 10), wrap="word")
        self.approval_label.pack(fill="x", padx=10, pady=5)
        self.approval_label.configure(state="disabled", foreground="orange")

        approval_btns = tk.Frame(self.root)
        approval_btns.pack()

        tk.Button(approval_btns, text="APPROVE", bg="blue", fg="white",
                  command=self.approve).pack(side="left", padx=5)

        tk.Button(approval_btns, text="REJECT", bg="gray", fg="white",
                  command=self.reject).pack(side="left", padx=5)

    def log(self, msg):
        # Thread-safe logging
        self.root.after(0, lambda: self._safe_log(msg))

    def _safe_log(self, msg):
        self.logbox.insert(tk.END, msg + "\n")
        self.logbox.see(tk.END)

    def start(self):
        goal = self.entry.get()
        # Launching agent in a thread prevents the "Iteration 0" freeze
        threading.Thread(target=self.agent.start, args=(goal,), daemon=True).start()

    def ask_approval(self, action):
        self.root.after(0, lambda: self._safe_ask_approval(action))

    def _safe_ask_approval(self, action):
        self.approval_label.configure(state="normal")
        self.approval_label.delete("1.0", tk.END)
        self.approval_label.insert(tk.END, f"Approve action:\n{action}")
        self.approval_label.configure(state="disabled")

    def approve(self):
        self._clear_approval()
        self.agent.approval.approve()

    def reject(self):
        self._clear_approval()
        self.agent.approval.reject()

    def _clear_approval(self):
        self.approval_label.configure(state="normal")
        self.approval_label.delete("1.0", tk.END)
        self.approval_label.configure(state="disabled")

def run_app():
    root = tk.Tk()
    App(root) # Fixed Pylance "not accessed" warning
    root.mainloop()