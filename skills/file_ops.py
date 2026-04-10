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
from typing import Any, Dict, List

from skills.base_skill import BaseSkill
from config.settings import settings
from core.state import AgentStatus
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
            "action": "One of: read_text | write_text | save_document | list_files | merge_and_clean",
            "path": "Relative path (required for read_text/write_text).",
            "folder": "Relative path to folder (required for merge_and_clean).",
            "content": "Text content (required for write/save).",
            "title": "Document title (required for save_document/merge_and_clean).",
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
        return 2

    def __init__(self, agent=None):
        self._agent = agent
        self._approval = getattr(agent, "approval", None) if agent else None
        self._base = os.path.abspath(settings.agent.workspace_path)
        os.makedirs(self._base, exist_ok=True)

    def _run(self, inputs: Dict[str, Any]) -> Any:
        action = inputs.get("action", "")
        
        # 1. READ actions
        if action == "read_text":
            return self._read(inputs.get("path", ""))
        elif action == "list_files":
            return self._list()

        # 2. WRITE actions (with Status Management)
        if action in ["write_text", "save_document", "merge_and_clean"]:
            try:
                if not self._request_permission(action, inputs):
                    return f"Permission Denied: User rejected the {action} request."

                if action == "write_text":
                    path = inputs.get("path")
                    if not path: return "Error: 'path' is required for write_text."
                    return self._write(path, inputs.get("content", ""))

                elif action == "save_document":
                    title = inputs.get("title")
                    if not title: return "Error: 'title' is required for save_document."
                    return self.save_document(title, inputs.get("content", ""))

                elif action == "merge_and_clean":
                    return self._handle_merge_and_clean(inputs)
            except PermissionError as pe:
                return f"Permission Error: {str(pe)}"
            except Exception as e:
                return f"Error during {action}: {str(e)}"
        return f"Unknown or unauthorized action: {action}"

    def _handle_merge_and_clean(self, inputs: Dict[str, Any]) -> str:
        folder_name = inputs.get("folder", "")
        if not folder_name: return "Error: 'folder' is required for merge_and_clean."
        
        folder_path = self._safe_path(folder_name)
        output_title = inputs.get("title", "Full_Document")
        
        if not os.path.exists(folder_path):
            return f"Error: Folder '{folder_name}' not found."

        chapters = sorted([f for f in os.listdir(folder_path) if f.startswith("Chapter_")])
        if not chapters:
            return "No chapters found starting with 'Chapter_' to merge."

        full_content = ""
        for snap in chapters:
            file_full_path = os.path.join(folder_path, snap)
            with open(file_full_path, 'r', encoding="utf-8") as f:
                full_content += f.read() + "\n\n---\n\n"
        
        self.save_document(output_title, full_content)
        
        for snap in chapters:
            os.remove(os.path.join(folder_path, snap))
            
        return f"Successfully merged {len(chapters)} chapters into '{output_title}' and cleaned up."

    def _request_permission(self, action: str, inputs: Dict[str, Any]) -> bool:
        if not self._approval:
            return True
            
        if self._agent and hasattr(self._agent, "state"):
            self._agent.state.set_status(AgentStatus.AWAITING_APPROVAL)

        target = inputs.get("path") or inputs.get("title") or inputs.get("folder") or "unknown"
        request_msg = f"ACTION: {action}\nTARGET: {target}\nCONTENT PREVIEW: {str(inputs.get('content'))[:150]}..."
        
        logger.info(f"Requesting approval for {action} on {target}")
        return self._approval.request(request_msg)

    def save_document(self, title: str, content: str, extension: str = ".md") -> str:
        clean = self._slugify(title)
        filename = f"{clean}{extension}"
        if len(clean) > 64:
            short_hash = hashlib.md5(title.encode()).hexdigest()[:6]
            filename = f"{clean[:50]}-{short_hash}{extension}"

        fm_date = datetime.utcnow().isoformat()
        front_matter = f"---\nauthor: GemmaCore Agent\ndate: {fm_date}\ntitle: {title}\n---\n\n"
        return self._write(filename, front_matter + content)

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
        target = os.path.abspath(os.path.join(self._base, user_path))
        if not target.startswith(os.path.abspath(self._base)):
            raise PermissionError(f"Access denied: {user_path} is outside workspace sandbox.")
        return target

    @staticmethod
    def _slugify(text: str, max_length: int = 64) -> str:
        if not text: return "untitled"
        text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
        text = re.sub(r"[^\w\s-]", "", text).strip()
        text = re.sub(r"[-\s]+", "-", text)
        return text[:max_length]