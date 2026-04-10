"""
main.py — GemmaCore Entry Point.
Defaults to GUI; use --cli for terminal mode.
"""
from __future__ import annotations
import argparse
import signal
import sys
import time
import threading
from typing import Optional

# Global imports to prevent "UnboundLocalError" or "Not Accessed" issues
from core.agent import OperatorAgent
from observability.logger import set_ui_callback

# ── CLI Console UI shim ────────────────────────────────────────────────────────

class ConsoleUI:
    """Minimal UI shim for the CLI."""
    PHASE_COLORS = {
        "[PERCEPTION]": "\033[36m", "[THOUGHT]": "\033[35m",
        "[PLAN]": "\033[33m", "[ACTION]": "\033[34m",
        "[RESULT]": "\033[32m", "[REFLECTION]": "\033[95m",
        "[SYSTEM]": "\033[90m", "[ERROR]": "\033[31m",
    }
    RESET = "\033[0m"

    def __init__(self):
        self.agent_ref: Optional[OperatorAgent] = None

    def log(self, msg: str) -> None:
        color = ""
        for tag, col in self.PHASE_COLORS.items():
            if tag in msg:
                color = col
                break
        print(f"{color}{msg}{self.RESET}", flush=True)

    def after(self, delay: int, fn) -> None:
        fn()

    def set_pending_action(self, action_text: str) -> None:
        """Handles the command-line approval prompt."""
        print(f"\n\033[33m{'='*60}\n ⏳ APPROVAL REQUIRED\n{'='*60}\033[0m")
        print(f" {action_text[:500]}")
        print(f"\033[33m{'='*60}\033[0m")
        
        choice = input(" [A]pprove / [R]eject: ").strip().lower()
        if choice.startswith('a') and self.agent_ref:
            self.agent_ref.approval.approve()
        elif self.agent_ref:
            self.agent_ref.approval.reject()

# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="GemmaCore — Local Cognitive Agent Runtime",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n  python main.py          # GUI Mode\n  python main.py --cli    # CLI Mode"
    )
    parser.add_argument("--goal", type=str, default="", help="Research goal")
    parser.add_argument("--cli", action="store_true", help="Run in terminal mode")
    parser.add_argument("--auto-approve", action="store_true", help="Skip approval prompts")
    parser.add_argument("--trace", action="store_true", help="Print reasoning trace on exit")
    
    args = parser.parse_args()

    # 1. UI Selection Logic
    if not args.cli:
        try:
            from ui.app import run_app
            run_app()
            return 
        except Exception as e:
            print(f"\033[31m[!] GUI failed: {e}\033[0m")
            print("Falling back to CLI mode...\n")

    # 2. CLI Mode Initialization
    print_banner()
    ui = ConsoleUI()
    agent = OperatorAgent(ui=ui)
    ui.agent_ref = agent
    set_ui_callback(ui.log)

    # 3. Handle Interrupts
    def _sigint_handler(sig, frame):
        print("\n\n\033[33m[SYSTEM] Stopping agent...\033[0m")
        agent.stop()
        sys.exit(0)
    signal.signal(signal.SIGINT, _sigint_handler)

    # 4. Goal Selection
    goal = args.goal.strip() or input("  Enter goal (or Enter for Autonomous): ").strip() or "Autonomous"
    print(f"\n  \033[32m▶ Starting session: {goal}\033[0m\n")

    # 5. Execution
    t = threading.Thread(
        target=agent.start,
        kwargs={"metadata": goal, "start_auto_approve": args.auto_approve},
        daemon=True,
    )
    t.start()

    try:
        while agent.core.state.running or t.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        agent.stop()

    if args.trace and agent.core.tracer:
        print("\n" + agent.core.tracer.render(last_n=40))

    print("\n  \033[32m✅ Session complete.\033[0m\n")

def print_banner() -> None:
    print("\033[34m╔══════════════════════════════════════════════╗")
    print("║        GemmaCore · Cognitive Runtime         ║")
    print("╚══════════════════════════════════════════════╝\033[0m")

if __name__ == "__main__":
    main()