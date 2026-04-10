"""
skills/file_ops.py — File system operations skill.

Provides sandboxed read/write access to the workspace directory.
Permission level 2: file writes require approval.
"""
from __future__ import annotations
import os
import re
import hashlib
import unicodedata
from datetime import datetime
from typing import Any, Dict, List, Optional

from skills.base_skill import BaseSkill
from config.settings import settings
from core.state import AgentStatus # Added for status management
from observability.logger import get_logger

logger = get_logger("skills.file_ops")

class FileOpsSkill(BaseSkill):

    @property
    def name(self) -> str:
        return "file_ops"

    @property
    def description(self) -> str:
        return "Read and write files within the sandboxed workspace directory."

    @property
    def input_schema(self) -> Dict[str, str]:
        return {
            "action": "One of: read_text | write_text | save_document | list_files",
            "path": "(read/write) Relative path within workspace.",
            "content": "(write/save) Text content to write.",
            "title": "(save_document) Document title for front-matter.",
        }

    @property
    def output_schema(self) -> Dict[str, str]:
        return {
            "output": "File content string (read) or success message (write).",
        }

    @property
    def side_effects(self) -> List[str]:
        return ["Writes files to workspace/", "Creates directories as needed"]

    @property
    def permission_level(self) -> int:
        return 2  # require approval for writes

    def __init__(self, agent=None):
        self._agent = agent
        # Reference to the approval system via agent core
        self._approval = getattr(agent, "approval", None) if agent else None
        self._base = os.path.abspath(settings.agent.workspace_path)
        os.makedirs(self._base, exist_ok=True)

    # ── BaseSkill ──────────────────────────────────────────────────────────────

    def _run(self, inputs: Dict[str, Any]) -> Any:
        action = inputs.get("action", "")
        
        # 1. READ actions (Low Permission - No Approval Needed)
        if action == "read_text":
            return self._read(inputs.get("path", ""))
        elif action == "list_files":
            return self._list()

        # 2. WRITE actions (High Permission - Approval Gate Required)
        # Check if we need to request approval
        if action in ["write_text", "save_document"]:
            if not self._request_permission(action, inputs):
                return f"Permission Denied: User rejected the {action} request."

            if action == "write_text":
                return self._write(inputs.get("path", ""), inputs.get("content", ""))
            elif action == "save_document":
                return self.save_document(inputs.get("title", "Untitled"), inputs.get("content", ""))
        
        return f"Unknown or unauthorized action: {action}"

    # ── Internal Approval Gate ────────────────────────────────────────────────

    def _request_permission(self, action: str, inputs: Dict[str, Any]) -> bool:
        """Helper to block and ask for permission via the ApprovalSystem."""
        if not self._approval:
            return True # Fallback if no approval system is wired
            
        # Update UI status if possible
        if self._agent and hasattr(self._agent, "state"):
            self._agent.state.set_status(AgentStatus.AWAITING_APPROVAL)

        # Formulate a clear request message for the user
        target = inputs.get("path") or inputs.get("title") or "unknown file"
        request_msg = f"ACTION: {action}\nTARGET: {target}\nCONTENT PREVIEW: {str(inputs.get('content'))[:200]}..."
        
        logger.info(f"Requesting approval for {action} on {target}")
        
        # This blocks the skill thread until user clicks Approve/Reject
        return self._approval.request(request_msg)

    # ── Public helpers ────────────────────────────────────────────────────────

    def save_document(self, title: str, content: str, extension: str = ".md") -> str:
        clean = self._slugify(title)
        if len(title) > 100:
            short_hash = hashlib.md5(title.encode()).hexdigest()[:6]
            filename = f"{clean}-{short_hash}{extension}"
        else:
            filename = f"{clean}{extension}"

        fm_date = datetime.utcnow().isoformat()
        front_matter = (
            f"---\nauthor: GemmaCore Agent\ndate: {fm_date}\n"
            f"title: {title}\n---\n\n"
        )
        return self._write(filename, front_matter + content)

    # ── Private ────────────────────────────────────────────────────────────────

    def _read(self, path: str) -> str:
        try:
            safe = self._safe_path(path)
            if not os.path.exists(safe):
                return f"Error: {path} not found."
            with open(safe, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"Read Error: {str(e)}"

    def _write(self, path: str, content: str) -> str:
        try:
            safe = self._safe_path(path)
            os.makedirs(os.path.dirname(safe), exist_ok=True)
            with open(safe, "w", encoding="utf-8") as f:
                f.write(content)
            rel = os.path.relpath(safe, self._base)
            return f"Saved: workspace/{rel}"
        except Exception as e:
            return f"Write Error: {str(e)}"

    def _list(self) -> str:
        files = []
        for root, _, fnames in os.walk(self._base):
            for fn in fnames:
                files.append(os.path.relpath(os.path.join(root, fn), self._base))
        return "\n".join(files) if files else "Workspace is empty."

    def _safe_path(self, user_path: str) -> str:
        # Prevent path traversal attacks
        target = os.path.abspath(os.path.join(self._base, user_path))
        if not target.startswith(self._base):
            raise PermissionError(f"Access denied: {user_path} is outside workspace sandbox.")
        return target

    @staticmethod
    def _slugify(text: str, max_length: int = 64) -> str:
        if not text:
            return "untitled"
        text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
        text = re.sub(r"[^\w\s-]", "", text).strip()
        text = re.sub(r"[-\s]+", "-", text)
        if len(text) > max_length:
            truncated = text[:max_length]
            last = truncated.rfind("-")
            text = truncated[:last] if last > max_length // 2 else truncated
        return text