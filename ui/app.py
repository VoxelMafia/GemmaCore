import tkinter as tk
import customtkinter as ctk
import threading
import subprocess
import time
import httpx
import os
import psutil
from core.agent import OperatorAgent
import config

# Global Styles & Colors
BG_COLOR = "#0F0F12"
CARD_COLOR = "#18181B"
ACCENT_BLUE = "#3B82F6"
ACCENT_GREEN = "#10B981"
ACCENT_AMBER = "#F59E0B"
TEXT_DIM = "#9CA3AF"

ctk.set_appearance_mode("Dark")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("GemmaCore | Research Agent")
        self.geometry("1100x850")
        self.configure(fg_color=BG_COLOR)

        # Logic State
        self.agent = OperatorAgent(self)
        self.is_awaiting_approval = False
        self.is_restarting = False
        self.is_running = False
        self.is_finished = False 
        self.last_activity_time = time.time() 
        self.current_goal = None

        self.build_ui()
        
        # Start watchdog
        threading.Thread(target=self.health_check_watchdog, daemon=True).start()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # --- TOP NAVIGATION BAR ---
        self.nav_bar = ctk.CTkFrame(self, height=60, fg_color=CARD_COLOR, corner_radius=0)
        self.nav_bar.grid(row=0, column=0, sticky="ew")

        self.status_container = ctk.CTkFrame(self.nav_bar, fg_color="transparent")
        self.status_container.pack(side="right", padx=25)

        self.health_dot = ctk.CTkLabel(self.status_container, text="●", text_color=ACCENT_GREEN, font=("Inter", 20))
        self.health_dot.pack(side="left", padx=(0, 5))
        
        self.health_text = ctk.CTkLabel(
            self.status_container, text="OLLAMA ONLINE", 
            font=ctk.CTkFont(family="Inter", size=11, weight="bold"), 
            text_color=TEXT_DIM
        )
        self.health_text.pack(side="left")

        # --- SEARCH SECTION ---
        self.search_card = ctk.CTkFrame(self, fg_color=CARD_COLOR, corner_radius=16)
        self.search_card.grid(row=1, column=0, padx=30, pady=(25, 10), sticky="ew")
        
        self.entry = ctk.CTkEntry(
            self.search_card, placeholder_text="What would you like to research today?",
            height=60, corner_radius=12, border_width=1, 
            fg_color="#09090B", border_color="#27272A",
            font=("Inter", 15), text_color="#FAFAFA"
        )
        self.entry.pack(fill="x", padx=15, pady=15)

        # --- CONSOLE/LOG SECTION ---
        self.console_frame = ctk.CTkFrame(self, fg_color=BG_COLOR)
        self.console_frame.grid(row=2, column=0, padx=30, pady=10, sticky="nsew")
        self.console_frame.grid_rowconfigure(1, weight=1)
        self.console_frame.grid_columnconfigure(0, weight=1)

        self.log_label = ctk.CTkLabel(self.console_frame, text="TERMINAL OUTPUT", font=("Inter", 11, "bold"), text_color="#52525B")
        self.log_label.grid(row=0, column=0, sticky="w", padx=5, pady=(0, 5))

        self.logbox = ctk.CTkTextbox(
            self.console_frame, font=("JetBrains Mono", 12), 
            fg_color="#09090B", border_color="#27272A", border_width=1, corner_radius=12,
            text_color="#D1D5DB"
        )
        self.logbox.grid(row=1, column=0, sticky="nsew")

        # --- CONTROL CENTER (GROUPED PANEL) ---
        self.bottom_panel = ctk.CTkFrame(self, fg_color=CARD_COLOR, height=120, corner_radius=20)
        self.bottom_panel.grid(row=3, column=0, padx=30, pady=(10, 30), sticky="ew")

        # Inner Container for grouping
        self.inner_control = ctk.CTkFrame(self.bottom_panel, fg_color="transparent")
        self.inner_control.pack(expand=True, fill="both", padx=30, pady=20)

        # Left side: Status & Preview
        self.info_group = ctk.CTkFrame(self.inner_control, fg_color="transparent")
        self.info_group.pack(side="left", fill="y")

        # FIX: Changed "medium" to "normal" to fix TclError
        self.preview_label = ctk.CTkLabel(
            self.info_group, text="System Ready", 
            font=("Inter", 13, "normal"), text_color=TEXT_DIM, anchor="w"
        )
        self.preview_label.pack(side="top", fill="x")

        self.sub_text = ctk.CTkLabel(
            self.info_group, text="Agent standing by for instructions...", 
            font=("Inter", 11), text_color="#52525B", anchor="w"
        )
        self.sub_text.pack(side="top", fill="x")

        # Right side: Buttons & Toggles
        self.action_group = ctk.CTkFrame(self.inner_control, fg_color="transparent")
        self.action_group.pack(side="right")

        self.auto_approve_var = tk.BooleanVar(value=(not getattr(config, 'REQUIRE_APPROVAL', True)))
        self.auto_switch = ctk.CTkSwitch(
            self.action_group, text="Auto-Approve", 
            command=self._on_toggle_auto_approve, 
            variable=self.auto_approve_var,
            font=("Inter", 12), progress_color=ACCENT_BLUE
        )
        self.auto_switch.pack(side="left", padx=20)

        self.action_button = ctk.CTkButton(
            self.action_group, text="INITIATE RESEARCH", 
            command=self.handle_action,
            font=ctk.CTkFont(family="Inter", size=14, weight="bold"), 
            height=50, width=200, corner_radius=12,
            fg_color=ACCENT_BLUE, hover_color="#2563EB"
        )
        self.action_button.pack(side="left")

    # --- LOGIC METHODS ---

    def health_check_watchdog(self):
        while True:
            current_time = time.time()
            try:
                response = httpx.get("http://localhost:11434/api/tags", timeout=3.0)
                if response.status_code == 200:
                    if self.is_running and not self.is_finished:
                        if (current_time - self.last_activity_time > 45):
                            self.update_health_status("LLM HANG DETECTED", ACCENT_AMBER)
                            if not self.is_restarting: self.restart_ollama_service()
                        else:
                            self.update_health_status("ONLINE", ACCENT_GREEN)
                    elif self.is_finished:
                        self.update_health_status("TASK COMPLETE", ACCENT_BLUE)
                    else:
                        self.update_health_status("ONLINE", ACCENT_GREEN)
            except Exception:
                if not self.is_finished:
                    self.update_health_status("OFFLINE", "#EF4444")
                    if not self.is_restarting: self.restart_ollama_service()
            time.sleep(5)

    def update_health_status(self, status, color):
        self.after(0, lambda: self.health_dot.configure(text_color=color))
        self.after(0, lambda: self.health_text.configure(text=f"OLLAMA {status}", text_color=color))

    def restart_ollama_service(self):
        self.is_restarting = True
        self.log("[SYSTEM] Emergency Restart: Service unresponsive.")
        try:
            self.agent.stop()
            for proc in psutil.process_iter(['name']):
                try:
                    name = proc.info['name'].lower()
                    if any(x in name for x in ["ollama", "chrome", "msedge"]): proc.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied): pass
            
            time.sleep(2)
            ollama_path = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama app.exe")
            if os.path.exists(ollama_path):
                subprocess.Popen([ollama_path], start_new_session=True)
            
            ready = False
            for _ in range(15):
                try:
                    if httpx.get("http://localhost:11434/api/tags").status_code == 200:
                        ready = True; break
                except: time.sleep(2)

            if ready:
                self.log("[SYSTEM] Service recovered. Resuming...")
                if self.current_goal and not self.is_finished:
                    self.after(1000, lambda: self.start_agent(self.current_goal))
        except Exception as e:
            self.log(f"[ERROR] Restart failed: {e}")
        finally:
            self.is_restarting = False

    def log(self, msg):
        self.last_activity_time = time.time() 
        if any(x in msg for x in ["Successfully wrote to", "✅"]):
            self.is_finished = True
            self.is_running = False
            self.after(0, self._reset_action_button)
        self.after(0, lambda: self._safe_log(msg))

    def _safe_log(self, msg):
        self.logbox.insert("end", f" [{time.strftime('%H:%M:%S')}] {msg}\n")
        self.logbox.see("end")

    def _reset_action_button(self):
        self.action_button.configure(state="normal", text="NEW RESEARCH", fg_color=ACCENT_BLUE)
        self.preview_label.configure(text="Research Finalized", text_color=ACCENT_GREEN)

    def handle_action(self):
        if self.is_awaiting_approval:
            self.approve()
        else:
            self.start_agent()

    def start_agent(self, goal=None):
        if goal is None: goal = self.entry.get()
        if not goal: return
        
        self.current_goal = goal
        self.is_running = True
        self.is_finished = False
        self.last_activity_time = time.time()
        
        self.action_button.configure(state="disabled", text="RUNNING...", fg_color="#27272A")
        self.preview_label.configure(text="Agent is browsing...", text_color=ACCENT_BLUE)
        threading.Thread(target=self.agent.start, args=(goal,), daemon=True).start()

    def ask_approval(self, action):
        self.last_activity_time = time.time() 
        self.after(0, lambda: self._setup_approval_ui(action))

    def _setup_approval_ui(self, action):
        self.is_awaiting_approval = True
        short_action = (action[:75] + '...') if len(action) > 75 else action
        self.preview_label.configure(text=f"PENDING APPROVAL", text_color=ACCENT_AMBER)
        self.sub_text.configure(text=short_action)
        self.action_button.configure(state="normal", text="APPROVE COMMAND", fg_color=ACCENT_GREEN)

    def approve(self):
        self.is_awaiting_approval = False
        self.last_activity_time = time.time()
        self.preview_label.configure(text="Command Executing...", text_color=ACCENT_BLUE)
        self.action_button.configure(text="RUNNING...", fg_color="#27272A", state="disabled")
        self.agent.approval.approve()

    def _on_toggle_auto_approve(self):
        val = bool(self.auto_approve_var.get())
        try: self.agent.approval.set_auto_approve(val)
        except: pass
        if val and self.is_awaiting_approval: self.approve()

    def on_closing(self):
        try:
            self.agent.stop()
            for proc in psutil.process_iter(['name']):
                name = proc.info['name'].lower()
                if "chrome" in name or "msedge" in name: proc.kill()
        finally: 
            self.destroy()

def run_app():
    app = App()
    app.mainloop()

if __name__ == "__main__":
    run_app()