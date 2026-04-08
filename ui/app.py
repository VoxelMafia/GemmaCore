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

# Set appearance
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue") 

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("⚡ GemmaCore: Research Agent")
        self.geometry("1000x800")
        self.configure(fg_color="#121212")

        self.agent = OperatorAgent(self)
        self.is_awaiting_approval = False
        self.is_restarting = False
        self.is_running = False
        self.is_finished = False # Tracks if the document was successfully written
        self.last_activity_time = time.time() 
        self.current_goal = None

        self.build_ui()
        
        # Start watchdog
        threading.Thread(target=self.health_check_watchdog, daemon=True).start()
        
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # Status Bar
        self.status_bar = ctk.CTkFrame(self, height=35, fg_color="#1a1a1a")
        self.status_bar.grid(row=0, column=0, sticky="ew")
        
        self.health_dot = ctk.CTkLabel(self.status_bar, text="●", text_color="#10b981", font=("Inter", 18))
        self.health_dot.pack(side="left", padx=(15, 5))
        
        self.health_text = ctk.CTkLabel(self.status_bar, text="OLLAMA ONLINE", font=("Inter", 11, "bold"), text_color="#888888")
        self.health_text.pack(side="left")

        # 1. Search Bar
        self.search_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.search_frame.grid(row=1, column=0, padx=30, pady=(20, 10), sticky="ew")
        
        self.entry = ctk.CTkEntry(
            self.search_frame, placeholder_text="Enter your Research Topic...",
            height=55, corner_radius=15, border_width=0, fg_color="#2a2a2a", font=("Inter", 16)
        )
        self.entry.pack(fill="x", side="left", expand=True)

        # 2. Logbox
        self.logbox = ctk.CTkTextbox(
            self, font=("Consolas", 13), fg_color="#1a1a1a", border_color="#333333", border_width=1, corner_radius=15
        )
        self.logbox.grid(row=2, column=0, padx=30, pady=10, sticky="nsew")

        # 3. Control Center
        self.control_card = ctk.CTkFrame(self, fg_color="#1e1e1e", corner_radius=20)
        self.control_card.grid(row=3, column=0, padx=30, pady=(10, 30), sticky="ew")
        
        self.preview_label = ctk.CTkLabel(self.control_card, text="System Ready", font=("Inter", 12, "italic"), text_color="#888888")
        self.preview_label.pack(pady=(15, 5))

        self.controls_frame = ctk.CTkFrame(self.control_card, fg_color="transparent")
        self.controls_frame.pack(pady=(0, 20))

        self.action_button = ctk.CTkButton(
            self.controls_frame, text="GO", command=self.handle_action,
            font=("Inter", 16, "bold"), height=50, width=220, corner_radius=25,
            fg_color="#3b82f6", hover_color="#2563eb"
        )
        self.action_button.pack(side="left", padx=(0, 15))

        self.auto_approve_var = tk.BooleanVar(value=(not getattr(config, 'REQUIRE_APPROVAL', True)))
        self.auto_switch = ctk.CTkSwitch(self.controls_frame, text="Auto-approve", command=self._on_toggle_auto_approve, variable=self.auto_approve_var)
        self.auto_switch.pack(side="left")

    def health_check_watchdog(self):
        while True:
            current_time = time.time()
            try:
                # 1. API Ping
                response = httpx.get("http://localhost:11434/api/tags", timeout=3.0)
                
                if response.status_code == 200:
                    # 2. Hang Detection (Only if running and NOT finished)
                    if self.is_running and not self.is_finished:
                        if (current_time - self.last_activity_time > 45): # 45s threshold
                            self.update_health_status("LLM HANG DETECTED", "#f59e0b")
                            if not self.is_restarting:
                                self.restart_ollama_service()
                        else:
                            self.update_health_status("ONLINE", "#10b981")
                    elif self.is_finished:
                        self.update_health_status("TASK COMPLETE", "#3b82f6")
                    else:
                        self.update_health_status("ONLINE", "#10b981")
                        
            except Exception:
                # 3. Service Offline Check
                if not self.is_finished:
                    self.update_health_status("OFFLINE", "#ef4444")
                    if not self.is_restarting:
                        self.restart_ollama_service()
            
            time.sleep(5)

    def update_health_status(self, status, color):
        self.after(0, lambda: self.health_dot.configure(text_color=color))
        self.after(0, lambda: self.health_text.configure(text=f"OLLAMA {status}", text_color=color))

    def restart_ollama_service(self):
            self.is_restarting = True
            self.log("[SYSTEM] Emergency Restart: Service unresponsive or LLM stuck.")
            
            try:
                # 1. Stop the current agent thread and cleanup browsers
                self.agent.stop()
                
                # 2. Kill Ollama and stray browser processes
                for proc in psutil.process_iter(['name']):
                    try:
                        name = proc.info['name'].lower()
                        if "ollama" in name or "chrome" in name or "msedge" in name:
                            proc.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                
                time.sleep(2)

                # 3. Restart Ollama executable
                ollama_path = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama app.exe")
                if os.path.exists(ollama_path):
                    subprocess.Popen([ollama_path], start_new_session=True)
                    self.log("[SYSTEM] Service restarting... waiting for model load.")
                
                # 4. Wait for readiness
                ready = False
                for _ in range(15): 
                    try:
                        if httpx.get("http://localhost:11434/api/tags").status_code == 200:
                            ready = True
                            break
                    except:
                        time.sleep(2)

                if ready:
                    self.log("[SYSTEM] Ollama is back! Resuming research...")
                    self.last_activity_time = time.time()
                    
                    # 5. AUTO-RESUME if not finished
                    if self.current_goal and not self.is_finished:
                        self.after(1000, lambda: self.start_agent(self.current_goal))
                else:
                    self.log("[ERROR] Ollama failed to wake up.")

            except Exception as e:
                self.log(f"[ERROR] Restart failed: {e}")
            finally:
                self.is_restarting = False

    def log(self, msg):
        # Update activity timestamp
        self.last_activity_time = time.time() 
        
        # Check for completion keywords
        if "Successfully wrote to" in msg or "✅" in msg:
            self.is_finished = True
            self.is_running = False
            self.after(0, lambda: self.action_button.configure(state="normal", text="GO", fg_color="#3b82f6"))

        self.after(0, lambda: self._safe_log(msg))

    def _safe_log(self, msg):
        self.logbox.insert("end", f" {msg}\n")
        self.logbox.see("end")

    def handle_action(self):
        if self.is_awaiting_approval:
            self.approve()
        else:
            self.start_agent()

    def start_agent(self, goal=None):
        if goal is None:
            goal = self.entry.get()
        if not goal: return
        
        self.current_goal = goal
        self.is_running = True
        self.is_finished = False
        self.last_activity_time = time.time()
        
        self.action_button.configure(state="disabled", text="RUNNING...", fg_color="#333333")
        threading.Thread(target=self.agent.start, args=(goal,), daemon=True).start()

    def ask_approval(self, action):
        self.last_activity_time = time.time() 
        self.after(0, lambda: self._setup_approval_ui(action))

    def _setup_approval_ui(self, action):
        self.is_awaiting_approval = True
        self.preview_label.configure(text=f"CONFIRM: {action[:80]}...", text_color="#fbbf24")
        self.action_button.configure(state="normal", text="APPROVE COMMAND", fg_color="#10b981")

    def approve(self):
        self.is_awaiting_approval = False
        self.last_activity_time = time.time()
        self.preview_label.configure(text="Resuming...", text_color="#888888")
        self.action_button.configure(text="RUNNING...", fg_color="#333333", state="disabled")
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
                if "chrome" in proc.info['name'].lower() or "msedge" in proc.info['name'].lower():
                    proc.kill()
        finally: 
            self.destroy()

def run_app():
    app = App()
    app.mainloop()

if __name__ == "__main__":
    run_app()