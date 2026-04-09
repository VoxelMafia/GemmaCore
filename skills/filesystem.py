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
        # Define the base workspace
        self.base_workspace = os.path.abspath("workspace")
        os.makedirs(self.base_workspace, exist_ok=True)
        
        # Initialize project_dir as the base until a specific goal is set
        self.project_dir = self.base_workspace

    def _get_project_path(self):
        """
        Dynamically determines the subfolder based on the agent's current goal.
        """
        goal = getattr(self.agent.loop, 'overall_thesis_goal', 'default_session')
        # Create a folder-safe name from the thesis goal
        folder_name = self._slugify(goal, max_length=50)
        
        project_path = os.path.join(self.base_workspace, folder_name)
        os.makedirs(project_path, exist_ok=True)
        return project_path

    def _slugify(self, text, max_length=64):
        """Converts a title into a filesystem-safe string."""
        if not text:
            return "untitled"

        # Normalize and Clean
        text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii').lower()
        text = re.sub(r'[^\w\s-]', '', text).strip()
        text = re.sub(r'[-\s]+', '-', text)

        # Truncate
        if len(text) > max_length:
            truncated = text[:max_length]
            last_hyphen = truncated.rfind('-')
            text = truncated[:last_hyphen] if last_hyphen > (max_length // 2) else truncated

        return text

    def _get_safe_path(self, user_path):
        """Ensures the path stays inside the specific project folder."""
        # Get the latest project-specific directory
        current_project_dir = self._get_project_path()
        
        target_path = os.path.abspath(os.path.join(current_project_dir, user_path))
        
        # Security: Ensure it doesn't escape the base workspace
        if not target_path.startswith(self.base_workspace):
            raise PermissionError(f"Access Denied: Path {user_path} is outside the sandbox.")
        
        return target_path

    def read_text(self, path):
        safe_path = self._get_safe_path(path)
        if not os.path.exists(safe_path):
            return f"Error: File {path} not found."
            
        with open(safe_path, 'r', encoding='utf-8') as f:
            return f.read()

    def write_text(self, path, content):
        safe_path = self._get_safe_path(path)
        os.makedirs(os.path.dirname(safe_path), exist_ok=True)
        
        with open(safe_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Extract relative path for a cleaner UI log
        rel_path = os.path.relpath(safe_path, self.base_workspace)
        return f"Document stored in: {rel_path}"

    def save_document(self, title, content, extension=".md"):
        """Slugifies the title and saves with metadata front-matter."""
        clean_name = self._slugify(title)
        
        # Unique naming to prevent collisions
        if len(title) > 100:
            short_hash = hashlib.md5(title.encode()).hexdigest()[:6]
            filename = f"{clean_name}-{short_hash}{extension}"
        else:
            filename = f"{clean_name}{extension}"

        # Metadata generation
        fm_author = "GemmaCore Agent"
        fm_date = datetime.utcnow().isoformat()
        fm_summary = title[:200] + "..." if len(title) > 200 else title
        
        front_matter = f"---\nauthor: {fm_author}\ndate: {fm_date}\ntitle: {title}\nsummary: {fm_summary}\n---\n\n"
        full_content = front_matter + content

        # Approval Logic
        if REQUIRE_APPROVAL and hasattr(self.agent, 'approval') and self.agent.approval:
            msg = f"Save Chapter to Workspace: {filename}?"
            if not self.agent.approval.request(msg):
                return f"Save aborted: {filename}"

        return self.write_text(filename, full_content)