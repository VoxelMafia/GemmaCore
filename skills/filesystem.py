import os
import re
import unicodedata
import hashlib
from .base_skill import BaseSkill
from datetime import datetime
from config import REQUIRE_APPROVAL

class FilesystemSkill(BaseSkill):
    def __init__(self, agent):
        super().__init__(agent)
        # Define a safe sandbox directory
        self.workspace = os.path.abspath("workspace")
        os.makedirs(self.workspace, exist_ok=True)

    def _slugify(self, text, max_length=64):
        """
        Converts a title into a filesystem-safe filename with a strict length limit.
        """
        if not text:
            return "untitled-document"

        # 1. Normalize and Clean
        text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii').lower()
        text = re.sub(r'[^\w\s-]', '', text).strip()
        text = re.sub(r'[-\s]+', '-', text)

        # 2. Truncate to safe length (64 chars is ideal for portability)
        if len(text) > max_length:
            # Try to cut at the last hyphen to avoid breaking words
            truncated = text[:max_length]
            last_hyphen = truncated.rfind('-')
            if last_hyphen > (max_length // 2):
                text = truncated[:last_hyphen]
            else:
                text = truncated

        return text

    def _get_safe_path(self, user_path):
        """Resolves path and ensures it stays within the workspace sandbox."""
        target_path = os.path.abspath(os.path.join(self.workspace, user_path))
        
        if not target_path.startswith(self.workspace):
            raise PermissionError(f"Access Denied: Path {user_path} is outside the sandbox.")
        
        return target_path

    def read_text(self, path):
        """Reads content from a file within the workspace."""
        safe_path = self._get_safe_path(path)
        if not os.path.exists(safe_path):
            return f"Error: File {path} not found."
            
        with open(safe_path, 'r', encoding='utf-8') as f:
            return f.read()

    def write_text(self, path, content):
        """Writes raw content to a specific path within the workspace."""
        safe_path = self._get_safe_path(path)
        os.makedirs(os.path.dirname(safe_path), exist_ok=True)
        
        with open(safe_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Successfully wrote to {path}"

    def save_document(self, title, content, extension=".md"):
        """
        Safely generates a filename from a title and writes the document.
        Fixes the 'Long Filename' crash by slugifying and truncating the title.
        """
        # Truncate title for filename but keep full title for front-matter
        clean_name = self._slugify(title)
        
        # Add a unique short hash if the title was extremely long to prevent overwrites
        if len(title) > 100:
            short_hash = hashlib.md5(title.encode()).hexdigest()[:6]
            filename = f"{clean_name}-{short_hash}{extension}"
        else:
            filename = f"{clean_name}{extension}"

        # Metadata generation
        fm_author = "GemmaCore Agent"
        fm_date = datetime.utcnow().isoformat()
        fm_summary = title[:200] + "..." if len(title) > 200 else title
        
        front_matter = f"---\nauthor: {fm_author}\ndate: {fm_date}\nsummary: {fm_summary}\n---\n\n"
        full_content = front_matter + content

        # Approval Logic
        if REQUIRE_APPROVAL and hasattr(self.agent, 'approval') and self.agent.approval:
            try:
                approved = self.agent.approval.request(f"Write file {filename} (Title: {title[:50]}...)")
            except Exception:
                approved = False

            if not approved:
                return f"Write aborted by operator: {filename}"

        return self.write_text(filename, full_content)