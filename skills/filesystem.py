import os
import re
import unicodedata
from .base_skill import BaseSkill
from datetime import datetime
from config import REQUIRE_APPROVAL

class FilesystemSkill(BaseSkill):
    def __init__(self, agent):
        super().__init__(agent)
        # Define a safe sandbox directory
        self.workspace = os.path.abspath("workspace")
        os.makedirs(self.workspace, exist_ok=True)

    def _slugify(self, text):
        """
        Converts a title or string into a filesystem-safe filename.
        Example: "My Awesome Article!" -> "my-awesome-article"
        """
        # Normalize unicode characters to remove accents
        text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii').lower()
        # Remove any character that isn't a word character, space, or hyphen
        text = re.sub(r'[^\w\s-]', '', text).strip()
        # Replace spaces or multiple hyphens with a single hyphen
        return re.sub(r'[-\s]+', '-', text)

    def _get_safe_path(self, user_path):
        """Resolves path and ensures it stays within the workspace sandbox."""
        # Join workspace with the requested path and resolve '..' or '.'
        target_path = os.path.abspath(os.path.join(self.workspace, user_path))
        
        # Security Check: Ensure the target is actually inside the workspace
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
        
        # Ensure subdirectories exist
        os.makedirs(os.path.dirname(safe_path), exist_ok=True)
        
        with open(safe_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Successfully wrote to {path}"

    def save_document(self, title, content, extension=".md"):
        """
        Recommended tool for the AI. 
        It generates a meaningful filename automatically from a title.
        """
        clean_name = self._slugify(title)
        filename = f"{clean_name}{extension}"
        # Prepend front-matter metadata (author, date, short summary)
        fm_author = "GemmaCore Agent"
        fm_date = datetime.utcnow().isoformat()
        fm_summary = title if title else ""
        front_matter = f"---\nauthor: {fm_author}\ndate: {fm_date}\nsummary: {fm_summary}\n---\n\n"
        full_content = front_matter + content

        # Require operator approval before writing files when configured
        if REQUIRE_APPROVAL and hasattr(self.agent, 'approval') and self.agent.approval:
            try:
                approved = self.agent.approval.request(f"Write file {filename} to workspace with title: {title}")
            except Exception:
                approved = False

            if not approved:
                return f"Write aborted by operator: {filename}"

        return self.write_text(filename, full_content)