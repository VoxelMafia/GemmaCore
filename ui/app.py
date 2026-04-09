import tkinter as tk
import customtkinter as ctk
import threading
import re
import time
import httpx

# Mock imports maintained from original script
try:
    from core.agent import OperatorAgent
    from utils import logger as ulogger
except ImportError:
    pass

# --- Global Styles & Colors (Scientific / Academic Theme) ---
BG_COLOR = "#0F172A"          # Deep Slate (Background)
CARD_COLOR = "#1E293B"        # Lighter Slate (Panels/Cards)
BORDER_COLOR = "#334155"      # Subtle borders for definition
ACCENT_PRIMARY = "#3B82F6"    # Academic Blue (Action buttons, primary highlights)
ACCENT_SUCCESS = "#10B981"    # Emerald Green (Online status, completion)
ACCENT_WARNING = "#F59E0B"    # Amber (Awaiting approval, alerts)
TEXT_MAIN = "#F8FAFC"         # Crisp White-Gray for main text
TEXT_MUTED = "#CBD5E1"        # Muted Gray for logs and secondary text

ctk.set_appearance_mode("Dark")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("GemmaCore | Thesis Task Master")
        self.geometry("1100x850")
        self.configure(fg_color=BG_COLOR)

        # Logic State
        # Ensure OperatorAgent exists in your environment
        try:
            self.agent = OperatorAgent(self)
        except NameError:
            self.agent = None 
            
        self.is_awaiting_approval = False
        self.is_restarting = False
        self.is_running = False
        self.is_finished = False 
        self.last_activity_time = time.time() 
        self.current_goal = None
        self.last_selection = None

        self.build_ui()
        
        threading.Thread(target=self.health_check_watchdog, daemon=True).start()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # --- TOP NAVIGATION BAR ---
        self.nav_bar = ctk.CTkFrame(self, height=60, fg_color=CARD_COLOR, corner_radius=0)
        self.nav_bar.grid(row=0, column=0, sticky="ew")

        # Status wrapper aligned with the console padding
        self.nav_status_wrapper = ctk.CTkFrame(self.nav_bar, fg_color="transparent")
        self.nav_status_wrapper.pack(side="right", padx=30, pady=10)

        # Refined, structured status card
        self.status_card = ctk.CTkFrame(self.nav_status_wrapper, fg_color=BG_COLOR, border_width=1, border_color=BORDER_COLOR, corner_radius=6)
        self.status_card.pack(side="right")

        self.status_inner = ctk.CTkFrame(self.status_card, fg_color="transparent")
        self.status_inner.pack(padx=12, pady=6)

        self.health_dot = ctk.CTkLabel(self.status_inner, text="●", text_color=ACCENT_SUCCESS, font=("Inter", 14))
        self.health_dot.pack(side="left", padx=(0, 8))

        self.preview_label = ctk.CTkLabel(self.status_inner, text="AGENT ONLINE", font=("Inter", 11, "bold"), text_color=ACCENT_SUCCESS)
        self.preview_label.pack(side="left")

        # --- CONSOLE SECTION ---
        self.console_frame = ctk.CTkFrame(self, fg_color=BG_COLOR)
        self.console_frame.grid(row=1, column=0, padx=30, pady=15, sticky="nsew")
        self.console_frame.grid_rowconfigure(1, weight=1)
        self.console_frame.grid_columnconfigure(0, weight=1)

        # Cleaner text box with subdued borders and professional monospace font
        self.logbox = ctk.CTkTextbox(
            self.console_frame, 
            font=("JetBrains Mono", 12), 
            fg_color=CARD_COLOR, 
            border_color=BORDER_COLOR, 
            border_width=1, 
            corner_radius=8, 
            text_color=TEXT_MUTED
        )
        self.logbox.grid(row=1, column=0, sticky="nsew")

        # Wire the persistent file logger to the UI
        try:
            ulogger.set_ui_callback(self._safe_log_from_logger)
        except Exception:
            pass

        # --- CONTROL CENTER ---
        self.bottom_panel = ctk.CTkFrame(self, fg_color=CARD_COLOR, height=100, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        self.bottom_panel.grid(row=2, column=0, padx=30, pady=(10, 30), sticky="ew")
        
        try:
            self.bottom_panel.grid_propagate(False)
        except Exception:
            pass

        self.inner_control = ctk.CTkFrame(self.bottom_panel, fg_color="transparent")
        self.inner_control.pack(expand=True, fill="both", padx=30, pady=20)

        self.inner_control.grid_columnconfigure(0, weight=0)
        self.inner_control.grid_columnconfigure(1, weight=1)
        self.inner_control.grid_columnconfigure(2, weight=0)

        # Center column: input
        self.center_group = ctk.CTkFrame(self.inner_control, fg_color="transparent")
        self.center_group.grid(row=0, column=1, sticky="nsew")

        entry_container = ctk.CTkFrame(self.center_group, fg_color="transparent")
        entry_container.pack(fill="x", padx=20, pady=(8, 8))

        self.entry_domain_a = ctk.CTkEntry(
            entry_container, 
            placeholder_text="Define research objective (e.g., 'AI in Climate Models') or leave blank for autonomous mode...", 
            height=42, 
            corner_radius=6, 
            fg_color=BG_COLOR, 
            text_color=TEXT_MAIN,
            font=("Inter", 13), 
            border_width=1, 
            border_color=BORDER_COLOR
        )
        self.entry_domain_a.pack(fill="x")
        self.entry_domain_a.bind("<Return>", lambda e: self.handle_action())

        # Right column: actions
        self.action_group = ctk.CTkFrame(self.inner_control, fg_color="transparent")
        self.action_group.grid(row=0, column=2, sticky="ns", padx=(10, 0))

        self.auto_approve_var = tk.BooleanVar(value=False)
        actions_inner = ctk.CTkFrame(self.action_group, fg_color="transparent")
        actions_inner.pack(side="right", anchor="e", pady=5)

        self.auto_switch = ctk.CTkSwitch(
            actions_inner, 
            text="Auto-Approve", 
            command=self._on_toggle_auto_approve, 
            variable=self.auto_approve_var, 
            font=("Inter", 12), 
            progress_color=ACCENT_PRIMARY, 
            button_color=TEXT_MAIN,
            button_hover_color=TEXT_MUTED,
            fg_color=BORDER_COLOR
        )
        self.auto_switch.pack(side="left", padx=(0, 20))

        self.action_button = ctk.CTkButton(
            actions_inner, 
            text="INITIATE RESEARCH", 
            command=self.handle_action, 
            font=("Inter", 13, "bold"), 
            height=42, 
            width=180, 
            corner_radius=6, 
            fg_color=ACCENT_PRIMARY,
            text_color=TEXT_MAIN,
            hover_color="#2563EB" # Slightly darker blue on hover
        )
        self.action_button.pack(side="left")

    def ask_approval(self, action):
        self.last_activity_time = time.time()
        try:
            if hasattr(self, 'set_pending_action'):
                self.after(0, lambda: self.set_pending_action(action))
        except Exception:
            pass

    def _setup_generic_approval(self, action):
        return

    def _internal_reject(self):
        self.last_selection = None
        try:
            self.agent.approval.reject()
        except Exception:
            pass
        self.clear_pending_action()
        self._reset_action_button()

    def approve(self):
        try:
            self.agent.approval.approve()
        except Exception:
            pass
        self.clear_pending_action()
        self.preview_label.configure(text="Execution in Progress...", text_color=ACCENT_PRIMARY)
        self.action_button.configure(text="RUNNING...", fg_color=BORDER_COLOR, state="normal")
        try:
            self.preview_label.configure(text="RUNNING", text_color=ACCENT_PRIMARY)
            self.health_dot.configure(text_color=ACCENT_PRIMARY)
        except Exception:
            pass

    def set_pending_action(self, action_text):
        self.is_awaiting_approval = True
        preview = action_text if len(action_text) <= 200 else action_text[:200] + "..."
        self.preview_label.configure(text=f"AUTHORIZATION REQUIRED: {preview}", text_color=ACCENT_WARNING)
        self.action_button.configure(text="APPROVE ACTION", fg_color=ACCENT_WARNING, text_color=BG_COLOR, state="normal")
        try:
            self.preview_label.configure(text="AWAITING INPUT", text_color=ACCENT_WARNING)
            self.health_dot.configure(text_color=ACCENT_WARNING)
        except Exception:
            pass

    def clear_pending_action(self):
        self.is_awaiting_approval = False
        if self.is_running and not self.is_finished:
            self.preview_label.configure(text="Execution in Progress...", text_color=ACCENT_PRIMARY)
            self.action_button.configure(text="RUNNING...", fg_color=BORDER_COLOR, text_color=TEXT_MAIN, state="normal")
        else:
            self._reset_action_button()
        try:
            self.preview_label.configure(text="IDLE", text_color=ACCENT_PRIMARY)
            self.health_dot.configure(text_color=ACCENT_SUCCESS)
        except Exception:
            pass

    def handle_action(self):
        if not self.is_running:
            self.start_agent()
            return

        try:
            if hasattr(self.agent, 'approval') and self.agent.approval and self.agent.approval.has_pending():
                self.approve()
                return
        except Exception:
            pass
        return

    def start_agent(self, goal=None):
        topic_a = self.entry_domain_a.get().strip()
        md_for_agent = None
        
        if not topic_a:
            md_for_agent = "Autonomous"
            self.current_goal = "Autonomous"
        else:
            parts = re.split(r"\s*(?:&|AND|and|/)\s*", topic_a)

            def _suitable_split(p0, p1):
                stop_words = {"research", "study", "project", "topic", "and", "vs", "versus"}
                a, b = p0.strip(), p1.strip()
                if not a or not b: return False
                if len(a) < 3 or len(b) < 3: return False
                if len(a) > 120 or len(b) > 120: return False
                if any(w.lower() in stop_words for w in (a.split()[0], b.split()[0])): return False
                if len(a.split()) > 12 or len(b.split()) > 12: return False
                return True

            if len(parts) >= 2 and _suitable_split(parts[0], parts[1]):
                md_for_agent = {'primary_domain': parts[0].strip(), 'intersection_domain': parts[1].strip()}
                self.current_goal = f"{parts[0].strip()} & {parts[1].strip()}"
            else:
                md_for_agent = topic_a
                self.current_goal = topic_a
                
        self.is_running = True
        self.is_finished = False

        self.action_button.configure(state="normal", text="RUNNING...", fg_color=BORDER_COLOR)

        if self.agent:
            threading.Thread(target=self.agent.start, args=(md_for_agent,), daemon=True).start()

    def _toggle_secondary(self):
        if not hasattr(self, '_secondary_visible'):
            self._secondary_visible = False

        if not self._secondary_visible:
            self.entry_domain_b.grid(row=0, column=1, padx=(5, 0), sticky="ew")
            self.secondary_toggle.configure(text="Remove secondary")
            self._secondary_visible = True
        else:
            try:
                self.entry_domain_b.delete(0, 'end')
            except: pass
            self.entry_domain_b.grid_forget()
            self.secondary_toggle.configure(text="Add secondary")
            self._secondary_visible = False

    def log(self, msg):
        self.last_activity_time = time.time() 
        if any(x in msg for x in ["✅", "COMPLETE"]):
            self.is_finished, self.is_running = True, False
            self.after(0, self._reset_action_button)
        self.after(0, lambda: self._safe_log(msg))

    def _safe_log(self, msg):
        self.logbox.insert("end", f" [{time.strftime('%H:%M:%S')}] {msg}\n")
        self.logbox.see("end")

    def _safe_log_from_logger(self, formatted_msg):
        try:
            self.last_activity_time = time.time()
            self.logbox.insert("end", formatted_msg + "\n")
            self.logbox.see("end")
        except Exception:
            pass

    def _reset_action_button(self):
        self.action_button.configure(state="normal", text="NEW RESEARCH", fg_color=ACCENT_PRIMARY, text_color=TEXT_MAIN)
        self.preview_label.configure(text="Task Finalized", text_color=ACCENT_SUCCESS)
        try:
            self.preview_label.configure(text="IDLE", text_color=ACCENT_PRIMARY)
            self.health_dot.configure(text_color=ACCENT_SUCCESS)
        except Exception:
            pass

    def update_health_status(self, status, color):
        self.after(0, lambda: self.health_dot.configure(text_color=color))
        label_text = "AGENT ONLINE" if status == "ONLINE" else "AGENT OFFLINE"
        self.after(0, lambda: self.preview_label.configure(text=label_text, text_color=color))

    def health_check_watchdog(self):
        while True:
            try:
                if httpx.get("http://localhost:11434/api/tags", timeout=3.0).status_code == 200:
                    self.update_health_status("ONLINE", ACCENT_SUCCESS)
                else: 
                    self.update_health_status("OFFLINE", "#EF4444") # Red 500 for offline
            except: 
                self.update_health_status("OFFLINE", "#EF4444")
            time.sleep(5)

    def _on_toggle_auto_approve(self):
        val = bool(self.auto_approve_var.get())
        try: 
            self.agent.approval.set_auto_approve(val)
        except: 
            pass

    def on_closing(self):
        try: 
            if self.agent:
                self.agent.stop()
        finally: 
            self.destroy()

def run_app():
    app = App()
    app.mainloop()

if __name__ == "__main__":
    run_app()