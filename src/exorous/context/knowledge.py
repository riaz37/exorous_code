from __future__ import annotations
from pathlib import Path
import json
import hashlib
import logging

logger = logging.getLogger(__name__)

class ProjectKnowledgeStore:
    """
    Manages project-specific persistent knowledge (decisions, conventions, etc.)
    Stores data in the user's data directory, separated by project path hash.
    """

    def __init__(self, data_dir: Path, project_path: Path):
        self.project_path = project_path
        project_hash = hashlib.md5(str(project_path.resolve()).encode()).hexdigest()
        self.storage_dir = data_dir / "projects" / project_hash
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.file_path = self.storage_dir / "knowledge.json"
        self.data = self._load()

    def _load(self) -> dict:
        if not self.file_path.exists():
            return {"decisions": {}, "conventions": [], "notes": []}
        try:
            return json.loads(self.file_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error(f"Failed to load project knowledge: {e}")
            return {"decisions": {}, "conventions": [], "notes": []}

    def save(self):
        try:
            self.file_path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to save project knowledge: {e}")

    def add_note(self, note: str):
        if note not in self.data["notes"]:
            self.data["notes"].append(note)
            self.save()

    def get_formatted_knowledge(self) -> str | None:
        """Returns a formatted string of all project knowledge for the system prompt."""
        sections = []
        if self.data["notes"]:
            sections.append("### Project-specific Notes & Decisions")
            for note in self.data["notes"]:
                sections.append(f"- {note}")
        
        return "\n".join(sections) if sections else None
