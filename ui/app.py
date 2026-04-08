import tkinter as tk
import customtkinter as ctk
import threading
from core.agent import OperatorAgent
import config

# Set the appearance and theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue") 

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("⚡ Operator Agent")
        self.geometry("1000x700")
        self.configure(fg_color="#121212") # Deep dark background

        self.agent = OperatorAgent(self)
        self.is_awaiting_approval = False

        self.build_ui()
        # Ensure we shut down background agents and browser when the GUI closes
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def build_ui(self):
        # --- Main Layout ---
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # 1. Top Search Bar Area
        self.search_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.search_frame.grid(row=0, column=0, padx=30, pady=(30, 10), sticky="ew")
        
        self.entry = ctk.CTkEntry(
            self.search_frame, 
            placeholder_text="Enter your goal (e.g., 'Research Bitcoin mining')...",
            height=50, 
            corner_radius=15,
            border_width=0,
            fg_color="#2a2a2a",
            font=("Inter", 15)
        )
        self.entry.pack(fill="x", side="left", expand=True)

        # 2. Log/Console Area
        self.logbox = ctk.CTkTextbox(
            self, 
            font=("Consolas", 13), 
            fg_color="#1a1a1a",
            border_color="#333333",
            border_width=1,
            corner_radius=15
        )
        self.logbox.grid(row=1, column=0, padx=30, pady=10, sticky="nsew")

        # 3. Bottom Interaction Card (The "Control Center")
        self.control_card = ctk.CTkFrame(self, fg_color="#1e1e1e", corner_radius=20, height=150)
        self.control_card.grid(row=2, column=0, padx=30, pady=30, sticky="ew")
        
        self.preview_label = ctk.CTkLabel(
            self.control_card, 
            text="Waiting for input...", 
            font=("Inter", 12, "italic"),
            text_color="#888888"
        )
        self.preview_label.pack(pady=(15, 5))

        # The "Universal" Button
        # Controls row: run button + auto-approve toggle
        self.controls_frame = ctk.CTkFrame(self.control_card, fg_color="transparent")
        self.controls_frame.pack(pady=(0, 20))

        self.action_button = ctk.CTkButton(
            self.controls_frame, 
            text="GO", 
            command=self.handle_action,
            font=("Inter", 16, "bold"),
            height=50,
            width=200,
            corner_radius=25,
            fg_color="#3b82f6", # Modern Blue
            hover_color="#2563eb"
        )
        self.action_button.pack(side="left", padx=(0, 12))

        # Auto-approve toggle (initial state: enabled when REQUIRE_APPROVAL is False)
        self.auto_approve_var = tk.BooleanVar(value=(not getattr(config, 'REQUIRE_APPROVAL', True)))
        self.auto_switch = ctk.CTkSwitch(
            self.controls_frame,
            text="Auto-approve",
            command=self._on_toggle_auto_approve,
            variable=self.auto_approve_var
        )
        self.auto_switch.pack(side="left")
        # Initialize ApprovalSystem auto-approve to match the switch
        try:
            self.agent.approval.set_auto_approve(bool(self.auto_approve_var.get()))
        except Exception:
            pass

    # --- Logic ---

    def log(self, msg):
        self.after(0, lambda: self._safe_log(msg))

    def _safe_log(self, msg):
        self.logbox.insert("end", f" {msg}\n")
        self.logbox.see("end")

    def handle_action(self):
        """Unified button logic"""
        if self.is_awaiting_approval:
            self.approve()
        else:
            self.start_agent()

    def start_agent(self):
        goal = self.entry.get()
        if not goal: return
        
        self.action_button.configure(state="disabled", text="RUNNING...", fg_color="#333333")
        threading.Thread(target=self.agent.start, args=(goal,), daemon=True).start()

    def ask_approval(self, action):
        self.after(0, lambda: self._setup_approval_ui(action))

    def _setup_approval_ui(self, action):
        self.is_awaiting_approval = True
        self.preview_label.configure(
            text=f"CONFIRM ACTION: {action[:80]}...", 
            text_color="#fbbf24" # Amber/Gold
        )
        self.action_button.configure(
            state="normal", 
            text="APPROVE COMMAND", 
            fg_color="#10b981", # Emerald Green
            hover_color="#059669"
        )

    def approve(self):
        self.is_awaiting_approval = False
        self.preview_label.configure(text="Action approved. Resuming...", text_color="#888888")
        self.action_button.configure(text="RUNNING...", fg_color="#333333", state="disabled")
        self.agent.approval.approve()

    def _on_toggle_auto_approve(self):
        val = bool(self.auto_approve_var.get())
        try:
            self.agent.approval.set_auto_approve(val)
        except Exception:
            pass

        # If we just enabled auto-approve while waiting, auto-approve the pending action
        if val and self.is_awaiting_approval:
            self.is_awaiting_approval = False
            self.preview_label.configure(text="Action auto-approved. Resuming...", text_color="#888888")
            self.action_button.configure(text="RUNNING...", fg_color="#333333", state="disabled")
            try:
                self.agent.approval.approve()
            except Exception:
                pass

    def on_closing(self):
        try:
            # Ask the agent to stop and clean up any running skills (browser)
            self.agent.stop()
            # If the loop has created a browser skill, attempt to close it
            try:
                if hasattr(self.agent.loop, 'browser') and self.agent.loop.browser:
                    self.agent.loop.browser.close()
            except:
                pass
        finally:
            self.destroy()

    # You could add a small 'X' button or right-click menu to Reject if needed

if __name__ == "__main__":
    app = App()
    app.mainloop()

def run_app():
    """Convenience entrypoint used by `main.py` to start the GUI."""
    app = App()
    app.mainloop()