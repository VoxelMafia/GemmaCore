"""
ui/app.py — Desktop UI.

Wired to the new OperatorAgent / AgentCore. All agent logic
has been removed from this file — the UI is purely presentational.
"""
import tkinter as tk
import customtkinter as ctk
import threading
import re
import time
import httpx

try:
    from core.agent import OperatorAgent
    from observability.logger import set_ui_callback
except ImportError:
    OperatorAgent = None

# ── Theme ──────────────────────────────────────────────────────────────────────
BG_COLOR       = "#0F172A"
CARD_COLOR     = "#1E293B"
BORDER_COLOR   = "#334155"
ACCENT_PRIMARY = "#3B82F6"
ACCENT_SUCCESS = "#10B981"
ACCENT_WARNING = "#F59E0B"
TEXT_MAIN      = "#F8FAFC"
TEXT_MUTED     = "#CBD5E1"

ctk.set_appearance_mode("Dark")


class App(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.title("GemmaCore | Cognitive Agent Runtime")
        self.geometry("1100x850")
        self.configure(fg_color=BG_COLOR)

        self.agent = OperatorAgent(self) if OperatorAgent else None
        self.is_running = False
        self.is_finished = False
        self.last_activity_time = time.time()

        self._build_ui()

        # Configure colors for log levels
        self.logbox.tag_config("INFO", foreground=ACCENT_PRIMARY)
        self.logbox.tag_config("ERROR", foreground="#EF4444")
        self.logbox.tag_config("WARN", foreground=ACCENT_WARNING)
        self.logbox.tag_config("DEBUG", foreground="#64748B")
        self.logbox.tag_config("SUCCESS", foreground=ACCENT_SUCCESS)

        if self.agent:
            try:
                set_ui_callback(self._safe_log_from_logger)
            except Exception:
                pass

        threading.Thread(target=self._health_watchdog, daemon=True).start()
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    # ── UI Construction ────────────────────────────────────────────────────────

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Nav bar
        nav = ctk.CTkFrame(self, height=60, fg_color=CARD_COLOR, corner_radius=0)
        nav.grid(row=0, column=0, sticky="ew")

        status_card = ctk.CTkFrame(nav, fg_color=BG_COLOR, border_width=1,
                                   border_color=BORDER_COLOR, corner_radius=6)
        status_card.pack(side="right", padx=30, pady=10)

        inner = ctk.CTkFrame(status_card, fg_color="transparent")
        inner.pack(padx=12, pady=6)

        self.health_dot = ctk.CTkLabel(inner, text="●", text_color=ACCENT_SUCCESS,
                                       font=("Inter", 14))
        self.health_dot.pack(side="left", padx=(0, 8))

        self.status_label = ctk.CTkLabel(inner, text="AGENT ONLINE",
                                         font=("Inter", 11, "bold"),
                                         text_color=ACCENT_SUCCESS)
        self.status_label.pack(side="left")

        # Console
        console = ctk.CTkFrame(self, fg_color=BG_COLOR)
        console.grid(row=1, column=0, padx=30, pady=15, sticky="nsew")
        console.grid_rowconfigure(0, weight=1)
        console.grid_columnconfigure(0, weight=1)

        self.logbox = ctk.CTkTextbox(
            console,
            font=("JetBrains Mono", 14),
            fg_color=CARD_COLOR,
            border_color=BORDER_COLOR,
            border_width=1,
            corner_radius=8,
            text_color=TEXT_MUTED,
            wrap ="word",
        )
        self.logbox.grid(row=0, column=0, sticky="nsew")

        # Control panel
        panel = ctk.CTkFrame(self, fg_color=CARD_COLOR, height=100,
                              corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        panel.grid(row=2, column=0, padx=30, pady=(10, 30), sticky="ew")
        panel.grid_propagate(False)

        ctrl = ctk.CTkFrame(panel, fg_color="transparent")
        ctrl.pack(expand=True, fill="both", padx=30, pady=20)
        ctrl.grid_columnconfigure(1, weight=1)

        # Goal entry
        center = ctk.CTkFrame(ctrl, fg_color="transparent")
        center.grid(row=0, column=1, sticky="nsew")

        self.entry_goal = ctk.CTkEntry(
            center,
            placeholder_text=(
                "Research goal (e.g. 'AI & Climate Science') "
                "— leave blank for autonomous mode…"
            ),
            height=42, corner_radius=6,
            fg_color=BG_COLOR, text_color=TEXT_MAIN,
            font=("Inter", 13), border_width=1, border_color=BORDER_COLOR,
        )
        self.entry_goal.pack(fill="x")
        self.entry_goal.bind("<Return>", lambda e: self._handle_action())

        # Action buttons
        action_group = ctk.CTkFrame(ctrl, fg_color="transparent")
        action_group.grid(row=0, column=2, sticky="ns", padx=(10, 0))

        actions_inner = ctk.CTkFrame(action_group, fg_color="transparent")
        actions_inner.pack(side="right", anchor="e", pady=5)

        self.auto_approve_var = tk.BooleanVar(value=False)
        self.auto_switch = ctk.CTkSwitch(
            actions_inner, text="Auto-Approve",
            command=self._on_toggle_auto_approve,
            variable=self.auto_approve_var,
            font=("Inter", 12),
            progress_color=ACCENT_PRIMARY,
            button_color=TEXT_MAIN,
            button_hover_color=TEXT_MUTED,
            fg_color=BORDER_COLOR,
        )
        self.auto_switch.pack(side="left", padx=(0, 20))

        self.action_btn = ctk.CTkButton(
            actions_inner, text="INITIATE RESEARCH",
            command=self._handle_action,
            font=("Inter", 13, "bold"), height=42, width=180,
            corner_radius=6, fg_color=ACCENT_PRIMARY,
            text_color=TEXT_MAIN, hover_color="#2563EB",
        )
        self.action_btn.pack(side="left")

    # ── Event handlers ─────────────────────────────────────────────────────────

    def _handle_action(self):
        if not self.is_running:
            self._start_agent()
            return
        # If approval is pending, the button acts as APPROVE
        if self.agent and hasattr(self.agent, "approval") and self.agent.approval.has_pending():
            self.agent.approval.approve()
            self._clear_pending()

    def _start_agent(self):
        raw = self.entry_goal.get().strip()
        if not raw:
            goal = "Autonomous"
        else:
            parts = re.split(r"\s*(?:&|AND|and|/)\s*", raw)
            if (len(parts) >= 2 and all(3 <= len(p.strip()) <= 120 for p in parts[:2])):
                goal = {"primary_domain": parts[0].strip(),
                        "intersection_domain": parts[1].strip()}
            else:
                goal = raw

        self.is_running = True
        self.is_finished = False
        self.action_btn.configure(state="normal", text="RUNNING…", fg_color=BORDER_COLOR)

        if self.agent:
            threading.Thread(
                target=self.agent.start,
                kwargs={"metadata": goal,
                        "start_auto_approve": bool(self.auto_approve_var.get())},
                daemon=True,
            ).start()

    def _on_toggle_auto_approve(self):
        val = bool(self.auto_approve_var.get())
        if self.agent and hasattr(self.agent, "approval"):
            self.agent.approval.set_auto_approve(val)

    # ── Approval UI ────────────────────────────────────────────────────────────

    def set_pending_action(self, action_text: str):
        preview = action_text[:200] + ("…" if len(action_text) > 200 else "")
        self.status_label.configure(text=f"AUTH REQUIRED: {preview}", text_color=ACCENT_WARNING)
        self.health_dot.configure(text_color=ACCENT_WARNING)
        self.action_btn.configure(text="APPROVE ACTION", fg_color=ACCENT_WARNING,
                                  text_color=BG_COLOR, state="normal")

    def _clear_pending(self):
        self.status_label.configure(text="Running…", text_color=ACCENT_PRIMARY)
        self.health_dot.configure(text_color=ACCENT_PRIMARY)
        self.action_btn.configure(text="RUNNING…", fg_color=BORDER_COLOR,
                                  text_color=TEXT_MAIN, state="normal")

    # ── Logging ────────────────────────────────────────────────────────────────

    def log(self, msg: str):
        self.last_activity_time = time.time()
        if any(x in msg for x in ["✅", "COMPLETE"]):
            self.is_finished = True
            self.is_running = False
            self.after(0, self._reset_btn)
        self.after(0, lambda: self._safe_log(msg))

    def _safe_log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        # Determine tag first
        tag = None
        if "ERROR" in msg: tag = "ERROR"
        elif "WARN" in msg: tag = "WARN"
        elif "DEBUG" in msg: tag = "DEBUG"
        elif any(x in msg for x in ["✅", "Saved", "SUCCESS"]): tag = "SUCCESS"
        elif "INFO" in msg: tag = "INFO"

        # Insert timestamp first (un-tagged or grey)
        self.logbox.insert("end", f"[{ts}] ", "DEBUG") 
        
        # Insert the message with the specific tag
        if tag:
            self.logbox.insert("end", f"{msg}\n", tag)
        else:
            self.logbox.insert("end", f"{msg}\n")
            
        self.logbox.see("end")

    def _safe_log_from_logger(self, formatted: str):
        try:
            self.last_activity_time = time.time()
            self._safe_log(formatted.strip())
        except Exception:
            pass

    # ── Status ─────────────────────────────────────────────────────────────────

    def _reset_btn(self):
        self.action_btn.configure(state="normal", text="NEW RESEARCH",
                                  fg_color=ACCENT_PRIMARY, text_color=TEXT_MAIN)
        self.status_label.configure(text="IDLE", text_color=ACCENT_SUCCESS)
        self.health_dot.configure(text_color=ACCENT_SUCCESS)

    def _update_health(self, online: bool):
        color = ACCENT_SUCCESS if online else "#EF4444"
        label = "AGENT ONLINE" if online else "AGENT OFFLINE"
        self.after(0, lambda: self.health_dot.configure(text_color=color))
        self.after(0, lambda: self.status_label.configure(text=label, text_color=color))

    def _health_watchdog(self):
        while True:
            try:
                ok = httpx.get("http://localhost:11434/api/tags", timeout=3.0).status_code == 200
            except Exception:
                ok = False
            self._update_health(ok)
            time.sleep(5)

    def _on_closing(self):
        try:
            if self.agent:
                self.agent.stop()
        finally:
            self.destroy()


def run_app():
    app = App()
    app.mainloop()
